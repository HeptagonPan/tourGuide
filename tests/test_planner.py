from datetime import UTC, datetime

import pytest

from app.repositories.presets import PresetRepository
from app.schemas.trip import TripPlan
from app.services.amap import AmapPoi, AmapRoute, AmapRouteStep, AmapUnavailableError
from app.services.planner import Planner


class FakeAmapClient:
    """提供稳定地点与路线的高德替身。"""

    async def search_pois(self, *, keywords: str, city: str) -> list[AmapPoi]:
        del city
        suffix = sum(ord(character) for character in keywords) % 1000
        return [
            AmapPoi(
                id=f"AMAP-{suffix}",
                name=keywords,
                longitude=121.47 + suffix / 100_000,
                latitude=31.23 + suffix / 100_000,
                address="上海市",
                typecode="110000",
                queried_at=datetime.now(UTC),
            )
        ]

    async def get_route(self, *, origin: str, destination: str) -> AmapRoute:
        del origin, destination
        return AmapRoute(
            queried_at=datetime.now(UTC),
            duration_minutes=18,
            distance_meters=2400,
            cost_cents=300,
            steps=[
                AmapRouteStep(
                    instruction="乘坐地铁前往下一站",
                    mode="transit",
                    distance_meters=2400,
                    duration_minutes=18,
                )
            ],
        )


class FailingRouteAmapClient(FakeAmapClient):
    """模拟无法验证相邻地点路线。"""

    async def get_route(self, *, origin: str, destination: str) -> AmapRoute:
        del origin, destination
        raise AmapUnavailableError("测试路线不可用")


@pytest.mark.asyncio
async def test_planner_builds_grounded_regional_days(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-03",
        interests=["culture", "food", "night_view"],
    )
    planner = Planner(repository=PresetRepository(), amap_client=FakeAmapClient())

    plan = await planner.generate(request)

    assert isinstance(plan, TripPlan)
    assert plan.destination == "上海"
    assert len(plan.days) == 2
    for day in plan.days:
        assert 1 <= len(day.activities) <= 4
        assert len({activity.region for activity in day.activities}) == 1
        assert len(day.routes) == len(day.activities) - 1
        assert all(activity.source_ids for activity in day.activities)
        assert all(route.source_ids for route in day.routes)
    assert plan.budget.total_cents == sum(plan.budget.categories.values())
    assert plan.source_ids


@pytest.mark.asyncio
async def test_planner_drops_unroutable_adjacent_activity(request_factory) -> None:
    request = request_factory(
        start_date="2026-10-02",
        end_date="2026-10-02",
        interests=["culture", "food", "night_view"],
    )
    planner = Planner(repository=PresetRepository(), amap_client=FailingRouteAmapClient())

    plan = await planner.generate(request)

    assert len(plan.days[0].activities) == 1
    assert plan.days[0].routes == []
