"""CSV lead store: dedup on name/website/email, append-only writes."""
import csv
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

CSV_PATH = Path(__file__).parent / "businesses.csv"
FIELDS = [
    "company_name", "website", "email", "phone", "industry",
    "city", "state", "source", "status", "discovered_at",
]


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\b(llc|inc|co|corp|ltd)\b\.?", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    url = url.lower().strip()
    url = re.sub(r"^https?://(www\.)?", "", url)
    return url.split("/")[0]


def lead_key(row: dict) -> str:
    """Return a stable identity that distinguishes duplicate company names."""
    parts = [
        _normalize(row.get("company_name")),
        _domain(row.get("website")),
        (row.get("email") or "").lower().strip(),
        _normalize(row.get("city")),
        _normalize(row.get("state")),
        (row.get("discovered_at") or "").strip(),
    ]
    return "|".join(parts)


def ensure_csv() -> None:
    if not CSV_PATH.exists():
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_PATH, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def load_all() -> list[dict]:
    ensure_csv()
    with open(CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def build_index(rows: list[dict]) -> tuple[set, set, set]:
    names = {_normalize(r["company_name"]) for r in rows}
    domains = {_domain(r["website"]) for r in rows if r.get("website")}
    emails = {r["email"].lower().strip() for r in rows if r.get("email")}
    return names, domains, emails


def index_business(business: dict, names: set, domains: set, emails: set) -> None:
    names.add(_normalize(business.get("company_name")))
    if business.get("website"):
        domains.add(_domain(business["website"]))
    if business.get("email"):
        emails.add(business["email"].lower().strip())


def exists(business: dict, names: set, domains: set, emails: set) -> bool:
    if _normalize(business.get("company_name")) in names:
        return True
    if business.get("website") and _domain(business["website"]) in domains:
        return True
    if business.get("email") and business["email"].lower().strip() in emails:
        return True
    return False


def append(business: dict) -> None:
    ensure_csv()
    row = {k: business.get(k, "") for k in FIELDS}
    with open(CSV_PATH, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(row)


def update_row(key: str, updates: dict) -> bool:
    """Update one lead atomically, returning whether a row matched."""
    rows = load_all()
    matched = False
    for row in rows:
        if lead_key(row) == key:
            for field, value in updates.items():
                if field in FIELDS:
                    row[field] = value
            matched = True
            break

    if not matched:
        return False

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=CSV_PATH.parent, prefix="businesses-", text=True)
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, CSV_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return True
