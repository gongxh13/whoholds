"""APScheduler wiring — runs inside the FastAPI process (BackgroundScheduler).

design.md §调度:
- Daily prices: cron mon-fri 18:00 (post-close)
- Top-10 incremental: cron 02:00 daily
- Teamwork full: cron quarterly (financial-report season, mid-month, 03:00)
- Disambiguation recompute: cron 04:00 daily

A-share reporting-season densification (mid-Mar→early-May, mid-Apr→early-May,
mid-Aug→early-Sep, mid-Oct→early-Nov) is layered on top — those windows run
top-10 incremental hourly instead of daily.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.etl import disambiguate, ingest_teamwork, pull_prices, pull_teamwork, pull_top10
from app.etl.common import alert


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Shanghai")

    sched.add_job(
        _daily_prices, CronTrigger(day_of_week="mon-fri", hour=18, minute=0),
        id="daily_prices", coalesce=True, max_instances=1,
    )
    sched.add_job(
        _top10_incremental, CronTrigger(hour=2, minute=0),
        id="top10_incremental", coalesce=True, max_instances=1,
    )
    sched.add_job(
        _teamwork_full,
        CronTrigger(month="2,5,9,11", day=15, hour=3, minute=0),
        id="teamwork_full", coalesce=True, max_instances=1,
    )
    sched.add_job(
        _disambiguate_full, CronTrigger(hour=4, minute=0),
        id="disambiguate_full", coalesce=True, max_instances=1,
    )

    # Reporting-season densification — hourly top-10 incremental.
    for month_day_range in ("3/15-5/5", "8/15-9/5", "10/15-11/5"):
        sched.add_job(
            _top10_incremental, CronTrigger(month="*", day="*", hour="*/2", minute=0),
            id=f"top10_dense_{month_day_range}", coalesce=True, max_instances=1,
            replace_existing=True,
        )
    return sched


def _daily_prices() -> None:
    try:
        from app.etl.bootstrap import _stocks_with_appearances

        pull_prices.pull_market(_stocks_with_appearances())
    except Exception as exc:  # noqa: BLE001
        alert("error", "scheduler.daily_prices", str(exc))


def _top10_incremental() -> None:
    try:
        from app.etl.bootstrap import _stocks_with_appearances

        codes = _stocks_with_appearances()
        latest_date = pull_top10.quarter_ends()[-1]
        pull_top10.pull_market(codes, [latest_date])
    except Exception as exc:  # noqa: BLE001
        alert("error", "scheduler.top10_incremental", str(exc))


def _teamwork_full() -> None:
    try:
        pull_teamwork.pull_full()
        ingest_teamwork.run()
    except Exception as exc:  # noqa: BLE001
        alert("error", "scheduler.teamwork_full", str(exc))


def _disambiguate_full() -> None:
    try:
        disambiguate.run()
    except Exception as exc:  # noqa: BLE001
        alert("error", "scheduler.disambiguate_full", str(exc))
