from app.schemas.trip import BudgetBreakdown, TransportOption, TripRequest


def calculate_budget(
    *,
    request: TripRequest,
    transport: TransportOption,
    accommodation_cents: int,
    dining_cents: int,
    attraction_cents: int,
    local_transport_cents: int,
) -> BudgetBreakdown:
    """使用整数分计算分类支出、备用金和预算余额。"""
    known_categories = {
        "intercity": transport.estimated_cents,
        "accommodation": accommodation_cents,
        "dining": dining_cents,
        "attractions": attraction_cents,
        "local_transport": local_transport_cents,
    }
    budgeted_known = sum(
        amount
        for category, amount in known_categories.items()
        if request.budget_includes_intercity or category != "intercity"
    )
    reserve_cents = budgeted_known // 10
    categories = {**known_categories, "reserve": reserve_cents}
    total_cents = sum(categories.values())
    scoped_total = total_cents
    if not request.budget_includes_intercity:
        scoped_total -= categories["intercity"]
    remaining_cents = request.budget_cents - scoped_total
    return BudgetBreakdown(
        categories=categories,
        total_cents=total_cents,
        remaining_cents=remaining_cents,
        is_over_budget=remaining_cents < 0,
    )
