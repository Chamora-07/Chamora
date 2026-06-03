from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from . import service, schemas

router = APIRouter()

@router.post("/signup", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
async def signup(user_data: schemas.UserSignUp, db: AsyncSession = Depends(get_db)):
    try:
        return await service.register_user(db, user_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.post("/login", response_model=schemas.Token)
async def login(credentials: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        return await service.authenticate_user(db, credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )