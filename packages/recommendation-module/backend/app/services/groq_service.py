from groq import Groq
from app.core.config import settings


def get_groq_client():
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured in .env")
    return Groq(api_key=settings.GROQ_API_KEY)


def generate_llm_response(system_prompt: str, user_prompt: str) -> str:
    client = get_groq_client()

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=400
    )

    return response.choices[0].message.content.strip()