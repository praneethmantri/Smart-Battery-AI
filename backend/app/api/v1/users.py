import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """Creates a new user profile with unique email constraint validation."""
    logger.info("Creating user with email: %s", payload.email)
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        logger.warning("Duplicate user registration attempt for email: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    new_user = User(
        name=payload.name,
        email=payload.email,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("User successfully created with ID: %d", new_user.id)
    return new_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves user information by primary key ID."""
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID must be a positive integer",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning("User query failed: ID %d not found", user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    return user


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users",
)
def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieves paginated list of users."""
    users = db.query(User).order_by(User.id.asc()).offset(offset).limit(limit).all()
    return users
