import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.user import ROLES

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or not _EMAIL_RE.match(value):
        raise ValueError("Email không hợp lệ")
    return value


def _check_role(value: str) -> str:
    if value not in ROLES:
        raise ValueError("Vai trò không hợp lệ")
    return value


def _check_password_strength(value: str) -> str:
    if (
        len(value) < 10
        or not any(c.isalpha() for c in value)
        or not any(c.isdigit() for c in value)
    ):
        raise ValueError("Mật khẩu tối thiểu 10 ký tự, gồm cả chữ và số")
    return value


Email = Annotated[str, AfterValidator(_normalize_email)]
Role = Annotated[str, AfterValidator(_check_role)]
NewPassword = Annotated[str, Field(max_length=128), AfterValidator(_check_password_strength)]


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: NewPassword


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
