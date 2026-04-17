from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional




class UserSignUp(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):

    id: int
    username: str  
    email: EmailStr
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """The schema returned to the UI after successful login."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """The schema for the data stored inside the JWT (used by the 'Guard')."""
    user_id: Optional[int] = None