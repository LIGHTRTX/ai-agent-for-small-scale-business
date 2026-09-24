import csv
from pathlib import Path

from data import store
from workflow import service


class FakeScraper:
    def discover(self, query, location, limit=20):
        return [{
            "company_name": "Example Garden",
            "website": "https://example.test",
            "email": "hello@example.test",
            "phone": "555-0100",
            "city": location,
            "state": "",
            "source": "fake",
        }]


def test_workflow_adds_lead_and_emits_events(tmp_path, monkeypatch):
    csv_path = tmp_path / "businesses.csv"
    monkeypatch.setattr(store, "CSV_PATH", csv_path)
    monkeypatch.setattr(service, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(service, "enrich", lambda business: {**business, "operating_status": "active"})
    monkeypatch.setattr(service, "classify", lambda api_key, business: "Landscaping")
    monkeypatch.setattr(service, "gen_outreach", lambda api_key, business: "Hello from the test.")

    events = []
    result = service.run_workflow(
        api_key="test-key",
        target_queries=[("Landscaping Companies", "Austin")],
        per_query_limit=1,
        max_per_category=1,
        progress_callback=events.append,
        scraper=FakeScraper(),
    )

    assert result.added == 1
    assert result.failed == 0
    assert events[-1].stage == "complete"
    assert store.load_all()[0]["company_name"] == "Example Garden"
    assert (tmp_path / "output" / "example_garden" / "outreach_email.txt").read_text() == "Hello from the test."


def test_workflow_skips_duplicates(tmp_path, monkeypatch):
    csv_path = tmp_path / "businesses.csv"
    monkeypatch.setattr(store, "CSV_PATH", csv_path)
    monkeypatch.setattr(service, "OUTPUT_DIR", tmp_path / "output")
    store.append({
        "company_name": "Example Garden",
        "website": "https://example.test",
        "email": "hello@example.test",
        "city": "Austin",
        "state": "",
    })

    result = service.run_workflow(
        api_key="test-key",
        target_queries=[("Landscaping Companies", "Austin")],
        per_query_limit=1,
        max_per_category=1,
        do_enrich=False,
        do_classify=False,
        generate_outreach=False,
        scraper=FakeScraper(),
    )

    assert result.added == 0
    assert result.duplicates == 1
