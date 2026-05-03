import os
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_explanation(listing, underwriting):
    prompt = f"""
    Property: {listing['address']}
    Asking price: {listing['asking_price']}

    Underwriting:
    {underwriting}

    Explain this deal in plain language.
    """

    if not GROQ_API_KEY:
        return "LLM key missing."

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
    )
    return resp.json()["choices"][0]["message"]["content"]
