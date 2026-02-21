from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, Institution
from db.session import get_db
from services.auth import (
    verify_password, hash_password, create_access_token,
    get_current_user, TokenData,
)
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "student"
    institution_id: str = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    email: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check existing user
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    if req.role not in ("student", "educator", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        institution_id=req.institution_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "institution_id": user.institution_id,
    })
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "institution_id": user.institution_id,
    })
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        email=user.email,
    )


@router.get("/me")
async def me(current_user: TokenData = Depends(get_current_user)):
    return current_user
