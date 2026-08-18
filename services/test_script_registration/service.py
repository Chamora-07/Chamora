from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, HTTPException
from db.models import TestScript
from db.supabase_client import get_supabase, BUCKET_TEST_SCRIPTS

async def upload_to_bucket(file: UploadFile, app_id: int) -> str:
    bucket_path = f"apps/{app_id}/scripts/{file.filename}"
    
    file_bytes = await file.read()
    
    try:
        get_supabase().storage.from_(BUCKET_TEST_SCRIPTS).upload(
            path=bucket_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    return bucket_path

async def register_script(db: AsyncSession, app_id: int, script_name: str, file: UploadFile):
    storage_path = await upload_to_bucket(file, app_id)

    db_script = TestScript(
        application_id=app_id,
        script_name=script_name,
        storage_path=storage_path
    )
    
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)
    return db_script