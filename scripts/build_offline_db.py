import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        url TEXT NOT NULL,
        license_note TEXT NOT NULL,
        accessed_at TEXT NOT NULL,
        source_type TEXT NOT NULL CHECK (source_type IN (
            'map', 'government', 'transit', 'official', 'manual'
        ))
    )
    """,
    """
    CREATE TABLE interests (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE pois (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        district TEXT NOT NULL,
        area TEXT NOT NULL,
        longitude REAL NOT NULL CHECK (longitude BETWEEN 120.8 AND 122.2),
        latitude REAL NOT NULL CHECK (latitude BETWEEN 30.6 AND 31.9),
        suggested_duration_minutes INTEGER NOT NULL
            CHECK (suggested_duration_minutes BETWEEN 30 AND 480),
        admission_cents INTEGER NOT NULL CHECK (admission_cents >= 0),
        opening_note TEXT NOT NULL,
        is_general_highlight INTEGER NOT NULL CHECK (is_general_highlight IN (0, 1)),
        source_id TEXT NOT NULL REFERENCES sources(id),
        verified_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE poi_interests (
        poi_id TEXT NOT NULL REFERENCES pois(id),
        interest_id TEXT NOT NULL REFERENCES interests(id),
        PRIMARY KEY (poi_id, interest_id)
    )
    """,
    """
    CREATE TABLE route_edges (
        origin_poi_id TEXT NOT NULL REFERENCES pois(id),
        destination_poi_id TEXT NOT NULL REFERENCES pois(id),
        transport_mode TEXT NOT NULL
            CHECK (transport_mode IN ('walk', 'metro', 'bus', 'mixed')),
        duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 1),
        distance_meters INTEGER NOT NULL CHECK (distance_meters >= 1),
        cost_cents INTEGER NOT NULL CHECK (cost_cents >= 0),
        summary TEXT NOT NULL,
        is_bidirectional INTEGER NOT NULL CHECK (is_bidirectional IN (0, 1)),
        source_id TEXT NOT NULL REFERENCES sources(id),
        verified_at TEXT NOT NULL,
        CHECK (origin_poi_id <> destination_poi_id),
        UNIQUE (origin_poi_id, destination_poi_id)
    )
    """,
    """
    CREATE TABLE metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_pois_district_area ON pois(district, area)",
    "CREATE INDEX idx_poi_interests_interest ON poi_interests(interest_id, poi_id)",
    "CREATE INDEX idx_route_edges_origin ON route_edges(origin_poi_id)",
    "CREATE INDEX idx_route_edges_destination ON route_edges(destination_poi_id)",
)


def _load_seed(seed_path: Path) -> dict[str, Any]:
    with seed_path.open(encoding="utf-8") as seed_file:
        seed: dict[str, Any] = json.load(seed_file)

    required_sections = {
        "metadata",
        "sources",
        "interests",
        "pois",
        "poi_interests",
        "route_edges",
    }
    missing_sections = required_sections.difference(seed)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"种子数据缺少必要部分：{missing}")
    return seed


def _populate_database(connection: sqlite3.Connection, seed: dict[str, Any]) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)

    sources = sorted(seed["sources"], key=lambda source: source["id"])
    connection.executemany(
        """
        INSERT INTO sources (
            id, name, url, license_note, accessed_at, source_type
        ) VALUES (
            :id, :name, :url, :license_note, :accessed_at, :source_type
        )
        """,
        sources,
    )

    interests = sorted(seed["interests"], key=lambda interest: interest["id"])
    connection.executemany(
        "INSERT INTO interests (id, label) VALUES (:id, :label)",
        interests,
    )

    pois = sorted(seed["pois"], key=lambda poi: poi["id"])
    connection.executemany(
        """
        INSERT INTO pois (
            id, name, district, area, longitude, latitude,
            suggested_duration_minutes, admission_cents, opening_note,
            is_general_highlight, source_id, verified_at
        ) VALUES (
            :id, :name, :district, :area, :longitude, :latitude,
            :suggested_duration_minutes, :admission_cents, :opening_note,
            :is_general_highlight, :source_id, :verified_at
        )
        """,
        pois,
    )

    poi_interests = sorted(
        seed["poi_interests"],
        key=lambda relation: (relation["poi_id"], relation["interest_id"]),
    )
    connection.executemany(
        """
        INSERT INTO poi_interests (poi_id, interest_id)
        VALUES (:poi_id, :interest_id)
        """,
        poi_interests,
    )

    route_edges = sorted(
        seed["route_edges"],
        key=lambda edge: (edge["origin_poi_id"], edge["destination_poi_id"]),
    )
    connection.executemany(
        """
        INSERT INTO route_edges (
            origin_poi_id, destination_poi_id, transport_mode,
            duration_minutes, distance_meters, cost_cents, summary,
            is_bidirectional, source_id, verified_at
        ) VALUES (
            :origin_poi_id, :destination_poi_id, :transport_mode,
            :duration_minutes, :distance_meters, :cost_cents, :summary,
            :is_bidirectional, :source_id, :verified_at
        )
        """,
        route_edges,
    )

    metadata = sorted(seed["metadata"].items())
    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        [(key, str(value)) for key, value in metadata],
    )


def build_database(seed_path: Path, output_path: Path) -> None:
    seed = _load_seed(seed_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.unlink(missing_ok=True)

    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            _populate_database(connection, seed)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从种子数据构建上海离线 SQLite 数据库")
    parser.add_argument("--seed", required=True, type=Path, help="JSON 种子数据路径")
    parser.add_argument("--output", required=True, type=Path, help="SQLite 输出路径")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_database(args.seed, args.output)


if __name__ == "__main__":
    main()
