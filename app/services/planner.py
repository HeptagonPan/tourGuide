from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.repositories.offline import OfflineRepository
from app.repositories.presets import PresetRepository
from app.schemas.offline import OfflinePoi, OfflineRoutePath
from app.schemas.trip import (
    ItineraryActivity,
    ItineraryRoute,
    TripDay,
    TripPlan,
    TripRequest,
)
from app.services.accommodation import build_accommodation_plan, calculate_default_rooms
from app.services.budget import calculate_budget
from app.services.offline_routes import OfflineRouteService
from app.services.transport import build_transport_options

ACTIVITY_SLOTS = ("上午", "午间", "下午", "晚间")
DINING_CENTS_PER_TRAVELER_DAY = 10_000


class Planner:
    """组合本地景点、离线路线、价格和预算的确定性规划器。"""

    def __init__(
        self,
        *,
        repository: PresetRepository,
        offline_repository: OfflineRepository,
        route_service: OfflineRouteService,
    ) -> None:
        self._repository = repository
        self._offline_repository = offline_repository
        self._route_service = route_service

    async def generate(self, request: TripRequest) -> TripPlan:
        """生成不依赖模型和外部地图服务的上海行程。"""
        transport_options = build_transport_options(request, self._repository)
        selected_transport = transport_options[0]
        accommodation = build_accommodation_plan(
            request,
            self._repository,
            tier=self._select_accommodation_tier(request, selected_transport.estimated_cents),
        )
        candidates = self._matching_pois(request)
        days = self._build_days(request, candidates)

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
        offline_metadata = self._offline_repository.get_metadata()
        return TripPlan(
            request=request,
            transport_options=transport_options,
            selected_transport=selected_transport,
            accommodation=accommodation,
            budget=budget,
            days=days,
            source_ids=source_ids,
            data_updated_at=max([*reference_dates, offline_metadata.generated_at.date()]),
        )

    def _matching_pois(self, request: TripRequest) -> list[OfflinePoi]:
        matches = self._offline_repository.list_pois(request.interests)
        if not matches:
            raise ValueError("没有符合所选兴趣的上海候选地点")
        if len(matches) < request.trip_days:
            matches.extend(self._same_area_general_highlights(matches))
        matches.sort(key=lambda poi: (poi.area, poi.is_general_highlight, poi.name))
        return matches

    def _same_area_general_highlights(self, selected: list[OfflinePoi]) -> list[OfflinePoi]:
        """候选不足时，追加同片区尚未选用的通用景点。"""
        selected_ids = {poi.id for poi in selected}
        selected_areas = {poi.area for poi in selected}
        fillers = [
            poi
            for poi in self._offline_repository.list_pois([])
            if poi.is_general_highlight
            and poi.id not in selected_ids
            and poi.area in selected_areas
        ]
        fillers.sort(key=lambda poi: (poi.area, poi.name))
        return fillers

    def _build_days(self, request: TripRequest, candidates: list[OfflinePoi]) -> list[TripDay]:
        grouped: dict[str, list[OfflinePoi]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.area].append(candidate)
        area_groups = sorted(grouped.values(), key=lambda group: (-len(group), group[0].area))

        days: list[TripDay] = []
        for day_index in range(request.trip_days):
            group = area_groups[day_index % len(area_groups)]
            rotated_group = group[day_index % len(group) :] + group[: day_index % len(group)]
            days.append(
                self._build_day(
                    date=request.start_date + timedelta(days=day_index),
                    candidates=rotated_group[:4],
                )
            )
        return days

    def _build_day(self, *, date, candidates: list[OfflinePoi]) -> TripDay:
        activities: list[ItineraryActivity] = []
        routes: list[ItineraryRoute] = []
        previous_poi: OfflinePoi | None = None

        for candidate in candidates:
            route: OfflineRoutePath | None = None
            if previous_poi is not None:
                route = self._route_service.find_route(previous_poi.id, candidate.id)
                if route is None:
                    continue

            activities.append(
                ItineraryActivity(
                    slot=ACTIVITY_SLOTS[len(activities)],
                    name=candidate.name,
                    region=candidate.area,
                    longitude=candidate.longitude,
                    latitude=candidate.latitude,
                    duration_minutes=candidate.suggested_duration_minutes,
                    cost_cents=candidate.admission_cents,
                    source_ids=[f"offline-poi:{candidate.id}", candidate.source_id],
                )
            )
            if route is not None and previous_poi is not None:
                routes.append(
                    ItineraryRoute(
                        origin_name=previous_poi.name,
                        destination_name=candidate.name,
                        duration_minutes=route.duration_minutes,
                        distance_meters=route.distance_meters,
                        cost_cents=route.cost_cents,
                        instructions=route.instructions,
                        queried_at=datetime.now(UTC),
                        source_ids=[
                            f"offline-route:{previous_poi.id}:{candidate.id}",
                            *route.source_ids,
                        ],
                    )
                )
            previous_poi = candidate

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
