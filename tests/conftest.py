from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.presets import PresetRepository
from app.schemas.trip import (
    AccommodationPlan,
    BudgetBreakdown,
    ItineraryActivity,
    TransportLeg,
    TransportOption,
    TripDay,
    TripPlan,
    TripRequest,
)


@pytest.fixture
def valid_request_data() -> dict[str, Any]:
    """提供一份可复用的有效问卷数据。"""
    return {
        "origin_city": "合肥",
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "relationship": "couple",
        "start_date": "2026-10-02",
        "end_date": "2026-10-05",
        "budget_cents": 600_000,
        "budget_includes_intercity": True,
        "interests": ["food", "culture"],
        "intercity_preference": "balanced",
        "local_transport_preference": "metro",
    }


@pytest.fixture
def request_factory(
    valid_request_data: dict[str, Any],
) -> Callable[..., TripRequest]:
    """按需覆盖字段并构造问卷模型。"""

    def factory(**overrides: Any) -> TripRequest:
        data = deepcopy(valid_request_data)
        data.update(overrides)
        return TripRequest.model_validate(data)

    return factory


@pytest.fixture
def repository() -> PresetRepository:
    """返回使用项目真实预设文件的数据仓库。"""
    return PresetRepository()


@pytest.fixture
def sample_plan(request_factory: Callable[..., TripRequest]) -> TripPlan:
    """提供页面、API 与导出测试共用的完整计划。"""
    request = request_factory(start_date="2026-10-02", end_date="2026-10-02")
    transport = TransportOption.from_legs(
        id="rail-hefei-shanghai",
        name="合肥往返上海高铁",
        mode="rail",
        legs=[
            TransportLeg(
                origin="合肥",
                destination="上海",
                mode="rail",
                price_min_cents=78_800,
                price_max_cents=166_400,
                source_id="rail-hefei-shanghai-20260805",
            )
        ],
    )
    accommodation = AccommodationPlan(
        rooms=1,
        nights=1,
        tier="comfort",
        nightly_min_cents=25_000,
        nightly_max_cents=45_000,
        total_min_cents=25_000,
        total_max_cents=45_000,
        source_ids=["hotel-shanghai-comfort-20260804"],
    )
    budget = BudgetBreakdown(
        categories={
            "intercity": 122_600,
            "accommodation": 35_000,
            "dining": 20_000,
            "attractions": 0,
            "local_transport": 600,
            "reserve": 17_820,
        },
        total_cents=196_020,
        remaining_cents=403_980,
        is_over_budget=False,
    )
    day = TripDay(
        date="2026-10-02",
        activities=[
            ItineraryActivity(
                slot="上午",
                name="上海博物馆",
                region="黄浦",
                longitude=121.475,
                latitude=31.228,
                duration_minutes=150,
                cost_cents=0,
                source_ids=["amap-poi:B001"],
            )
        ],
        routes=[],
    )
    return TripPlan(
        request=request,
        transport_options=[transport],
        selected_transport=transport,
        accommodation=accommodation,
        budget=budget,
        days=[day],
        source_ids=[
            "rail-hefei-shanghai-20260805",
            "hotel-shanghai-comfort-20260804",
            "amap-poi:B001",
        ],
        data_updated_at="2026-08-04",
        narrative="一天内从人民广场开始，节奏从容。",
    )


@pytest.fixture
def client(sample_plan: TripPlan) -> TestClient:
    """返回注入固定规划与文字服务的测试客户端。"""

    class FixedPlanner:
        async def generate(self, request: TripRequest) -> TripPlan:
            return sample_plan.model_copy(update={"request": request})

    class FixedNarrator:
        async def describe(self, plan: TripPlan) -> str:
            return plan.narrative

    return TestClient(
        create_app(
            planner=FixedPlanner(),
            narrator=FixedNarrator(),
            repository=PresetRepository(),
        )
    )
