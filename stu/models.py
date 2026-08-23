"""Core Pydantic models for Project Stu v3.0."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .constants import (
    DaemonName,
    DaemonPriority,
    HealthStatusValue,
    LoopPhase,
    LoopStatus,
    MCPConnectionStatus,
    MCPSchemaStatus,
    MemoryLayer,
    ProjectScope,
    SecurityDecision,
    TelemetryLevel,
    ToolExecutionStatus,
    ToolKind,
    ToolSafetyLevel,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(BaseModel):
    id: str
    name: str
    scope: ProjectScope
    created_at: datetime = Field(default_factory=utc_now)
    description: str | None = None


class MemoryEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: str
    layer: MemoryLayer
    key: str
    content: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoopState(BaseModel):
    schema_version: int = 1
    status: LoopStatus
    phase: LoopPhase
    project_id: str
    iteration: int = 0
    message: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ToolDescriptor(BaseModel):
    name: str
    kind: ToolKind
    safety_level: ToolSafetyLevel
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ToolInvocationRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tool_name: str
    project_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=utc_now)


class ToolInvocationResult(BaseModel):
    request_id: UUID
    status: ToolExecutionStatus
    output: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class MCPToolSchema(BaseModel):
    name: str
    version: str
    schema_status: MCPSchemaStatus
    raw_schema: dict[str, Any] = Field(default_factory=dict)


class MCPConnectionInfo(BaseModel):
    name: str
    status: MCPConnectionStatus
    endpoint: str | None = None
    last_error: str | None = None


class DaemonStatus(BaseModel):
    name: DaemonName
    priority: DaemonPriority
    enabled: bool
    running: bool = False
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    error: str | None = None


class TelemetryEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    level: TelemetryLevel
    source: str
    message: str
    project_id: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    decision: SecurityDecision
    source: str
    reason: str
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceManifest(BaseModel):
    root: Path
    projects: Path
    default_project: Path
    memory: Path
    memory_l2: Path
    archive: Path
    vectors: Path
    vector_store: Path
    models: Path
    logs: Path
    runtime: Path
    tmp: Path
    artifacts: Path
    mcp: Path
    loop_state_file: Path


class HealthStatus(BaseModel):
    status: HealthStatusValue
    version: str
    workspace_ready: bool
    timestamp: datetime


class PublicAppInfo(BaseModel):
    name: str
    version: str
    environment: str
    default_project_id: str


class PublicRateLimit(BaseModel):
    enabled: bool
    min_interval_seconds: float
    max_concurrency: int


class PublicUiConfig(BaseModel):
    default_active_view: str
    default_nav_collapsed: bool
    default_telemetry_visible: bool
    theme: str


class PublicConfig(BaseModel):
    app: PublicAppInfo
    ui: PublicUiConfig
    llm_rate_limit: PublicRateLimit
