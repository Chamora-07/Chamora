try:
    from groq import Groq
except ImportError:  # optional dependency in environments that use synthetic fallback
    Groq = None
from ..core.config import settings


def get_groq_client():
    if Groq is None:
        raise ValueError("Groq client is not available in this environment")

    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured in .env")
    return Groq(api_key=settings.GROQ_API_KEY)


def generate_llm_response(system_prompt: str, user_prompt: str) -> str:
    client = get_groq_client()

    print("=== SYSTEM PROMPT SENT TO GROQ ===")
    print(system_prompt)
    print("=== MODEL:", settings.GROQ_MODEL, "===")

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4,
        max_tokens=700,
        reasoning_effort="medium",
    )

    message = response.choices[0].message
    content = (message.content or "").strip()

    if not content:
        reasoning = getattr(message, "reasoning", None)
        if reasoning:
            content = reasoning.strip()

    return content