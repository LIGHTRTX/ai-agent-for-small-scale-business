"""Scraper interface. Each source implements discover() -> list[dict].

Raw dict keys expected: company_name, website, email, phone, city, state, source
Use compliant sources only (Google Places API, state biz registries, Clutch).
Do not scrape Google Maps / LinkedIn HTML directly — ToS violation + IP bans.
"""
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    source_name: str = "base"

    @abstractmethod
    def discover(self, query: str, location: str, limit: int = 20) -> list[dict]:
        """Return list of raw business dicts. Must include company_name."""
        raise NotImplementedError
