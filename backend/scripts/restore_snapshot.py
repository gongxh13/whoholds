"""Restore a snapshot into backend/data/.

Downloads zst artifacts from a GitHub Release (default tag `data-snapshot`),
decompresses each prices year-shard and merges into backend/data/prices.db
via one-shot ATTACH + INSERT OR REPLACE, then unpacks core.tar.zst over
backend/data/.

Design: docs/designs/agents/db-snapshot-distribution/design.md
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, ensure_data_dir  # noqa: E402
from app.db.migrations import migrate_all  # noqa: E402
from scripts.build_snapshot import HOT_LABEL, PRICES_SCHEMA, YEAR_BUCKETS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "snapshot"

DEFAULT_TAG = "data-snapshot"


def _check_zstd() -> None:
    if shutil.which("zstd") is None:
        raise SystemExit("zstd binary not found — install with `brew install zstd` or `apt-get install zstd`")


def _check_tar() -> None:
    if shutil.which("tar") is None:
        raise SystemExit("tar binary not found")


def _shards_to_fetch(*, hot_only: bool, year_from: str | None) -> list[str]:
    out: list[str] = []
    for label, _, _ in YEAR_BUCKETS:
        if hot_only and label != HOT_LABEL:
            continue
        if year_from is not None and label < year_from:
            continue
        out.append(f"prices_{label}.db.zst")
    return out


def download_release(
    *,
    tag: str,
    repo: str | None,
    targets: list[str],
    dest: Path,
) -> None:
    """Use `gh release download` to grab the named assets."""
    if shutil.which("gh") is None:
        raise SystemExit("gh CLI not found — install from cli.github.com or use --from-local")
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["gh", "release", "download", tag, "--clobber", "-D", str(dest)]
    if repo:
        cmd += ["--repo", repo]
    for asset in targets:
        cmd += ["-p", asset]
    print(f">> {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def merge_prices_shard(zst_path: Path, target_conn: sqlite3.Connection) -> int:
    """Decompress one prices_*.db.zst and ATTACH + INSERT OR REPLACE into target."""
    db_tmp = zst_path.with_suffix("")  # drop .zst
    zst_mb = zst_path.stat().st_size / 1024 / 1024
    print(f"    decompressing {zst_path.name} ({zst_mb:.0f} MB)...", flush=True)
    subprocess.run(
        ["zstd", "-d", "-f", "-q", str(zst_path), "-o", str(db_tmp)],
        check=True,
    )
    db_mb = db_tmp.stat().st_size / 1024 / 1024
    print(f"    merging into prices.db ({db_mb:.0f} MB raw)...", flush=True)
    try:
        target_conn.execute(f"ATTACH DATABASE '{db_tmp}' AS src")
        try:
            cur = target_conn.execute("SELECT COUNT(*) FROM src.stock_daily_price")
            n = cur.fetchone()[0]
            cur.close()
            target_conn.execute(
                "INSERT OR REPLACE INTO main.stock_daily_price "
                "SELECT * FROM src.stock_daily_price"
            )
            # commit before detach — otherwise src stays write-locked by the
            # open implicit transaction and DETACH errors with "database src is locked".
            target_conn.commit()
        finally:
            target_conn.execute("DETACH DATABASE src")
    finally:
        db_tmp.unlink(missing_ok=True)
    return n


def restore_core(zst_path: Path) -> None:
    """tar --zstd -xf core.tar.zst into backend/data/, overwriting."""
    ensure_data_dir()
    subprocess.run(
        ["tar", "--zstd", "-xf", str(zst_path), "-C", str(DATA_DIR)],
        check=True,
    )


def run(
    *,
    tag: str = DEFAULT_TAG,
    repo: str | None = None,
    from_local: Path | None = None,
    hot_only: bool = False,
    year_from: str | None = None,
    skip_core: bool = False,
) -> None:
    _check_zstd()
    _check_tar()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    shards = _shards_to_fetch(hot_only=hot_only, year_from=year_from)
    targets = list(shards)
    if not skip_core:
        targets.append("core.tar.zst")

    total_assets = len(targets)
    if from_local is not None:
        src_dir = from_local.resolve()
        print(f">> [stage 1/3] copy {total_assets} asset(s) from {src_dir}", flush=True)
        for i, asset in enumerate(targets, 1):
            src_file = src_dir / asset
            if not src_file.exists():
                raise SystemExit(f"missing local asset: {src_file}")
            dst_file = SNAPSHOT_DIR / asset
            print(f"  [{i}/{total_assets}] {asset} ({src_file.stat().st_size/1024/1024:.0f} MB)", flush=True)
            if src_file != dst_file:
                shutil.copy(src_file, dst_file)
    else:
        print(f">> [stage 1/3] download {total_assets} asset(s) from release '{tag}'", flush=True)
        download_release(tag=tag, repo=repo, targets=targets, dest=SNAPSHOT_DIR)

    # 1. Ensure schemas exist (idempotent).
    migrate_all()

    # 2. Restore core (overwrite entities/holdings/wd_cache).
    if not skip_core:
        core_path = SNAPSHOT_DIR / "core.tar.zst"
        if not core_path.exists():
            raise SystemExit(f"core asset missing: {core_path}")
        print(f">> [stage 2/3] unpack core.tar.zst ({core_path.stat().st_size/1024/1024:.0f} MB) → backend/data/", flush=True)
        restore_core(core_path)

    # 3. Merge prices shards into prices.db.
    target_db = DATA_DIR / "prices.db"
    target = sqlite3.connect(target_db)
    try:
        target.executescript("PRAGMA journal_mode=WAL;\n" + PRICES_SCHEMA)
        n_shards = len(shards)
        print(f">> [stage 3/3] merge {n_shards} prices shard(s) → prices.db", flush=True)
        for idx, asset in enumerate(shards, 1):
            zst_path = SNAPSHOT_DIR / asset
            if not zst_path.exists():
                raise SystemExit(f"shard missing: {zst_path}")
            print(f"  [{idx}/{n_shards}] {asset}", flush=True)
            t0 = time.time()
            n = merge_prices_shard(zst_path, target)
            print(f"    ✓ {n} rows in {time.time()-t0:.1f}s", flush=True)
    finally:
        target.close()

    print(f"\nrestored to {DATA_DIR}", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Restore snapshot into backend/data/.")
    p.add_argument("--tag", default=DEFAULT_TAG, help=f"release tag (default {DEFAULT_TAG})")
    p.add_argument("--repo", default=None, help="owner/name; default: gh auto-detect")
    p.add_argument("--from-local", type=Path, default=None,
                   help="restore from a local dir of .zst files instead of GitHub")
    p.add_argument("--hot", action="store_true",
                   help="only the hot year shard (+ core unless --skip-core)")
    p.add_argument("--year-from", default=None,
                   help='earliest year label to include, e.g. "2021-2024"')
    p.add_argument("--skip-core", action="store_true",
                   help="don't unpack core.tar.zst (prices-only refresh)")
    args = p.parse_args(argv)

    run(
        tag=args.tag,
        repo=args.repo,
        from_local=args.from_local,
        hot_only=args.hot,
        year_from=args.year_from,
        skip_core=args.skip_core,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
