from datetime import UTC
from pathlib import Path

import pytest

from app.repositories.offline import OfflineRepository
from app.repositories.presets import PresetRepository
from app.schemas.offline import OfflinePoi, OfflineRoutePath
from app.schemas.trip import TripPlan
from app.services.offline_routes import OfflineRouteService
from app.services.planner import Planner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data/offline/shanghai.db"

GENERATED_SOURCE_PREFIXES = (
    "offline-poi:",
    "offline-route:",
    "rail-",
    "hotel-",
    "assumption:",
)


def offline_repository() -> OfflineRepository:
    """返回指向项目内置上海数据库的真实只读仓库。"""
    return OfflineRepository(DATABASE_PATH)


def raw_offline_source_ids() -> frozenset[str]:
    """返回数据库内置景点与路线边的原始来源标识。"""
    repository = offline_repository()
    return frozenset(
        {poi.source_id for poi in repository.list_pois([])}
        | {edge.source_id for edge in repository.list_route_edges()}
    )


def make_planner(route_service: OfflineRouteService | None = None) -> Planner:
    """构造使用真实离线仓库和路线服务的规划器。"""
    repository = offline_repository()
    return Planner(
        repository=PresetRepository(),
        offline_repository=repository,
        route_service=route_service or OfflineRouteService(repository),
    )


class DisconnectedRouteService:
    """模拟完全断开的离线路线图。"""

    def find_route(self, origin_poi_id: str, destination_poi_id: str) -> None:
        del origin_poi_id, destination_poi_id
        return None


class PartiallyDisconnectedRouteService:
    """断开指定景点，验证规划器跳过该活动而不是编造路线。"""

    def __init__(self, real_service: OfflineRouteService, disconnected_poi_id: str) -> None:
        self._real_service = real_service
        self._disconnected_poi_id = disconnected_poi_id

    def find_route(self, origin_poi_id: str, destination_poi_id: str) -> OfflineRoutePath | None:
        if self._disconnected_poi_id in (origin_poi_id, destination_poi_id):
            return None
        return self._real_service.find_route(origin_poi_id, destination_poi_id)


def expected_first_day_names(repository: OfflineRepository, interests: list[str]) -> list[str]:
    """按简报排序规则推导第一天的活动名单：同片区优先、通用景点次优先、名称稳定排序。"""
    grouped: dict[str, list[OfflinePoi]] = {}
    for poi in repository.list_pois(interests):
        grouped.setdefault(poi.area, []).append(poi)
    area_groups = sorted(grouped.values(), key=lambda group: (-len(group), group[0].area))
    first_group = sorted(area_groups[0], key=lambda poi: (poi.is_general_highlight, poi.name))
    return [poi.name for poi in first_group[:4]]


@pytest.mark.asyncio
async def test_planner_builds_grounded_offline_days(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-03",
        interests=["culture", "food", "night_view"],
    )
    repository = offline_repository()
    planner = make_planner()

    plan = await planner.generate(request)

    assert isinstance(plan, TripPlan)
    assert plan.destination == "上海"
    assert len(plan.days) == 2
    poi_by_id = {poi.id: poi for poi in repository.list_pois(request.interests)}
    raw_sources = raw_offline_source_ids()
    for day in plan.days:
        assert 1 <= len(day.activities) <= 4
        assert len(day.routes) == len(day.activities) - 1
        for activity in day.activities:
            poi = poi_by_id[activity.source_ids[0].removeprefix("offline-poi:")]
            assert activity.source_ids == [f"offline-poi:{poi.id}", poi.source_id]
            assert activity.name == poi.name
            assert activity.duration_minutes == poi.suggested_duration_minutes
            assert activity.cost_cents == poi.admission_cents
        for route in day.routes:
            origin_id, destination_id = (
                route.source_ids[0].removeprefix("offline-route:").split(":", maxsplit=1)
            )
            assert route.origin_name == poi_by_id[origin_id].name
            assert route.destination_name == poi_by_id[destination_id].name
            assert all(source_id in raw_sources for source_id in route.source_ids[1:])
            assert route.instructions
            assert route.duration_minutes >= 1
            assert route.queried_at.tzinfo is UTC
    assert any(source_id.startswith("offline-poi:") for source_id in plan.source_ids)
    assert any(source_id.startswith("offline-route:") for source_id in plan.source_ids)
    assert all(
        source_id.startswith(GENERATED_SOURCE_PREFIXES) or source_id in raw_sources
        for source_id in plan.source_ids
    )
    assert not any(source_id.startswith("amap-") for source_id in plan.source_ids)


