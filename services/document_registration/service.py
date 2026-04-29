from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile, HTTPException
from db.models import Document, Application
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = "application-documents"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def verify_application_ownership(
    db: AsyncSession,
    app_id: int,
    user_id: int
) -> Application:
    """
    Ensures the application exists and belongs to the requesting user.
    Prevents users from uploading documents to other users' applications.
    """
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.user_id == user_id
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found or does not belong to your account."
        )
    return application


async def upload_to_bucket(file: UploadFile, app_id: int) -> str:
    """
    Uploads document to Supabase storage.
    Path format: application/{app_id}/documents/{filename}
    """
    bucket_path = f"application/{app_id}/documents/{file.filename}"
    file_bytes = await file.read()

    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=bucket_path,
            file=file_bytes,
            file_options={
                "content-type": file.content_type or "application/octet-stream"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )

    return bucket_path


async def register_document(
    db: AsyncSession,
    app_id: int,
    file: UploadFile,
    user_id: int
) -> Document:
    # 1. Verify ownership before doing anything
    await verify_application_ownership(db, app_id, user_id)

    # 2. Upload to Supabase storage
    storage_path = await upload_to_bucket(file, app_id)

    # 3. Save record to DB
    db_document = Document(
        application_id=app_id,
        file_name=file.filename,
        storage_path=storage_path
    )

    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)
    return db_document


async def get_documents_for_application(
    db: AsyncSession,
    app_id: int,
    user_id: int
) -> list[Document]:
    """Returns all documents for an application, verifying ownership first."""
    await verify_application_ownership(db, app_id, user_id)

    result = await db.execute(
        select(Document).where(Document.application_id == app_id)
    )
    return result.scalars().all()


async def delete_document(
    db: AsyncSession,
    document_id: int,
    user_id: int
) -> None:
    """Deletes document record from DB and file from Supabase storage."""
    # 1. Fetch the document
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 2. Verify the application it belongs to is owned by this user
    await verify_application_ownership(db, document.application_id, user_id)

    # 3. Delete from Supabase storage
    try:
        supabase.storage.from_(SUPABASE_BUCKET).remove([document.storage_path])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file from storage: {str(e)}"
        )

    # 4. Delete DB record
    await db.delete(document)
    await db.commit()