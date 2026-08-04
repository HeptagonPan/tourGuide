import pytest
from pydantic import ValidationError

from app.schemas.trip import TripRequest


def test_trip_request_accepts_supported_origin(valid_request_data: dict) -> None:
    request = TripRequest.model_validate(valid_request_data)

    assert request.origin_city == "合肥"
    assert request.trip_days == 4


def test_trip_request_rejects_unsupported_origin(valid_request_data: dict) -> None:
    valid_request_data["origin_city"] = "东京"

    with pytest.raises(ValidationError, match="暂不支持该出发城市"):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_rejects_reversed_dates(valid_request_data: dict) -> None:
    valid_request_data["start_date"] = "2026-10-05"
    valid_request_data["end_date"] = "2026-10-02"

    with pytest.raises(ValidationError, match="结束日期不能早于出发日期"):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_rejects_trip_longer_than_fourteen_days(
    valid_request_data: dict,
) -> None:
    valid_request_data["end_date"] = "2026-10-20"

    with pytest.raises(ValidationError, match="旅行天数不能超过 14 天"):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_rejects_room_count_above_traveler_count(
    valid_request_data: dict,
) -> None:
    valid_request_data["rooms"] = 3

    with pytest.raises(ValidationError, match="房间数不能超过同行总人数"):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_requires_at_least_one_interest(valid_request_data: dict) -> None:
    valid_request_data["interests"] = []

    with pytest.raises(ValidationError):
        TripRequest.model_validate(valid_request_data)


def test_trip_request_allows_room_count_to_be_decided_later(
    valid_request_data: dict,
) -> None:
    valid_request_data["rooms"] = None

    request = TripRequest.model_validate(valid_request_data)

    assert request.rooms is None
