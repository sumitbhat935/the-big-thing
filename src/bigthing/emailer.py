"""Professional daily portfolio intelligence email report.

Generates a structured HTML email covering all 4 modules:
regime, portfolio health, opportunities, and capital allocation.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

from .config import EmailConfig, ExternalHolding
from .regime import RegimeResult
from .health import PortfolioHealthResult
from .scanner import ScannerResult
from .allocator import AllocationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
_GREEN = "#16a34a"
_AMBER = "#ca8a04"
_RED = "#dc2626"
_BLUE = "#2563eb"
_GRAY = "#64748b"


def _regime_color(regime: str) -> str:
    if regime == "RISK_ON":
        return _GREEN
    elif regime == "RISK_OFF":
        return _RED
    return _AMBER


def _decision_color(decision: str) -> str:
    if "STRONG" in decision:
        return _GREEN
    elif "HOLD" == decision:
        return _BLUE
    elif "TRIM" in decision:
        return _AMBER
    return _RED


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_report_html(
    regime: RegimeResult,
    health: PortfolioHealthResult,
    scanner: ScannerResult,
    allocation: AllocationResult,
    external_holdings: List[ExternalHolding],
) -> str:
    """Build the full HTML email report."""
    now = datetime.now().strftime("%B %d, %Y")

    sections = [
        _section_regime(regime),
        _section_portfolio_health(health),
        _section_external_holdings(external_holdings),
        _section_actions(allocation),
        _section_opportunities(scanner),
        _section_capital(allocation),
        _section_risk_notes(allocation),
    ]

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 16px; background: #f8fafc; color: #1e293b;">

  <div style="background: linear-gradient(135deg, #0f172a, #1e3a5f); color: white; padding: 28px 32px; border-radius: 12px 12px 0 0;">
    <h1 style="margin: 0 0 4px 0; font-size: 22px; letter-spacing: -0.5px;">BigThing Daily Portfolio Intelligence</h1>
    <p style="margin: 0; opacity: 0.8; font-size: 13px;">{now} &bull; After-market analysis</p>
  </div>

  <div style="background: white; padding: 28px 32px; border-radius: 0 0 12px 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
    {''.join(sections)}
    <p style="margin-top: 32px; font-size: 10px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 16px;">
      This report is for informational purposes only and does not constitute financial advice.
      Past performance does not guarantee future results. All investing involves risk of loss.
    </p>
  </div>
</body></html>"""


