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

    args = parser.parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
