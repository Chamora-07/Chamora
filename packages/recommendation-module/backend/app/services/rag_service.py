import re
from app.core.supabase_client import get_supabase_client


STOP_WORDS = {
    "the", "is", "are", "a", "an", "to", "for", "of", "and", "or", "in",
    "on", "my", "about", "what", "why", "how", "does", "do", "with"
}


def normalize_text(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [word for word in words if word not in STOP_WORDS and len(word) > 2]


def calculate_keyword_score(question: str, chunk_text: str) -> int:
    question_words = normalize_text(question)
    chunk_words = normalize_text(chunk_text)

    score = 0

    for word in question_words:
        if word in chunk_words:
            score += 2  # stronger weight

    # bonus for phrase match
    if any(word in chunk_text.lower() for word in question_words):
        score += 1

    return score


def get_chunks_for_application(app_id: str):
    supabase = get_supabase_client()

    result = (
        supabase.table("knowledge_chunks")
        .select("id,document_id,application_id,chunk_index,chunk_text,metadata_json")
        .eq("application_id", app_id)
        .execute()
    )

    return result.data or []


def retrieve_relevant_chunks(app_id: str, question: str, top_k: int = 3):
    chunks = get_chunks_for_application(app_id)

    scored_chunks = []

    for chunk in chunks:
        score = calculate_keyword_score(question, chunk.get("chunk_text", ""))

        if score > 0:
            scored_chunks.append(
                {
                    "id": chunk["id"],
                    "document_id": chunk["document_id"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["chunk_text"],
                    "metadata": chunk.get("metadata_json") or {},
                    "score": score,
                }
            )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)

    return scored_chunks[:top_k]


def format_retrieved_knowledge(retrieved_chunks, max_chars=2000):
    if not retrieved_chunks:
        return "No relevant knowledge found."

    combined = ""
    for chunk in retrieved_chunks:
        text = chunk["text"]

        if len(combined) + len(text) > max_chars:
            break

        combined += "\n\n" + text

    return combined.strip()