#!/usr/bin/env python3
"""TEJAS Business Agent v4 — orchestrator.

Commands:
    python3 main.py savekey YOUR_GROQ_KEY
    python3 main.py test
    python3 main.py run
"""
import logging
import sys
from pathlib import Path

from config import save_key, load_key
from data import store
from workflow.service import DEFAULT_TARGET_QUERIES, run_workflow

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"

TARGET_QUERIES = DEFAULT_TARGET_QUERIES


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "agent.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run() -> None:
    setup_logging()
    log = logging.getLogger("agent")
    api_key = load_key()
    if not api_key:
        log.error("No Groq key found. Run: python3 main.py savekey YOUR_GROQ_KEY")
        sys.exit(1)

    def report(event) -> None:
        if event.level == "error":
            log.error(event.message)
        else:
            log.info(event.message)

    run_workflow(
        api_key=api_key,
        target_queries=TARGET_QUERIES,
        per_query_limit=20,
        max_per_category=15,
        progress_callback=report,
    )


def test() -> None:
    setup_logging()
    log = logging.getLogger("agent")
    api_key = load_key()
    log.info(f"Groq key present: {bool(api_key)}")
    places_key = load_key("GOOGLE_PLACES_KEY")
    log.info(f"Google Places key present: {bool(places_key)}")
    store.ensure_csv()
    log.info(f"CSV path: {store.CSV_PATH} (exists: {store.CSV_PATH.exists()})")
    OUTPUT_DIR.mkdir(exist_ok=True)
    log.info("Test OK. Environment ready.")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "savekey":
        if len(sys.argv) < 3:
            print("Usage: python3 main.py savekey YOUR_GROQ_KEY")
            sys.exit(1)
        save_key(sys.argv[2])
    elif cmd == "test":
        test()
    elif cmd == "run":
        run()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
