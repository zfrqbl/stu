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

from .api import chat, execution, mcp, memory, projects, security, telemetry, tools
from .chat.service import ChatService
from .config import AppConfig, load_app_config, load_secrets
from .constants import HealthStatusValue, ToolSafetyLevel
from .daemons.lifecycle import MemoryLifecycleDaemon
from .daemons.manager import DaemonManager
from .daemons.maintenance import MaintenanceDaemon
from .daemons.reporting import ReportingDaemon
from .daemons.telemetry import TelemetryDaemon, TelemetryWebSocketManager
from .execution.orchestrator import Orchestrator
from .execution.state_manager import StateManager
from .llm.gateway import LLMGateway
from .llm.rate_limiter import LLMRateLimiter
from .logging import setup_logging
from .mcp.connection_manager import ConnectionManager
from .mcp.schema_validator import SchemaValidator
from .mcp.sandbox_interceptor import SandboxInterceptor
from .memory.lifecycle import MemoryLifecycleManager
from .memory.service import MemoryService
from .models import HealthStatus, PublicAppInfo, PublicConfig, PublicRateLimit, PublicUiConfig
from .projects.service import ProjectService
from .security.egress import EgressGuard
from .security.events import SecurityEventStore
from .security.guardrails import GuardrailOrchestrator
from .security.sanitizer import SkillSanitizer
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

        security_event_store = SecurityEventStore(config.security.event_retention)
        sanitizer = SkillSanitizer(config.security)
        egress_guard = EgressGuard(config.security, config.tools)
        guardrails = GuardrailOrchestrator(
            config=config.security,
            sanitizer=sanitizer,
            egress=egress_guard,
            event_store=security_event_store,
        )

        tool_catalog = ToolCatalog(config.tools)
        tool_rag = ToolRagService(
            catalog=tool_catalog,
            tools_config=config.tools,
            embedding_config=config.memory.embedding,
            models_dir=manifest.models,
        )
        tool_rag.prepare()

        tool_executor = ToolExecutor(tool_catalog, config.tools, guardrails=guardrails)

        mcp_schema_validator = SchemaValidator(strict=config.mcp.strict_schema_validation)
        mcp_interceptor = SandboxInterceptor(guardrails=guardrails)
        mcp_connection_manager = ConnectionManager(
            config=config.mcp,
            schema_validator=mcp_schema_validator,
            interceptor=mcp_interceptor,
        )

        await mcp_connection_manager.connect_all()

        for connection in mcp_connection_manager.get_all_connections():
            if connection.status != "connected":
                continue
            for tool in connection.tools:
                full_name = f"mcp_{connection.config.name}_{tool.name}"
                server_name = connection.config.name
                tool_name = tool.name

                async def mcp_tool_impl(parsed_args, context, _sn=server_name, _tn=tool_name):
                    args_dict = parsed_args.model_dump() if hasattr(parsed_args, "model_dump") else dict(parsed_args)
                    result = await mcp_connection_manager.call_tool(
                        _sn, _tn, args_dict, context.project_id
                    )
                    if result.error:
                        raise ValueError(result.error)
                    return result.output

                from pydantic import create_model

                schema_properties = tool.input_schema.get("properties", {})
                required_fields = set(tool.input_schema.get("required", []))
                field_definitions = {}
                for prop_name, prop_def in schema_properties.items():
                    prop_type = prop_def.get("type", "string")
                    python_type = {
                        "string": str,
                        "number": float,
                        "integer": int,
                        "boolean": bool,
                    }.get(prop_type, str)

                    if prop_name in required_fields:
                        field_definitions[prop_name] = (python_type, ...)
                    else:
                        field_definitions[prop_name] = (python_type, None)

                dynamic_model = create_model(f"{full_name}_Args", **field_definitions)

                try:
                    tool_catalog.register_mcp_tool(
                        full_name=full_name,
                        description=tool.description,
                        implementation=mcp_tool_impl,
                        arg_model=dynamic_model,
                        safety_level=ToolSafetyLevel.MODERATE,
                    )
                except ValueError as e:
                    logger.warning(f"Could not register MCP tool '{full_name}': {e}")

        orchestrator = Orchestrator(
            state_manager=state_manager,
            llm_gateway=llm_gateway,
            memory_service=memory_service,
            tool_executor=tool_executor,
            project_service=project_service,
            config=config,
            workspace_root=manifest.root,
        )

        # --- Daemons ---
        daemon_manager = DaemonManager()
        telemetry_ws_manager = telemetry.get_ws_manager()

        telemetry_daemon = TelemetryDaemon(
            interval_seconds=config.daemons.telemetry.interval_seconds,
            enabled=config.daemons.telemetry.enabled,
            ws_manager=telemetry_ws_manager,
            state_manager=state_manager,
            tool_catalog=tool_catalog,
            mcp_connection_manager=mcp_connection_manager,
            memory_service=memory_service,
            daemon_manager=daemon_manager,
        )

        maintenance_daemon = MaintenanceDaemon(
            interval_seconds=config.daemons.maintenance.interval_seconds,
            enabled=config.daemons.maintenance.enabled,
            workspace_root=manifest.root,
            projects_dir=manifest.projects,
            tmp_dir=manifest.tmp,
        )

        reporting_daemon = ReportingDaemon(
            interval_seconds=config.daemons.reporting.interval_seconds,
            enabled=config.daemons.reporting.enabled,
            state_manager=state_manager,
            memory_service=memory_service,
            llm_gateway=llm_gateway,
            project_id=config.app.default_project_id,
        )

        memory_lifecycle_manager = MemoryLifecycleManager(
            config=config.memory.lifecycle,
            memory_service=memory_service,
            llm_gateway=llm_gateway,
        )

        memory_lifecycle_daemon = MemoryLifecycleDaemon(
            interval_seconds=config.memory.lifecycle.interval_seconds,
            enabled=config.memory.lifecycle.enabled,
            lifecycle_manager=memory_lifecycle_manager,
            project_id=config.app.default_project_id,
        )

        daemon_manager.register(telemetry_daemon)
        daemon_manager.register(maintenance_daemon)
        daemon_manager.register(reporting_daemon)
        daemon_manager.register(memory_lifecycle_daemon)

        await daemon_manager.start_all()

        app.state.config = config
        app.state.secrets = secrets
        app.state.workspace = manifest
        app.state.rate_limiter = rate_limiter
        app.state.llm_gateway = llm_gateway
        app.state.project_service = project_service
        app.state.memory_service = memory_service
        app.state.chat_service = chat_service
        app.state.state_manager = state_manager
        app.state.security_event_store = security_event_store
        app.state.sanitizer = sanitizer
        app.state.egress_guard = egress_guard
        app.state.guardrails = guardrails
        app.state.tool_catalog = tool_catalog
        app.state.tool_rag = tool_rag
        app.state.tool_executor = tool_executor
        app.state.mcp_connection_manager = mcp_connection_manager
        app.state.mcp_schema_validator = mcp_schema_validator
        app.state.mcp_interceptor = mcp_interceptor
        app.state.orchestrator = orchestrator
        app.state.daemon_manager = daemon_manager
        app.state.memory_lifecycle_manager = memory_lifecycle_manager
        app.state.workspace_ready = True

        logger.info("Project Stu API startup complete.")
        try:
            yield
        finally:
            await daemon_manager.stop_all()
            await mcp_connection_manager.disconnect_all()
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
    app.include_router(security.router, prefix=config.server.api_prefix)
    app.include_router(mcp.router, prefix=config.server.api_prefix)
    app.include_router(telemetry.router, prefix=config.server.api_prefix)

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
