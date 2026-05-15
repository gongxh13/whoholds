#!/usr/bin/env python3
"""Cross-platform local entrypoint.

Wraps uv + pnpm so Mac / Linux / Windows users get the same commands. Docker
is its own track — see deploy/README.md.

Usage:
    python run.py <command> [args...]

Commands:
    install        uv sync (+ etl extras) and pnpm install
    migrate        create the 5 empty SQLite files
    bootstrap      real-data ETL pull from AKShare etc. (≈6h, network-bound)
    dev            concurrently run backend + frontend dev servers (Ctrl-C kills both)
    test           pytest (backend) + vitest (frontend)
    lint           ruff + biome + tsc
    clean          drop generated DBs (asks for confirmation)
    snapshot       build / pull data snapshot artifacts (see `snapshot --help`)
    refresh        run incremental ETL (used by the weekly GitHub Actions workflow)
    help           print this help
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def cmd_install(_args: argparse.Namespace) -> int:
    print(">> uv sync --extra etl")
    if _run(["uv", "sync", "--extra", "etl"], cwd=BACKEND):
        return 1
    print(">> pnpm install --frozen-lockfile")
    return _run(["pnpm", "install", "--frozen-lockfile"], cwd=FRONTEND)


def cmd_migrate(_args: argparse.Namespace) -> int:
    return _run(["uv", "run", "python", "scripts/migrate.py"], cwd=BACKEND)


def cmd_bootstrap(_args: argparse.Namespace) -> int:
    print(">> WARNING: full bootstrap ≈ 6 hours, needs network (AKShare + Wikidata)")
    return _run(["uv", "run", "python", "-m", "app.etl.bootstrap"], cwd=BACKEND)


def cmd_dev(_args: argparse.Namespace) -> int:
    """Run uvicorn + vite concurrently. Ctrl-C kills both, no zombies."""
    procs: list[subprocess.Popen] = []
    env_back = os.environ.copy()
    env_back["WHOHOLDS_DISABLE_SCHEDULER"] = "1"

    backend = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=BACKEND,
        env=env_back,
    )
    procs.append(backend)
    frontend = subprocess.Popen(["pnpm", "dev"], cwd=FRONTEND)
    procs.append(frontend)

    print()
    print("  backend  → http://127.0.0.1:8000  (api docs at /docs)")
    print("  frontend → http://localhost:5174")
    print()
    print("  Ctrl-C 退出（两个进程一起退）")
    print()

    def _shutdown(*_) -> None:
        for p in procs:
            if p.poll() is None:
                try:
                    if os.name == "nt":
                        p.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        p.send_signal(signal.SIGINT)
                except (ProcessLookupError, OSError):
                    pass

    signal.signal(signal.SIGINT, _shutdown)
    if os.name != "nt":
        signal.signal(signal.SIGTERM, _shutdown)

    rc = 0
    try:
        while procs:
            for p in list(procs):
                ret = p.poll()
                if ret is not None:
                    procs.remove(p)
                    if ret != 0:
                        rc = ret
                    # If one dies, kill the other so we don't sit half-running.
                    _shutdown()
            try:
                # Sleep without busy-spin; signals interrupt the wait.
                signal.pause() if os.name != "nt" else None
            except (AttributeError, InterruptedError):
                pass
            for p in list(procs):
                if p.poll() is not None:
                    procs.remove(p)
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    return rc


def cmd_test(_args: argparse.Namespace) -> int:
    print(">> backend pytest")
    rc1 = _run(["uv", "run", "pytest", "-q"], cwd=BACKEND)
    print(">> frontend vitest")
    rc2 = _run(["pnpm", "test"], cwd=FRONTEND)
    return rc1 or rc2


def cmd_lint(_args: argparse.Namespace) -> int:
    print(">> ruff")
    rc1 = _run(["uv", "run", "ruff", "check"], cwd=BACKEND)
    print(">> biome")
    rc2 = _run(["pnpm", "check"], cwd=FRONTEND)
    print(">> tsc")
    rc3 = _run(["pnpm", "typecheck"], cwd=FRONTEND)
    return rc1 or rc2 or rc3


def cmd_refresh(args: argparse.Namespace) -> int:
    """Incremental ETL — daily prices last N days + latest quarter top10 + disambiguate."""
    cmd = ["uv", "run", "python", "-m", "app.etl.refresh"]
    if args.days_back is not None:
        cmd += ["--days-back", str(args.days_back)]
    if args.concurrency is not None:
        cmd += ["--concurrency", str(args.concurrency)]
    return _run(cmd, cwd=BACKEND)


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Build / pull / roll-year on the distributable data snapshot."""
    if args.snapshot_cmd == "build":
        build_args: list[str] = []
        if args.all:
            build_args.append("--all")
        elif args.hot:
            build_args.append("--hot")
        elif args.core_only:
            build_args.append("--core-only")
        else:
            print("ERROR: pick one of --all / --hot / --core-only", file=sys.stderr)
            return 2
        return _run(
            ["uv", "run", "python", "scripts/build_snapshot.py", *build_args],
            cwd=BACKEND,
        )
    if args.snapshot_cmd == "pull":
        pull_args: list[str] = []
        if args.tag:
            pull_args += ["--tag", args.tag]
        if args.repo:
            pull_args += ["--repo", args.repo]
        if args.from_local:
            pull_args += ["--from-local", str(args.from_local)]
        if args.hot:
            pull_args.append("--hot")
        if args.year_from:
            pull_args += ["--year-from", args.year_from]
        if args.skip_core:
            pull_args.append("--skip-core")
        return _run(
            ["uv", "run", "python", "scripts/restore_snapshot.py", *pull_args],
            cwd=BACKEND,
        )
    if args.snapshot_cmd == "roll-year":
        # TODO(2026-12): rename current hot bucket in YEAR_BUCKETS into a frozen
        # range, append a new ("YYYY", ...) entry, rebuild + upload to release.
        # Until 2026-12 this only needs a stub.
        print(
            "roll-year not implemented yet — manually edit YEAR_BUCKETS in "
            "backend/scripts/build_snapshot.py + rebuild + re-release.",
            file=sys.stderr,
        )
        return 1
    print(f"unknown snapshot subcommand: {args.snapshot_cmd}", file=sys.stderr)
    return 2


