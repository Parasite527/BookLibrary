from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models, schemas
from .auth import get_password_hash


# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):

    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# Category CRUD
def get_category(db: Session, category_id: int):
    return db.query(models.Category).filter(models.Category.id == category_id).first()


def get_category_by_name(db: Session, name: str):
    return db.query(models.Category).filter(models.Category.name == name).first()


def create_category(db: Session, category: schemas.CategoryCreate):
    db_category = models.Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def get_all_categories(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Category).offset(skip).limit(limit).all()


# Book CRUD
def get_book(db: Session, book_id: int):
    return db.query(models.Book).filter(models.Book.id == book_id).first()


def get_books(
    db: Session, skip: int = 0, limit: int = 100, category_id: Optional[int] = None
):
    query = db.query(models.Book)
    if category_id:
        query = query.join(models.Book.categories).filter(
            models.Category.id == category_id
        )
    return query.offset(skip).limit(limit).all()


def create_book(db: Session, book: schemas.BookCreate):
    db_book = models.Book(
        title=book.title,
        author=book.author,
        year=book.year,
        publisher=book.publisher,
        pages=book.pages,
        total_copies=book.total_copies,
        available_copies=book.total_copies,
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)

    # Add categories if provided
    if book.category_ids:
        categories = (
            db.query(models.Category)
            .filter(models.Category.id.in_(book.category_ids))
            .all()
        )
        db_book.categories.extend(categories)
        db.commit()

    return db_book


def update_book(db: Session, book_id: int, book_update: schemas.BookUpdate):
    db_book = get_book(db, book_id)
    if not db_book:
        return None

    update_data = book_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_book, field, value)

    db.commit()
    db.refresh(db_book)
    return db_book


def delete_book(db: Session, book_id: int):
    db_book = get_book(db, book_id)
    if not db_book:
        return False

    db.delete(db_book)
    db.commit()
    return True


# Review CRUD
def create_review(
    db: Session, review: schemas.ReviewCreate, user_id: int, book_id: int
):
    # Check if user already reviewed this book
    existing_review = (
        db.query(models.Review)
        .filter(models.Review.user_id == user_id, models.Review.book_id == book_id)
        .first()
    )

    if existing_review:
        return None

    db_review = models.Review(**review.model_dump(), user_id=user_id, book_id=book_id)
    db.add(db_review)
    db.commit()
    db.refresh(db_review)

    # Update book's average rating
    update_book_rating(db, book_id)

    return db_review


def update_book_rating(db: Session, book_id: int):
    book = get_book(db, book_id)
    if book:
        avg_rating = (
            db.query(func.avg(models.Review.rating))
            .filter(models.Review.book_id == book_id)
            .scalar()
        )
        book.average_rating = avg_rating or 0.0
        db.commit()


def get_book_reviews(db: Session, book_id: int, skip: int = 0, limit: int = 50):
    return (
        db.query(models.Review)
        .filter(models.Review.book_id == book_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


# Borrow CRUD
def borrow_book(db: Session, user_id: int, borrow_data: schemas.BorrowCreate):
    book = get_book(db, borrow_data.book_id)
    if not book or book.available_copies <= 0:
        return None

    db_borrow = models.Borrow(
        user_id=user_id, book_id=borrow_data.book_id, due_date=borrow_data.due_date
    )
    book.available_copies -= 1

    db.add(db_borrow)
    db.commit()
    db.refresh(db_borrow)
    return db_borrow


def return_book(db: Session, borrow_id: int):
    borrow = db.query(models.Borrow).filter(models.Borrow.id == borrow_id).first()
    if not borrow or borrow.is_returned:
        return None

    borrow.is_returned = True
    borrow.return_date = datetime.now(timezone.utc)

    book = get_book(db, borrow.book_id)
    if book:
        book.available_copies += 1

    db.commit()
    return borrow


def get_user_borrows(db: Session, user_id: int):
    return db.query(models.Borrow).filter(models.Borrow.user_id == user_id).all()
