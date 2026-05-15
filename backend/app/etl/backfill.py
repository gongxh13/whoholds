"""Historic pull_top10 backfill — for filling in quarters older than Day-0.

design.md §抓取细节 budgets the 20-year full pull at ~18 days serial; with
concurrency=6 each year of history takes ~1h. Run this in chunks (overnight
windows) so partial progress survives — `already_succeeded` skips any
(stock, quarter) already marked 'ok' so re-invocations resume cleanly.

Usage:
    python -m app.etl.backfill --start-year 2021 --end-year 2025
    python -m app.etl.backfill --start-year 1995 --end-year 2020 --concurrency 8

Eastmoney's top10 endpoint serves data from ~1995 onward; pre-IPO quarters
return ValueError (recorded as 'error' in etl_progress, not retried by
`already_succeeded` until you manually mark them 'skipped').
"""
from __future__ import annotations

import argparse
import time

from app.etl import bootstrap, pull_top10


def run(start_year: int, end_year: int, *, concurrency: int = 6) -> None:
    codes = bootstrap._stocks_with_appearances()
    qends = pull_top10.quarter_ends(start_year=start_year, end_year=end_year)
    print(
        f"[backfill] {len(codes)} stocks × {len(qends)} quarters "
        f"({qends[0]}..{qends[-1]}), concurrency={concurrency}",
        flush=True,
    )
    t0 = time.time()
    n = pull_top10.pull_market(codes, qends, concurrency=concurrency)
    print(f"[backfill] {n} ok in {time.time()-t0:.0f}s", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Pull top10 over a historic year range.")
    p.add_argument("--start-year", type=int, required=True, help="inclusive")
    p.add_argument("--end-year", type=int, required=True, help="inclusive")
    p.add_argument("--concurrency", type=int, default=6)
    args = p.parse_args()
    run(args.start_year, args.end_year, concurrency=args.concurrency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
