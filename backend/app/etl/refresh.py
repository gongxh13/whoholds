"""Weekly incremental ETL — the one-shot entrypoint GH Actions calls.

Differs from `bootstrap.run()` in three ways:
- starts from an already-restored snapshot, not empty DBs
- pulls only the recent window (~14 days of prices, latest quarter for top10)
- runs heavy teamwork full-refresh only in earnings-window months

Design: docs/designs/agents/periodic-etl-refresh/design.md
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from app.etl import (
    disambiguate,
    ingest_teamwork,
    pull_prices,
    pull_teamwork,
    pull_top10,
)
from app.etl.bootstrap import _stocks_with_appearances

# Teamwork is ~35 min per call; only worth re-running in earnings window months.
TEAMWORK_WINDOW_MONTHS = {2, 5, 9, 11}


def _in_teamwork_window(today: date) -> bool:
    return today.month in TEAMWORK_WINDOW_MONTHS


def run(*, days_back: int = 14, concurrency: int = 6) -> None:
    t0 = time.time()
    today = date.today()
    codes = _stocks_with_appearances()
    start_date = (today - timedelta(days=days_back)).strftime("%Y%m%d")

    print(f"[refresh] step 1/4 — pull_prices over {len(codes)} stocks "
          f"from {start_date} (concurrency={concurrency})", flush=True)
    pull_prices.pull_market(codes, start_date=start_date, concurrency=concurrency)

    latest_q = pull_top10.quarter_ends()[-1]
    print(f"[refresh] step 2/4 — pull_top10 over {len(codes)} stocks @ {latest_q} "
          f"(concurrency={concurrency})", flush=True)
    pull_top10.pull_market(codes, [latest_q], concurrency=concurrency)

    if _in_teamwork_window(today):
        print("[refresh] step 3/4 — pull_teamwork + ingest_teamwork (window month)", flush=True)
        pull_teamwork.pull_full()
        ingest_teamwork.run()
    else:
        print(f"[refresh] step 3/4 — skip teamwork (month {today.month} not in window)", flush=True)

    print("[refresh] step 4/4 — disambiguate", flush=True)
    disambiguate.run()

    print(f"[refresh] complete in {time.time()-t0:.0f}s", flush=True)


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Weekly incremental ETL refresh")
    p.add_argument("--days-back", type=int, default=14,
                   help="prices window in days (default 14)")
    p.add_argument("--concurrency", type=int, default=6,
                   help="parallel fetchers (default 6; 1 = serial)")
    args = p.parse_args()
    run(days_back=args.days_back, concurrency=args.concurrency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
