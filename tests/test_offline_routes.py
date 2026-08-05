import re
from datetime import date
from pathlib import Path
from typing import Literal

from app.repositories.offline import OfflineRepository
from app.schemas.offline import OfflineRouteEdge
from app.services.offline_routes import OfflineRouteService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data/offline/shanghai.db"

DIRECTIONAL_SUMMARY_PATTERN = re.compile(r"至|前往|方向|向南")


class FakeOfflineRepository:
    """只暴露 list_route_edges 的内存仓库，用于控制路线图数据。"""

    def __init__(self, edges: list[OfflineRouteEdge]) -> None:
        self._edges = list(edges)

    def list_route_edges(self) -> list[OfflineRouteEdge]:
        return list(self._edges)


def make_edge(
    origin: str,
    destination: str,
    *,
    transport_mode: Literal["walk", "metro", "bus", "mixed"] = "walk",
    duration_minutes: int = 10,
    distance_meters: int = 1000,
    cost_cents: int = 0,
    summary: str = "步行",
    bidirectional: bool = True,
    source_id: str = "offline-route:test",
) -> OfflineRouteEdge:
    return OfflineRouteEdge(
        origin_poi_id=origin,
        destination_poi_id=destination,
        transport_mode=transport_mode,
        duration_minutes=duration_minutes,
        distance_meters=distance_meters,
        cost_cents=cost_cents,
        summary=summary,
        is_bidirectional=bidirectional,
        source_id=source_id,
        verified_at=date(2026, 8, 5),
    )


def test_find_route_returns_direct_edge() -> None:
    edge = make_edge(
        "a",
        "b",
        duration_minutes=12,
        distance_meters=900,
        summary="步行至 B",
        source_id="edge-ab",
    )
    service = OfflineRouteService(FakeOfflineRepository([edge]))

    path = service.find_route("a", "b")

    assert path is not None
    assert path.origin_poi_id == "a"
    assert path.destination_poi_id == "b"
    assert [edge.origin_poi_id for edge in path.edges] == ["a"]
    assert path.duration_minutes == 12
    assert path.distance_meters == 900
    assert path.cost_cents == 0
    assert path.instructions == ["步行至 B"]
    assert path.source_ids == ["edge-ab"]


def test_find_route_reuses_bidirectional_edge_in_reverse() -> None:
    edge = make_edge(
        "a",
        "b",
        transport_mode="metro",
        duration_minutes=12,
        distance_meters=900,
        cost_cents=300,
        summary="乘坐地铁 1 号线至 B",
        source_id="edge-ab",
    )
    service = OfflineRouteService(FakeOfflineRepository([edge]))

    path = service.find_route("b", "a")

    assert path is not None
    assert len(path.edges) == 1
    reverse = path.edges[0]
    assert reverse.origin_poi_id == "b"
    assert reverse.destination_poi_id == "a"
    assert reverse.duration_minutes == 12
    assert reverse.distance_meters == 900
    assert reverse.cost_cents == 300
    assert reverse.source_id == "edge-ab"
    assert path.instructions == ["乘坐地铁 1 号线至 B"]


def test_find_route_returns_shortest_time_path() -> None:
    edges = [
        make_edge(
            "a",
            "b",
            duration_minutes=10,
            distance_meters=800,
            summary="步行至 B",
            source_id="walk-ab",
        ),
        make_edge(
            "b",
            "c",
            transport_mode="metro",
            duration_minutes=15,
            distance_meters=5000,
            cost_cents=400,
            summary="乘坐地铁 2 号线至 C",
            source_id="metro-bc",
        ),
        make_edge(
            "a",
            "c",
            transport_mode="metro",
            duration_minutes=40,
            distance_meters=9000,
            cost_cents=500,
            summary="地铁 1 号线直达",
            source_id="metro-ac",
        ),
    ]
    service = OfflineRouteService(FakeOfflineRepository(edges))

    path = service.find_route("a", "c")

    assert path is not None
    assert [edge.destination_poi_id for edge in path.edges] == ["b", "c"]
    assert path.duration_minutes == 25
    assert path.distance_meters == 5800
    assert path.cost_cents == 400
    assert path.instructions == ["步行至 B", "乘坐地铁 2 号线至 C"]
    assert path.source_ids == ["walk-ab", "metro-bc"]
    assert service.find_route("a", "missing") is None
    assert service.find_route("missing", "a") is None


