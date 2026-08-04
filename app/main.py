from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import NarratorService, PlannerService, register_routes
from app.repositories.presets import PresetRepository


def create_app(
    *,
    planner: PlannerService | None = None,
    narrator: NarratorService | None = None,
    repository: PresetRepository | None = None,
) -> FastAPI:
    """创建本地 Web 应用。"""
    app = FastAPI(title="tourGuide")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=422,
            content={"detail": "输入内容有误，请检查人数、日期、预算和选项"},
        )

    register_routes(
        app,
        planner=planner,
        narrator=narrator,
        repository=repository,
    )

    return app


app = create_app()
