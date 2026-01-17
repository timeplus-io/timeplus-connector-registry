"""Publisher API routes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from registry.config import get_settings
from registry.database import get_db
from registry.models import Publisher
from registry.schemas import (
    ConnectorListResponse,
    ErrorResponse,
    LoginRequest,
    PublisherCreate,
    PublisherResponse,
    Token,
)
from registry.services import ConnectorService, PublisherService
from registry.utils import authenticate_publisher, create_access_token, get_required_publisher

router = APIRouter(tags=["Publishers"])
settings = get_settings()


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def register_publisher(
    publisher_data: PublisherCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new publisher account.

    Returns an access token for authentication.
    """
    service = PublisherService(db)

    try:
        publisher = await service.create_publisher(
            namespace=publisher_data.namespace,
            display_name=publisher_data.display_name,
            email=publisher_data.email,
            password=publisher_data.password,
        )
    except ValueError as e:
        if "already" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": publisher.namespace},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return Token(access_token=access_token)


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"model": ErrorResponse},
    },
)
async def login(
    login_request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login to get an access token.
    """
    publisher = await authenticate_publisher(
        db, login_request.namespace, login_request.password
    )

    if publisher is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid namespace or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": publisher.namespace},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return Token(access_token=access_token)


@router.get("/me", response_model=PublisherResponse)
async def get_current_user(
    publisher: Publisher = Depends(get_required_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated publisher information."""
    service = PublisherService(db)
    return await service.get_publisher(publisher.namespace)


@router.get("/publishers/{namespace}", response_model=PublisherResponse)
async def get_publisher(
    namespace: str,
    db: AsyncSession = Depends(get_db),
):
    """Get publisher information by namespace."""
    service = PublisherService(db)
    publisher = await service.get_publisher(namespace)

    if publisher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publisher '{namespace}' not found",
        )

    return publisher


@router.get("/publishers/{namespace}/connectors", response_model=ConnectorListResponse)
async def get_publisher_connectors(
    namespace: str,
    db: AsyncSession = Depends(get_db),
):
    """List all connectors by a publisher."""
    connector_service = ConnectorService(db)
    return await connector_service.list_connectors(namespace=namespace)
