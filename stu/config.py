"""Configuration loading and validation for Project Stu v3.0."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import DaemonPriority, Environment, LogLevel, ToolSafetyLevel, UIView


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppInfoConfig(StrictModel):
    name: str
    version: str
    environment: Environment
    log_level: LogLevel
    log_format: str
    log_filename: str
    default_project_id: str


class ServerConfig(StrictModel):
    host: str
    port: int = Field(..., ge=1, le=65535)
    api_prefix: str
    static_dir: str
    static_mount_path: str
    cors_enabled: bool
    cors_origins: list[str]

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("api_prefix must start with /")
        if value == "/":
            raise ValueError("api_prefix must not be /")
        return value.rstrip("/")

    @field_validator("static_mount_path")
    @classmethod
    def validate_static_mount_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("static_mount_path must start with /")
        normalized = value.rstrip("/")
        return normalized if normalized else "/"


class WorkspaceConfig(StrictModel):
    root: str
    projects_dir: str
    models_dir: str
    logs_dir: str
    runtime_dir: str
    tmp_dir: str
    artifacts_dir: str
    mcp_dir: str
    fail_on_symlink_escape: bool


class RagConfig(StrictModel):
    enabled: bool
    top_k: int = Field(..., ge=1, le=100)


class EmbeddingConfig(StrictModel):
    provider: str
    model: str
    device: str
    batch_size: int = Field(..., ge=1)


class MemoryConfig(StrictModel):
    l1_max_entries: int = Field(..., ge=0)
    project_memory_dir: str
    project_l2_dir: str
    project_archive_dir: str
    project_vectors_dir: str
    sqlite_filename: str
    rag: RagConfig
    embedding: EmbeddingConfig


class ExecutionConfig(StrictModel):
    loop_state_filename: str
    max_iterations: int = Field(..., ge=1)
    crash_recovery_debounce_seconds: float = Field(..., ge=0)
    phase_timeout_seconds: float = Field(..., gt=0)


class ToolCatalogEntry(StrictModel):
    name: str = Field(..., pattern=r"^[a-z0-9_]+$")
    description: str
    safety_level: ToolSafetyLevel
    enabled: bool


class ToolRagConfig(StrictModel):
    enabled: bool
    top_k: int = Field(..., ge=1, le=25)
    vector_subdir: str

    @field_validator("vector_subdir")
    @classmethod
    def validate_vector_subdir(cls, value: str) -> str:
        if Path(value).is_absolute():
            raise ValueError("tools.rag.vector_subdir must be relative")
        return value


class ToolsConfig(StrictModel):
    enabled: bool
    default_timeout_seconds: float = Field(..., gt=0)
    allow_network: bool
    max_output_bytes: int = Field(..., ge=0)
    write_subdir: str
    core_fallback: list[str]
    catalog: list[ToolCatalogEntry]
    rag: ToolRagConfig

    @field_validator("write_subdir")
    @classmethod
    def validate_write_subdir(cls, value: str) -> str:
        if Path(value).is_absolute():
            raise ValueError("tools.write_subdir must be relative")
        return value

    @model_validator(mode="after")
    def validate_catalog(self) -> "ToolsConfig":
        names = [entry.name for entry in self.catalog]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool names found in tools.catalog")

        name_set = set(names)
        for fallback_name in self.core_fallback:
            if fallback_name not in name_set:
                raise ValueError(
                    f"tools.core_fallback contains unknown tool: {fallback_name}"
                )

        return self


class McpConfig(StrictModel):
    enabled: bool
    connection_timeout_seconds: float = Field(..., gt=0)
    strict_schema_validation: bool
    allow_local_stdio: bool

class MCPToolConfig(StrictModel):
    name: str = Field(..., pattern=r"^[a-z0-9_]+$")
    description: str
    input_schema: dict = Field(default_factory=dict)


class MCPServerConfig(StrictModel):
    name: str = Field(..., pattern=r"^[a-z0-9_]+$")
    transport: str
    enabled: bool = False
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    timeout_seconds: float | None = None
    tools: list[MCPToolConfig] = Field(default_factory=list)

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, value: str) -> str:
        allowed = {"mock", "stdio", "http"}
        if value not in allowed:
            raise ValueError(f"transport must be one of: {', '.join(sorted(allowed))}")
        return value

    @model_validator(mode="after")
    def validate_server(self) -> "MCPServerConfig":
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"MCP server '{self.name}' uses stdio transport but has no command")
        if self.transport == "http" and not self.url:
            raise ValueError(f"MCP server '{self.name}' uses http transport but has no url")
        return self


class McpConfig(StrictModel):
    enabled: bool
    connection_timeout_seconds: float = Field(..., gt=0)
    strict_schema_validation: bool
    allow_local_stdio: bool
    allowed_stdio_commands: list[str] = Field(default_factory=list)
    servers: list[MCPServerConfig] = Field(default_factory=list)


class DaemonConfig(StrictModel):
    enabled: bool
    interval_seconds: float = Field(..., gt=0)
    priority: DaemonPriority


class DaemonsConfig(StrictModel):
    telemetry: DaemonConfig
    maintenance: DaemonConfig
    reporting: DaemonConfig


class GuardrailPolicyConfig(StrictModel):
    fail_loop_on_deny: bool
    block_on_review: bool
    record_allow_events: bool


class SecurityConfig(StrictModel):
    enable_guardrails: bool
    enable_skill_sanitizer: bool
    egress_allowlist: list[str]
    forbidden_path_patterns: list[str]
    path_traversal_patterns: list[str]
    forbidden_argument_patterns: list[str]
    shell_command_patterns: list[str]
    secret_patterns: list[str]
    max_argument_bytes: int = Field(..., ge=0)
    max_output_scan_bytes: int = Field(..., ge=0)
    event_retention: int = Field(..., ge=1)
    policy: GuardrailPolicyConfig

    @field_validator(
        "forbidden_path_patterns",
        "path_traversal_patterns",
        "forbidden_argument_patterns",
        "shell_command_patterns",
        "secret_patterns",
    )
    @classmethod
    def validate_regex_list(cls, value: list[str]) -> list[str]:
        for pattern in value:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}") from exc
        return value


class UiConfig(StrictModel):
    default_active_view: UIView
    default_nav_collapsed: bool
    default_telemetry_visible: bool
    theme: str

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        allowed = {"dark", "light", "system"}
        if value not in allowed:
            raise ValueError("theme must be one of: dark, light, system")
        return value


class LlmRateLimitConfig(StrictModel):
    enabled: bool
    min_interval_seconds: float = Field(..., ge=0)
    max_concurrency: int = Field(..., ge=1)
    max_queue_wait_seconds: float = Field(..., ge=0)
    fail_on_timeout: bool
    telemetry_events: bool


class LlmConfig(StrictModel):
    provider: str
    model: str
    rate_limit: LlmRateLimitConfig

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        allowed = {"mock", "aisuite"}
        if value not in allowed:
            raise ValueError(f"provider must be one of: {', '.join(sorted(allowed))}")
        return value


class ChatConfig(StrictModel):
    history_limit: int = Field(..., ge=1, le=500)
    system_prompt: str


class AppConfig(StrictModel):
    app: AppInfoConfig
    server: ServerConfig
    workspace: WorkspaceConfig
    memory: MemoryConfig
    execution: ExecutionConfig
    tools: ToolsConfig
    mcp: McpConfig
    daemons: DaemonsConfig
    security: SecurityConfig
    ui: UiConfig
    llm: LlmConfig
    chat: ChatConfig


class SecretsConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="STU_",
        extra="ignore",
    )

    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    mcp_token: SecretStr | None = None
    embedding_api_key: SecretStr | None = None


def get_config_path() -> Path:
    env_path = os.getenv("STU_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return Path.cwd() / "stu.json"


def load_app_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or get_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}. "
            "Create stu.json or set STU_CONFIG_PATH."
        )

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return AppConfig.model_validate(data)


def load_secrets() -> SecretsConfig:
    return SecretsConfig()
