"""Module 4: Capital Allocation Engine.

Enforces risk-based position sizing, max position limits, minimum cash reserve,
and regime-aware deployment rules.

Produces a weekly capital deployment plan.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

from .config import AppConfig
from .health import PortfolioHealthResult
from .regime import RegimeResult
from .scanner import ScannerResult, Candidate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class AllocationPlan:
    """A single suggested allocation."""
    ticker: str
    action: str                  # "BUY" | "TRIM" | "EXIT"
    shares: int
    entry_price: float
    stop_price: float
    risk_per_share: float
    capital_required: float
    risk_amount: float           # dollar risk
    risk_pct_of_portfolio: float
    rationale: str


@dataclass
class AllocationResult:
    """Output of the Capital Allocation Engine."""
    # Portfolio summary
    total_portfolio_value: float
    invested_value: float
    cash_value: float
    cash_pct: float
    total_exposure_pct: float
    position_count: int
    max_positions: int

    # Sector concentration
    sector_concentration: Dict[str, float]  # sector -> % of portfolio

    # Plans
    trim_exit_plans: List[AllocationPlan]
    buy_plans: List[AllocationPlan]

    # Deployment guidance
    weekly_deployment_plan: str
    risk_notes: List[str]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def compute_allocation(
    config: AppConfig,
    regime: RegimeResult,
    health: PortfolioHealthResult,
    scanner: ScannerResult,
) -> AllocationResult:
    """Compute the capital allocation plan."""
    portfolio_value = config.portfolio.total_value
    max_positions = config.portfolio.max_positions
    min_cash_pct = config.portfolio.min_cash_pct
    max_risk_pct = config.portfolio.max_risk_per_trade_pct

    # ---- Current state ----
    invested = health.total_current_value
    cash = portfolio_value - invested
    cash_pct = (cash / portfolio_value * 100) if portfolio_value > 0 else 100
    exposure_pct = 100 - cash_pct
    current_positions = len([h for h in health.holdings if h.current_price > 0])

    # ---- Sector concentration ----
    sector_values: Dict[str, float] = {}
    for h in health.holdings:
        sector = h.macro_details.get("sector", "Unknown")
        sector_values[sector] = sector_values.get(sector, 0) + h.position_value
    sector_concentration = {
        s: round(v / portfolio_value * 100, 1)
        for s, v in sorted(sector_values.items(), key=lambda x: -x[1])
    }

    # ---- TRIM / EXIT plans from health module ----
    trim_exit_plans: List[AllocationPlan] = []
    freed_capital = 0.0

    for h in health.holdings:
        if h.decision == "EXIT":
            freed = h.position_value
            freed_capital += freed
            trim_exit_plans.append(AllocationPlan(
                ticker=h.ticker,
                action="EXIT",
                shares=int(h.shares),
                entry_price=h.current_price,
                stop_price=0,
                risk_per_share=0,
                capital_required=0,
                risk_amount=0,
                risk_pct_of_portfolio=0,
                rationale=h.explanation,
            ))
        elif h.decision == "TRIM 25%":
            trim_shares = max(1, int(h.shares * 0.25))
            freed = trim_shares * h.current_price
            freed_capital += freed
            trim_exit_plans.append(AllocationPlan(
                ticker=h.ticker,
                action="TRIM",
                shares=trim_shares,
                entry_price=h.current_price,
                stop_price=h.suggested_stop,
                risk_per_share=h.risk_per_share,
                capital_required=0,
                risk_amount=0,
                risk_pct_of_portfolio=0,
                rationale=h.explanation,
            ))

    # ---- BUY plans from scanner ----
    buy_plans: List[AllocationPlan] = []

    available_cash = cash + freed_capital
    min_cash_reserve = portfolio_value * (min_cash_pct / 100)
    deployable = max(0, available_cash - min_cash_reserve)

    # How many new positions can we add?
    exits = sum(1 for p in trim_exit_plans if p.action == "EXIT")
    open_slots = max(0, max_positions - current_positions + exits)

    risk_notes: List[str] = []

    # RISK_OFF: no new entries unless candidate score >= 90 (exceptional)
    if regime.classification == "RISK_OFF":
        risk_notes.append(
            "RISK_OFF regime: No new positions unless candidate score >= 90/100."
        )

    for candidate in scanner.candidates:
        if len(buy_plans) >= open_slots:
            break

        if deployable <= 0:
            break

        # RISK_OFF gate
        if regime.classification == "RISK_OFF" and candidate.composite_score < 90:
            continue

        # Position sizing: max 1% risk * regime multiplier
        max_risk_dollars = portfolio_value * (max_risk_pct / 100) * regime.multiplier
        risk_per_share = candidate.risk_per_share

        if risk_per_share <= 0:
            continue

        shares = int(max_risk_dollars / risk_per_share)
        if shares <= 0:
            continue

        capital_needed = shares * candidate.current_price
        if capital_needed > deployable:
            shares = int(deployable / candidate.current_price)
            capital_needed = shares * candidate.current_price

        if shares <= 0:
            continue

        actual_risk = shares * risk_per_share
        risk_pct = actual_risk / portfolio_value * 100

        buy_plans.append(AllocationPlan(
            ticker=candidate.ticker,
            action="BUY",
            shares=shares,
            entry_price=candidate.current_price,
            stop_price=candidate.suggested_stop,
            risk_per_share=round(risk_per_share, 2),
            capital_required=round(capital_needed, 2),
            risk_amount=round(actual_risk, 2),
            risk_pct_of_portfolio=round(risk_pct, 2),
            rationale=(
                f"Score {candidate.composite_score}/100. "
                f"{candidate.sector}. RSI {candidate.rsi}. "
                f"Entry zone ${candidate.entry_zone_low}-${candidate.entry_zone_high}."
            ),
        ))
        deployable -= capital_needed

    # ---- Risk notes ----
    if cash_pct < min_cash_pct:
        risk_notes.append(
            f"Cash ({cash_pct:.1f}%) is below the {min_cash_pct}% minimum. "
            f"Prioritize trimming weak positions before adding new ones."
        )

    for sector, pct in sector_concentration.items():
        if pct > 30:
            risk_notes.append(
                f"Sector concentration alert: {sector} at {pct:.1f}% of portfolio. "
                f"Consider diversifying."
            )

    if not risk_notes:
        risk_notes.append("No elevated risks detected. Portfolio is within guidelines.")

    # ---- Weekly deployment plan ----
    weekly_plan = _build_weekly_plan(
        regime, buy_plans, deployable + min_cash_reserve - (portfolio_value * min_cash_pct / 100),
        len(buy_plans),
    )

    return AllocationResult(
        total_portfolio_value=round(portfolio_value, 2),
        invested_value=round(invested, 2),
        cash_value=round(cash, 2),
        cash_pct=round(cash_pct, 1),
        total_exposure_pct=round(exposure_pct, 1),
        position_count=current_positions,
        max_positions=max_positions,
        sector_concentration=sector_concentration,
        trim_exit_plans=trim_exit_plans,
        buy_plans=buy_plans,
        weekly_deployment_plan=weekly_plan,
        risk_notes=risk_notes,
    )


def _build_weekly_plan(
    regime: RegimeResult,
    buy_plans: List[AllocationPlan],
    remaining_deployable: float,
    new_positions: int,
) -> str:
    """Generate a human-readable weekly deployment plan."""
    if regime.classification == "RISK_OFF":
        return (
            "RISK_OFF: Preserve capital. Do not initiate new positions unless "
            "an exceptional opportunity (score >= 90) appears. Focus on "
            "trimming underperformers and raising cash."
        )

    if not buy_plans:
        return (
            "No new opportunities meet all criteria this week. "
            "Maintain current positions and monitor for setups."
        )

    total_buy = sum(p.capital_required for p in buy_plans)
    tickers = ", ".join(p.ticker for p in buy_plans)

    if regime.classification == "RISK_ON":
        return (
            f"RISK_ON: Deploy up to ${total_buy:,.0f} across {new_positions} new "
            f"position(s): {tickers}. Consider scaling in over 2-3 days rather "
            f"than entering all at once. Use limit orders at the entry zone."
        )
    else:
        return (
            f"NEUTRAL: Selectively deploy up to ${total_buy:,.0f} across "
            f"{new_positions} position(s): {tickers}. Use 70% of normal size. "
            f"Scale in gradually over the week. Maintain higher cash reserves."
        )


