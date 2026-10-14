import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import annotations, audio, auth, export, passages, recordings, tasks, users
from app.config import get_settings
from app.db import SessionLocal
from app.services.checkout import expire_leases

log = logging.getLogger("app")


def _expire_leases_job() -> None:
    with SessionLocal() as db:
        released = expire_leases(db)
    if released:
        log.info("Released %d expired task lease(s)", released)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = None
    if get_settings().scheduler_enabled:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(_expire_leases_job, "interval", minutes=1, id="expire_leases", coalesce=True)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Urdu Reading Annotation Platform", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="annot_session",
        max_age=settings.session_lifetime_minutes * 60,
        same_site="lax",
        https_only=settings.environment == "production",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Range", "Accept-Ranges"],
    )
    for module in (auth, users, passages, recordings, tasks, annotations, audio, export):
        app.include_router(module.router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
