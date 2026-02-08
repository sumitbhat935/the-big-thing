"""Standalone daily report script for scheduled execution.

Usage:
    python scripts/daily_report.py --config config.json --output report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import os

# Ensure the src directory is on the path when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bigthing.config import load_config, save_json
from bigthing.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="BigThing v2 Daily Report")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--output", default="report.json", help="Output report path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

    logger = logging.getLogger("bigthing.daily_report")

    try:
        config = load_config(args.config)
        result = run_pipeline(config, send_email=True)
        save_json(args.output, result)
        logger.info("Report saved to %s", args.output)
    except ValueError as exc:
        logger.error("Data integrity check failed: %s", exc)
        logger.error("No report generated. Aborting.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
