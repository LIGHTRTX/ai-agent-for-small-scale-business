"""Presentation helpers shared by the Streamlit dashboard."""
from pathlib import Path

from data import store

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"


def lead_key(row: dict) -> str:
    return store.lead_key(row)


def location(row: dict) -> str:
    parts = [row.get("city", "").strip(), row.get("state", "").strip()]
    return ", ".join(part for part in parts if part)


def output_dir(row: dict) -> Path:
    name = row.get("company_name", "")
    safe_name = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in name.strip().lower()
    )[:60]
    return OUTPUT_DIR / safe_name


def load_outreach(row: dict) -> str:
    path = output_dir(row) / "outreach_email.txt"
    return path.read_text() if path.exists() else ""


def display(value: object, fallback: str = "Not available") -> str:
    text = str(value or "").strip()
    return text or fallback
