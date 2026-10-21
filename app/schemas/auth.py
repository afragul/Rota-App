from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Kayıt isteği. Sınırlar, argon2'ye ya da veritabanına aşırı büyük girdi gitmesin diye."""

    email: EmailStr = Field(max_length=254)
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _username_bosluk_kirp(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Kullanıcı adı en az 2 karakter olmalı")
        return value


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
