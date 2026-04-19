from fastapi import FastAPI

from app.database import init_database
from app.dependencies import get_app_settings
from app.routers.health import router as health_router
from app.routers.namespaces import router as namespaces_router


def create_app() -> FastAPI:
    settings = get_app_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        description="Autonomous memory runtime scaffold for agent systems.",
    )

    app.include_router(health_router)
    app.include_router(namespaces_router, prefix=settings.api_prefix)

    if settings.auto_create_tables:
        init_database()

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "status": "ok",
            "docs": "/docs",
        }

    return app


app = create_app()
