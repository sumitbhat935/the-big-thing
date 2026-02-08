"""Main orchestration pipeline for BigThing v2.

Runs all 4 modules in sequence:
  1. Market Regime Engine
  2. Portfolio Health Engine
  3. Opportunity Scanner
  4. Capital Allocation Engine

Then optionally sends the daily email report.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .config import AppConfig
from .data_provider import DataProvider
from .universe import build_universe, PreFilterConfig
from .regime import analyze_regime, RegimeResult
from .health import analyze_portfolio_health, PortfolioHealthResult
from .scanner import scan_opportunities, ScannerResult
from .allocator import compute_allocation, AllocationResult
from .emailer import send_report

logger = logging.getLogger(__name__)


def run_pipeline(config: AppConfig, send_email: bool = True) -> Dict[str, Any]:
    """Execute the full daily pipeline and return a summary dict."""

    # ================================================================
    # Step 1: Market Regime
    # ================================================================
    logger.info("=" * 60)
    logger.info("STEP 1: Market Regime Engine")
    logger.info("=" * 60)

    regime = analyze_regime(config.regime, config.data)
    logger.info("Regime: %s (multiplier: %.1fx)", regime.classification, regime.multiplier)

    # ================================================================
    # Step 2: Build dynamic universe + fetch data
    # ================================================================
    logger.info("=" * 60)
    logger.info("STEP 2: Building universe and fetching data")
    logger.info("=" * 60)

    # Determine all tickers we need
    pf = PreFilterConfig(
        min_price=config.universe.min_price,
        max_price=config.universe.max_price,
        min_avg_volume=config.universe.min_avg_volume,
        sources=config.universe.sources,
    )
    universe_tickers = build_universe(pf)
    logger.info("Universe: %d tickers after pre-filter", len(universe_tickers))

    # Also include current holdings + regime tickers
    holding_tickers = [h.ticker for h in config.portfolio.holdings]
    all_tickers = sorted(set(
        universe_tickers
        + holding_tickers
        + [config.regime.spy_ticker]
    ))

    provider = DataProvider(config=config.data, batch_size=config.universe.batch_size)
    market_data = provider.fetch_all(
        tickers=all_tickers,
        lookback_days=config.data.daily_lookback_days,
        fetch_fundamentals=True,
    )

    # ================================================================
    # Step 3: Portfolio Health
    # ================================================================
    logger.info("=" * 60)
    logger.info("STEP 3: Portfolio Health Engine")
    logger.info("=" * 60)

    health = analyze_portfolio_health(config, market_data, regime)
    logger.info(
        "Portfolio: %d holdings, P&L: %+.1f%%, actions: %d",
        len(health.holdings), health.total_pnl_pct, len(health.actions_required),
    )

    # ================================================================
    # Step 4: Opportunity Scanner
    # ================================================================
    logger.info("=" * 60)
    logger.info("STEP 4: Opportunity Scanner")
    logger.info("=" * 60)

    scanner = scan_opportunities(config, market_data, regime)
    logger.info(
        "Scanner: %d passed filters, top %d candidates",
        scanner.passed_filter, len(scanner.candidates),
    )

    # ================================================================
    # Step 5: Capital Allocation
    # ================================================================
    logger.info("=" * 60)
    logger.info("STEP 5: Capital Allocation Engine")
    logger.info("=" * 60)

    allocation = compute_allocation(config, regime, health, scanner)
    logger.info(
        "Allocation: %d buys, %d trims/exits, cash %.1f%%",
        len(allocation.buy_plans),
        len(allocation.trim_exit_plans),
        allocation.cash_pct,
    )

    # ================================================================
    # Step 6: Email
    # ================================================================
    if send_email:
        logger.info("=" * 60)
        logger.info("STEP 6: Sending email report")
        logger.info("=" * 60)
        send_report(config.email, regime, health, scanner, allocation, config.external_holdings)

    # ================================================================
    # Build summary
    # ================================================================
    summary = {
        "regime": {
            "classification": regime.classification,
            "multiplier": regime.multiplier,
            "explanation": regime.explanation,
            "signals": regime.signals,
        },
        "external_holdings": [
            {
                "name": h.name,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "notes": h.notes,
            }
            for h in config.external_holdings
        ],
        "portfolio_health": {
            "total_invested": health.total_invested,
            "total_current_value": health.total_current_value,
            "total_pnl_pct": health.total_pnl_pct,
            "actions_required": health.actions_required,
            "holdings": [
                {
                    "ticker": h.ticker,
                    "price": h.current_price,
                    "pnl_pct": h.unrealized_pnl_pct,
                    "score": h.total_score,
                    "decision": h.decision,
                    "stop": h.suggested_stop,
                }
                for h in health.holdings
            ],
        },
        "opportunities": [
            {
                "ticker": c.ticker,
                "sector": c.sector,
                "price": c.current_price,
                "score": c.composite_score,
                "entry_zone": [c.entry_zone_low, c.entry_zone_high],
                "stop": c.suggested_stop,
                "shares": c.position_size_shares,
                "capital": c.capital_required,
                "bull": c.bull_scenario,
                "base": c.base_scenario,
                "bear": c.bear_scenario,
                "outlook": c.six_month_outlook,
            }
            for c in scanner.candidates
        ],
        "allocation": {
            "portfolio_value": allocation.total_portfolio_value,
            "cash_pct": allocation.cash_pct,
            "exposure_pct": allocation.total_exposure_pct,
            "positions": allocation.position_count,
            "sector_concentration": allocation.sector_concentration,
            "weekly_plan": allocation.weekly_deployment_plan,
            "risk_notes": allocation.risk_notes,
        },
    }

    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info("=" * 60)

    return summary
