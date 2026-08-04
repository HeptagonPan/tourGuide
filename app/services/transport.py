from app.repositories.presets import PresetDataError, PresetRepository
from app.schemas.trip import TransportLeg, TransportOption, TripRequest


def build_transport_options(
    request: TripRequest,
    repository: PresetRepository,
) -> list[TransportOption]:
    """根据已核验的参考记录生成往返大交通候选。"""
    rail_prices = repository.find_prices(category="rail", origin_city=request.origin_city)
    if len(rail_prices) != 1:
        raise PresetDataError(f"高铁参考数据不唯一: {request.origin_city}")

    price = rail_prices[0]
    round_trip_travelers = request.traveler_count * 2
    leg = TransportLeg(
        origin=request.origin_city,
        destination="上海",
        mode="rail",
        price_min_cents=price.price_min_cents * round_trip_travelers,
        price_max_cents=price.price_max_cents * round_trip_travelers,
        source_id=price.id,
    )
    return [
        TransportOption.from_legs(
            id=f"rail-{request.origin_city}-shanghai",
            name=f"{request.origin_city}往返上海高铁",
            mode="rail",
            legs=[leg],
        )
    ]
