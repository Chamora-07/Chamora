from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from services.auth.schemas import Token, UserLogin, UserResponse, UserSignUp
from services.auth.utils import hash_password , verify_password , create_access_token


async def register_user(db: AsyncSession , user_data: UserSignUp )-> UserResponse:

    query = select(User).where(User.email == user_data.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise Exception("A user with this email already exists")

    new_user = User(
        username = user_data.full_name,
        email = user_data.email,
        hashed_password = hash_password(user_data.password)
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)

async def authenticate_user(db: AsyncSession, login_data: UserLogin) -> Token:

    query = select(User).where(User.email == login_data.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password , user.hashed_password):
        raise Exception("Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token, token_type="bearer")