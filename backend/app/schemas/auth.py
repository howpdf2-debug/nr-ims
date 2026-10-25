from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str | None = None

class LoginRequest(BaseModel):
    """JSON body of ``POST /auth/login``.

    ``email`` is deliberately a plain string, NOT ``EmailStr``: pydantic's e-mail validator rejects special-use
    domains, so every seeded account (``irca@nr-ims.local`` ...) would get a 422 (gap G-29). The value is only
    compared with ``users.email``, so no address syntax check is needed. Lengths are capped before the password
    reaches the (deliberately slow) argon2 hash. Unknown keys are refused (a typo must not be silently ignored).
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)