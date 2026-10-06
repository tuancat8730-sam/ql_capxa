from pydantic import BaseModel, Field

from app.schemas.auth import Email, Role, UserOut


class UserCreate(BaseModel):
    email: Email
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    role: Role


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    role: Role | None = None
    is_active: bool | None = None


class UserWithTempPassword(UserOut):
    temporary_password: str


class TempPasswordOut(BaseModel):
    temporary_password: str
