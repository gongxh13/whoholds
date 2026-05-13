"""Unit tests for the Layer 2 same-name disambiguation algorithm.

Builds a tiny entities.db fixture with a few synthetic holders and verifies
the bucket split matches design.md §同名消歧算法 验证 expectations.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def _seeded_entities(_isolated_data_dir: Path):
    """Seed then clean entities.db so other tests can re-assert emptiness."""
    _seed(_isolated_data_dir)
    yield _isolated_data_dir
    db = sqlite3.connect(_isolated_data_dir / "entities.db")
    db.executescript(
        "DELETE FROM holder_companies; DELETE FROM coholder_pairs;"
        "DELETE FROM entity; DELETE FROM appearance_entity;"
    )
    db.commit()
    db.close()


def _seed(data_dir: Path) -> None:
    """Two distinct 张三s: one shares peer 李四 across 3 companies, the other is alone."""
    db = sqlite3.connect(data_dir / "entities.db")
    db.executescript(
        """
        DELETE FROM holder_companies;
        DELETE FROM coholder_pairs;

        INSERT INTO holder_companies VALUES ('张三','个人','sh600001','A公司','20240630');
        INSERT INTO holder_companies VALUES ('张三','个人','sh600002','B公司','20240630');
        INSERT INTO holder_companies VALUES ('张三','个人','sh600003','C公司','20240630');
        INSERT INTO holder_companies VALUES ('张三','个人','sh600099','Z公司','20240630');
        INSERT INTO holder_companies VALUES ('李四','个人','sh600001','A公司','20240630');
        INSERT INTO holder_companies VALUES ('李四','个人','sh600002','B公司','20240630');
        INSERT INTO holder_companies VALUES ('李四','个人','sh600003','C公司','20240630');

        INSERT INTO coholder_pairs VALUES (
            '张三','个人','李四','个人',3,
            '600001|A公司|20240630,600002|B公司|20240630,600003|C公司|20240630'
        );
        """
    )
    db.commit()
    db.close()


def test_disambiguate_splits_two_buckets(_seeded_entities: Path) -> None:
    from app.db.connection import connect
    from app.services.disambiguate import compute_buckets

    with connect("entities") as conn:
        buckets, code_to_bucket, _ = compute_buckets(conn, "张三")

    assert buckets is not None
    assert code_to_bucket is not None
    multi = [b for b in buckets if b.bucket_idx is not None]
    singles = [b for b in buckets if b.bucket_idx is None]
    assert len(multi) == 1, [b.size for b in buckets]
    assert multi[0].size == 3
    assert multi[0].level in ("mid", "high"), multi[0].level
    assert "李四" in multi[0].evidence
    # The lonely sh600099 is a singleton bucket.
    assert any(b.size == 1 for b in singles)


def test_disambiguate_missing_name_returns_none(_isolated_data_dir: Path) -> None:
    from app.db.connection import connect
    from app.services.disambiguate import compute_buckets

    with connect("entities") as conn:
        buckets, _, _ = compute_buckets(conn, "不存在的名字")
    assert buckets is None