def cmd_clean(args: argparse.Namespace) -> int:
    data = BACKEND / "data"
    if not data.exists():
        print(f"{data} 不存在，没什么可清的。")
        return 0
    if not args.yes:
        reply = input(f"删除 {data} 下所有 SQLite 文件? [y/N] ").strip().lower()
        if reply != "y":
            return 0
    shutil.rmtree(data)
    print(f"removed {data}")
    return 0


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> int:
    try:
        return subprocess.run(cmd, cwd=cwd, env=env).returncode
    except FileNotFoundError as e:
        print(f"ERROR: {e}\n  did you run `python run.py install` first?", file=sys.stderr)
        return 127


COMMANDS = {
    "install": cmd_install,
    "migrate": cmd_migrate,
    "bootstrap": cmd_bootstrap,
    "dev": cmd_dev,
    "test": cmd_test,
    "lint": cmd_lint,
    "clean": cmd_clean,
    "snapshot": cmd_snapshot,
    "refresh": cmd_refresh,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in COMMANDS:
        sp = sub.add_parser(name, help=COMMANDS[name].__doc__ or name)
        if name == "clean":
            sp.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
        elif name == "snapshot":
            snap_sub = sp.add_subparsers(dest="snapshot_cmd", required=True)
            sp_build = snap_sub.add_parser("build", help="produce snapshot zst files in backend/snapshot/")
            g = sp_build.add_mutually_exclusive_group()
            g.add_argument("--all", action="store_true", help="all year shards + core (first-time seed)")
            g.add_argument("--hot", action="store_true", help="only hot year shard + core (weekly refresh)")
            g.add_argument("--core-only", action="store_true", help="only core tarball")
            sp_pull = snap_sub.add_parser("pull", help="download + merge snapshot into backend/data/")
            sp_pull.add_argument("--tag", default=None, help="release tag (default data-snapshot)")
            sp_pull.add_argument("--repo", default=None, help="owner/name (default gh auto-detect)")
            sp_pull.add_argument("--from-local", type=Path, default=None,
                                 help="use a local dir of .zst files instead of GitHub")
            sp_pull.add_argument("--hot", action="store_true", help="only hot shard")
            sp_pull.add_argument("--year-from", default=None,
                                 help='earliest year label, e.g. "2021-2024"')
            sp_pull.add_argument("--skip-core", action="store_true",
                                 help="don't unpack core.tar.zst")
            snap_sub.add_parser("roll-year",
                                help="rotate hot → frozen + open new hot (manual, end of year)")
        elif name == "refresh":
            sp.add_argument("--days-back", type=int, default=None,
                            help="prices window in days (default 14)")
            sp.add_argument("--concurrency", type=int, default=None,
                            help="parallel fetchers (default 6; 1 = serial)")

    args = parser.parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
