"""Generate a personalized outreach email. Always anchors on ONE specific,
concrete detail about the business (not generic SMB automation pitch)."""
from generators.groq_client import complete

SYSTEM = """You write short, direct cold outreach emails offering AI/CRM automation
services to small business owners. Rules:
- Under 120 words.
- Open with a specific, real observation about THEIR business (from the context given).
- One clear, concrete value proposition tied to that observation.
- One low-friction call to action (15-min call, or reply with a question).
- No generic phrases like "I hope this finds you well" or "streamline your operations".
- No exclamation points, no emojis, no fluff.
"""


def generate(api_key: str, business: dict, specific_gap: str = "") -> str:
    context = (
        f"Company: {business.get('company_name', '')}\n"
        f"Industry: {business.get('industry', '')}\n"
        f"Website description: {business.get('meta_description', '')}\n"
        f"Specific gap/observation: {specific_gap or 'none provided — infer from description'}\n"
    )
    return complete(api_key, SYSTEM, context, temperature=0.5, max_tokens=250)
