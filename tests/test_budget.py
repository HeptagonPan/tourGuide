from app.services.budget import calculate_budget
from app.services.transport import build_transport_options


def test_budget_uses_integer_cents(request_factory, repository) -> None:
    request = request_factory(origin_city="南京", budget_cents=600_000)
    transport = build_transport_options(request, repository)[0]

    result = calculate_budget(
        request=request,
        transport=transport,
        accommodation_cents=160_000,
        dining_cents=80_000,
        attraction_cents=20_000,
        local_transport_cents=12_000,
    )

    assert result.total_cents == sum(result.categories.values())
    assert result.remaining_cents == request.budget_cents - result.total_cents
    assert result.categories["reserve"] == 32_610
    assert result.is_over_budget is False


def test_budget_marks_overspending(request_factory, repository) -> None:
    request = request_factory(origin_city="南京", budget_cents=100_000)
    transport = build_transport_options(request, repository)[0]

    result = calculate_budget(
        request=request,
        transport=transport,
        accommodation_cents=160_000,
        dining_cents=80_000,
        attraction_cents=20_000,
        local_transport_cents=12_000,
    )

    assert result.is_over_budget is True
    assert result.remaining_cents < 0


def test_budget_can_exclude_intercity_from_user_limit(request_factory, repository) -> None:
    request = request_factory(
        origin_city="南京",
        budget_cents=300_000,
        budget_includes_intercity=False,
    )
    transport = build_transport_options(request, repository)[0]

    result = calculate_budget(
        request=request,
        transport=transport,
        accommodation_cents=160_000,
        dining_cents=40_000,
        attraction_cents=20_000,
        local_transport_cents=12_000,
    )

    scoped_total = result.total_cents - result.categories["intercity"]
    assert result.remaining_cents == request.budget_cents - scoped_total
