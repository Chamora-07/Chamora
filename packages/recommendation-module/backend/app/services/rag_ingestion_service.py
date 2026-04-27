from io import BytesIO
from pypdf import PdfReader

from app.core.supabase_client import get_supabase_client
from app.core.config import settings


def get_documents_for_application(app_id: str):
    supabase = get_supabase_client()

    result = (
        supabase.table("documents")
        .select("id,application_id,file_name,storage_path")
        .eq("application_id", app_id)
        .execute()
    )

    return result.data or []


def download_document(storage_path: str) -> bytes:
    supabase = get_supabase_client()

    return supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(storage_path)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def extract_text(file_name: str, file_bytes: bytes) -> str:
    lower_name = file_name.lower()

    if lower_name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)

    if lower_name.endswith(".txt") or lower_name.endswith(".md") or lower_name.endswith(".jmx"):
        return file_bytes.decode("utf-8", errors="ignore")

    return ""


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200):
    clean_text = " ".join(text.split())

    if not clean_text:
        return []

    chunks = []
    start = 0

    while start < len(clean_text):
        end = start + chunk_size
        chunk = clean_text[start:end]

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap

        if start < 0:
            start = 0

        if start >= len(clean_text):
            break

    return chunks


def delete_existing_chunks(document_id):
    supabase = get_supabase_client()

    supabase.table("knowledge_chunks").delete().eq("document_id", document_id).execute()


def save_chunks(document, chunks):
    supabase = get_supabase_client()

    rows = []

    for index, chunk in enumerate(chunks):
        rows.append(
            {
                "document_id": document["id"],
                "application_id": document["application_id"],
                "chunk_index": index,
                "chunk_text": chunk,
                "token_count": len(chunk.split()),
                "metadata_json": {
                    "file_name": document["file_name"],
                    "storage_path": document["storage_path"],
                    "source": "user_uploaded_document",
                },
            }
        )

    if rows:
        supabase.table("knowledge_chunks").insert(rows).execute()

    return len(rows)


def ingest_document(document):
    file_bytes = download_document(document["storage_path"])
    text = extract_text(document["file_name"], file_bytes)

    if not text.strip():
        return {
            "document_id": document["id"],
            "status": "failed",
            "reason": "No extractable text found",
            "chunks_created": 0,
        }

    chunks = chunk_text(text)

    delete_existing_chunks(document["id"])
    count = save_chunks(document, chunks)

    return {
        "document_id": document["id"],
        "file_name": document["file_name"],
        "status": "completed",
        "chunks_created": count,
    }


def ingest_application_documents(app_id: str):
    documents = get_documents_for_application(app_id)

    results = []

    for document in documents:
        try:
            results.append(ingest_document(document))
        except Exception as e:
            results.append(
                {
                    "document_id": document.get("id"),
                    "file_name": document.get("file_name"),
                    "status": "failed",
                    "reason": str(e),
                    "chunks_created": 0,
                }
            )

    return {
        "application_id": app_id,
        "documents_found": len(documents),
        "results": results,
    }