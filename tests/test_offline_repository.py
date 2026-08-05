import shutil
import sqlite3
from pathlib import Path

import pytest

from app.repositories.offline import OfflineDataError, OfflineRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data/offline/shanghai.db"


def _database_with_schema_version(tmp_path: Path, version: str) -> Path:
    database_path = tmp_path / f"schema-{version}.db"
    shutil.copy(DATABASE_PATH, database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE metadata SET value = ? WHERE key = 'schema_version'", (version,))
    return database_path


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
    assert any(set(poi.interests) - {"culture", "food"} for poi in pois)

    with sqlite3.connect(f"file:{DATABASE_PATH.resolve()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        expected_interests = {
            row["poi_id"]: row["interests"].split(",")
            for row in connection.execute(
                """
                SELECT poi_id, GROUP_CONCAT(interest_id, ',') AS interests
                FROM poi_interests
                GROUP BY poi_id
                """
            )
        }

    assert all(set(poi.interests) == set(expected_interests[poi.id]) for poi in pois)
    assert [poi.id for poi in pois] == [
        poi.id for poi in sorted(pois, key=lambda poi: (poi.district, poi.area, poi.name))
    ]


def test_get_poi_rejects_unknown_poi() -> None:
    repository = OfflineRepository(DATABASE_PATH)

    with pytest.raises(OfflineDataError, match="景点不存在"):
        repository.get_poi("unknown-poi")


def test_repository_reports_missing_database_in_simplified_chinese(tmp_path: Path) -> None:
    repository = OfflineRepository(tmp_path / "missing.db")

    with pytest.raises(OfflineDataError, match="离线数据库不存在"):
        repository.get_metadata()


def test_repository_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    repository = OfflineRepository(_database_with_schema_version(tmp_path, "2"))

    with pytest.raises(OfflineDataError, match="不支持的离线数据版本"):
        repository.get_metadata()


def test_list_pois_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    repository = OfflineRepository(_database_with_schema_version(tmp_path, "2"))

    with pytest.raises(OfflineDataError, match="不支持的离线数据版本"):
        repository.list_pois({"culture"})


def test_get_poi_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    repository = OfflineRepository(_database_with_schema_version(tmp_path, "2"))

    with pytest.raises(OfflineDataError, match="不支持的离线数据版本"):
        repository.get_poi("guyi-garden")


def test_list_route_edges_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    repository = OfflineRepository(_database_with_schema_version(tmp_path, "2"))

    with pytest.raises(OfflineDataError, match="不支持的离线数据版本"):
        repository.list_route_edges()


def test_repository_reports_query_failure_in_simplified_chinese(tmp_path: Path) -> None:
    database_path = tmp_path / "missing-table.db"
    shutil.copy(DATABASE_PATH, database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE poi_interests")

    repository = OfflineRepository(database_path)

    with pytest.raises(OfflineDataError, match="离线数据查询失败") as exc_info:
        repository.list_pois({"culture"})

    message = str(exc_info.value)
    assert str(database_path) not in message
    assert "poi_interests" not in message
    assert "SELECT" not in message


def test_repository_reports_open_failure_in_simplified_chinese(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr("app.repositories.offline.sqlite3.connect", failing_connect)

    repository = OfflineRepository(DATABASE_PATH)

    with pytest.raises(OfflineDataError, match="离线数据库无法打开") as exc_info:
        repository.list_pois({"culture"})

    message = str(exc_info.value)
    assert "unable to open database file" not in message
    assert str(DATABASE_PATH) not in message
