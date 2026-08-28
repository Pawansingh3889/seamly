"""Composition root: the only place the adapters and modules meet."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from seamly import engine as engine_module
from seamly.common.db import make_engine, make_sessionmaker
from seamly.config import get_settings
from seamly.modules import analyst, auth, exception, ingest, reconcile
from seamly.modules.auth import repository as auth_repo
from seamly.modules.auth import service as auth_service


def register_all(app_engine: engine_module.Engine) -> None:
    app_engine.register("ingest.load", ingest.handle_load, ingest.PERMISSIONS["ingest.load"])
    app_engine.register(
        "reconcile.run", reconcile.handle_run, reconcile.PERMISSIONS["reconcile.run"]
    )
    app_engine.register(
        "exception.assign", exception.handle_assign, exception.PERMISSIONS["exception.assign"]
    )
    app_engine.register(
        "exception.resolve", exception.handle_resolve, exception.PERMISSIONS["exception.resolve"]
    )
    app_engine.register(
        "exception.accept_risk",
        exception.handle_accept_risk,
        exception.PERMISSIONS["exception.accept_risk"],
    )
    app_engine.register("analyst.ask", analyst.handle_ask, analyst.PERMISSIONS["analyst.ask"])
    app_engine.register("auth.login", auth.handle_login, auth.PERMISSIONS["auth.login"])
    app_engine.register("auth.logout", auth.handle_logout, auth.PERMISSIONS["auth.logout"])
    app_engine.register(
        "auth.bootstrap_demo_user",
        auth.handle_bootstrap_demo_user,
        auth.PERMISSIONS["auth.bootstrap_demo_user"],
    )


def create_app() -> FastAPI:
    settings = get_settings()
    db_engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(db_engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_engine = engine_module.new_engine(actor="system", role="admin")
        register_all(app_engine)
        app.state.engine = app_engine
        async with sessionmaker() as session:
            await auth.handle_bootstrap_demo_user(session, {})
            await session.commit()
        yield

    app = FastAPI(title="Seamly", version="0.1.0", lifespan=lifespan)
    app.state.sessionmaker = sessionmaker
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory="src/seamly/static"), name="static")

    from seamly.api.routes import router as api_router
    from seamly.ui.routes import router as ui_router

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ui_router)

    @app.middleware("http")
    async def attach_engine_and_session(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        token = request.cookies.get("seamly_session", "")
        role, actor = "anonymous", "anonymous"
        async with sessionmaker() as session:
            if token:
                stored = await auth_repo.session_by_token_hash(
                    session, auth_service.hash_token(token)
                )
                if stored is not None:
                    user = await auth_repo.user_by_id(session, stored.user_id)
                    if user is not None:
                        actor, role = user.email, user.role
            request.state.session = session
            request.state.app_engine = engine_module.new_engine(actor=actor, role=role)
            register_all(request.state.app_engine)
            request.state.actor = actor
            request.state.role = role
            response = await call_next(request)
        return response

    return app


async def get_session(request: Request) -> AsyncSession:
    session: AsyncSession = request.state.session
    return session
