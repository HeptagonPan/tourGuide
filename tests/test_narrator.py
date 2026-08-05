from pathlib import Path

import httpx
import pytest

from app.repositories.offline import OfflineRepository
from app.repositories.presets import PresetRepository
from app.services.narrator import Narrator
from app.services.offline_routes import OfflineRouteService
from app.services.planner import Planner


def make_planner() -> Planner:
    """构造使用真实离线仓库和路线服务的规划器。"""
    repository = OfflineRepository(Path(__file__).resolve().parents[1] / "data/offline/shanghai.db")
    return Planner(
        repository=PresetRepository(),
        offline_repository=repository,
        route_service=OfflineRouteService(repository),
    )


@pytest.mark.asyncio
async def test_narrator_falls_back_without_changing_facts(request_factory) -> None:
    request = request_factory(start_date="2026-10-02", end_date="2026-10-02")
    plan = await make_planner().generate(request)

    def fail_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Ollama 未启动", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail_request)) as client:
        text = await Narrator(http_client=client).describe(plan)

    assert plan.destination in text
    assert f"¥{plan.budget.total_cents / 100:,.0f}" in text
    assert plan.days[0].activities[0].name in text
    assert "暂未连接本地模型" not in text


@pytest.mark.asyncio
async def test_narrator_uses_nonempty_local_model_response(request_factory) -> None:
    request = request_factory(start_date="2026-10-02", end_date="2026-10-02")
    plan = await make_planner().generate(request)

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "上海行程已按区域整理。"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        text = await Narrator(http_client=client).describe(plan)

    assert text == "上海行程已按区域整理。"
