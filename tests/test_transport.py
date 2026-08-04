from app.schemas.trip import TransportLeg, TransportOption
from app.services.transport import build_transport_options


def test_direct_rail_option_uses_verified_reference(request_factory, repository) -> None:
    request = request_factory(origin_city="南京", adults=2, children=0)

    options = build_transport_options(request, repository)

    assert len(options) == 1
    assert options[0].mode == "rail"
    assert options[0].price_min_cents == 2 * 2 * 10_100
    assert options[0].price_max_cents == 2 * 2 * 16_950
    assert options[0].source_ids == ["rail-nanjing-shanghai-20260805"]


def test_multileg_option_adds_each_segment_cost() -> None:
    option = TransportOption.from_legs(
        id="huainan-hefei-flight-shanghai",
        name="淮南经合肥飞往上海",
        mode="flight",
        legs=[
            TransportLeg(
                origin="淮南",
                destination="合肥新桥国际机场",
                mode="transfer",
                price_min_cents=8_000,
                price_max_cents=12_000,
                source_id="amap-transfer-example",
            ),
            TransportLeg(
                origin="合肥新桥国际机场",
                destination="上海虹桥国际机场",
                mode="flight",
                price_min_cents=30_000,
                price_max_cents=60_000,
                source_id="ctrip-flight-example",
            ),
        ],
    )

    assert option.price_min_cents == 38_000
    assert option.price_max_cents == 72_000
    assert option.source_ids == ["amap-transfer-example", "ctrip-flight-example"]
