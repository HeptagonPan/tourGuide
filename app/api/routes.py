from typing import Protocol
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.repositories.presets import PresetRepository
from app.schemas.trip import (
    IntercityPreference,
    LocalTransportPreference,
    TripPlan,
    TripRequest,
)
from app.services.amap import AmapClient
from app.services.exporter import HtmlExporter
from app.services.narrator import Narrator
from app.services.planner import Planner


class PlannerService(Protocol):
    """规划路由所需的最小服务接口。"""

    async def generate(self, request: TripRequest) -> TripPlan: ...


class NarratorService(Protocol):
    """文字路由所需的最小服务接口。"""

    async def describe(self, plan: TripPlan) -> str: ...


def register_routes(
    app: FastAPI,
    *,
    planner: PlannerService | None = None,
    narrator: NarratorService | None = None,
    repository: PresetRepository | None = None,
) -> None:
    """注册页面、规划与导出路由。"""
    router = APIRouter()
    preset_repository = repository or PresetRepository()
    exporter = HtmlExporter()
    templates = Jinja2Templates(directory=Settings().project_root / "app" / "templates")

    @router.get("/")
    async def index(request: Request) -> Response:
        return templates.TemplateResponse(request=request, name="index.html")

    @router.get("/result")
    async def result_shell(request: Request) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"plan_payload": None},
        )

    @router.post("/result")
    async def result_with_plan(request: Request, plan: TripPlan) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"plan_payload": plan.model_dump(mode="json")},
        )

    @router.get("/api/options")
    async def options() -> dict[str, object]:
        return {
            "cities": [city.model_dump(mode="json") for city in preset_repository.load_cities()],
            "interests": [
                interest.model_dump(mode="json") for interest in preset_repository.load_interests()
            ],
            "intercity_preferences": [item.value for item in IntercityPreference],
            "local_transport_preferences": [item.value for item in LocalTransportPreference],
        }

    @router.post("/api/plans", response_model=TripPlan)
    async def create_plan(request: TripRequest) -> TripPlan:
        amap_client: AmapClient | None = None
        local_narrator: Narrator | None = None
        try:
            active_planner = planner
            if active_planner is None:
                settings = Settings()
                amap_client = AmapClient(web_key=settings.amap_web_key)
                active_planner = Planner(
                    repository=preset_repository,
                    amap_client=amap_client,
                )
            plan = await active_planner.generate(request)

            active_narrator = narrator
            if active_narrator is None:
                local_narrator = Narrator()
                active_narrator = local_narrator
            narrative = await active_narrator.describe(plan)
            return plan.model_copy(update={"narrative": narrative})
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="规划服务暂时不可用，请稍后重试",
            ) from exc
        finally:
            if amap_client is not None:
                await amap_client.aclose()
            if local_narrator is not None:
                await local_narrator.aclose()

    @router.post("/api/export", response_class=Response)
    async def export(plan: TripPlan) -> Response:
        html = exporter.render(plan)
        filename = f"tourGuide-{plan.destination}-{plan.request.start_date:%Y%m%d}.html"
        encoded_filename = quote(filename)
        disposition = (
            f"attachment; filename=tourGuide-export.html; filename*=UTF-8''{encoded_filename}"
        )
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )

    app.include_router(router)
