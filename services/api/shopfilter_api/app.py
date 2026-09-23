
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.api.shopfilter_api.config import ApiSettings, get_settings
from services.api.shopfilter_api.database import Database
from services.api.shopfilter_api.routers import (
    authentication,
    evaluations,
    health,
    organizations,
    resources,
)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    database = Database(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        database.dispose()

    app = FastAPI(
        title="ShopFilter Eval API",
        version="0.1.0",
        description="Tenant-aware persistence API for e-commerce search evaluation.",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.settings = resolved
    app.include_router(health.router)
    app.include_router(authentication.router)
    app.include_router(organizations.router)
    app.include_router(resources.router)
    app.include_router(evaluations.router)
    return app


app = create_app()
