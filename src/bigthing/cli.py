"""CLI entry point for BigThing v2 Portfolio Intelligence System."""
from __future__ import annotations

import argparse
import logging

from .config import load_config, save_json
from .pipeline import run_pipeline


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


def _run(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose)
    config = load_config(args.config)
    result = run_pipeline(config, send_email=not args.no_email)
    if args.output:
        save_json(args.output, result)
        print(f"Report saved to {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BigThing v2 — Daily Portfolio Intelligence System"
    )
    parser.add_argument("--config", required=True, help="Path to config JSON.")
    parser.add_argument("--output", help="Optional: save report JSON to this path.")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    parser.set_defaults(func=_run)

    args = parser.parse_args()
    args.func(args)
