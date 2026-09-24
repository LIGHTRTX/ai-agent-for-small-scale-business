"""OpenStreetMap Overpass API scraper. 100% free, no API key, no billing.

Two-step process:
  1. Geocode the location name -> OSM area ID via Nominatim (free, needs User-Agent).
  2. Query Overpass for businesses matching an OSM tag filter within that area.

Rate limits: Overpass public instances are shared infra — be polite.
  - Nominatim: max 1 request/sec, must set a real User-Agent (their ToS).
  - Overpass: no hard key limit, but heavy/rapid queries get you soft-blocked.
    Keep limit sane (<=50 per call) and don't hammer in a tight loop.

Docs: https://wiki.openstreetmap.org/wiki/Overpass_API
      https://nominatim.org/release-docs/latest/api/Search/
"""
import time
import requests
from scrapers.base import BaseScraper

NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "tejas-business-agent/1.0 (contact: tejasmani17@gmail.com)"

# Map human query phrases -> OSM tag filters.
# Each entry is a list of (key, value) pairs, OR'd together in the Overpass query.
INDUSTRY_TAG_MAP = {
    "landscaping": [("craft", "gardener"), ("shop", "garden_centre"), ("landuse", "landscaping")],
    "real estate": [("office", "estate_agent")],
    "dental": [("amenity", "dentist")],
    "law": [("office", "lawyer")],
    "legal": [("office", "lawyer")],
    "construction": [("office", "construction_company"), ("craft", "builder")],
    "renovation": [("craft", "general_construction"), ("craft", "carpenter"), ("craft", "painter")],
    "logistics": [("office", "logistics"), ("office", "moving_company")],
    "property manage": [("office", "property_management")],
    "boutique": [("office", "advertising_agency"), ("office", "marketing")],
    "local services": [("shop", "yes")],  # broad catch-all, expect noisy results
    "hvac": [("craft", "hvac"), ("shop", "hvac")],
    "architecture": [("office", "architect"), ("office", "engineer")],
    "engineering": [("office", "engineer"), ("office", "architect")],
    "wealth management": [("office", "financial_advisor"), ("office", "financial")],
    "financial": [("office", "financial_advisor"), ("office", "financial")],
    "it": [("office", "it"), ("office", "coworking")],
    "cybersecurity": [("office", "it")],
    "catering": [("craft", "caterer"), ("amenity", "conference_centre")],
    "event venue": [("amenity", "conference_centre"), ("amenity", "events_venue")],
    "automotive": [("shop", "car_repair"), ("shop", "car")],
    "collision": [("shop", "car_repair")],
    "detail": [("shop", "car_repair")],
    "yacht": [("shop", "boat"), ("craft", "boatbuilder"), ("leisure", "marina")],
    "boat charter": [("shop", "boat"), ("amenity", "boat_rental")],
    "solar": [("shop", "energy"), ("craft", "electrician")],
    "pest control": [("office", "pest_control"), ("craft", "pest_control")],
    "medical equipment": [("shop", "medical_supply")],
}


def _match_tags(query: str) -> list[tuple[str, str]]:
    """Find the best tag filter for a free-text query string."""
    q = query.lower()
    for keyword, tags in INDUSTRY_TAG_MAP.items():
        if keyword in q:
            return tags
    # fallback: no match, use a generic office tag so the query still returns something
    return [("office", "company")]


class OSMOverpassScraper(BaseScraper):
    source_name = "osm_overpass"

    def __init__(self):
        self._area_cache: dict[str, str] = {}

    def _geocode_area(self, location: str) -> str | None:
        """Resolve a place name to an Overpass area ref (e.g. 'area(3600123456)')."""
        if location in self._area_cache:
            return self._area_cache[location]

        resp = requests.get(
            NOMINATIM_ENDPOINT,
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
        time.sleep(1)  # Nominatim ToS: max 1 req/sec

        if not results:
            return None

        osm_type = results[0]["osm_type"]  # 'relation', 'way', or 'node'
        osm_id = int(results[0]["osm_id"])

        # Overpass area IDs: relation -> +3600000000, way -> +2400000000
        if osm_type == "relation":
            area_id = osm_id + 3600000000
        elif osm_type == "way":
            area_id = osm_id + 2400000000
        else:
            return None  # nodes can't be used as search areas

        area_ref = f"area({area_id})"
        self._area_cache[location] = area_ref
        return area_ref

    def discover(self, query: str, location: str, limit: int = 20) -> list[dict]:
        area_ref = self._geocode_area(location)
        if not area_ref:
            return []

        tags = _match_tags(query)
        tag_clauses = "".join(f'node["{k}"="{v}"](area.searchArea);' for k, v in tags)
        tag_clauses += "".join(f'way["{k}"="{v}"](area.searchArea);' for k, v in tags)

        overpass_query = f"""
        [out:json][timeout:25];
        {area_ref}->.searchArea;
        (
          {tag_clauses}
        );
        out center {limit};
        """

        resp = requests.post(
            OVERPASS_ENDPOINT,
            data={"data": overpass_query},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        out = []
        for el in elements[:limit]:
            t = el.get("tags", {})
            name = t.get("name")
            if not name:
                continue  # skip unnamed nodes, not useful leads
            if any(k.startswith(("disused:", "was:", "closed:", "abandoned:", "demolished:"))
                   for k in t.keys()):
                continue
            out.append({
                "company_name": name,
                "website": t.get("website", t.get("contact:website", "")),
                "email": t.get("email", t.get("contact:email", "")),
                "phone": t.get("phone", t.get("contact:phone", "")),
                "city": t.get("addr:city", location),
                "state": t.get("addr:state", ""),
                "source": self.source_name,
                "osm_id": el.get("id", ""),
            })
        return out