def test_find_route_deduplicates_source_ids() -> None:
    edges = [
        make_edge("a", "b", duration_minutes=10, distance_meters=800, source_id="shared-source"),
        make_edge("b", "c", duration_minutes=5, distance_meters=1200, source_id="shared-source"),
    ]
    service = OfflineRouteService(FakeOfflineRepository(edges))

    path = service.find_route("a", "c")

    assert path is not None
    assert path.source_ids == ["shared-source"]


def test_find_route_breaks_duration_ties_by_shorter_distance() -> None:
    edges = [
        make_edge("a", "b", duration_minutes=10, distance_meters=600),
        make_edge("b", "c", duration_minutes=10, distance_meters=2000),
        make_edge("a", "c", duration_minutes=20, distance_meters=1000),
    ]
    service = OfflineRouteService(FakeOfflineRepository(edges))

    path = service.find_route("a", "c")

    assert path is not None
    assert [edge.destination_poi_id for edge in path.edges] == ["c"]
    assert path.duration_minutes == 20
    assert path.distance_meters == 1000


def test_find_route_handles_cycles() -> None:
    edges = [
        make_edge("a", "b", duration_minutes=10, distance_meters=800),
        make_edge("b", "c", duration_minutes=5, distance_meters=900),
        make_edge("c", "b", duration_minutes=5, distance_meters=900),
        make_edge("c", "a", duration_minutes=100, distance_meters=9000),
        make_edge("a", "c", duration_minutes=20, distance_meters=3000),
    ]
    service = OfflineRouteService(FakeOfflineRepository(edges))

    path = service.find_route("a", "c")

    assert path is not None
    assert [edge.destination_poi_id for edge in path.edges] == ["b", "c"]
    assert path.duration_minutes == 15


def test_find_route_returns_none_for_disconnected_graph() -> None:
    edges = [make_edge("a", "b"), make_edge("c", "d")]
    service = OfflineRouteService(FakeOfflineRepository(edges))

    assert service.find_route("a", "d") is None
    assert service.find_route("d", "a") is None


def test_find_route_returns_none_for_same_endpoint() -> None:
    service = OfflineRouteService(FakeOfflineRepository([make_edge("a", "b")]))

    assert service.find_route("a", "a") is None


def test_find_route_does_not_traverse_one_way_edge_in_reverse() -> None:
    edge = make_edge("a", "b", bidirectional=False)
    service = OfflineRouteService(FakeOfflineRepository([edge]))

    assert service.find_route("a", "b") is not None
    assert service.find_route("b", "a") is None


def test_reversed_route_instructions_do_not_misstate_direction() -> None:
    service = OfflineRouteService(OfflineRepository(DATABASE_PATH))

    to_bund = service.find_route("oriental-pearl-tower", "the-bund")
    from_bund = service.find_route("the-bund", "oriental-pearl-tower")

    assert to_bund is not None
    assert from_bund is not None
    assert to_bund.instructions == from_bund.instructions
    assert to_bund.instructions == ["地铁2号线连接南京东路站与陆家嘴站"]


def test_bidirectional_route_summaries_are_direction_neutral() -> None:
    repository = OfflineRepository(DATABASE_PATH)
    service = OfflineRouteService(repository)

    for edge in repository.list_route_edges():
        if not edge.is_bidirectional:
            continue
        assert not DIRECTIONAL_SUMMARY_PATTERN.search(edge.summary)
        reverse = service.find_route(edge.destination_poi_id, edge.origin_poi_id)
        assert reverse is not None
        for instruction in reverse.instructions:
            assert not DIRECTIONAL_SUMMARY_PATTERN.search(instruction)
