from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator

SUPPORTED_ORIGIN_CITIES = frozenset(
    {"合肥", "芜湖", "蚌埠", "淮南", "阜阳", "安庆", "黄山", "马鞍山", "滁州", "南京"}
)
SUPPORTED_INTERESTS = frozenset({"food", "nature", "culture", "family", "shopping", "night_view"})


class Relationship(StrEnum):
    """同行关系选项。"""

    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"
    COLLEAGUES = "colleagues"
    OTHER = "other"


class IntercityPreference(StrEnum):
    """大交通选择偏好。"""

    BALANCED = "balanced"
    RAIL = "rail"
    FLIGHT = "flight"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"


class LocalTransportPreference(StrEnum):
    """上海市内交通偏好。"""

    BALANCED = "balanced"
    METRO = "metro"
    LESS_WALKING = "less_walking"
    TAXI = "taxi"


class TripRequest(BaseModel):
    """经过校验的七步问卷输入。"""

    origin_city: str
    adults: int = Field(ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    rooms: int | None = Field(default=None, ge=1)
    relationship: Relationship
    start_date: date
    end_date: date
    budget_cents: int = Field(ge=10_000)
    budget_includes_intercity: bool = True
    interests: list[str] = Field(min_length=1)
    intercity_preference: IntercityPreference = IntercityPreference.BALANCED
    local_transport_preference: LocalTransportPreference = LocalTransportPreference.BALANCED

    @model_validator(mode="after")
    def validate_trip_constraints(self) -> "TripRequest":
        """校验需要多个字段共同判断的旅行约束。"""
        if self.origin_city not in SUPPORTED_ORIGIN_CITIES:
            raise ValueError("暂不支持该出发城市")
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于出发日期")
        if self.trip_days > 14:
            raise ValueError("旅行天数不能超过 14 天")
        if self.rooms is not None and self.rooms > self.traveler_count:
            raise ValueError("房间数不能超过同行总人数")

        unknown_interests = set(self.interests) - SUPPORTED_INTERESTS
        if unknown_interests:
            raise ValueError("包含暂不支持的旅行兴趣")
        return self

    @property
    def traveler_count(self) -> int:
        """返回成人和儿童的总人数。"""
        return self.adults + self.children

    @property
    def trip_days(self) -> int:
        """按包含首尾日期的方式计算旅行天数。"""
        return (self.end_date - self.start_date).days + 1


class CityPreset(BaseModel):
    """预设出发城市及其交通枢纽。"""

    name: str
    province: str
    railway_stations: list[str] = Field(min_length=1)
    nearby_airports: list[str] = Field(min_length=1)


class InterestPreset(BaseModel):
    """问卷兴趣选项与高德 POI 分类映射。"""

    id: str
    label: str
    poi_categories: list[str] = Field(min_length=1)


class SourceLink(BaseModel):
    """外部事实的最小来源标识。"""

    id: str
    url: HttpUrl
