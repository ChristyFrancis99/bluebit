from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from core.config import settings

import hashlib

# Use sha256_crypt as fallback if bcrypt has version issues
try:
    import bcrypt as _bcrypt
    # Test bcrypt works correctly
    _bcrypt.hashpw(b"test", _bcrypt.gensalt())
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _USE_BCRYPT = True
except Exception:
    pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
    _USE_BCRYPT = False

bearer_scheme = HTTPBearer()


class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    institution_id: Optional[str] = None


def _prep_password(password: str) -> str:
    """Truncate to 72 bytes (bcrypt hard limit) via sha256 hex digest."""
    # sha256 hex = 64 chars, safely within 72 bytes
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_prep_password(plain), hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(_prep_password(password))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return TokenData(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            institution_id=payload.get("institution_id"),
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    return decode_token(credentials.credentials)


async def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def require_educator(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    if current_user.role not in ("educator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Educator or admin privileges required",
        )
    return current_user
