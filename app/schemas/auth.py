from pydantic import BaseModel, EmailStr, Field, field_validator


def _username_temizle(value: str) -> str:
    value = value.strip()
    if len(value) < 2:
        raise ValueError("Kullanıcı adı en az 2 karakter olmalı")
    return value


class RegisterRequest(BaseModel):
    """Kayıt isteği. Sınırlar, argon2'ye ya da veritabanına aşırı büyük girdi gitmesin diye."""

    email: EmailStr = Field(max_length=254)
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    _username = field_validator("username")(_username_temizle)


class UpdateProfileRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)

    _username = field_validator("username")(_username_temizle)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
