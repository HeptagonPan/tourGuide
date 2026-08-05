import httpx
from fastapi.testclient import TestClient

from app.main import create_app

_real_async_client = httpx.AsyncClient


class OfflineOnlyTransport(httpx.AsyncBaseTransport):
    """只允许本机回环请求，其余目标一律视为外部网络访问。"""

    def __init__(self) -> None:
        self._inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "127.0.0.1":
            raise AssertionError(f"禁止外部网络请求: {request.url}")
        return await self._inner.handle_async_request(request)


def guarded_async_client(*args, **kwargs):
    """构造始终拦截外部网络目标的异步客户端。"""
    kwargs.setdefault("transport", OfflineOnlyTransport())
    return _real_async_client(*args, **kwargs)


def test_full_offline_flow_works_without_external_network(
    monkeypatch,
    valid_request_data,
) -> None:
    """无高德密钥且禁止外部网络时，默认离线流程仍完成规划、页面与导出。"""
    monkeypatch.delenv("AMAP_WEB_KEY", raising=False)
    monkeypatch.delenv("AMAP_JS_KEY", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", guarded_async_client)

    client = TestClient(create_app())

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
    activities = [activity for day in plan["days"] for activity in day["activities"]]
    routes = [route for day in plan["days"] for route in day["routes"]]
    assert activities
    assert routes
    assert all(
        any(source.startswith("offline-poi:") for source in activity["source_ids"])
        for activity in activities
    )
    assert all(
        any(source.startswith("offline-route:") for source in route["source_ids"])
        for route in routes
    )
    export_html = export_response.text
    assert "预算明细" in export_html
    assert "restapi.amap.com" not in export_html
    assert "AMAP_WEB_KEY" not in export_html
    assert "localhost" not in export_html
