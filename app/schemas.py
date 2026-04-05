from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Category schemas
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        from_attributes = True

# Book schemas
class BookBase(BaseModel):
    title: str
    author: str
    year: int
    publisher: Optional[str] = None
    pages: Optional[int] = None
    total_copies: int = 1

class BookCreate(BookBase):
    category_ids: Optional[List[int]] = None

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    pages: Optional[int] = None
    total_copies: Optional[int] = None

class BookResponse(BookBase):
    id: int
    available_copies: int
    average_rating: float
    created_at: datetime
    categories: List[CategoryResponse] = []
    reviews_count: int = 0
    
    class Config:
        from_attributes = True

# Review schemas
class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    book_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ReviewWithUserResponse(ReviewResponse):
    username: str

# Borrow schemas
class BorrowCreate(BaseModel):
    book_id: int
    due_date: datetime

class BorrowResponse(BaseModel):
    id: int
    book_id: int
    user_id: int
    borrow_date: datetime
    due_date: datetime
    return_date: Optional[datetime]
    is_returned: bool
    
    class Config:
        from_attributes = True

# Recommendation schemas
class RecommendationRequest(BaseModel):
    user_id: int
    limit: int = 5

class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[BookResponse]
    algorithm_used: str
    confidence_score: float

# Message response
class MessageResponse(BaseModel):
    message: str
    details: Optional[str] = None