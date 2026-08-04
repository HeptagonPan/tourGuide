from fastapi import FastAPI


def create_app() -> FastAPI:
    """创建本地 Web 应用。"""
    app = FastAPI(title="tourGuide")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
