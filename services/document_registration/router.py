from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from . import service, schemas
from db.connection import get_db
from services.auth.dependencies import get_current_user
from db.models import User

router = APIRouter()


@router.post("/", response_model=schemas.DocumentResponse, status_code=201)
async def upload_document(
    application_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.register_document(
        db=db,
        app_id=application_id,
        file=file,
        user_id=current_user.id
    )


@router.get("/{application_id}", response_model=List[schemas.DocumentResponse])
async def get_documents(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.get_documents_for_application(
        db=db,
        app_id=application_id,
        user_id=current_user.id
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await service.delete_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id
    )