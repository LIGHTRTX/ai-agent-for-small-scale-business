"""Enrich a raw discovered business with website/contact details, and flag
whether it appears to still be operating (website live vs dead/parked).
"""
import re
import requests


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")

DEAD_DOMAIN_MARKERS = [
    "domain is for sale", "domain may be for sale", "buy this domain",
    "this domain is parked", "website is currently unavailable",
    "account has been suspended", "this site can't be reached",
]


def enrich(business: dict) -> dict:
    website = business.get("website")
    if not website:
        business["operating_status"] = "unverified"
        return business

    try:
        resp = requests.get(
            website, timeout=10, headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
        )
        html = resp.text
    except requests.RequestException:
        business["operating_status"] = "likely_closed"
        return business

    if resp.status_code >= 400:
        business["operating_status"] = "likely_closed"
        return business

    lowered = html.lower()
    if any(marker in lowered for marker in DEAD_DOMAIN_MARKERS):
        business["operating_status"] = "likely_closed"
        return business

    business["operating_status"] = "active"

    if not business.get("email"):
        m = EMAIL_RE.search(html)
        if m:
            business["email"] = m.group(0)
    if not business.get("phone"):
        m = PHONE_RE.search(html)
        if m:
            business["phone"] = m.group(0)

    title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    business["page_title"] = title_m.group(1).strip() if title_m else ""
    desc_m = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
        html, re.IGNORECASE,
    )
    business["meta_description"] = desc_m.group(1).strip() if desc_m else ""
    return business
