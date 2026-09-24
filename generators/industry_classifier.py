"""Classify a business into one of the target industries. Strict enum output."""
from generators.groq_client import complete

INDUSTRIES = [
    "Landscaping", "Real Estate", "Dental", "Legal", "Construction",
    "Home Renovation", "Logistics", "Local Services", "Boutique Agencies",
    "Property Management", "HVAC", "Architecture & Engineering",
    "Wealth Management", "IT & Cybersecurity", "Catering & Events",
    "Automotive", "Yacht & Boat Charter", "Solar Energy",
    "Pest Control", "Medical Equipment", "Other",
]

SYSTEM = (
    "You classify a small business into exactly one category from this list: "
    + ", ".join(INDUSTRIES)
    + ". Reply with ONLY the category name, nothing else. If unsure, reply 'Other'."
)


def classify(api_key: str, business: dict) -> str:
    context = (
        f"Name: {business.get('company_name', '')}\n"
        f"Website title: {business.get('page_title', '')}\n"
        f"Description: {business.get('meta_description', '')}"
    )
    result = complete(api_key, SYSTEM, context, temperature=0.0, max_tokens=10)
    result = result.strip()
    return result if result in INDUSTRIES else "Other"
