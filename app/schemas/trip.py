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


class ReferenceCategory(StrEnum):
    """可维护的参考价格类别。"""

    HOTEL = "hotel"
    ATTRACTION = "attraction"
    RAIL = "rail"
    FLIGHT = "flight"


class TransportMode(StrEnum):
    """大交通或接驳段的方式。"""

    RAIL = "rail"
    FLIGHT = "flight"
    TRANSFER = "transfer"


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


class ReferencePrice(BaseModel):
    """一条带采集时间和来源链接的参考价格。"""

    id: str = Field(min_length=1)
    category: ReferenceCategory
    origin_city: str | None = None
    destination_city: str
    name: str = Field(min_length=1)
    tier: str | None = None
    price_min_cents: int = Field(ge=0)
    price_max_cents: int = Field(ge=0)
    source_url: HttpUrl
    observed_at: date
    valid_from: date
    valid_to: date

    @model_validator(mode="after")
    def validate_price_range(self) -> "ReferencePrice":
        """保证价格和适用日期区间有效。"""
        if self.price_max_cents < self.price_min_cents:
            raise ValueError("最高参考价格不能低于最低参考价格")
        if self.valid_to < self.valid_from:
            raise ValueError("参考价格适用结束日期不能早于开始日期")
        if self.category is ReferenceCategory.RAIL and self.origin_city is None:
            raise ValueError("高铁参考价格必须包含出发城市")
        return self


class AccommodationPlan(BaseModel):
    """住宿房间和参考价格计算结果。"""

    rooms: int = Field(ge=1)
    nights: int = Field(ge=1)
    tier: str
    nightly_min_cents: int = Field(ge=0)
    nightly_max_cents: int = Field(ge=0)
    total_min_cents: int = Field(ge=0)
    total_max_cents: int = Field(ge=0)
    source_ids: list[str] = Field(min_length=1)

    @property
    def estimated_cents(self) -> int:
        """返回住宿总区间的整数中点。"""
        return (self.total_min_cents + self.total_max_cents) // 2


class TransportLeg(BaseModel):
    """一段带价格来源的城际交通。"""

    origin: str
    destination: str
    mode: TransportMode
    price_min_cents: int = Field(ge=0)
    price_max_cents: int = Field(ge=0)
    source_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_price_range(self) -> "TransportLeg":
        if self.price_max_cents < self.price_min_cents:
            raise ValueError("交通最高参考价格不能低于最低参考价格")
        return self


class TransportOption(BaseModel):
    """由一段或多段交通组成的完整候选方案。"""

    id: str
    name: str
    mode: TransportMode
    legs: list[TransportLeg] = Field(min_length=1)
    price_min_cents: int = Field(ge=0)
    price_max_cents: int = Field(ge=0)
    source_ids: list[str] = Field(min_length=1)

    @classmethod
    def from_legs(
        cls,
        *,
        id: str,
        name: str,
        mode: TransportMode | str,
        legs: list[TransportLeg],
    ) -> "TransportOption":
        """累加每一段的费用和来源，避免遗漏接驳成本。"""
        return cls(
            id=id,
            name=name,
            mode=mode,
            legs=legs,
            price_min_cents=sum(leg.price_min_cents for leg in legs),
            price_max_cents=sum(leg.price_max_cents for leg in legs),
            source_ids=list(dict.fromkeys(leg.source_id for leg in legs)),
        )

    @property
    def estimated_cents(self) -> int:
        """返回交通总区间的整数中点。"""
        return (self.price_min_cents + self.price_max_cents) // 2


class BudgetBreakdown(BaseModel):
    """预算分类、余额和超支状态。"""

    categories: dict[str, int]
    total_cents: int
    remaining_cents: int
    is_over_budget: bool


class SourceLink(BaseModel):
    """外部事实的最小来源标识。"""

    id: str
    url: HttpUrl
