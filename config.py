"""Config loader/saver. Stores Groq key in .env, never in code."""
import os
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"


def save_key(key: str, name: str = "GROQ_API_KEY") -> None:
    lines = []
    if ENV_PATH.exists():
        lines = [l for l in ENV_PATH.read_text().splitlines() if not l.startswith(f"{name}=")]
    lines.append(f"{name}={key}")
    ENV_PATH.write_text("\n".join(lines) + "\n")
    print(f"[config] saved {name} to {ENV_PATH}")


def load_key(name: str = "GROQ_API_KEY") -> str | None:
    # .env (managed by this app's savekey command) takes priority over any
    # stray shell export, so a leftover `export GROQ_API_KEY=...` in
    # .bashrc/.profile can't silently override a correctly saved key.
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    if os.environ.get(name):
        return os.environ[name]
    return None
