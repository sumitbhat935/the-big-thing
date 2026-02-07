from __future__ import annotations

from typing import Dict, List

from .config import AppConfig
from .data_provider import YahooProvider


def _portfolio_value(holdings: List[Dict[str, float]], prices: Dict[str, float], cash: float) -> float:
    total = float(cash)
    for h in holdings:
        ticker = h["ticker"]
        shares = float(h["shares"])
        price = float(prices.get(ticker, h.get("entry_price", 0.0)))
        total += shares * price
    return total


def _portfolio_cost(holdings: List[Dict[str, float]], cash: float) -> float:
    total = float(cash)
    for h in holdings:
        shares = float(h["shares"])
        entry = float(h.get("entry_price", 0.0))
        total += shares * entry
    return total


def check_portfolio(
    config: AppConfig,
    portfolio: Dict[str, object],
) -> Dict[str, object]:
    holdings = list(portfolio.get("holdings", []))
    cash = float(portfolio.get("cash", 0.0))

    tickers = [h["ticker"] for h in holdings]
    provider = YahooProvider()
    prices = provider.get_latest_prices(tickers)

    current_value = _portfolio_value(holdings, prices, cash)
    cost_value = _portfolio_cost(holdings, cash)
    pct_change = 0.0 if cost_value == 0 else (current_value - cost_value) / cost_value * 100

    alerts = []
    if pct_change <= config.risk.portfolio_stop_loss_pct:
        alerts.append(
            {
                "type": "stop_loss",
                "message": "Portfolio reached stop-loss threshold.",
                "pct_change": round(pct_change, 2),
            }
        )
    if pct_change >= config.risk.take_profit_pct:
        alerts.append(
            {
                "type": "take_profit",
                "message": "Portfolio reached take-profit threshold.",
                "pct_change": round(pct_change, 2),
            }
        )

    return {
        "portfolio_value": round(current_value, 2),
        "portfolio_cost": round(cost_value, 2),
        "pct_change": round(pct_change, 2),
        "prices": prices,
        "alerts": alerts,
    }
