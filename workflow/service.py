"""Reusable lead discovery and processing workflow."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Iterable

from data import store
from enrich.company_enrich import enrich
from generators.industry_classifier import classify
from generators.outreach_generator import generate as gen_outreach
from scrapers.osm_overpass import OSMOverpassScraper

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

DEFAULT_TARGET_QUERIES = [
    ("Landscaping Companies", "Austin, Texas, USA"),
    ("Landscaping Companies", "Toronto, Ontario, Canada"),
    ("Real Estate Brokerages", "Denver, Colorado, USA"),
    ("Real Estate Brokerages", "Vancouver, British Columbia, Canada"),
    ("Dental Clinics", "Phoenix, Arizona, USA"),
    ("Dental Clinics", "Calgary, Alberta, Canada"),
    ("Law Firms", "Charlotte, North Carolina, USA"),
    ("Law Firms", "Ottawa, Ontario, Canada"),
    ("Construction Contractors", "Nashville, Tennessee, USA"),
    ("Construction Contractors", "Edmonton, Alberta, Canada"),
    ("Home Renovation Companies", "Tampa, Florida, USA"),
    ("Home Renovation Companies", "Winnipeg, Manitoba, Canada"),
    ("Logistics Companies", "Columbus, Ohio, USA"),
    ("Logistics Companies", "Mississauga, Ontario, Canada"),
    ("Local Service Businesses", "Portland, Oregon, USA"),
    ("Local Service Businesses", "Halifax, Nova Scotia, Canada"),
    ("Boutique Agencies", "Austin, Texas, USA"),
    ("Boutique Agencies", "Montreal, Quebec, Canada"),
    ("Property Managers", "Raleigh, North Carolina, USA"),
    ("Property Managers", "Hamilton, Ontario, Canada"),
    ("Commercial HVAC Contractors", "Dallas, Texas, USA"),
    ("Commercial HVAC Contractors", "Calgary, Alberta, Canada"),
    ("Architecture & Engineering Firms", "Chicago, Illinois, USA"),
    ("Architecture & Engineering Firms", "Toronto, Ontario, Canada"),
    ("Wealth Management & Financial Advisories", "Boston, Massachusetts, USA"),
    ("Wealth Management & Financial Advisories", "Toronto, Ontario, Canada"),
    ("Corporate IT & Cybersecurity Providers", "Austin, Texas, USA"),
    ("Corporate IT & Cybersecurity Providers", "Ottawa, Ontario, Canada"),
    ("Catering & Corporate Event Venues", "Atlanta, Georgia, USA"),
    ("Catering & Corporate Event Venues", "Toronto, Ontario, Canada"),
    ("Automotive Collision & Detail Centers", "Houston, Texas, USA"),
    ("Automotive Collision & Detail Centers", "Vancouver, British Columbia, Canada"),
    ("Custom Yacht & Boat Charter Agencies", "Miami, Florida, USA"),
    ("Custom Yacht & Boat Charter Agencies", "Vancouver, British Columbia, Canada"),
    ("Solar Energy Installers", "Phoenix, Arizona, USA"),
    ("Solar Energy Installers", "Calgary, Alberta, Canada"),
    ("Commercial Pest Control Providers", "Orlando, Florida, USA"),
    ("Commercial Pest Control Providers", "Toronto, Ontario, Canada"),
    ("Medical Equipment Distributors", "Minneapolis, Minnesota, USA"),
    ("Medical Equipment Distributors", "Toronto, Ontario, Canada"),
]


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    message: str
    completed: int = 0
    total: int = 0
    level: str = "info"


@dataclass
class WorkflowResult:
    added: int = 0
    previewed: int = 0
    duplicates: int = 0
    closed: int = 0
    failed: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    query_errors: list[str] = field(default_factory=list)
    lead_errors: list[str] = field(default_factory=list)

    @property
    def processed(self) -> int:
        return self.added + self.previewed


ProgressCallback = Callable[[ProgressEvent], None]


def safe_slug(name: str) -> str:
    return "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in name.strip().lower()
    )[:60]


def save_lead_package(business: dict, outreach_email: str) -> None:
    company_dir = OUTPUT_DIR / safe_slug(business["company_name"])
    company_dir.mkdir(parents=True, exist_ok=True)

    (company_dir / "company_info.json").write_text(json.dumps({
        "company_name": business.get("company_name", ""),
        "website": business.get("website", ""),
        "industry": business.get("industry", ""),
        "city": business.get("city", ""),
        "state": business.get("state", ""),
        "source": business.get("source", ""),
        "operating_status": business.get("operating_status", "unverified"),
        "page_title": business.get("page_title", ""),
        "meta_description": business.get("meta_description", ""),
    }, indent=2))

    (company_dir / "contact_info.json").write_text(json.dumps({
        "email": business.get("email", ""),
        "phone": business.get("phone", ""),
    }, indent=2))

    (company_dir / "outreach_email.txt").write_text(outreach_email)
    (company_dir / "notes.txt").write_text(
        f"discovered_at: {business.get('discovered_at', '')}\n"
        f"status: {business.get('status', 'new')}\n"
    )


def _emit(callback: ProgressCallback | None, event: ProgressEvent) -> None:
    if callback:
        callback(event)


def run_workflow(
    api_key: str | None,
    target_queries: Iterable[tuple[str, str]] = DEFAULT_TARGET_QUERIES,
    per_query_limit: int = 20,
    max_per_category: int = 15,
    do_enrich: bool = True,
    do_classify: bool = True,
    generate_outreach: bool = True,
    dry_run: bool = False,
    progress_callback: ProgressCallback | None = None,
    scraper=None,
) -> WorkflowResult:
    """Discover and process leads while isolating failures per query and lead."""
    if (do_classify or generate_outreach) and not api_key:
        raise ValueError("A Groq API key is required for classification or outreach generation.")
    if per_query_limit < 1 or max_per_category < 1:
        raise ValueError("Query and category limits must be at least 1.")

    queries = list(target_queries)
    result = WorkflowResult()
    existing_rows = store.load_all()
    names, domains, emails = store.build_index(existing_rows)
    scraper = scraper or OSMOverpassScraper()

    _emit(progress_callback, ProgressEvent(
        stage="ready",
        message=f"Loaded {len(existing_rows)} existing leads.",
        total=len(queries),
    ))

    for query_index, (query, location) in enumerate(queries, start=1):
        if result.category_counts.get(query, 0) >= max_per_category:
            _emit(progress_callback, ProgressEvent(
                stage="skip",
                message=f"Skipped {query} in {location}: category cap reached.",
                completed=query_index,
                total=len(queries),
            ))
            continue

        _emit(progress_callback, ProgressEvent(
            stage="discover",
            message=f"Discovering {query} in {location}.",
            completed=query_index - 1,
            total=len(queries),
        ))
        try:
            discovered = scraper.discover(query, location, limit=per_query_limit)
        except Exception as exc:
            error = f"{query} / {location}: {exc}"
            result.query_errors.append(error)
            result.failed += 1
            _emit(progress_callback, ProgressEvent(
                stage="error",
                message=f"Discovery failed: {error}",
                completed=query_index,
                total=len(queries),
                level="error",
            ))
            continue

        for business in discovered:
            if result.category_counts.get(query, 0) >= max_per_category:
                break

            company_name = business.get("company_name", "Unnamed business")
            if store.exists(business, names, domains, emails):
                result.duplicates += 1
                _emit(progress_callback, ProgressEvent(
                    stage="duplicate",
                    message=f"Skipped duplicate: {company_name}.",
                    completed=query_index,
                    total=len(queries),
                ))
                continue

            try:
                if do_enrich:
                    business = enrich(business)
                else:
                    business.setdefault("operating_status", "unverified")

                if business.get("operating_status") == "likely_closed":
                    result.closed += 1
                    _emit(progress_callback, ProgressEvent(
                        stage="closed",
                        message=f"Skipped likely closed business: {company_name}.",
                        completed=query_index,
                        total=len(queries),
                    ))
                    continue

                if do_classify:
                    business["industry"] = classify(api_key, business)
                else:
                    business["industry"] = business.get("industry") or "Other"

                business["discovered_at"] = datetime.now(timezone.utc).isoformat()
                business["status"] = "new"
                outreach_email = gen_outreach(api_key, business) if generate_outreach else ""
            except Exception as exc:
                error = f"{company_name}: {exc}"
                result.lead_errors.append(error)
                result.failed += 1
                _emit(progress_callback, ProgressEvent(
                    stage="error",
                    message=f"Lead processing failed: {error}",
                    completed=query_index,
                    total=len(queries),
                    level="error",
                ))
                continue

            store.index_business(business, names, domains, emails)
            result.category_counts[query] = result.category_counts.get(query, 0) + 1

            if dry_run:
                result.previewed += 1
                action = "Previewed"
            else:
                save_lead_package(business, outreach_email)
                store.append(business)
                result.added += 1
                action = "Added"

            _emit(progress_callback, ProgressEvent(
                stage="saved" if not dry_run else "preview",
                message=f"{action} {company_name} [{business['industry']}].",
                completed=query_index,
                total=len(queries),
            ))

    _emit(progress_callback, ProgressEvent(
        stage="complete",
        message=(
            f"Run complete: {result.added} added, {result.previewed} previewed, "
            f"{result.duplicates} duplicates, {result.closed} closed, "
            f"{result.failed} failed."
        ),
        completed=len(queries),
        total=len(queries),
        level="success" if not result.query_errors and not result.lead_errors else "warning",
    ))
    return result
