from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional

class UserSignUp(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    timezone: str = Field(default="UTC")  # ← e.g. "Asia/Colombo" from browser

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    timezone: str = Field(default="UTC")  # ← sent on every login, stays fresh

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    timezone: Optional[str] = "UTC"  # ← extracted from JWT in dependencies