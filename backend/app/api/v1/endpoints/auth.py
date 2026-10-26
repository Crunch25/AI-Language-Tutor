from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.exceptions import (
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    SecurityCompromisedError,
    TokenRevokedError,
)
from app.core.unit_of_work import UOWDep
from app.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new learner account",
)
async def register(
    payload: UserRegister,
    uow: UOWDep,
) -> UserRead:
    """Registers a unique learner and hashes credentials."""
    auth_service = AuthService(uow=uow)
    try:
        user = await auth_service.register(payload)
        return UserRead.model_validate(user)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive access + refresh token pair",
)
async def login(
    request: Request,
    uow: UOWDep,
) -> TokenResponse:
    """
    Accepts credentials via either application/json (Next.js frontend)
    or application/x-www-form-urlencoded (Swagger UI / OAuth2 specification).
    """
    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Form data missing required username or password fields",
            )
        login_dto = UserLogin(email=str(username), password=str(password))
    else:
        try:
            body = await request.json()
            login_dto = UserLogin.model_validate(body)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid or missing JSON credentials in request body",
            )

    auth_service = AuthService(uow=uow)
    try:
        return await auth_service.authenticate(login_dto)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new token pair",
)
async def refresh_token(
    payload: TokenRefreshRequest,
    uow: UOWDep,
) -> TokenResponse:
    """
    Rotates the incoming refresh token. Detects replay attacks and revokes
    all active sessions if an already-invalidated token is presented.
    """
    auth_service = AuthService(uow=uow)
    try:
        return await auth_service.refresh_token(payload.refresh_token)
    except SecurityCompromisedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (InvalidTokenError, TokenRevokedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message,
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke active refresh token session",
)
async def logout(
    payload: TokenRefreshRequest,
    uow: UOWDep,
) -> None:
    """Invalidates the provided refresh token session."""
    auth_service = AuthService(uow=uow)
    await auth_service.logout(payload.refresh_token)