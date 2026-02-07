from __future__ import annotations

import argparse
import time

from .config import load_config, load_json, save_json
from .recommend import build_recommendations
from .portfolio import check_portfolio


def _recommend(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    result = build_recommendations(config)
    save_json(args.output, result)
    print(f"Saved {len(result['top_picks'])} recommendations to {args.output}")


def _monitor(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    portfolio = load_json(args.portfolio)

    def run_once() -> None:
        result = check_portfolio(config, portfolio)
        save_json(args.output, result)
        print(
            f"Portfolio change {result['pct_change']}% "
            f"(alerts: {len(result['alerts'])}) -> {args.output}"
        )

    if args.loop:
        while True:
            run_once()
            time.sleep(config.risk.check_interval_minutes * 60)
    else:
        run_once()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stock recommendation and portfolio monitoring tool."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    rec = subparsers.add_parser("recommend", help="Generate buy-score rankings.")
    rec.add_argument("--config", required=True, help="Path to config JSON.")
    rec.add_argument(
        "--output", required=True, help="Output JSON for recommendations."
    )
    rec.set_defaults(func=_recommend)

    mon = subparsers.add_parser("monitor", help="Check portfolio risk thresholds.")
    mon.add_argument("--config", required=True, help="Path to config JSON.")
    mon.add_argument("--portfolio", required=True, help="Path to portfolio JSON.")
    mon.add_argument("--output", required=True, help="Output JSON for alerts.")
    mon.add_argument(
        "--loop",
        action="store_true",
        help="Keep checking at configured interval.",
    )
    mon.set_defaults(func=_monitor)

    args = parser.parse_args()
    args.func(args)
