"""ETL placeholder.

PR 7 lands real fetchers:
- etl/pull_top10.py       — AKShare top-10 shareholders (季报 quarterly)
- etl/pull_prices.py      — AKShare daily K-line
- etl/pull_teamwork.py    — Eastmoney shareholder-cooperation export

PR 8 lands the disambiguation pipeline (`etl/disambiguate.py`).
PR 9 wires APScheduler into the FastAPI process.
"""