def _section_regime(r: RegimeResult) -> str:
    color = _regime_color(r.classification)
    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 0;">
      1. Market Regime
    </h2>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
      <span style="background: {color}; color: white; padding: 6px 16px; border-radius: 6px; font-weight: bold; font-size: 14px;">
        {r.classification}
      </span>
      <span style="color: {_GRAY}; font-size: 13px;">
        Position size multiplier: <b>{r.multiplier}x</b>
      </span>
    </div>
    <p style="font-size: 13px; line-height: 1.6; color: #334155;">{r.explanation}</p>
    <table style="width: 100%; font-size: 12px; border-collapse: collapse; margin-bottom: 8px;">
      <tr style="background: #f8fafc;">
        <td style="padding: 6px 10px;"><b>SPY</b></td>
        <td style="padding: 6px 10px;">${r.spy_price:.2f}</td>
        <td style="padding: 6px 10px;">200 MA: ${r.spy_200ma:.2f}</td>
        <td style="padding: 6px 10px;">50 MA: ${r.spy_50ma:.2f}</td>
      </tr>
      <tr>
        <td style="padding: 6px 10px;"><b>VIX</b></td>
        <td style="padding: 6px 10px;">{r.vix_level:.1f}</td>
        <td style="padding: 6px 10px;"><b>10Y Yield</b></td>
        <td style="padding: 6px 10px;">{r.treasury_yield:.2f}%</td>
      </tr>
    </table>"""


def _section_portfolio_health(h: PortfolioHealthResult) -> str:
    if not h.holdings:
        return """
        <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          2. Portfolio Health
        </h2>
        <p style="font-size: 13px; color: #64748b;">No holdings configured.</p>"""

    rows = ""
    for hh in h.holdings:
        color = _decision_color(hh.decision)
        rows += f"""<tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 8px; font-weight: bold;">{hh.ticker}</td>
          <td style="padding: 8px;">${hh.current_price:.2f}</td>
          <td style="padding: 8px; color: {'green' if hh.unrealized_pnl_pct >= 0 else 'red'};">{hh.unrealized_pnl_pct:+.1f}%</td>
          <td style="padding: 8px; text-align: center;">{hh.trend_score}</td>
          <td style="padding: 8px; text-align: center;">{hh.fundamental_score}</td>
          <td style="padding: 8px; text-align: center;">{hh.relative_strength_score}</td>
          <td style="padding: 8px; text-align: center;">{hh.macro_alignment_score}</td>
          <td style="padding: 8px; text-align: center; font-weight: bold;">{hh.total_score}</td>
          <td style="padding: 8px;"><span style="color: {color}; font-weight: bold;">{hh.decision}</span></td>
          <td style="padding: 8px;">${hh.suggested_stop:.2f}</td>
        </tr>"""

    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      2. Portfolio Health
    </h2>
    <p style="font-size: 13px; color: #334155;">
      Invested: <b>${h.total_current_value:,.0f}</b> &bull;
      P&L: <b style="color: {'green' if h.total_pnl_pct >= 0 else 'red'};">{h.total_pnl_pct:+.1f}%</b>
    </p>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
      <thead>
        <tr style="background: #f1f5f9; text-align: left;">
          <th style="padding: 8px;">Ticker</th>
          <th style="padding: 8px;">Price</th>
          <th style="padding: 8px;">P&L</th>
          <th style="padding: 8px; text-align: center;">Trend</th>
          <th style="padding: 8px; text-align: center;">Fund</th>
          <th style="padding: 8px; text-align: center;">RS</th>
          <th style="padding: 8px; text-align: center;">Macro</th>
          <th style="padding: 8px; text-align: center;">Total</th>
          <th style="padding: 8px;">Decision</th>
          <th style="padding: 8px;">Stop</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _section_actions(a: AllocationResult) -> str:
    items = ""
    all_plans = a.trim_exit_plans + a.buy_plans
    if not all_plans:
        return """
        <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          4. Actions Required
        </h2>
        <p style="font-size: 13px; color: #64748b;">No actions required today. Maintain current positions.</p>"""

    for p in all_plans:
        color = _RED if p.action == "EXIT" else (_AMBER if p.action == "TRIM" else _GREEN)
        items += f"""<li style="margin-bottom: 8px;">
          <span style="color: {color}; font-weight: bold;">{p.action}</span>
          <b>{p.ticker}</b> ({p.shares} shares)
          {f'&mdash; Stop: ${p.stop_price:.2f}' if p.action == 'BUY' else ''}
          {f'&mdash; Capital: ${p.capital_required:,.0f}' if p.action == 'BUY' else ''}
          <br><span style="color: #64748b; font-size: 11px;">{p.rationale}</span>
        </li>"""

    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      4. Actions Required
    </h2>
    <ul style="font-size: 13px; line-height: 1.6; padding-left: 20px;">{items}</ul>"""


