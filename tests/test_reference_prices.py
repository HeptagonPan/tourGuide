import json
from datetime import date

import pytest

from app.repositories.presets import PresetDataError, PresetRepository

EXPECTED_ORIGINS = {
    "合肥",
    "芜湖",
    "蚌埠",
    "淮南",
    "阜阳",
    "安庆",
    "黄山",
    "马鞍山",
    "滁州",
    "南京",
}


def test_every_reference_price_is_traceable(repository: PresetRepository) -> None:
    records = repository.load_reference_prices()

    assert records
    for record in records:
        assert str(record.source_url).startswith("https://")
        assert record.observed_at <= date.today()
        assert record.price_min_cents >= 0
        assert record.price_max_cents >= record.price_min_cents
        assert record.valid_to >= record.valid_from


def test_rail_prices_cover_every_supported_origin(repository: PresetRepository) -> None:
    records = repository.find_prices(category="rail")

    assert {record.origin_city for record in records} == EXPECTED_ORIGINS


def test_hotel_prices_cover_three_budget_tiers(repository: PresetRepository) -> None:
    records = repository.find_prices(category="hotel")

    assert {record.tier for record in records} == {"economy", "comfort", "quality"}


def test_find_prices_filters_by_origin(repository: PresetRepository) -> None:
    records = repository.find_prices(category="rail", origin_city="淮南")

    assert len(records) == 1
    assert records[0].destination_city == "上海"


def test_duplicate_reference_ids_are_rejected(tmp_path) -> None:
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    duplicate_record = {
        "id": "duplicate",
        "category": "rail",
        "origin_city": "合肥",
        "destination_city": "上海",
        "name": "测试票价",
        "tier": None,
        "price_min_cents": 20_300,
        "price_max_cents": 41_600,
        "source_url": "https://trains.ctrip.com/",
        "observed_at": "2026-08-04",
        "valid_from": "2026-08-05",
        "valid_to": "2026-08-05",
    }
    (reference_dir / "prices.json").write_text(
        json.dumps([duplicate_record, duplicate_record], ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(PresetDataError, match="存在重复 ID"):
        PresetRepository(data_dir=tmp_path).load_reference_prices()
