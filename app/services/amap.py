from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import BaseModel, Field


class AmapUnavailableError(RuntimeError):
    """高德服务无法提供可靠结果。"""


class AmapRouteStep(BaseModel):
    """归一化后的单段市内路线。"""

    instruction: str
    mode: str
    distance_meters: int = Field(ge=0)
    duration_minutes: int = Field(ge=0)


class AmapRoute(BaseModel):
    """归一化后的高德公交路线。"""

    source: str = "amap"
    queried_at: datetime
    duration_minutes: int = Field(ge=0)
    distance_meters: int = Field(ge=0)
    cost_cents: int = Field(ge=0)
    steps: list[AmapRouteStep] = Field(min_length=1)


class AmapPoi(BaseModel):
    """归一化后的高德地点。"""

    id: str
    name: str
    longitude: float
    latitude: float
    address: str
    typecode: str
    source: str = "amap"
    queried_at: datetime


class AmapWeather(BaseModel):
    """归一化后的高德实况天气。"""

    city: str
    weather: str
    temperature_celsius: int
    wind_direction: str
    wind_power: str
    humidity_percent: int = Field(ge=0, le=100)
    reported_at: str
    source: str = "amap"
    queried_at: datetime


class AmapClient:
    """高德 Web 服务的异步适配器。"""

    def __init__(
        self,
        *,
        web_key: str,
        timeout_seconds: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._web_key = web_key
        self._client = http_client or httpx.AsyncClient(
            base_url="https://restapi.amap.com",
            timeout=timeout_seconds,
        )
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        """关闭由适配器创建的 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def search_pois(self, *, keywords: str, city: str) -> list[AmapPoi]:
        """搜索地点并返回稳定的项目内部结构。"""
        payload = await self._get(
            "/v5/place/text",
            params={"keywords": keywords, "region": city, "show_fields": "business"},
        )
        queried_at = datetime.now(UTC)
        results: list[AmapPoi] = []
        for poi in payload.get("pois", []):
            longitude, latitude = self._parse_location(poi.get("location"))
            results.append(
                AmapPoi(
                    id=str(poi.get("id", "")),
                    name=str(poi.get("name", "")),
                    longitude=longitude,
                    latitude=latitude,
                    address=self._as_text(poi.get("address")),
                    typecode=self._as_text(poi.get("typecode")),
                    queried_at=queried_at,
                )
            )
        return results

    async def get_route(self, *, origin: str, destination: str) -> AmapRoute:
        """查询公交路线并将秒、米和元转换为内部单位。"""
        payload = await self._get(
            "/v5/direction/transit/integrated",
            params={
                "origin": origin,
                "destination": destination,
                "city1": "上海",
                "city2": "上海",
            },
        )
        transits = payload.get("route", {}).get("transits", [])
        if not transits:
            raise AmapUnavailableError("高德未返回可用路线")

        transit = transits[0]
        steps = self._normalize_route_steps(transit.get("segments", []))
        if not steps:
            raise AmapUnavailableError("高德路线缺少可用步骤")
        return AmapRoute(
            queried_at=datetime.now(UTC),
            duration_minutes=self._seconds_to_minutes(transit.get("duration")),
            distance_meters=self._to_non_negative_int(transit.get("distance")),
            cost_cents=self._yuan_to_cents(transit.get("cost")),
            steps=steps,
        )

    async def get_weather(self, *, city: str) -> AmapWeather:
        """查询城市实况天气并返回稳定字段。"""
        payload = await self._get(
            "/v3/weather/weatherInfo",
            params={"city": city, "extensions": "base"},
        )
        lives = payload.get("lives", [])
        if not lives:
            raise AmapUnavailableError("高德未返回可用天气")

        live = lives[0]
        return AmapWeather(
            city=self._as_text(live.get("city")),
            weather=self._as_text(live.get("weather")),
            temperature_celsius=self._to_int(live.get("temperature")),
            wind_direction=self._as_text(live.get("winddirection")),
            wind_power=self._as_text(live.get("windpower")),
            humidity_percent=self._to_non_negative_int(live.get("humidity")),
            reported_at=self._as_text(live.get("reporttime")),
            queried_at=datetime.now(UTC),
        )

    async def _get(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        request_params = {**params, "key": self._web_key}
        for attempt in range(2):
            try:
                response = await self._client.get(path, params=request_params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 0:
                    continue
                raise AmapUnavailableError("高德服务暂时不可用") from exc

            if response.status_code >= 500:
                if attempt == 0:
                    continue
                raise AmapUnavailableError("高德服务暂时不可用")
            if response.status_code >= 400:
                raise AmapUnavailableError(f"高德请求失败，状态码 {response.status_code}")

            try:
                payload = response.json()
            except ValueError as exc:
                raise AmapUnavailableError("高德返回了无法解析的数据") from exc
            if payload.get("status") != "1":
                info = self._as_text(payload.get("info")) or "未知错误"
                raise AmapUnavailableError(f"高德返回业务错误: {info}")
            return payload

        raise AmapUnavailableError("高德服务暂时不可用")

    def _normalize_route_steps(self, segments: list[dict[str, Any]]) -> list[AmapRouteStep]:
        steps: list[AmapRouteStep] = []
        for segment in segments:
            walking = segment.get("walking") or {}
            for walking_step in walking.get("steps", []):
                steps.append(
                    AmapRouteStep(
                        instruction=self._as_text(walking_step.get("instruction")),
                        mode="walking",
                        distance_meters=self._to_non_negative_int(walking_step.get("distance")),
                        duration_minutes=self._seconds_to_minutes(walking.get("duration")),
                    )
                )

            bus = segment.get("bus") or {}
            for busline in bus.get("buslines", []):
                departure = self._as_text((busline.get("departure_stop") or {}).get("name"))
                arrival = self._as_text((busline.get("arrival_stop") or {}).get("name"))
                name = self._as_text(busline.get("name"))
                steps.append(
                    AmapRouteStep(
                        instruction=f"乘坐{name}：{departure}至{arrival}",
                        mode="transit",
                        distance_meters=self._to_non_negative_int(busline.get("distance")),
                        duration_minutes=self._seconds_to_minutes(busline.get("duration")),
                    )
                )
        return steps

    @staticmethod
    def _parse_location(value: Any) -> tuple[float, float]:
        try:
            longitude, latitude = str(value).split(",", maxsplit=1)
            return float(longitude), float(latitude)
        except (TypeError, ValueError) as exc:
            raise AmapUnavailableError("高德地点坐标格式无效") from exc

    @staticmethod
    def _seconds_to_minutes(value: Any) -> int:
        seconds = AmapClient._to_non_negative_int(value)
        return (seconds + 59) // 60

    @staticmethod
    def _yuan_to_cents(value: Any) -> int:
        try:
            return int(Decimal(str(value or "0")) * 100)
        except (InvalidOperation, ValueError) as exc:
            raise AmapUnavailableError("高德路线费用格式无效") from exc

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError) as exc:
            raise AmapUnavailableError("高德数值格式无效") from exc

    @staticmethod
    def _to_non_negative_int(value: Any) -> int:
        result = AmapClient._to_int(value or 0)
        if result < 0:
            raise AmapUnavailableError("高德数值不能为负数")
        return result

    @staticmethod
    def _as_text(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return "" if value is None else str(value)
