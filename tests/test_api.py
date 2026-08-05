import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.presets import PresetRepository
from app.schemas.trip import TripRequest


def test_create_plan_returns_grounded_plan(client, valid_request_data) -> None:
    response = client.post("/api/plans", json=valid_request_data)

    assert response.status_code == 200
    body = response.json()
    assert body["destination"] == "上海"
    assert body["days"]
    assert body["source_ids"]


def test_options_return_supported_questionnaire_values(client) -> None:
    response = client.get("/api/options")

    assert response.status_code == 200
    body = response.json()
    assert len(body["cities"]) == 10
    assert len(body["interests"]) == 6
    assert body["intercity_preferences"]
    assert body["local_transport_preferences"]


def test_invalid_plan_request_uses_simplified_chinese(client, valid_request_data) -> None:
    valid_request_data["adults"] = 0

    response = client.post("/api/plans", json=valid_request_data)

    assert response.status_code == 422
    assert response.json()["detail"] == "输入内容有误，请检查人数、日期、预算和选项"


def test_external_failure_returns_sanitized_503(valid_request_data) -> None:
    class FailingPlanner:
        async def generate(self, request: TripRequest):
            del request
            raise RuntimeError("AMAP_WEB_KEY=secret-value")

    client = TestClient(create_app(planner=FailingPlanner(), repository=PresetRepository()))

    response = client.post("/api/plans", json=valid_request_data)

    assert response.status_code == 503
    assert response.json() == {"detail": "规划服务暂时不可用，请稍后重试"}
    assert "secret-value" not in response.text
    assert "RuntimeError" not in response.text


def test_default_api_uses_offline_data_without_amap_key_or_network(
    monkeypatch,
    valid_request_data,
) -> None:
    """无 AMAP_WEB_KEY 且禁止网络时，默认 API 仍返回离线上海计划。"""
    monkeypatch.delenv("AMAP_WEB_KEY", raising=False)

    async def deny_network(*args, **kwargs):
        raise AssertionError("网络访问被禁止")

    monkeypatch.setattr(httpx.AsyncClient, "get", deny_network)
    client = TestClient(create_app())

    valid_request_data["end_date"] = "2026-10-02"
    response = client.post("/api/plans", json=valid_request_data)

    assert response.status_code == 200
    body = response.json()
    activities = [activity for day in body["days"] for activity in day["activities"]]
    assert activities
    assert all(
        any(source.startswith("offline-poi:") for source in activity["source_ids"])
        for activity in activities
    )
    routes = [route for day in body["days"] for route in day["routes"]]
    assert routes
    assert all(route["instructions"] for route in routes)
