"""Configuration for BigThing v2 Portfolio Intelligence System.

All settings are config-driven. No magic numbers in code.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Holding (user input)
# ---------------------------------------------------------------------------

@dataclass
class Holding:
    """A single stock position in the portfolio."""
    ticker: str
    shares: float
    avg_cost: float


@dataclass
class ExternalHolding:
    """A non-equity holding tracked as notes only (no analytics)."""
    name: str
    quantity: float
    avg_cost: float
    notes: str = ""


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------

@dataclass
class PortfolioConfig:
    """Portfolio-level parameters."""
    total_value: float = 100_000.0
    max_positions: int = 12
    min_cash_pct: float = 10.0
    max_risk_per_trade_pct: float = 1.0
    holdings: List[Holding] = field(default_factory=list)


@dataclass
class UniverseConfig:
    """Which stocks to scan."""
    sources: List[str] = field(default_factory=lambda: ["sp500", "nasdaq100"])
    min_price: float = 10.0
    max_price: float = 10_000.0
    min_avg_volume: float = 1_000_000
    batch_size: int = 50


@dataclass
class RegimeConfig:
    """Market Regime Engine parameters."""
    spy_ticker: str = "SPY"
    vix_ticker: str = "^VIX"
    treasury_ticker: str = "^TNX"
    lookback_days: int = 250
    ma_long: int = 200
    ma_short: int = 50
    trend_window: int = 20
    vix_elevated_threshold: float = 25.0


@dataclass
class ScannerConfig:
    """Opportunity Scanner parameters."""
    rsi_min: float = 45.0
    rsi_max: float = 65.0
    rsi_period: int = 14
    volume_expansion_threshold: float = 1.2
    volume_lookback: int = 30
    earnings_blackout_days: int = 5
    top_n: int = 10
    # Composite score weights
    weight_trend: float = 0.30
    weight_fundamental: float = 0.25
    weight_relative_strength: float = 0.20
    weight_volume: float = 0.15
    weight_valuation: float = 0.10


@dataclass
class EmailConfig:
    """SMTP email settings."""
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""
    recipient_email: str = ""


@dataclass
class DataConfig:
    """Data integrity and retry settings."""
    min_data_coverage_pct: float = 80.0
    max_retries: int = 3
    retry_delay_seconds: float = 5.0
    daily_lookback_days: int = 300  # ~1 year of trading days


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    """Root configuration for BigThing v2."""
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    data: DataConfig = field(default_factory=DataConfig)
    external_holdings: List[ExternalHolding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str) -> AppConfig:
    """Load config from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Portfolio
    p = raw.get("portfolio", {})
    holdings = [
        Holding(
            ticker=str(h["ticker"]).upper(),
            shares=float(h["shares"]),
            avg_cost=float(h["avg_cost"]),
        )
        for h in p.get("holdings", [])
    ]
    portfolio = PortfolioConfig(
        total_value=float(p.get("total_value", 100_000)),
        max_positions=int(p.get("max_positions", 12)),
        min_cash_pct=float(p.get("min_cash_pct", 10)),
        max_risk_per_trade_pct=float(p.get("max_risk_per_trade_pct", 1.0)),
        holdings=holdings,
    )

    # Universe
    u = raw.get("universe", {})
    universe = UniverseConfig(
        sources=list(u.get("sources", ["sp500", "nasdaq100"])),
        min_price=float(u.get("min_price", 10)),
        max_price=float(u.get("max_price", 10_000)),
        min_avg_volume=float(u.get("min_avg_volume", 1_000_000)),
        batch_size=int(u.get("batch_size", 50)),
    )

    # Regime
    r = raw.get("regime", {})
    regime = RegimeConfig(
        spy_ticker=str(r.get("spy_ticker", "SPY")),
        vix_ticker=str(r.get("vix_ticker", "^VIX")),
        treasury_ticker=str(r.get("treasury_ticker", "^TNX")),
        lookback_days=int(r.get("lookback_days", 250)),
        ma_long=int(r.get("ma_long", 200)),
        ma_short=int(r.get("ma_short", 50)),
        trend_window=int(r.get("trend_window", 20)),
        vix_elevated_threshold=float(r.get("vix_elevated_threshold", 25)),
    )

    # Scanner
    s = raw.get("scanner", {})
    scanner = ScannerConfig(
        rsi_min=float(s.get("rsi_min", 45)),
        rsi_max=float(s.get("rsi_max", 65)),
        rsi_period=int(s.get("rsi_period", 14)),
        volume_expansion_threshold=float(s.get("volume_expansion_threshold", 1.2)),
        volume_lookback=int(s.get("volume_lookback", 30)),
        earnings_blackout_days=int(s.get("earnings_blackout_days", 5)),
        top_n=int(s.get("top_n", 10)),
        weight_trend=float(s.get("weight_trend", 0.30)),
        weight_fundamental=float(s.get("weight_fundamental", 0.25)),
        weight_relative_strength=float(s.get("weight_relative_strength", 0.20)),
        weight_volume=float(s.get("weight_volume", 0.15)),
        weight_valuation=float(s.get("weight_valuation", 0.10)),
    )

    # Email
    e = raw.get("email", {})
    email = EmailConfig(
        enabled=bool(e.get("enabled", False)),
        smtp_server=str(e.get("smtp_server", "smtp.gmail.com")),
        smtp_port=int(e.get("smtp_port", 587)),
        sender_email=str(e.get("sender_email", "")),
        sender_password=str(e.get("sender_password", "")),
        recipient_email=str(e.get("recipient_email", "")),
    )

    # Data
    d = raw.get("data", {})
    data = DataConfig(
        min_data_coverage_pct=float(d.get("min_data_coverage_pct", 80)),
        max_retries=int(d.get("max_retries", 3)),
        retry_delay_seconds=float(d.get("retry_delay_seconds", 5)),
        daily_lookback_days=int(d.get("daily_lookback_days", 300)),
    )

    # External holdings (notes-only)
    ext = raw.get("external_holdings", [])
    external_holdings = [
        ExternalHolding(
            name=str(h.get("name", "")).strip(),
            quantity=float(h.get("quantity", 0)),
            avg_cost=float(h.get("avg_cost", 0)),
            notes=str(h.get("notes", "")),
        )
        for h in ext
    ]

    return AppConfig(
        portfolio=portfolio,
        universe=universe,
        regime=regime,
        scanner=scanner,
        email=email,
        data=data,
        external_holdings=external_holdings,
    )


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
