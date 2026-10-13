import shutil
import sqlite3
import warnings
from pathlib import Path

import pytest

from orgroamtools.data import RoamGraph

FIXTURES = Path(__file__).parent / "fixtures"
ROAM_DIR = FIXTURES / "roam"


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    """Copy of the fixture db with file paths made absolute.

    The committed db stores paths relative to ``tests/fixtures/roam/`` (see
    ``tests/fixtures/build_db.el``); org-roam strings are stored quoted, so
    ``"alpha.org"`` becomes ``"/abs/.../roam/alpha.org"``.
    """
    path = tmp_path_factory.mktemp("db") / "org-roam.db"
    shutil.copy(FIXTURES / "org-roam.db", path)
    prefix = f"{ROAM_DIR}/"
    with sqlite3.connect(path) as con:
        for table in ("nodes", "files"):
            con.execute(
                f"UPDATE {table} SET file = '\"' || ? || substr(file, 2)", (prefix,)
            )
    con.close()
    return path


@pytest.fixture
def graph(db_path) -> RoamGraph:
    """Fresh graph per test, since some methods mutate in place."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return RoamGraph(str(db_path))
