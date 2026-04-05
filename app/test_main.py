import pytest

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .main import app
from .database import Base, get_db


# Test database
@pytest.fixture()
def client():
    file_path = "./test.db"
    Path(file_path).unlink(missing_ok=True)

    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    return client


@pytest.fixture
def test_user(client: TestClient):
    """Create test user and return token"""
    # Register user
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
    }
    response = client.post("/register", json=user_data)
    assert response.status_code == 201

    # Login
    login_data = {"username": "testuser", "password": "testpass123"}
    response = client.post("/token", json=login_data)
    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"token": token, "username": "testuser"}


@pytest.fixture
def test_category(client: TestClient, test_user):
    """Create test category"""
    response = client.post(
        "/categories",
        json={"name": "Fiction", "description": "Fiction books"},
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def test_book(client: TestClient, test_user, test_category):
    """Create test book"""
    book_data = {
        "title": "Test Book",
        "author": "Test Author",
        "year": 2023,
        "publisher": "Test Publisher",
        "pages": 200,
        "total_copies": 5,
        "category_ids": [test_category["id"]],
    }
    response = client.post(
        "/books",
        json=book_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    return response.json()


# Tests
def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_register_user(client: TestClient):
    """Test user registration"""
    user_data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
    }
    response = client.post("/register", json=user_data)
    assert response
    assert response.status_code == 201
    assert response.json()["username"] == "newuser"


def test_create_category(client: TestClient, test_user):
    """Test category creation"""
    category_data = {"name": "Science Fiction", "description": "Sci-fi books"}
    response = client.post(
        "/categories",
        json=category_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Science Fiction"


def test_create_book(client: TestClient, test_user, test_category):
    """Test book creation"""
    book_data = {
        "title": "New Book",
        "author": "New Author",
        "year": 2023,
        "publisher": "Publisher",
        "pages": 300,
        "total_copies": 3,
        "category_ids": [test_category["id"]],
    }
    response = client.post(
        "/books",
        json=book_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "New Book"
    assert response.json()["available_copies"] == 3


def test_get_books(client: TestClient, test_book):
    """Test getting all books"""
    response = client.get("/books")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_get_book_by_id(client: TestClient, test_book):
    """Test getting a specific book"""
    book_id = test_book["id"]
    response = client.get(f"/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["id"] == book_id


def test_get_nonexistent_book(client: TestClient):
    """Test getting a book that doesn't exist"""
    response = client.get("/books/99999")
    assert response.status_code == 404


def test_update_book(client: TestClient, test_user, test_book):
    """Test updating a book"""
    update_data = {"title": "Updated Book Title", "year": 2024}
    response = client.put(
        f"/books/{test_book['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Book Title"
    assert response.json()["year"] == 2024


def test_create_review(client: TestClient, test_user, test_book):
    """Test creating a book review"""
    review_data = {"rating": 5, "comment": "Excellent book!"}
    response = client.post(
        f"/books/{test_book['id']}/reviews",
        json=review_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    assert response.json()["rating"] == 5


def test_duplicate_review(client: TestClient, test_user, test_book):
    """Test creating duplicate review (should fail)"""
    review_data = {"rating": 4, "comment": "Another review"}
    # First review
    client.post(
        f"/books/{test_book['id']}/reviews",
        json=review_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    # Second review (should fail)
    response = client.post(
        f"/books/{test_book['id']}/reviews",
        json=review_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 400


def test_borrow_book(client: TestClient, test_user, test_book):
    """Test borrowing a book"""
    borrow_data = {"book_id": test_book["id"], "due_date": "2024-12-31T23:59:59"}
    response = client.post(
        "/borrow",
        json=borrow_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 201
    assert response.json()["book_id"] == test_book["id"]


def test_return_book(client: TestClient, test_user, test_book):
    """Test returning a borrowed book"""
    # First borrow
    borrow_data = {"book_id": test_book["id"], "due_date": "2024-12-31T23:59:59"}
    borrow_response = client.post(
        "/borrow",
        json=borrow_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    borrow_id = borrow_response.json()["id"]

    # Return
    response = client.post(
        f"/return/{borrow_id}",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    assert "returned successfully" in response.json()["message"]


def test_get_recommendations(client: TestClient, test_user, test_book):
    """Test getting book recommendations"""
    # Create some reviews first to have data for recommendations
    review_data = {"rating": 4, "comment": "Good book"}
    client.post(
        f"/books/{test_book['id']}/reviews",
        json=review_data,
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )

    # Get recommendations
    response = client.get(
        "/recommendations?limit=5",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200
    assert "recommendations" in response.json()
    assert "algorithm_used" in response.json()
    assert "confidence_score" in response.json()


def test_unauthorized_access(client: TestClient):
    """Test accessing protected endpoints without token"""
    response = client.get("/users/me")
    assert response.status_code == 401


def test_delete_book(client: TestClient, test_user, test_book):
    """Test deleting a book"""
    response = client.delete(
        f"/books/{test_book['id']}",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert response.status_code == 200

    # Verify book is deleted
    get_response = client.get(f"/books/{test_book['id']}")
    assert get_response.status_code == 404
