from sqlalchemy.orm import Session
from fastapi import UploadFile
from . import models, schemas
import os

async def upload_to_bucket(file: UploadFile, app_id: int) -> str:
    # Logic to upload file to S3/Supabase/MinIO
    # Standard path structure: /apps/{app_id}/scripts/{filename}
    bucket_path = f"apps/{app_id}/scripts/{file.filename}"
    
    # Placeholder: Insert your bucket upload code here
    # await storage_client.upload(bucket_path, file)
    
    return bucket_path

async def register_script(db: Session, app_id: int, script_name: str, file: UploadFile):
    # 1. Upload the file first
    storage_path = await upload_to_bucket(file, app_id)

    # 2. Save metadata to the database
    db_script = models.TestScript(
        application_id=app_id,
        script_name=script_name,
        storage_path=storage_path
    )
    
    db.add(db_script)
    db.commit()
    db.refresh(db_script)
    return db_script