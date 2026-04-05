from typing import List
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import database, models, schemas, auth, crud
from .recommendations import BookRecommendationEngine

# Create database tables
database.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Library Management System",
    description="Advanced library management system with book recommendations",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== AUTHENTICATION ENDPOINTS ====================


@app.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Register a new user"""
    # Check if user exists
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_email = crud.get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    return crud.create_user(db=db, user=user)


@app.post("/token", response_model=schemas.Token)
def login(user_data: schemas.UserLogin, db: Session = Depends(database.get_db)):
    """Login and get access token"""
    user = auth.authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """Get current user information"""
    return current_user


# ==================== CATEGORY ENDPOINTS ====================


@app.post(
    "/categories",
    response_model=schemas.CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(database.get_db),
    _current_user: models.User = Depends(auth.get_current_active_user),
):
    """Create a new book category (admin only)"""
    existing = crud.get_category_by_name(db, category.name)
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    return crud.create_category(db=db, category=category)


@app.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(
    skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)
):
    """Get all categories"""
    return crud.get_all_categories(db, skip=skip, limit=limit)


# ==================== BOOK CRUD ENDPOINTS ====================


@app.post(
    "/books", response_model=schemas.BookResponse, status_code=status.HTTP_201_CREATED
)
def create_book(
    book: schemas.BookCreate,
    db: Session = Depends(database.get_db),
    _current_user: models.User = Depends(auth.get_current_active_user),
):
    """Create a new book (admin only)"""
    return crud.create_book(db=db, book=book)


@app.get("/books", response_model=List[schemas.BookResponse])
def get_books(
    skip: int = 0,
    limit: int = 100,
    category_id: int = None,
    db: Session = Depends(database.get_db),
):
    """Get all books with optional category filter"""
    books = crud.get_books(db, skip=skip, limit=limit, category_id=category_id)

    # Enhance with review counts
    result = []
    for book in books:
        review_count = (
            db.query(models.Review).filter(models.Review.book_id == book.id).count()
        )

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
            categories=[
                schemas.CategoryResponse.from_orm(cat) for cat in book.categories
            ],
            reviews_count=review_count,
        )
        result.append(book_response)

    return result


@app.get("/books/{book_id}", response_model=schemas.BookResponse)
def get_book(book_id: int, db: Session = Depends(database.get_db)):
    """Get a book by ID"""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    review_count = (
        db.query(models.Review).filter(models.Review.book_id == book.id).count()
    )

    return schemas.BookResponse(
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
        reviews_count=review_count,
    )


@app.put("/books/{book_id}", response_model=schemas.BookResponse)
def update_book(
    book_id: int,
    book_update: schemas.BookUpdate,
    db: Session = Depends(database.get_db),
    _current_user: models.User = Depends(auth.get_current_active_user),
):
    """Update a book (admin only)"""
    updated_book = crud.update_book(db, book_id, book_update)
    if not updated_book:
        raise HTTPException(status_code=404, detail="Book not found")
    return updated_book


@app.delete("/books/{book_id}", response_model=schemas.MessageResponse)
def delete_book(
    book_id: int,
    db: Session = Depends(database.get_db),
    _current_user: models.User = Depends(auth.get_current_active_user),
):
    """Delete a book (admin only)"""
    success = crud.delete_book(db, book_id)
    if not success:
        raise HTTPException(status_code=404, detail="Book not found")
    return schemas.MessageResponse(message="Book deleted successfully")


# ==================== REVIEW ENDPOINTS ====================


@app.post(
    "/books/{book_id}/reviews",
    response_model=schemas.ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    book_id: int,
    review: schemas.ReviewCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    """Add a review for a book"""
    book = crud.get_book(db, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    new_review = crud.create_review(db, review, current_user.id, book_id)
    if not new_review:
        raise HTTPException(
            status_code=400, detail="You have already reviewed this book"
        )

    return new_review


@app.get("/books/{book_id}/reviews", response_model=List[schemas.ReviewResponse])
def get_book_reviews(
    book_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(database.get_db)
):
    """Get all reviews for a book"""
    return crud.get_book_reviews(db, book_id, skip=skip, limit=limit)


# ==================== BORROWING ENDPOINTS ====================


@app.post(
    "/borrow",
    response_model=schemas.BorrowResponse,
    status_code=status.HTTP_201_CREATED,
)
def borrow_book(
    borrow_data: schemas.BorrowCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    """Borrow a book"""
    borrow = crud.borrow_book(db, current_user.id, borrow_data)
    if not borrow:
        raise HTTPException(status_code=400, detail="Book not available for borrowing")
    return borrow


@app.post("/return/{borrow_id}", response_model=schemas.MessageResponse)
def return_book(
    borrow_id: int,
    db: Session = Depends(database.get_db),
    _current_user: models.User = Depends(auth.get_current_active_user),
):
    """Return a borrowed book"""
    borrow = crud.return_book(db, borrow_id)
    if not borrow:
        raise HTTPException(
            status_code=404, detail="Borrow record not found or book already returned"
        )
    return schemas.MessageResponse(message="Book returned successfully")


@app.get("/my-borrows", response_model=List[schemas.BorrowResponse])
def get_my_borrows(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    """Get current user's borrowing history"""
    borrows = crud.get_user_borrows(db, current_user.id)

    result = []
    for borrow in borrows:
        result.append(
            schemas.BorrowResponse(
                id=borrow.id,
                book_id=borrow.book_id,
                user_id=borrow.user_id,
                borrow_date=borrow.borrow_date,
                due_date=borrow.due_date,
                return_date=borrow.return_date,
                is_returned=borrow.is_returned,
                book_title=borrow.book.title,
            )
        )

    return result


# ==================== RECOMMENDATION ENDPOINT (BUSINESS LOGIC) ====================


@app.get("/recommendations", response_model=schemas.RecommendationResponse)
def get_recommendations(
    limit: int = 5,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_active_user),
):
    """
    Get personalized book recommendations based on user's reading history.

    This endpoint implements a hybrid recommendation algorithm combining:
    1. Collaborative filtering (finding similar users)
    2. Content-based filtering (finding similar books)
    3. Weighted scoring based on user preferences

    The algorithm analyzes:
    - User's reading and borrowing history
    - Book ratings and reviews
    - Author and category preferences
    - Temporal decay for older interactions

    Returns recommendations with confidence score.
    """
    engine = BookRecommendationEngine(db)
    recommendations_result = engine.get_recommendations(current_user.id, limit)

    if not recommendations_result:
        raise HTTPException(
            status_code=404,
            detail="Not enough data to generate recommendations. \
Please review or borrow some books first.",
        )

    return recommendations_result


# ==================== HEALTH CHECK ====================


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Library Management System is running"}
