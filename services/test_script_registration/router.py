from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from . import service, schemas, database
from db.models import User
from auth.dependencies import get_current_user  # ← import your existing dependency

router = APIRouter()

@router.post("/", response_model=schemas.TestScriptResponse)
async def create_test_script(
    application_id: int = Form(...),
    script_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_user)  # ← add this
):
    return await service.register_script(
        db=db,
        app_id=application_id,
        script_name=script_name,
        file=file
    )