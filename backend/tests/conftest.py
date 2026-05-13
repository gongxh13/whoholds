from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Point WHOHOLDS_DATA_DIR at a temp dir and disable the scheduler.

    Must run before any `from app.* import …` — that's why this is autouse and
    the test files import the app lazily inside each test function.
    """
    data_dir = tmp_path_factory.mktemp("whoholds_data")
    os.environ["WHOHOLDS_DATA_DIR"] = str(data_dir)
    os.environ["WHOHOLDS_DISABLE_SCHEDULER"] = "1"

    from app.db.migrations import migrate_all

    migrate_all()
    return data_dir
