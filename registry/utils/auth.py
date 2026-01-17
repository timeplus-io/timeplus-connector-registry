"""Authentication and authorization utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.config import get_settings
from registry.database import get_db
from registry.models import Publisher
from registry.schemas import TokenData

settings = get_settings()

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        namespace: Optional[str] = payload.get("sub")
        if namespace is None:
            return None
        return TokenData(namespace=namespace)
    except JWTError:
        return None


async def get_current_publisher(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[Publisher]:
    """Get the current authenticated publisher (optional)."""
    if credentials is None:
        return None

    token_data = decode_token(credentials.credentials)
    if token_data is None or token_data.namespace is None:
        return None

    result = await db.execute(
        select(Publisher).where(Publisher.namespace == token_data.namespace)
    )
    publisher = result.scalar_one_or_none()
    return publisher


async def get_required_publisher(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Publisher:
    """Get the current authenticated publisher (required)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token_data = decode_token(credentials.credentials)
    if token_data is None or token_data.namespace is None:
        raise credentials_exception

    result = await db.execute(
        select(Publisher).where(Publisher.namespace == token_data.namespace)
    )
    publisher = result.scalar_one_or_none()

    if publisher is None:
        raise credentials_exception

    return publisher


async def authenticate_publisher(
    db: AsyncSession, namespace: str, password: str
) -> Optional[Publisher]:
    """Authenticate a publisher by namespace and password."""
    result = await db.execute(select(Publisher).where(Publisher.namespace == namespace))
    publisher = result.scalar_one_or_none()

    if publisher is None:
        return None

    if not verify_password(password, publisher.api_key_hash):
        return None

    return publisher
