from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Float,
    DateTime,
    Boolean,
    Table,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# Association table for many-to-many relationship between books and categories
book_category = Table(
    "book_category",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("books.id")),
    Column("category_id", Integer, ForeignKey("categories.id")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reviews = relationship(
        "Review", back_populates="user", cascade="all, delete-orphan"
    )
    borrows = relationship(
        "Borrow", back_populates="user", cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    author = Column(String, index=True, nullable=False)
    year = Column(Integer, nullable=False)
    publisher = Column(String)
    pages = Column(Integer)
    total_copies = Column(Integer, default=1)
    available_copies = Column(Integer, default=1)
    average_rating = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    reviews = relationship(
        "Review", back_populates="book", cascade="all, delete-orphan"
    )
    borrows = relationship(
        "Borrow", back_populates="book", cascade="all, delete-orphan"
    )
    categories = relationship(
        "Category", secondary=book_category, back_populates="books"
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String)

    # Relationships
    books = relationship("Book", secondary=book_category, back_populates="categories")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(Integer, ForeignKey("books.id"))

    # Relationships
    user = relationship("User", back_populates="reviews")
    book = relationship("Book", back_populates="reviews")


class Borrow(Base):
    __tablename__ = "borrows"

    id = Column(Integer, primary_key=True, index=True)
    borrow_date = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=False)
    return_date = Column(DateTime(timezone=True))
    is_returned = Column(Boolean, default=False)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(Integer, ForeignKey("books.id"))

    # Relationships
    user = relationship("User", back_populates="borrows")
    book = relationship("Book", back_populates="borrows")
