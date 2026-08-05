import shutil
import sqlite3
from pathlib import Path

import pytest

from app.repositories.offline import OfflineDataError, OfflineRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data/offline/shanghai.db"


def test_repository_opens_database_with_read_only_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    connect = sqlite3.connect
    captured: dict[str, object] = {}

    def recording_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        captured["database"] = args[0]
        captured["uri"] = kwargs.get("uri")
        return connect(*args, **kwargs)

    monkeypatch.setattr("app.repositories.offline.sqlite3.connect", recording_connect)

    OfflineRepository(DATABASE_PATH).get_metadata()

    assert captured["database"] == f"file:{DATABASE_PATH.resolve()}?mode=ro"
    assert captured["uri"] is True


def test_list_pois_filters_interests_without_duplicates() -> None:
    repository = OfflineRepository(DATABASE_PATH)

    pois = repository.list_pois({"culture", "food"})

    assert pois
    assert len({poi.id for poi in pois}) == len(pois)
    assert all({"culture", "food"}.intersection(poi.interests) for poi in pois)


def test_get_poi_rejects_unknown_poi() -> None:
    repository = OfflineRepository(DATABASE_PATH)

    with pytest.raises(OfflineDataError, match="景点不存在"):
        repository.get_poi("unknown-poi")


def test_repository_reports_missing_database_in_simplified_chinese(tmp_path: Path) -> None:
    repository = OfflineRepository(tmp_path / "missing.db")

    with pytest.raises(OfflineDataError, match="离线数据库不存在"):
        repository.get_metadata()


def test_repository_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    database_path = tmp_path / "unsupported-schema.db"
    shutil.copy(DATABASE_PATH, database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE metadata SET value = '2' WHERE key = 'schema_version'")

    repository = OfflineRepository(database_path)

    with pytest.raises(OfflineDataError, match="不支持的离线数据版本"):
        repository.get_metadata()
