from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.rag_ingestion_service import ingest_application_documents
from app.services.rag_service import retrieve_relevant_chunks, format_retrieved_knowledge


router = APIRouter(prefix="/rag", tags=["RAG"])


class RetrievalRequest(BaseModel):
    app_id: str
    question: str
    top_k: int = 3


@router.post("/ingest/{app_id}")
def ingest_documents(app_id: str):
    try:
        return ingest_application_documents(app_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG ingestion failed: {str(e)}")


@router.post("/retrieve")
def retrieve_documents(request: RetrievalRequest):
    try:
        chunks = retrieve_relevant_chunks(
            app_id=request.app_id,
            question=request.question,
            top_k=request.top_k,
        )

        return {
            "application_id": request.app_id,
            "question": request.question,
            "chunks_found": len(chunks),
            "chunks": chunks,
            "formatted_knowledge": format_retrieved_knowledge(chunks),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG retrieval failed: {str(e)}")