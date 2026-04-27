from fastapi import APIRouter, HTTPException
from app.services.rag_ingestion_service import ingest_application_documents

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/ingest/{app_id}")
def ingest_documents(app_id: str):
    try:
        return ingest_application_documents(app_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG ingestion failed: {str(e)}")