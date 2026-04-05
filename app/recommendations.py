from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Dict, Tuple
from . import models, schemas
from collections import defaultdict
import math

class BookRecommendationEngine:
    """
    Advanced recommendation engine using collaborative filtering and content-based filtering
    with weighted scoring algorithm.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_reading_history(self, user_id: int) -> List[models.Book]:
        """Get user's reading history from borrows and reviews"""
        user_books = self.db.query(models.Book).join(
            models.Borrow, models.Borrow.book_id == models.Book.id
        ).filter(models.Borrow.user_id == user_id).all()
        
        reviewed_books = self.db.query(models.Book).join(
            models.Review, models.Review.book_id == models.Book.id
        ).filter(models.Review.user_id == user_id).all()
        
        # Combine and deduplicate
        all_books = list({book.id: book for book in user_books + reviewed_books}.values())
        return all_books
    
    def calculate_user_preferences(self, user_id: int) -> Dict:
        """Calculate user preferences based on their reviews and borrowed books"""
        preferences = {
            'favorite_authors': defaultdict(float),
            'favorite_categories': defaultdict(float),
            'favorite_years': defaultdict(float),
            'avg_rating_given': 0.0
        }
        
        # Analyze reviews
        reviews = self.db.query(models.Review).filter(
            models.Review.user_id == user_id
        ).all()
        
        if reviews:
            total_rating = 0
            for review in reviews:
                total_rating += review.rating
                book = review.book
                
                # Weight by rating (higher ratings give more weight)
                weight = review.rating / 5.0
                preferences['favorite_authors'][book.author] += weight
                preferences['favorite_years'][book.year] += weight
                
                for category in book.categories:
                    preferences['favorite_categories'][category.name] += weight
            
            preferences['avg_rating_given'] = total_rating / len(reviews)
        
        # Analyze borrowed books
        borrows = self.db.query(models.Borrow).filter(
            models.Borrow.user_id == user_id,
            models.Borrow.is_returned == True
        ).all()
        
        for borrow in borrows:
            book = borrow.book
            # Older borrows have less weight
            days_since_borrow = (borrow.borrow_date - borrow.return_date).days if borrow.return_date else 0
            weight = 1.0 / (1 + math.log(days_since_borrow + 1))
            
            preferences['favorite_authors'][book.author] += weight
            preferences['favorite_years'][book.year] += weight
            
            for category in book.categories:
                preferences['favorite_categories'][category.name] += weight
        
        return preferences
    
    def collaborative_filtering(self, user_id: int, limit: int = 20) -> List[Tuple[int, float]]:
        """
        Find similar users based on their reading history and ratings
        """
        # Get all users who reviewed books
        all_users = self.db.query(models.User).filter(models.User.id != user_id).all()
        
        # Get current user's rated books
        user_ratings = {
            review.book_id: review.rating 
            for review in self.db.query(models.Review).filter(
                models.Review.user_id == user_id
            ).all()
        }
        
        if not user_ratings:
            return []
        
        user_book_set = set(user_ratings.keys())
        similarity_scores = []
        
        for other_user in all_users:
            # Get other user's ratings
            other_ratings = {
                review.book_id: review.rating
                for review in self.db.query(models.Review).filter(
                    models.Review.user_id == other_user.id
                ).all()
            }
            
            if not other_ratings:
                continue
            
            other_book_set = set(other_ratings.keys())
            common_books = user_book_set & other_book_set
            
            if len(common_books) < 2:
                continue
            
            # Calculate Pearson correlation coefficient
            user_ratings_list = [user_ratings[book] for book in common_books]
            other_ratings_list = [other_ratings[book] for book in common_books]
            
            correlation = self.pearson_correlation(user_ratings_list, other_ratings_list)
            
            if correlation > 0:
                # Predict ratings for unrated books
                for book_id in other_book_set - user_book_set:
                    similarity_scores.append((book_id, correlation * other_ratings[book_id]))
        
        # Aggregate and sort recommendations
        book_scores = defaultdict(float)
        for book_id, score in similarity_scores:
            book_scores[book_id] += score
        
        sorted_books = sorted(book_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_books[:limit]
    
    def content_based_filtering(self, user_id: int, limit: int = 20) -> List[Tuple[int, float]]:
        """
        Recommend books similar to user's reading history using TF-IDF inspired approach
        """
        user_books = self.get_user_reading_history(user_id)
        
        if not user_books:
            return []
        
        # Create user profile vector
        user_profile = defaultdict(float)
        
        for book in user_books:
            # Weight by average rating or default
            avg_rating = self.db.query(func.avg(models.Review.rating)).filter(
                models.Review.book_id == book.id
            ).scalar() or 3.0
            
            weight = avg_rating / 5.0
            
            # Add features to profile
            user_profile[f"author_{book.author}"] += weight
            
            for category in book.categories:
                user_profile[f"category_{category.name}"] += weight
            
            # Year bins
            year_bin = (book.year // 10) * 10
            user_profile[f"decade_{year_bin}"] += weight
        
        # Find similar books
        all_books = self.db.query(models.Book).filter(
            models.Book.id.notin_([book.id for book in user_books])
        ).all()
        
        book_scores = []
        
        for book in all_books:
            score = 0.0
            # Calculate cosine similarity
            book_vector = defaultdict(float)
            book_vector[f"author_{book.author}"] += 1
            
            for category in book.categories:
                book_vector[f"category_{category.name}"] += 1
            
            year_bin = (book.year // 10) * 10
            book_vector[f"decade_{year_bin}"] += 1
            
            # Calculate dot product
            for feature, weight in user_profile.items():
                if feature in book_vector:
                    score += weight * book_vector[feature]
            
            # Normalize
            if user_profile:
                score = score / (math.sqrt(sum(w*w for w in user_profile.values())) + 1e-8)
            
            # Add popularity boost
            review_count = self.db.query(func.count(models.Review.id)).filter(
                models.Review.book_id == book.id
            ).scalar()
            popularity_boost = min(1.0, review_count / 50.0)
            score = score * (1 + popularity_boost)
            
            book_scores.append((book.id, score))
        
        book_scores.sort(key=lambda x: x[1], reverse=True)
        return book_scores[:limit]
    
    def hybrid_recommendations(self, user_id: int, limit: int = 10) -> List[Tuple[int, float]]:
        """
        Combine collaborative and content-based filtering with weighted average
        """
        collab_recs = dict(self.collaborative_filtering(user_id, limit * 2))
        content_recs = dict(self.content_based_filtering(user_id, limit * 2))
        
        # Normalize scores
        if collab_recs:
            max_collab = max(collab_recs.values())
            collab_recs = {k: v/max_collab for k, v in collab_recs.items()}
        
        if content_recs:
            max_content = max(content_recs.values())
            content_recs = {k: v/max_content for k, v in content_recs.items()}
        
        # Combine with weights (collaborative has higher weight if available)
        combined_scores = {}
        collab_weight = 0.7 if collab_recs else 0
        content_weight = 0.3
        
        for book_id, score in content_recs.items():
            combined_scores[book_id] = score * content_weight
        
        for book_id, score in collab_recs.items():
            combined_scores[book_id] = combined_scores.get(book_id, 0) + score * collab_weight
        
        sorted_books = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_books[:limit]
    
    def calculate_confidence_score(self, recommendations: List[Tuple[int, float]], user_id: int) -> float:
        """
        Calculate confidence score for recommendations based on user history coverage
        """
        if not recommendations:
            return 0.0
        
        avg_score = sum(score for _, score in recommendations) / len(recommendations)
        
        # Adjust based on user's review count
        review_count = self.db.query(func.count(models.Review.id)).filter(
            models.Review.user_id == user_id
        ).scalar()
        
        confidence_boost = min(1.0, review_count / 20.0)
        
        return (avg_score * 0.7 + confidence_boost * 0.3) * 100
    
    @staticmethod
    def pearson_correlation(x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        n = len(x)
        
        if n == 0:
            return 0.0
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        
        numerator = sum_xy - (sum_x * sum_y) / n
        denominator = ((sum_x2 - (sum_x * sum_x) / n) * (sum_y2 - (sum_y * sum_y) / n)) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def get_recommendations(self, user_id: int, limit: int = 5) -> schemas.RecommendationResponse:
        """
        Get personalized book recommendations for a user
        """
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None
        
        # Get hybrid recommendations
        recommended_books = self.hybrid_recommendations(user_id, limit)
        
        # Fetch book details
        books = []
        for book_id, score in recommended_books:
            book = self.db.query(models.Book).filter(models.Book.id == book_id).first()
            if book and book.available_copies > 0:
                books.append(book)
        
        # Convert to response schema
        book_responses = []
        for book in books:
            review_count = self.db.query(func.count(models.Review.id)).filter(
                models.Review.book_id == book.id
            ).scalar()
            
            book_response = schemas.BookResponse(
                id=book.id,
                title=book.title,
                author=book.author,
                year=book.year,
                publisher=book.publisher,
                pages=book.pages,
                total_copies=book.total_copies,
                available_copies=book.available_copies,
                average_rating=book.average_rating,
                created_at=book.created_at,
                categories=[schemas.CategoryResponse.from_orm(cat) for cat in book.categories],
                reviews_count=review_count
            )
            book_responses.append(book_response)
        
        confidence = self.calculate_confidence_score(recommended_books, user_id)
        
        return schemas.RecommendationResponse(
            user_id=user_id,
            recommendations=book_responses,
            algorithm_used="Hybrid Collaborative & Content-based Filtering with Weighted Scoring",
            confidence_score=confidence
        )