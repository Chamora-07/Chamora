from ..core.supabase_client import get_supabase_client


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


def get_chat_sessions(application_id: str) -> list[dict]:
    supabase = get_supabase_client()

    result = (
        supabase.table("chat_sessions")
        .select("id, application_id, current_mode, status, created_at")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .execute()
    )

    sessions = result.data or []
    enriched_sessions: list[dict] = []

    for session in sessions:
        session_id = session.get("id")
        latest_message_result = (
            supabase.table("chat_messages")
            .select("message_text, role, created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_message = (latest_message_result.data or [{}])[0]
        preview = latest_message.get("message_text") or "No messages yet"
        timestamp = latest_message.get("created_at") or session.get("created_at")

        enriched_sessions.append(
            {
                "id": str(session_id),
                "application_id": str(session.get("application_id")),
                "title": f"{str(session.get('current_mode') or 'advisory').replace('_', ' ').title()} Chat",
                "preview": preview,
                "timestamp": timestamp,
                "mode": session.get("current_mode") or "advisory",
                "status": session.get("status") or "active",
            }
        )

    return enriched_sessions


def get_chat_messages(session_id: str) -> list[dict]:
    supabase = get_supabase_client()

    result = (
        supabase.table("chat_messages")
        .select("id, role, message_text, question_type, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )

    messages = result.data or []

    return [
        {
            "id": str(message.get("id")),
            "type": "bot" if message.get("role") == "assistant" else "user",
            "content": message.get("message_text") or "",
            "details": None,
            "timestamp": message.get("created_at"),
        }
        for message in messages
    ]