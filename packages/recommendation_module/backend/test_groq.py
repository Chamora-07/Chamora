# backend/test_groq.py
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

print("API key present:", bool(api_key))
print("Model:", model)

client = Groq(api_key=api_key)

response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "user", "content": "Say hello in one short sentence."}
    ],
    temperature=0.2,
    max_tokens=50
)

print("SUCCESS")
print(response.choices[0].message.content)