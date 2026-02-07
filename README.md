# the-big-thing

Stock signal and portfolio monitoring tool.

This project builds daily buy-score recommendations based on simple, configurable
factors and monitors a paper portfolio for stop-loss or take-profit alerts.
It does not place trades.

Important: This is educational software, not financial advice. Markets are
unpredictable and losses are possible.

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Install the package in editable mode:
   - `pip install -e .`

## Quick start

1. Copy `config.example.json` to `config.json` and edit tickers and weights.
2. Generate recommendations:
   - `python -m bigthing recommend --config config.json --output recommendations.json`
3. Create a paper portfolio using `portfolio.example.json`.
4. Run a portfolio check once:
   - `python -m bigthing monitor --config config.json --portfolio portfolio.json --output alerts.json`

## Files

- `config.example.json`: factor weights, tickers, and risk settings
- `portfolio.example.json`: sample holdings format
- `recommendations.json`: generated top picks with buy scores
- `alerts.json`: generated stop-loss / take-profit alerts

## Notes

- Data is pulled from Yahoo Finance using `yfinance`.
- You can adjust factor weights and directions to fit your strategy.