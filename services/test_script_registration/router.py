from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession  # ← async session
from . import service, schemas
from db.connection import get_db
from services.auth.dependencies import get_current_user
from db.models import User

router = APIRouter()

@router.post("/", response_model=schemas.TestScriptResponse)
async def create_test_script(
    application_id: int = Form(...),
    script_name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),  # ← AsyncSession
    current_user: User = Depends(get_current_user)
):
    return await service.register_script(
        db=db,
        app_id=application_id,
        script_name=script_name,
        file=file
    )