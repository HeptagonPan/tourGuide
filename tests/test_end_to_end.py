import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.presets import PresetRepository
from app.schemas.trip import TripPlan, TripRequest
from app.services.narrator import Narrator


class FixedPlanner:
    """返回固定且完整的已核验计划。"""

    def __init__(self, plan: TripPlan) -> None:
        self._plan = plan

    async def generate(self, request: TripRequest) -> TripPlan:
        return self._plan.model_copy(update={"request": request})


class FailingHttpClient:
    """模拟未启动的本地 Ollama。"""

    async def post(self, url: str, **kwargs):
        del kwargs
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("Ollama 未启动", request=request)


def test_full_flow_succeeds_when_local_model_is_offline(
    sample_plan: TripPlan,
    valid_request_data,
) -> None:
    client = TestClient(
        create_app(
            planner=FixedPlanner(sample_plan),
            narrator=Narrator(http_client=FailingHttpClient()),
            repository=PresetRepository(),
        )
    )

    options_response = client.get("/api/options")
    plan_response = client.post("/api/plans", json=valid_request_data)
    plan = plan_response.json()
    result_response = client.post("/result", json=plan)
    export_response = client.post("/api/export", json=plan)

    assert options_response.status_code == 200
    assert plan_response.status_code == 200
    assert result_response.status_code == 200
    assert export_response.status_code == 200
    assert plan["narrative"]
    assert all(activity["source_ids"] for day in plan["days"] for activity in day["activities"])
    assert all(route["source_ids"] for day in plan["days"] for route in day["routes"])
    assert "预算明细" in export_response.text
    assert "localhost" not in export_response.text
