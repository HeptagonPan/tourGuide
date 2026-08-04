import json
from pathlib import Path

import httpx
import pytest

from app.services.amap import AmapClient, AmapUnavailableError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "amap_transit.json"
AMAP_TRANSIT_FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def amap_client() -> AmapClient:
    """返回使用测试密钥的高德客户端。"""
    return AmapClient(web_key="test-key", timeout_seconds=0.1)


@pytest.mark.asyncio
async def test_get_route_normalizes_amap_response(amap_client, respx_mock) -> None:
    route_mock = respx_mock.get(path="/v5/direction/transit/integrated").mock(
        return_value=httpx.Response(200, json=AMAP_TRANSIT_FIXTURE)
    )

    route = await amap_client.get_route(origin="121.47,31.23", destination="121.49,31.24")

    assert route.source == "amap"
    assert route.duration_minutes == 31
    assert route.distance_meters == 6200
    assert route.cost_cents == 400
    assert [step.instruction for step in route.steps] == [
        "步行至南京东路站",
        "乘坐地铁2号线：南京东路至陆家嘴",
    ]
    assert route_mock.call_count == 1


@pytest.mark.asyncio
async def test_get_route_retries_one_timeout(amap_client, respx_mock) -> None:
    route_mock = respx_mock.get(path="/v5/direction/transit/integrated").mock(
        side_effect=[
            httpx.ReadTimeout("第一次超时"),
            httpx.Response(200, json=AMAP_TRANSIT_FIXTURE),
        ]
    )

    route = await amap_client.get_route(origin="121.47,31.23", destination="121.49,31.24")

    assert route.duration_minutes == 31
    assert route_mock.call_count == 2


@pytest.mark.asyncio
async def test_get_route_raises_after_two_transport_failures(amap_client, respx_mock) -> None:
    route_mock = respx_mock.get(path="/v5/direction/transit/integrated").mock(
        side_effect=httpx.ConnectError("连接失败")
    )

    with pytest.raises(AmapUnavailableError, match="高德服务暂时不可用"):
        await amap_client.get_route(origin="121.47,31.23", destination="121.49,31.24")

    assert route_mock.call_count == 2


@pytest.mark.asyncio
async def test_business_error_is_not_retried(amap_client, respx_mock) -> None:
    route_mock = respx_mock.get(path="/v5/direction/transit/integrated").mock(
        return_value=httpx.Response(200, json={"status": "0", "info": "INVALID_USER_KEY"})
    )

    with pytest.raises(AmapUnavailableError, match="高德返回业务错误"):
        await amap_client.get_route(origin="121.47,31.23", destination="121.49,31.24")

    assert route_mock.call_count == 1


@pytest.mark.asyncio
async def test_search_pois_normalizes_results(amap_client, respx_mock) -> None:
    respx_mock.get(path="/v5/place/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "B001",
                        "name": "上海博物馆",
                        "location": "121.475,31.228",
                        "address": "人民大道201号",
                        "typecode": "140100",
                    }
                ],
            },
        )
    )

    pois = await amap_client.search_pois(keywords="博物馆", city="上海")

    assert pois[0].id == "B001"
    assert pois[0].longitude == 121.475
    assert pois[0].latitude == 31.228
    assert pois[0].source == "amap"


@pytest.mark.asyncio
async def test_get_weather_normalizes_live_weather(amap_client, respx_mock) -> None:
    respx_mock.get(path="/v3/weather/weatherInfo").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "lives": [
                    {
                        "city": "上海市",
                        "weather": "晴",
                        "temperature": "29",
                        "winddirection": "东南",
                        "windpower": "≤3",
                        "humidity": "61",
                        "reporttime": "2026-08-04 12:00:00",
                    }
                ],
            },
        )
    )

    weather = await amap_client.get_weather(city="上海")

    assert weather.city == "上海市"
    assert weather.temperature_celsius == 29
    assert weather.humidity_percent == 61
    assert weather.source == "amap"
