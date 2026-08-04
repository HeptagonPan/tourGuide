from app.services.accommodation import build_accommodation_plan, calculate_default_rooms


def test_couple_defaults_to_one_room(request_factory) -> None:
    request = request_factory(adults=2, relationship="couple", rooms=None)

    assert calculate_default_rooms(request) == 1


def test_friends_default_to_separate_rooms(request_factory) -> None:
    request = request_factory(adults=2, relationship="friends", rooms=None)

    assert calculate_default_rooms(request) == 2


def test_explicit_room_count_overrides_default(request_factory) -> None:
    request = request_factory(adults=2, relationship="friends", rooms=1)

    assert calculate_default_rooms(request) == 1


def test_accommodation_plan_multiplies_rooms_and_nights(request_factory, repository) -> None:
    request = request_factory(rooms=2, start_date="2026-10-02", end_date="2026-10-05")

    plan = build_accommodation_plan(request, repository, tier="comfort")

    assert plan.rooms == 2
    assert plan.nights == 3
    assert plan.total_min_cents == 2 * 3 * 25_000
    assert plan.total_max_cents == 2 * 3 * 45_000
    assert plan.source_ids == ["hotel-shanghai-comfort-20260804"]
