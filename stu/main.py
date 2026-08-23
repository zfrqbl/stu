"""FastAPI application entrypoint for Project Stu v3.0."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api import chat, execution, memory, projects, tools
from .chat.service import ChatService
from .config import AppConfig, load_app_config, load_secrets
from .constants import HealthStatusValue
from .execution.orchestrator import Orchestrator
from .execution.state_manager import StateManager
from .llm.gateway import LLMGateway
from .llm.rate_limiter import LLMRateLimiter
from .logging import setup_logging
from .memory.service import MemoryService
from .models import HealthStatus, PublicAppInfo, PublicConfig, PublicRateLimit, PublicUiConfig
from .projects.service import ProjectService
from .tools.catalog import ToolCatalog
from .tools.executor import ToolExecutor
from .tools.rag import ToolRagService
from .workspace import bootstrap_workspace

REQUIRED_STATIC_FILES = ("index.html", "styles.css", "app.js")


def build_api_path(prefix: str, route: str) -> str:
    prefix = prefix.rstrip("/")
    route = route.lstrip("/")
    return f"{prefix}/{route}" if prefix else f"/{route}"


def resolve_static_dir(static_dir: str) -> Path:
    path = Path(static_dir).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    path = path.resolve()

    if path.exists() and not path.is_dir():
        raise ValueError(f"Static directory path exists but is not a directory: {path}")

    path.mkdir(parents=True, exist_ok=True)

    missing = [
        required_file
        for required_file in REQUIRED_STATIC_FILES
        if not (path / required_file).is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required static files: "
            f"{', '.join(missing)} in {path}. "
            "Ensure Milestone 1 frontend files were saved correctly."
        )

    return path


def create_app(config_path: Path | None = None) -> FastAPI:
    config: AppConfig = load_app_config(config_path)
    secrets = load_secrets()
    static_dir = resolve_static_dir(config.server.static_dir)

    if config.server.static_mount_path == "/":
        raise ValueError(
            "static_mount_path must not be '/'. "
            "Use '/static' in stu.json for explicit static asset routing."
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manifest = bootstrap_workspace(config)
        setup_logging(config, manifest.logs)

        rate_limiter = LLMRateLimiter(config.llm.rate_limit)
        llm_gateway = LLMGateway(config.llm, rate_limiter)

        project_service = ProjectService(manifest.root, config)
        memory_service = MemoryService(manifest.root, config, manifest.models)
        chat_service = ChatService(config, memory_service, llm_gateway)

        state_manager = StateManager(manifest.runtime, config)
        recovered_state = state_manager.check_crash_recovery()
        if recovered_state:
            logger.info(f"Crash recovery found resumable loop: {recovered_state.loop_id}")

        tool_catalog = ToolCatalog(config.tools)
        tool_rag = ToolRagService(
            catalog=tool_catalog,
            tools_config=config.tools,
            embedding_config=config.memory.embedding,
            models_dir=manifest.models,
        )
        tool_rag.prepare()

        tool_executor = ToolExecutor(tool_catalog, config.tools)

        orchestrator = Orchestrator(
            state_manager=state_manager,
            llm_gateway=llm_gateway,
            memory_service=memory_service,
            tool_executor=tool_executor,
            project_service=project_service,
            config=config,
            workspace_root=manifest.root,
        )

        app.state.config = config
        app.state.secrets = secrets
        app.state.workspace = manifest
        app.state.rate_limiter = rate_limiter
        app.state.llm_gateway = llm_gateway
        app.state.project_service = project_service
        app.state.memory_service = memory_service
        app.state.chat_service = chat_service
        app.state.state_manager = state_manager
        app.state.tool_catalog = tool_catalog
        app.state.tool_rag = tool_rag
        app.state.tool_executor = tool_executor
        app.state.orchestrator = orchestrator
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

    app.include_router(projects.router, prefix=config.server.api_prefix)
    app.include_router(memory.router, prefix=config.server.api_prefix)
    app.include_router(chat.router, prefix=config.server.api_prefix)
    app.include_router(execution.router, prefix=config.server.api_prefix)
    app.include_router(tools.router, prefix=config.server.api_prefix)

    @app.get(build_api_path(config.server.api_prefix, "health"), response_model=HealthStatus)
    async def health() -> HealthStatus:
        return HealthStatus(
            status=HealthStatusValue.OK,
            version=config.app.version,
            workspace_ready=bool(getattr(app.state, "workspace_ready", False)),
            timestamp=datetime.now(timezone.utc),
        )

    @app.get(
        build_api_path(config.server.api_prefix, "config/public"),
        response_model=PublicConfig,
    )
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

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    app.mount(
        config.server.static_mount_path,
        StaticFiles(directory=static_dir, html=False),
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
