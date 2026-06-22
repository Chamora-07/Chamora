from app.core.supabase_client import get_supabase_client


def create_chat_session(application_id: str, user_id: str | None, mode: str) -> dict:
    supabase = get_supabase_client()

    payload = {
        "application_id": application_id,
        "user_id": user_id,
        "current_mode": mode,
        "status": "active",
    }

    result = supabase.table("chat_sessions").insert(payload).execute()
    return result.data[0]


def store_chat_message(
    session_id: str,
    application_id: str,
    user_id: str | None,
    role: str,
    message_text: str,
    question_type: str,
) -> dict:
    supabase = get_supabase_client()

    payload = {
        "session_id": session_id,
        "application_id": application_id,
        "user_id": user_id,
        "role": role,
        "message_text": message_text,
        "question_type": question_type,
    }

    result = supabase.table("chat_messages").insert(payload).execute()
    return result.data[0]


def store_recommendation_history(
    application_id: str,
    user_id: str | None,
    session_id: str,
    question: str,
    answer: str,
    mode: str,
    recommendations_json=None,
) -> dict:
    supabase = get_supabase_client()

    payload = {
        "application_id": application_id,
        "user_id": user_id,
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "mode": mode,
        "recommendations_json": recommendations_json or [],
    }

    result = supabase.table("recommendation_history").insert(payload).execute()
    return result.data[0]