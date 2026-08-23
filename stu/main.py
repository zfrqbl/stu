"""FastAPI application entrypoint for Project Stu v3.0."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .config import AppConfig, load_app_config, load_secrets
from .constants import HealthStatusValue
from .llm.rate_limiter import LLMRateLimiter
from .logging import setup_logging
from .models import (
    HealthStatus,
    PublicAppInfo,
    PublicConfig,
    PublicRateLimit,
    PublicUiConfig,
)
from .workspace import bootstrap_workspace


def build_api_path(prefix: str, route: str) -> str:
    prefix = prefix.rstrip("/")
    route = route.lstrip("/")
    if not prefix:
        return f"/{route}"
    return f"{prefix}/{route}"


def resolve_static_dir(static_dir: str) -> Path:
    path = Path(static_dir).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    path = path.resolve()

    if path.exists() and not path.is_dir():
        raise ValueError(f"Static directory path exists but is not a directory: {path}")

    path.mkdir(parents=True, exist_ok=True)
    return path


def create_app() -> FastAPI:
    config: AppConfig = load_app_config()
    secrets = load_secrets()
    static_dir = resolve_static_dir(config.server.static_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manifest = bootstrap_workspace(config)
        setup_logging(config, manifest.logs)

        rate_limiter = LLMRateLimiter(config.llm.rate_limit)

        app.state.config = config
        app.state.secrets = secrets
        app.state.workspace = manifest
        app.state.rate_limiter = rate_limiter
        app.state.workspace_ready = True

        logger.info("Project Stu API startup complete.")
        try:
            yield
        finally:
            logger.info("Project Stu API shutting down.")

    app = FastAPI(
        title=config.app.name,
        version=config.app.version,
        lifespan=lifespan,
    )

    app.state.workspace_ready = False

    if config.server.cors_enabled and config.server.cors_origins:
        allow_credentials = "*" not in config.server.cors_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.server.cors_origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    health_path = build_api_path(config.server.api_prefix, "health")
    public_config_path = build_api_path(config.server.api_prefix, "config/public")

    @app.get(health_path, response_model=HealthStatus)
    async def health() -> HealthStatus:
        return HealthStatus(
            status=HealthStatusValue.OK,
            version=config.app.version,
            workspace_ready=bool(getattr(app.state, "workspace_ready", False)),
            timestamp=datetime.now(timezone.utc),
        )

    @app.get(public_config_path, response_model=PublicConfig)
    async def public_config() -> PublicConfig:
        return PublicConfig(
            app=PublicAppInfo(
                name=config.app.name,
                version=config.app.version,
                environment=config.app.environment.value,
                default_project_id=config.app.default_project_id,
            ),
            ui=PublicUiConfig(
                default_active_view=config.ui.default_active_view.value,
                default_nav_collapsed=config.ui.default_nav_collapsed,
                default_telemetry_visible=config.ui.default_telemetry_visible,
                theme=config.ui.theme,
            ),
            llm_rate_limit=PublicRateLimit(
                enabled=config.llm.rate_limit.enabled,
                min_interval_seconds=config.llm.rate_limit.min_interval_seconds,
                max_concurrency=config.llm.rate_limit.max_concurrency,
            ),
        )

    if config.server.static_mount_path == "/":
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="static",
        )
    else:
        @app.get("/", include_in_schema=False)
        async def root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        app.mount(
            config.server.static_mount_path,
            StaticFiles(directory=static_dir, html=True),
            name="static",
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    run_config = load_app_config()
    uvicorn.run(
        "stu.main:app",
        host=run_config.server.host,
        port=run_config.server.port,
        reload=False,
    )
