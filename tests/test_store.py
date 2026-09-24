from data import store


def test_update_row_writes_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "CSV_PATH", tmp_path / "businesses.csv")
    store.append({
        "company_name": "Example Garden",
        "website": "https://example.test",
        "email": "hello@example.test",
        "city": "Austin",
        "state": "TX",
        "status": "new",
    })
    row = store.load_all()[0]

    assert store.update_row(store.lead_key(row), {"status": "contacted"}) is True
    assert store.load_all()[0]["status"] == "contacted"
    assert store.update_row("missing", {"status": "archived"}) is False
