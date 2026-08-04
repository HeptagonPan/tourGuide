from app.repositories.presets import PresetDataError, PresetRepository
from app.schemas.trip import AccommodationPlan, Relationship, TripRequest


def calculate_default_rooms(request: TripRequest) -> int:
    """根据显式选择或同行关系计算默认房间数。"""
    if request.rooms is not None:
        return request.rooms
    if request.relationship is Relationship.COUPLE:
        return 1
    return request.adults


def build_accommodation_plan(
    request: TripRequest,
    repository: PresetRepository,
    *,
    tier: str = "comfort",
) -> AccommodationPlan:
    """使用指定住宿档位计算房间和晚数的价格区间。"""
    matching_prices = [
        record for record in repository.find_prices(category="hotel") if record.tier == tier
    ]
    if len(matching_prices) != 1:
        raise PresetDataError(f"住宿档位数据不唯一: {tier}")

    price = matching_prices[0]
    rooms = calculate_default_rooms(request)
    nights = max(1, request.trip_days - 1)
    return AccommodationPlan(
        rooms=rooms,
        nights=nights,
        tier=tier,
        nightly_min_cents=price.price_min_cents,
        nightly_max_cents=price.price_max_cents,
        total_min_cents=price.price_min_cents * rooms * nights,
        total_max_cents=price.price_max_cents * rooms * nights,
        source_ids=[price.id],
    )
