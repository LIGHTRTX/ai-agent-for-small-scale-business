"""Google Places Text Search scraper. Requires GOOGLE_PLACES_KEY env/config.
Compliant alternative to scraping Maps HTML directly.
"""
import requests
from scrapers.base import BaseScraper


class GooglePlacesScraper(BaseScraper):
    source_name = "google_places"
    ENDPOINT = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def discover(self, query: str, location: str, limit: int = 20) -> list[dict]:
        params = {"query": f"{query} in {location}", "key": self.api_key}
        results, out = [], []
        while len(out) < limit:
            resp = requests.get(self.ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            for r in results:
                out.append({
                    "company_name": r.get("name", ""),
                    "website": "",  # requires Place Details call to fill
                    "email": "",
                    "phone": "",
                    "city": location,
                    "state": "",
                    "source": self.source_name,
                    "place_id": r.get("place_id", ""),
                })
                if len(out) >= limit:
                    break
            token = data.get("next_page_token")
            if not token or len(out) >= limit:
                break
            params = {"pagetoken": token, "key": self.api_key}
        return out
