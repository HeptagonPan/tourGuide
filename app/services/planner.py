from collections import defaultdict
from datetime import timedelta

from app.repositories.presets import PresetRepository
from app.schemas.trip import (
    ItineraryActivity,
    ItineraryRoute,
    PoiPreset,
    TripDay,
    TripPlan,
    TripRequest,
)
from app.services.accommodation import build_accommodation_plan, calculate_default_rooms
from app.services.amap import AmapClient, AmapPoi, AmapUnavailableError
from app.services.budget import calculate_budget
from app.services.transport import build_transport_options

ACTIVITY_SLOTS = ("上午", "午间", "下午", "晚间")
DINING_CENTS_PER_TRAVELER_DAY = 10_000


class Planner:
    """组合已核验地点、路线、价格和预算的确定性规划器。"""

    def __init__(self, *, repository: PresetRepository, amap_client: AmapClient) -> None:
        self._repository = repository
        self._amap = amap_client

    async def generate(self, request: TripRequest) -> TripPlan:
        """生成不依赖模型计算事实的上海行程。"""
        transport_options = build_transport_options(request, self._repository)
        selected_transport = transport_options[0]
        accommodation = build_accommodation_plan(
            request,
            self._repository,
            tier=self._select_accommodation_tier(request, selected_transport.estimated_cents),
        )
        candidates = self._matching_pois(request)
        days = await self._build_days(request, candidates)

        attraction_cents = sum(activity.cost_cents for day in days for activity in day.activities)
        local_transport_cents = sum(route.cost_cents for day in days for route in day.routes)
        dining_cents = request.traveler_count * request.trip_days * DINING_CENTS_PER_TRAVELER_DAY
        budget = calculate_budget(
            request=request,
            transport=selected_transport,
            accommodation_cents=accommodation.estimated_cents,
            dining_cents=dining_cents,
            attraction_cents=attraction_cents,
            local_transport_cents=local_transport_cents,
        )

        source_ids = self._collect_source_ids(
            transport_options=transport_options,
            accommodation_source_ids=accommodation.source_ids,
            days=days,
        )
        reference_dates = [
            record.observed_at for record in self._repository.load_reference_prices()
        ]
        return TripPlan(
            request=request,
            transport_options=transport_options,
            selected_transport=selected_transport,
            accommodation=accommodation,
            budget=budget,
            days=days,
            source_ids=source_ids,
            data_updated_at=max(reference_dates),
        )

    def _matching_pois(self, request: TripRequest) -> list[PoiPreset]:
        interests = set(request.interests)
        matches = [
            poi
            for poi in self._repository.load_shanghai_pois()
            if interests.intersection(poi.interests)
        ]
        if not matches:
            raise ValueError("没有符合所选兴趣的上海候选地点")
        return matches

    async def _build_days(
        self,
        request: TripRequest,
        candidates: list[PoiPreset],
    ) -> list[TripDay]:
        grouped: dict[str, list[PoiPreset]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.region].append(candidate)
        regional_groups = sorted(grouped.values(), key=lambda group: (-len(group), group[0].region))

        days: list[TripDay] = []
        for day_index in range(request.trip_days):
            group = regional_groups[day_index % len(regional_groups)]
            rotated_group = group[day_index % len(group) :] + group[: day_index % len(group)]
            day = await self._build_day(
                date=request.start_date + timedelta(days=day_index),
                candidates=rotated_group[:4],
            )
            days.append(day)
        return days

    async def _build_day(self, *, date, candidates: list[PoiPreset]) -> TripDay:
        activities: list[ItineraryActivity] = []
        routes: list[ItineraryRoute] = []
        previous_poi: AmapPoi | None = None

        for candidate in candidates:
            matches = await self._amap.search_pois(keywords=candidate.name, city="上海")
            if not matches:
                continue
            verified_poi = matches[0]

            route = None
            if previous_poi is not None:
                try:
                    route = await self._amap.get_route(
                        origin=self._coordinate(previous_poi),
                        destination=self._coordinate(verified_poi),
                    )
                except AmapUnavailableError:
                    continue

            activity_sources = [f"amap-poi:{verified_poi.id}"]
            if candidate.reference_price_id:
                activity_sources.append(candidate.reference_price_id)
            activities.append(
                ItineraryActivity(
                    slot=ACTIVITY_SLOTS[len(activities)],
                    name=verified_poi.name,
                    region=candidate.region,
                    longitude=verified_poi.longitude,
                    latitude=verified_poi.latitude,
                    duration_minutes=candidate.suggested_duration_minutes,
                    cost_cents=candidate.admission_cents,
                    source_ids=activity_sources,
                )
            )
            if route is not None and previous_poi is not None:
                route_number = len(routes) + 1
                routes.append(
                    ItineraryRoute(
                        origin_name=previous_poi.name,
                        destination_name=verified_poi.name,
                        duration_minutes=route.duration_minutes,
                        distance_meters=route.distance_meters,
                        cost_cents=route.cost_cents,
                        instructions=[step.instruction for step in route.steps],
                        queried_at=route.queried_at,
                        source_ids=[f"amap-route:{date.isoformat()}:{route_number}"],
                    )
                )
            previous_poi = verified_poi

        if not activities:
            raise AmapUnavailableError("高德未能核验任何上海候选地点")
        return TripDay(date=date, activities=activities, routes=routes)

    @staticmethod
    def _select_accommodation_tier(request: TripRequest, transport_cents: int) -> str:
        rooms = calculate_default_rooms(request)
        nights = max(1, request.trip_days - 1)
        available_per_room_night = max(0, request.budget_cents - transport_cents) // (
            rooms * nights
        )
        if available_per_room_night >= 45_000:
            return "quality"
        if available_per_room_night >= 25_000:
            return "comfort"
        return "economy"

    @staticmethod
    def _collect_source_ids(*, transport_options, accommodation_source_ids, days) -> list[str]:
        source_ids = [source_id for option in transport_options for source_id in option.source_ids]
        source_ids.extend(accommodation_source_ids)
        source_ids.append("assumption:dining-100-cny-per-traveler-day")
        for day in days:
            for activity in day.activities:
                source_ids.extend(activity.source_ids)
            for route in day.routes:
                source_ids.extend(route.source_ids)
        return list(dict.fromkeys(source_ids))

    @staticmethod
    def _coordinate(poi: AmapPoi) -> str:
        return f"{poi.longitude},{poi.latitude}"
