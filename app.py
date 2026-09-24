from pathlib import Path
import json
import shutil

import pandas as pd
import streamlit as st

from config import load_key
from data import store
from generators.outreach_generator import generate as gen_outreach
from ui.formatting import display, lead_key, load_outreach, location, output_dir
from workflow.service import DEFAULT_TARGET_QUERIES, ProgressEvent, run_workflow

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="TEJAS Lead Workspace",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --ink: #17231f; --muted: #65716b; --line: #dce5df; --accent: #176b52; --accent-soft: #e6f2ec; }
    .stApp { background: #f7faf8; color: var(--ink); }
    [data-testid="stSidebar"] { background: #eef5f0; border-right: 1px solid var(--line); }
    [data-testid="stMetric"] { background: white; border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); }
    .eyebrow { color: var(--accent); font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: .35rem; }
    .subtle { color: var(--muted); }
    .detail-panel { background: white; border: 1px solid var(--line); border-radius: 10px; padding: 1.15rem 1.25rem; }
    .detail-label { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
    .detail-value { color: var(--ink); font-size: 1rem; margin-bottom: .85rem; overflow-wrap: anywhere; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_api_key() -> str | None:
    try:
        secret = st.secrets.get("GROQ_API_KEY")
    except Exception:
        secret = None
    return secret or load_key()


def load_rows() -> list[dict]:
    if not store.CSV_PATH.exists():
        demo_path = ROOT / "data" / "demo_businesses.csv"
        if demo_path.exists():
            store.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(demo_path, store.CSV_PATH)
    return store.load_all()


def write_outreach(row: dict, content: str) -> None:
    target = output_dir(row) / "outreach_email.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def read_package_info(row: dict) -> dict:
    path = output_dir(row) / "company_info.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def render_run_controls() -> None:
    st.sidebar.markdown("## Run discovery")
    st.sidebar.caption("Find, enrich, classify, and prepare new leads.")

    target_options = list(dict.fromkeys(DEFAULT_TARGET_QUERIES))
    selected_targets = st.sidebar.multiselect(
        "Target searches",
        target_options,
        default=target_options[:2],
        format_func=lambda target: f"{target[0]} · {target[1]}",
    )
    with st.sidebar.expander("Add a custom target"):
        custom_query = st.text_input("Business category", key="custom_query")
        custom_location = st.text_input("City or region", key="custom_location")

    per_query_limit = st.sidebar.number_input("Results per search", min_value=1, max_value=50, value=10)
    max_per_category = st.sidebar.number_input("Maximum leads per category", min_value=1, max_value=100, value=15)
    do_enrich = st.sidebar.checkbox("Check websites for contacts", value=True)
    do_classify = st.sidebar.checkbox("Classify industries with Groq", value=True)
    generate_outreach = st.sidebar.checkbox("Generate outreach emails", value=True)
    dry_run = st.sidebar.checkbox("Preview only, do not save", value=False)

    api_key_ready = bool(get_api_key())
    if api_key_ready:
        st.sidebar.success("Groq key ready")
    else:
        st.sidebar.warning("Groq key missing")
        st.sidebar.caption("Add GROQ_API_KEY in Community Cloud Secrets to classify or generate emails.")

    st.sidebar.info("Community Cloud storage is ephemeral. Commit durable data to a database or export it before redeploying.")

    if st.sidebar.button("Discover and process", type="primary", use_container_width=True):
        targets = list(selected_targets)
        if custom_query.strip() and custom_location.strip():
            targets.append((custom_query.strip(), custom_location.strip()))
        if not targets:
            st.sidebar.error("Choose at least one target search.")
            return
        if (do_classify or generate_outreach) and not api_key_ready:
            st.sidebar.error("Add GROQ_API_KEY before using Groq steps.")
            return

        progress_slot = st.empty()
        status_slot = st.empty()
        events: list[str] = []
        progress_slot.progress(0, text="Starting discovery")

        def on_event(event: ProgressEvent) -> None:
            events.append(event.message)
            if event.total:
                progress_slot.progress(
                    min(event.completed / event.total, 1.0),
                    text=event.message,
                )
            if event.level == "error":
                status_slot.error(event.message)
            elif event.level == "success":
                status_slot.success(event.message)
            elif event.level == "warning":
                status_slot.warning(event.message)
            else:
                status_slot.info(event.message)

        try:
            result = run_workflow(
                api_key=get_api_key(),
                target_queries=targets,
                per_query_limit=int(per_query_limit),
                max_per_category=int(max_per_category),
                do_enrich=do_enrich,
                do_classify=do_classify,
                generate_outreach=generate_outreach,
                dry_run=dry_run,
                progress_callback=on_event,
            )
        except Exception as exc:
            st.sidebar.error(str(exc))
            return

        st.session_state["last_run_result"] = result
        st.session_state["run_events"] = events
        st.rerun()


def apply_filters(rows: list[dict]) -> list[dict]:
    industries = sorted({row.get("industry", "") for row in rows if row.get("industry")})
    locations = sorted({location(row) for row in rows if location(row)})
    statuses = sorted({row.get("status", "") for row in rows if row.get("status")})

    with st.form("lead_filters"):
        st.markdown("#### Filter leads")
        first, second, third, fourth = st.columns([2, 1, 1, 1])
        with first:
            search = st.text_input("Search", placeholder="Company, email, website, or phone", key="filter_search_input")
        with second:
            industry = st.multiselect("Industry", industries, key="filter_industry_input")
        with third:
            selected_locations = st.multiselect("Location", locations, key="filter_location_input")
        with fourth:
            status = st.multiselect("Status", statuses, key="filter_status_input")
        fifth, sixth, seventh = st.columns([1, 1, 1])
        with fifth:
            has_email = st.checkbox("Has email", key="filter_email_input")
        with sixth:
            has_website = st.checkbox("Has website", key="filter_website_input")
        with seventh:
            submitted = st.form_submit_button("Apply filters", use_container_width=True)

    filters = {
        "search": st.session_state.get("filter_search_input", ""),
        "industry": st.session_state.get("filter_industry_input", []),
        "location": st.session_state.get("filter_location_input", []),
        "status": st.session_state.get("filter_status_input", []),
        "has_email": st.session_state.get("filter_email_input", False),
        "has_website": st.session_state.get("filter_website_input", False),
    }
    if submitted:
        st.session_state["filters_applied"] = True

    filtered = []
    for row in rows:
        haystack = " ".join(row.get(field, "") for field in ("company_name", "email", "website", "phone")).lower()
        if filters["search"].strip().lower() not in haystack:
            continue
        if filters["industry"] and row.get("industry") not in filters["industry"]:
            continue
        if filters["location"] and location(row) not in filters["location"]:
            continue
        if filters["status"] and row.get("status") not in filters["status"]:
            continue
        if filters["has_email"] and not row.get("email", "").strip():
            continue
        if filters["has_website"] and not row.get("website", "").strip():
            continue
        filtered.append(row)
    return filtered


def render_run_summary() -> None:
    result = st.session_state.get("last_run_result")
    if not result:
        return
    st.markdown("#### Latest run")
    cols = st.columns(5)
    cols[0].metric("Added", result.added)
    cols[1].metric("Previewed", result.previewed)
    cols[2].metric("Duplicates", result.duplicates)
    cols[3].metric("Closed", result.closed)
    cols[4].metric("Failed", result.failed)
    errors = result.query_errors + result.lead_errors
    if errors:
        with st.expander(f"{len(errors)} run issue(s)"):
            for error in errors:
                st.write(f"- {error}")


def render_lead_detail(row: dict) -> None:
    selected_key = lead_key(row)
    if st.session_state.get("selected_lead_key") != selected_key:
        st.session_state["selected_lead_key"] = selected_key
        st.session_state["draft_email"] = load_outreach(row)

    package = read_package_info(row)
    st.markdown("#### Lead inspector")
    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
        st.markdown(f"### {display(row.get('company_name'))}")
        st.markdown(f'<div class="detail-label">Industry</div><div class="detail-value">{display(row.get("industry"))}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-label">Location</div><div class="detail-value">{display(location(row))}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-label">Email</div><div class="detail-value">{display(row.get("email"))}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="detail-label">Phone</div><div class="detail-value">{display(row.get("phone"))}</div>', unsafe_allow_html=True)
        if row.get("website"):
            st.link_button("Open website", row["website"], use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        status_options = ["new", "contacted", "qualified", "converted", "archived"]
        current_status = row.get("status") or "new"
        status_index = status_options.index(current_status) if current_status in status_options else 0
        new_status = st.selectbox("Lead status", status_options, index=status_index, key="selected_status")
        if st.button("Save status", use_container_width=True):
            if store.update_row(selected_key, {"status": new_status}):
                st.success("Status saved.")
                st.rerun()
            st.error("Lead could not be found in the CSV.")

    with right:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
        st.markdown("### Outreach email")
        if package.get("meta_description"):
            st.caption(package["meta_description"])
        draft = st.text_area("Email content", key="draft_email", height=260, label_visibility="collapsed")
        action_left, action_right = st.columns(2)
        with action_left:
            if st.button("Save email", use_container_width=True):
                write_outreach(row, draft)
                st.success("Email saved to the lead package.")
        with action_right:
            if st.button("Generate email", use_container_width=True):
                api_key = get_api_key()
                if not api_key:
                    st.error("Add GROQ_API_KEY before generating email.")
                else:
                    lead_for_email = {**row, **package}
                    lead_for_email["industry"] = row.get("industry", package.get("industry", ""))
                    st.session_state["draft_email"] = gen_outreach(api_key, lead_for_email)
                    st.rerun()
        st.download_button(
            "Download email",
            data=draft,
            file_name=f"{output_dir(row).name or 'lead'}-outreach.txt",
            mime="text/plain",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        metadata = {key: value for key, value in package.items() if key in ("operating_status", "page_title") and value}
        if metadata:
            with st.expander("Enrichment details"):
                for key, value in metadata.items():
                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")


def render_dashboard() -> None:
    rows = load_rows()
    filtered = apply_filters(rows)

    total = len(rows)
    new_count = sum(row.get("status") == "new" for row in rows)
    email_count = sum(bool(row.get("email", "").strip()) for row in rows)
    st.markdown('<div class="eyebrow">Streamlit-hosted workspace</div>', unsafe_allow_html=True)
    st.title("TEJAS lead workspace")
    st.markdown("Discover local businesses, turn them into structured leads, and prepare the next outreach action.")
    metrics = st.columns(4)
    metrics[0].metric("Total leads", total)
    metrics[1].metric("New leads", new_count)
    metrics[2].metric("With email", email_count)
    metrics[3].metric("Matching filters", len(filtered))

    render_run_summary()

    if not filtered:
        st.info("No leads match these filters. Clear a filter or run a new discovery search.")
        return

    industry_counts = pd.Series([row.get("industry") or "Unknown" for row in filtered]).value_counts().rename("Leads")
    with st.expander("Industry mix", expanded=False):
        st.bar_chart(industry_counts)

    display_rows = []
    for row in filtered:
        display_rows.append({
            "Company": row.get("company_name", ""),
            "Industry": row.get("industry", ""),
            "Location": location(row),
            "Email": row.get("email", ""),
            "Website": row.get("website", ""),
            "Status": row.get("status", ""),
            "Source": row.get("source", ""),
            "Discovered": row.get("discovered_at", "")[:10],
        })
    st.markdown("#### Lead table")
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

    row_by_key = {lead_key(row): row for row in filtered}
    selected_options = list(row_by_key)
    current_key = st.session_state.get("selected_lead_key")
    selected_index = selected_options.index(current_key) if current_key in selected_options else 0
    selected_key = st.selectbox(
        "Inspect a lead",
        selected_options,
        index=selected_index,
        format_func=lambda key: f"{row_by_key[key].get('company_name', 'Unnamed')} · {location(row_by_key[key]) or 'Location unknown'}",
    )
    render_lead_detail(row_by_key[selected_key])


render_run_controls()
render_dashboard()
