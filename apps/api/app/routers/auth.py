import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response

from app.core.config import get_settings
from app.core.deps import CurrentUserAllowPwChange, SessionDep
from app.core.errors import AppError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenOut, UserOut
from app.services import audit
from app.services.auth import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(str(user.id), "refresh", token_version=user.token_version),
        max_age=settings.jwt_refresh_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _token_out(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_token(str(user.id), "access", token_version=user.token_version),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginRequest, request: Request, response: Response, session: SessionDep
) -> TokenOut:
    user = await authenticate(session, body.email, body.password, request)
    _set_refresh_cookie(response, user)
    return _token_out(user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenOut:
    if not refresh_token:
        raise AppError(401, "unauthorized", "Chưa đăng nhập")
    claims = decode_token(refresh_token, "refresh")
    try:
        user = await session.get(User, uuid.UUID(claims["sub"]))
    except ValueError as exc:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ") from exc
    if user is None or not user.is_active or claims.get("tv") != user.token_version:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return _token_out(user)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUserAllowPwChange) -> User:
    return user


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: CurrentUserAllowPwChange,
    session: SessionDep,
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(400, "wrong_password", "Mật khẩu hiện tại không đúng")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version += 1  # revokes every access/refresh token issued so far
    audit.record(
        session,
        action="update",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        changes={"credential": "changed"},
        request=request,
    )
    await session.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
