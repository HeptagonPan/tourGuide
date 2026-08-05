import sqlite3
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from pathlib import Path

from app.schemas.offline import OfflineMetadata, OfflinePoi, OfflineRouteEdge


class OfflineDataError(ValueError):
    """表示离线上海数据不可用或不兼容。"""


class OfflineRepository:
    """提供 schema version 1 上海离线数据库的只读查询。"""

    _SCHEMA_VERSION = "1"

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_pois(self, interests: Collection[str]) -> list[OfflinePoi]:
        self._validate_schema_version()
        normalized_interests = sorted(set(interests))
        filter_sql = ""
        parameters: list[str] = []
        if normalized_interests:
            placeholders = ", ".join("?" for _ in normalized_interests)
            filter_sql = f"""
                WHERE EXISTS (
                    SELECT 1
                    FROM poi_interests selected_interest
                    WHERE selected_interest.poi_id = p.id
                      AND selected_interest.interest_id IN ({placeholders})
                )
            """
            parameters = normalized_interests

        rows = self._execute(
            f"""
            SELECT
                p.id, p.name, p.district, p.area, p.longitude, p.latitude,
                p.suggested_duration_minutes, p.admission_cents, p.opening_note,
                p.is_general_highlight, p.source_id, p.verified_at,
                GROUP_CONCAT(pi.interest_id, ',') AS interests
            FROM pois p
            JOIN poi_interests pi ON pi.poi_id = p.id
            {filter_sql}
            GROUP BY p.id
            ORDER BY p.district, p.area, p.name
            """,
            parameters,
        )
        return [self._poi_from_row(row) for row in rows]

    def get_poi(self, poi_id: str) -> OfflinePoi:
        self._validate_schema_version()
        rows = self._execute(
            """
            SELECT
                p.id, p.name, p.district, p.area, p.longitude, p.latitude,
                p.suggested_duration_minutes, p.admission_cents, p.opening_note,
                p.is_general_highlight, p.source_id, p.verified_at,
                GROUP_CONCAT(pi.interest_id, ',') AS interests
            FROM pois p
            JOIN poi_interests pi ON pi.poi_id = p.id
            WHERE p.id = ?
            GROUP BY p.id
            """,
            [poi_id],
        )
        if not rows:
            raise OfflineDataError("景点不存在")
        return self._poi_from_row(rows[0])

    def list_route_edges(self) -> list[OfflineRouteEdge]:
        self._validate_schema_version()
        rows = self._execute(
            """
            SELECT
                origin_poi_id, destination_poi_id, transport_mode,
                duration_minutes, distance_meters, cost_cents, summary,
                is_bidirectional, source_id, verified_at
            FROM route_edges
            ORDER BY origin_poi_id, destination_poi_id
            """
        )
        return [OfflineRouteEdge.model_validate(dict(row)) for row in rows]

    def get_metadata(self) -> OfflineMetadata:
        rows = self._execute("SELECT key, value FROM metadata")
        values = {row["key"]: row["value"] for row in rows}
        if values.get("schema_version") != self._SCHEMA_VERSION:
            raise OfflineDataError("不支持的离线数据版本")
        try:
            return OfflineMetadata.model_validate(
                {
                    "schema_version": values["schema_version"],
                    "data_version": values["data_version"],
                    "generated_at": values["generated_at"],
                    "poi_count": values["poi_count"],
                    "route_edge_count": values["route_edge_count"],
                }
            )
        except (KeyError, ValueError) as error:
            raise OfflineDataError("离线数据元信息无效") from error

    def _validate_schema_version(self) -> None:
        rows = self._execute("SELECT value FROM metadata WHERE key = 'schema_version'")
        if not rows or rows[0]["value"] != self._SCHEMA_VERSION:
            raise OfflineDataError("不支持的离线数据版本")

    def _execute(self, query: str, parameters: Collection[str] = ()) -> list[sqlite3.Row]:
        with self._connection() as connection:
            try:
                return connection.execute(query, tuple(parameters)).fetchall()
            except sqlite3.Error as error:
                raise OfflineDataError("离线数据查询失败") from error

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not self._database_path.is_file():
            raise OfflineDataError("离线数据库不存在")
        uri = f"file:{self._database_path.resolve()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as error:
            raise OfflineDataError("离线数据库无法打开") from error
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _poi_from_row(row: sqlite3.Row) -> OfflinePoi:
        data = dict(row)
        data["interests"] = data["interests"].split(",")
        return OfflinePoi.model_validate(data)
