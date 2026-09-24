"""Thin Groq chat completion wrapper with rate-limit + connection-error retry."""
import time
import requests

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def complete(api_key: str, system: str, user: str, model: str = DEFAULT_MODEL,
             temperature: float = 0.3, max_tokens: int = 600,
             max_retries: int = 5) -> str:
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 2 ** attempt))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    if last_err:
        raise last_err
    resp.raise_for_status()
