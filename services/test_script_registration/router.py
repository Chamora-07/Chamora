from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from . import service, schemas, database  # Adjust imports based on your setup

router = APIRouter()

@router.post("/", response_model=schemas.TestScriptResponse)
async def create_test_script(
    application_id: int = Form(...),
    script_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db)
):
    return await service.register_script(
        db=db, 
        app_id=application_id, 
        script_name=script_name, 
        file=file
    )