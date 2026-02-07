import json
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class RiskConfig:
    portfolio_stop_loss_pct: float
    take_profit_pct: float
    check_interval_minutes: int


@dataclass
class AppConfig:
    tickers: List[str]
    morning_minutes: int
    interval: str
    period: str
    top_n: int
    weights: Dict[str, float]
    factor_directions: Dict[str, str]
    risk: RiskConfig


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    risk_raw = raw.get("risk", {})
    risk = RiskConfig(
        portfolio_stop_loss_pct=float(risk_raw.get("portfolio_stop_loss_pct", -0.5)),
        take_profit_pct=float(risk_raw.get("take_profit_pct", 3.0)),
        check_interval_minutes=int(risk_raw.get("check_interval_minutes", 15)),
    )

    return AppConfig(
        tickers=list(raw.get("tickers", [])),
        morning_minutes=int(raw.get("morning_minutes", 90)),
        interval=str(raw.get("interval", "5m")),
        period=str(raw.get("period", "10d")),
        top_n=int(raw.get("top_n", 15)),
        weights=dict(raw.get("weights", {})),
        factor_directions=dict(raw.get("factor_directions", {})),
        risk=risk,
    )


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