@pytest.mark.asyncio
async def test_planner_drops_unroutable_activity(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-02",
        interests=["culture", "food", "night_view"],
    )
    planner = make_planner(route_service=DisconnectedRouteService())

    plan = await planner.generate(request)

    assert len(plan.days) == 1
    day = plan.days[0]
    assert len(day.activities) == 1
    assert day.routes == []
    assert len(day.routes) == len(day.activities) - 1
    assert day.activities[0].source_ids[0].startswith("offline-poi:")


@pytest.mark.asyncio
async def test_planner_drops_disconnected_poi_instead_of_inventing_route(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-02",
        interests=["culture", "food", "night_view"],
    )
    repository = offline_repository()
    expected_names = expected_first_day_names(repository, request.interests)
    pois_by_name = {poi.name: poi for poi in repository.list_pois(request.interests)}
    disconnected = pois_by_name[expected_names[1]]
    planner = make_planner(
        route_service=PartiallyDisconnectedRouteService(
            OfflineRouteService(repository), disconnected.id
        )
    )

    plan = await planner.generate(request)

    day = plan.days[0]
    assert [activity.name for activity in day.activities] == [
        name for name in expected_names if name != disconnected.name
    ]
    assert len(day.routes) == len(day.activities) - 1
    assert disconnected.name not in {activity.name for activity in day.activities}


@pytest.mark.asyncio
async def test_planner_orders_candidates_by_area_highlight_then_name(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-02",
        interests=["culture", "food", "night_view"],
    )
    repository = offline_repository()
    planner = make_planner()

    plan = await planner.generate(request)

    activities = plan.days[0].activities
    pois_by_name = {poi.name: poi for poi in repository.list_pois(request.interests)}
    assert len({activity.region for activity in activities}) == 1
    grouped_names: dict[bool, list[str]] = {False: [], True: []}
    for activity in activities:
        poi = pois_by_name[activity.name]
        grouped_names[poi.is_general_highlight].append(activity.name)
    highlight_flags = [pois_by_name[activity.name].is_general_highlight for activity in activities]
    assert highlight_flags == sorted(highlight_flags)
    for names in grouped_names.values():
        assert names == sorted(names)


@pytest.mark.asyncio
async def test_planner_fills_gaps_with_same_area_general_highlights(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-11",
        interests=["shopping"],
    )
    repository = offline_repository()
    planner = make_planner()

    plan = await planner.generate(request)

    assert len(plan.days) == 10
    shopping_pois = repository.list_pois(["shopping"])
    shopping_ids = {poi.id for poi in shopping_pois}
    shopping_areas = {poi.area for poi in shopping_pois}
    all_pois_by_id = {poi.id: poi for poi in repository.list_pois([])}
    used_pois: list[OfflinePoi] = []
    for day in plan.days:
        assert 1 <= len(day.activities) <= 4
        assert len(day.routes) == len(day.activities) - 1
        for activity in day.activities:
            poi = all_pois_by_id[activity.source_ids[0].removeprefix("offline-poi:")]
            used_pois.append(poi)
            assert poi.id in shopping_ids or (
                poi.is_general_highlight and poi.area in shopping_areas
            )
    assert any(poi.is_general_highlight and poi.id not in shopping_ids for poi in used_pois)
