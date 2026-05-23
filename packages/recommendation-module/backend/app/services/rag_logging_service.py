from app.core.supabase_client import get_supabase_client


def log_retrieval(app_id, question, chunks):
    supabase = get_supabase_client()

    try:
        supabase.table("rag_retrieval_logs").insert({
            "application_id": app_id,
            "question": question,
            "retrieved_chunk_ids": [c["id"] for c in chunks],
        }).execute()
    except Exception:
        pass