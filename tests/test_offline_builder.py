import sqlite3
from pathlib import Path

from scripts.build_offline_db import build_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = PROJECT_ROOT / "data/offline/shanghai_seed.json"


def test_build_database_creates_complete_valid_database(tmp_path: Path) -> None:
    database_path = tmp_path / "shanghai.db"

    build_database(SEED_PATH, database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("SELECT COUNT(*) FROM pois").fetchone()[0] == 60
        assert connection.execute("SELECT COUNT(*) FROM interests").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM route_edges").fetchone()[0] >= 90
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[
                0
            ]
            == "1"
        )


def test_build_database_is_deterministic(tmp_path: Path) -> None:
    first_database_path = tmp_path / "first.db"
    second_database_path = tmp_path / "second.db"

    build_database(SEED_PATH, first_database_path)
    build_database(SEED_PATH, second_database_path)

    with (
        sqlite3.connect(first_database_path) as first_connection,
        sqlite3.connect(second_database_path) as second_connection,
    ):
        assert list(first_connection.iterdump()) == list(second_connection.iterdump())
