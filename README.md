# BigThing v2 — Portfolio Intelligence System

A **disciplined, rule-based portfolio manager** for swing and position trading (2 weeks to 6 months horizon). BigThing runs once daily after market close and delivers a structured intelligence report via email.

> This is NOT a day-trading tool.
> This is NOT a prediction fantasy system.
> This is a capital-preservation-first portfolio operating system.

---

## Architecture

BigThing is a 4-module system that runs sequentially:

```
┌──────────────────────────────────────────────────────────────┐
│  1. MARKET REGIME ENGINE                                     │
│     SPY trend · VIX level · 10Y yield → RISK_ON/NEUTRAL/OFF │
├──────────────────────────────────────────────────────────────┤
│  2. PORTFOLIO HEALTH ENGINE                                  │
│     Score each holding 0-10 → STRONG HOLD / HOLD / TRIM / EXIT │
├──────────────────────────────────────────────────────────────┤
│  3. OPPORTUNITY SCANNER                                      │
│     S&P 500 + NASDAQ-100 → filter → rank → top 5-10 picks   │
├──────────────────────────────────────────────────────────────┤
│  4. CAPITAL ALLOCATION ENGINE                                │
│     Risk-based sizing · max 12 positions · 10% cash floor    │
└──────────────────────────────────────────────────────────────┘
                          ↓
              📧 Daily Email Report
```

---

## Module Details

### Module 1: Market Regime Engine

Classifies the macro environment using daily-timeframe data:

| Signal | Source | Purpose |
|--------|--------|---------|
| SPY vs 200-day MA | SPY | Long-term trend |
| SPY vs 50-day MA | SPY | Medium-term trend |
| 50-MA trend direction | SPY | Momentum confirmation |
| Higher/lower highs | SPY | Price structure |
| VIX level + trend | ^VIX | Fear gauge |
| 10Y yield trend | ^TNX | Rate environment |

**Output:**
| Regime | Criteria | Position Multiplier |
|--------|----------|-------------------|
| RISK_ON | SPY > 200 MA, 50 MA rising, higher highs | 1.0x |
| NEUTRAL | Mixed signals | 0.7x |
| RISK_OFF | SPY < 200 MA, lower highs, VIX elevated | 0.4x |

### Module 2: Portfolio Health Engine

Scores each holding on 4 dimensions:

| Dimension | Max Score | Components |
|-----------|-----------|------------|
| Trend | 3 | Above 200 MA, above 50 MA, higher highs |
| Fundamentals | 3 | Revenue growth, EPS growth, healthy margins |
| Relative Strength | 2 | Outperforming SPY over 60 days |
| Macro Alignment | 2 | Sector-regime fit, regime direction |
| **Total** | **10** | |

**Decision Rules:**
| Score | Action |
|-------|--------|
| 8-10 | STRONG HOLD |
| 6-7 | HOLD |
| 4-5 | TRIM 25% |
| 0-3 | EXIT |

Also computes: suggested stop-loss (2x ATR), risk per position, distance from MAs.

### Module 3: Opportunity Scanner

**Universe:** S&P 500 + NASDAQ-100 (daily data only)

**Filters (all must pass):**
- Price above 200-day MA
- 50-day MA rising
- RSI between 45-65 (not overbought or oversold)
- Volume expanding vs 30-day average
- Positive earnings growth trend
- No earnings within 5 trading days

**Composite Score Weights:**

| Factor | Weight |
|--------|--------|
| Trend Strength | 30% |
| Fundamental Growth | 25% |
| Relative Strength | 20% |
| Volume Expansion | 15% |
| Valuation vs Growth | 10% |

**Output per candidate:**
- Entry zone, suggested stop, risk per share
- Position size (regime-adjusted)
- 6-week bull/base/bear probability scenarios
- 6-month outlook summary

### Module 4: Capital Allocation Engine

**Rules:**
- Max risk per trade: 1% of portfolio value
- Position size = (Portfolio × 0.01 × regime_multiplier) ÷ (Entry − Stop)
- Max 10-12 total positions
- Minimum 10% cash reserve
- No new capital deployed in RISK_OFF (unless score ≥ 90)

**Output:**
- Total exposure and cash percentages
- Sector concentration breakdown
- Weekly capital deployment plan
- Risk notes and alerts