def _section_external_holdings(externals: List[ExternalHolding]) -> str:
    if not externals:
        return ""

    rows = ""
    for h in externals:
        notes = f"<br><span style='color: #64748b; font-size: 11px;'>{h.notes}</span>" if h.notes else ""
        rows += (
            f"<tr style=\"border-bottom: 1px solid #f1f5f9;\">"
            f"<td style=\"padding: 8px; font-weight: bold;\">{h.name}</td>"
            f"<td style=\"padding: 8px;\">{h.quantity}</td>"
            f"<td style=\"padding: 8px;\">${h.avg_cost:,.2f}</td>"
            f"<td style=\"padding: 8px;\">Notes-only (no analytics){notes}</td>"
            f"</tr>"
        )

    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      3. External Holdings (Notes)
    </h2>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 8px;">
      <thead>
        <tr style="background: #f1f5f9; text-align: left;">
          <th style="padding: 8px;">Asset</th>
          <th style="padding: 8px;">Quantity</th>
          <th style="padding: 8px;">Avg Cost</th>
          <th style="padding: 8px;">Notes</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _section_opportunities(s: ScannerResult) -> str:
    if not s.candidates:
        return """
        <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          5. New Opportunities
        </h2>
        <p style="font-size: 13px; color: #64748b;">
          No candidates meet all criteria today. Scanned {0} stocks.
        </p>""".format(s.universe_scanned)

    rows = ""
    for i, c in enumerate(s.candidates[:10], 1):
        rows += f"""<tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 8px; font-weight: bold;">{i}</td>
          <td style="padding: 8px; font-weight: bold;">{c.ticker}</td>
          <td style="padding: 8px;">{c.sector}</td>
          <td style="padding: 8px;">${c.current_price:.2f}</td>
          <td style="padding: 8px; font-weight: bold; color: {_GREEN if c.composite_score >= 60 else _AMBER};">{c.composite_score:.0f}</td>
          <td style="padding: 8px;">${c.entry_zone_low:.2f} - ${c.entry_zone_high:.2f}</td>
          <td style="padding: 8px;">${c.suggested_stop:.2f}</td>
          <td style="padding: 8px;">{c.position_size_shares}</td>
          <td style="padding: 8px;">${c.capital_required:,.0f}</td>
        </tr>"""

    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      5. New Opportunities
    </h2>
    <p style="font-size: 12px; color: #64748b;">
      {s.universe_scanned} stocks scanned &bull; {s.passed_filter} passed filters &bull; Top {len(s.candidates)} shown
    </p>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
      <thead>
        <tr style="background: #f1f5f9; text-align: left;">
          <th style="padding: 8px;">#</th>
          <th style="padding: 8px;">Ticker</th>
          <th style="padding: 8px;">Sector</th>
          <th style="padding: 8px;">Price</th>
          <th style="padding: 8px;">Score</th>
          <th style="padding: 8px;">Entry Zone</th>
          <th style="padding: 8px;">Stop</th>
          <th style="padding: 8px;">Shares</th>
          <th style="padding: 8px;">Capital</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def _section_capital(a: AllocationResult) -> str:
    sector_rows = ""
    for sector, pct in list(a.sector_concentration.items())[:8]:
        sector_rows += f"<tr><td style='padding: 4px 8px;'>{sector}</td><td style='padding: 4px 8px;'>{pct:.1f}%</td></tr>"

    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      6. Capital Deployment
    </h2>
    <table style="font-size: 13px; border-collapse: collapse; margin-bottom: 12px;">
      <tr><td style="padding: 4px 16px 4px 0;"><b>Portfolio Value</b></td><td>${a.total_portfolio_value:,.0f}</td></tr>
      <tr><td style="padding: 4px 16px 4px 0;"><b>Invested</b></td><td>${a.invested_value:,.0f} ({a.total_exposure_pct:.1f}%)</td></tr>
      <tr><td style="padding: 4px 16px 4px 0;"><b>Cash</b></td><td>${a.cash_value:,.0f} ({a.cash_pct:.1f}%)</td></tr>
      <tr><td style="padding: 4px 16px 4px 0;"><b>Positions</b></td><td>{a.position_count} / {a.max_positions}</td></tr>
    </table>
    <p style="font-size: 12px; color: #64748b;"><b>Sector Concentration:</b></p>
    <table style="font-size: 12px; border-collapse: collapse; margin-bottom: 12px;">{sector_rows}</table>
    <div style="background: #f1f5f9; padding: 12px 16px; border-radius: 8px; font-size: 13px; line-height: 1.6;">
      <b>Weekly Plan:</b> {a.weekly_deployment_plan}
    </div>"""


def _section_risk_notes(a: AllocationResult) -> str:
    items = "".join(f"<li>{n}</li>" for n in a.risk_notes)
    return f"""
    <h2 style="color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
      7. Risk Notes
    </h2>
    <ul style="font-size: 13px; line-height: 1.6; color: #475569; padding-left: 20px;">{items}</ul>"""


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_report(
    email_config: EmailConfig,
    regime: RegimeResult,
    health: PortfolioHealthResult,
    scanner: ScannerResult,
    allocation: AllocationResult,
    external_holdings: List[ExternalHolding],
) -> bool:
    """Send the daily portfolio intelligence email."""
    if not email_config.enabled:
        logger.info("Email disabled in config.")
        return False
    if not email_config.sender_email or not email_config.sender_password:
        logger.warning("Email credentials not configured.")
        return False

    now = datetime.now().strftime("%b %d, %Y")
    subject = f"BigThing Daily Portfolio Intelligence - {now} [{regime.classification}]"

    html = build_report_html(regime, health, scanner, allocation, external_holdings)

    # Plain text fallback
    plain = (
        f"BigThing Daily Report - {now}\n\n"
        f"Regime: {regime.classification} ({regime.multiplier}x)\n"
        f"Holdings: {len(health.holdings)}\n"
        f"External holdings: {len(external_holdings)}\n"
        f"Actions: {len(allocation.trim_exit_plans + allocation.buy_plans)}\n"
        f"Opportunities: {len(scanner.candidates)}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_config.sender_email
    msg["To"] = email_config.recipient_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        logger.info("Sending report to %s ...", email_config.recipient_email)
        with smtplib.SMTP(email_config.smtp_server, email_config.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(email_config.sender_email, email_config.sender_password)
            server.sendmail(email_config.sender_email, email_config.recipient_email, msg.as_string())
        logger.info("Email sent successfully.")
        return True
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        return False