---

## Email Report

Sent once daily after market close. Sections:

1. **Market Regime Summary** — regime classification with plain-English explanation
2. **Portfolio Health Table** — all holdings scored with decisions
3. **External Holdings (Notes)** — non-equity positions tracked for visibility only
4. **Actions Required** — specific trim/exit/buy instructions
5. **New Opportunities** — top candidates with entry zones and sizing
6. **Capital Deployment Guidance** — weekly plan based on regime
7. **Risk Notes** — cash levels, concentration alerts, regime warnings

**Tone:** Professional, structured, probability-framed. No hype. No certainty language.

---

## Project Structure

```
the-big-thing/
├── src/bigthing/
│   ├── __init__.py          # Package metadata
│   ├── __main__.py          # python -m bigthing
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration dataclasses + loader
│   ├── pipeline.py          # Main orchestration (runs all 4 modules)
│   ├── data_provider.py     # Daily OHLCV + fundamentals from Yahoo Finance
│   ├── utils.py             # Technical analysis (SMA, RSI, ATR, trend)
│   ├── universe.py          # Dynamic stock universe (S&P 500, NASDAQ-100)
│   ├── regime.py            # Module 1: Market Regime Engine
│   ├── health.py            # Module 2: Portfolio Health Engine
│   ├── scanner.py           # Module 3: Opportunity Scanner
│   ├── allocator.py         # Module 4: Capital Allocation Engine
│   └── emailer.py           # HTML email report builder + sender
├── scripts/
│   ├── daily_report.py      # Standalone script for scheduled runs
│   └── setup_scheduler.bat  # Windows Task Scheduler setup
├── config.json              # Your active config (gitignored)
├── config.example.json      # Template config
├── pyproject.toml           # Package definition
├── requirements.txt         # pip dependencies
└── README.md
```

---

## Setup

```bash
# Clone and navigate to the project
cd the-big-thing

# Install dependencies
pip install -r requirements.txt

# Or install as editable package
pip install -e .

# Copy and edit config
cp config.example.json config.json
# Edit config.json with your holdings, email settings, etc.
```

---

## Usage

### Run the full pipeline

```bash
python -m bigthing --config config.json --output report.json
```

### Run with verbose logging

```bash
python -m bigthing --config config.json --output report.json -v
```

### Run without sending email

```bash
python -m bigthing --config config.json --output report.json --no-email
```

### Run via the standalone script

```bash
python scripts/daily_report.py --config config.json --output report.json
```

### Schedule daily (Windows)

```bash
# Run as Administrator
scripts\setup_scheduler.bat
```

This creates a Windows scheduled task that runs at 5:00 PM daily.

---

## Configuration

Edit `config.json` to customize:

| Section | Key Settings |
|---------|-------------|
| `portfolio` | Total value, max positions, holdings list |
| `universe` | Sources (sp500/nasdaq100), price/volume filters |
| `regime` | MA periods, VIX threshold, trend window |
| `scanner` | RSI range, volume threshold, score weights |
| `email` | SMTP settings, Gmail app password |
| `data` | Coverage threshold, retry logic |
| `external_holdings` | Notes-only positions (e.g., crypto) |

### Email Setup (Gmail)

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Generate an App Password (search "App passwords")
4. Set `sender_password` in config.json to the generated password

---

## Data Integrity

- Minimum 80% data coverage required (configurable)
- 3 retries with 5-second delay on failed downloads
- System **aborts** and produces no output if data integrity fails
- All data is daily timeframe (no intraday)

---

## Prepared for Future Extensions

The architecture is modular and ready for:

- **News sentiment aggregation** — add a sentiment module to the pipeline
- **Sector rotation heatmap** — extend regime engine with sector ETF data
- **Long/Short extension** — add short-side scanning to scanner module
- **Web dashboard (Streamlit)** — pipeline returns JSON, easy to visualize

---

## Philosophy

> *"The goal of a good trader is not to make money. It is to trade well.
> If they trade well, money will follow."* — Alexander Elder

BigThing is built on these principles:
- **Capital preservation first** — risk management is not optional
- **Position sizing is the edge** — not stock picking
- **Regime awareness** — reduce when markets are hostile
- **Probability framing** — no predictions, only probabilities
- **Discipline over conviction** — rules execute, emotions don't
