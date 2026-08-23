"""Core constants for Project Stu v3.0."""

from enum import Enum


class Environment(str, Enum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MemoryLayer(str, Enum):
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"


class ProjectScope(str, Enum):
    PRIVATE = "private"
    SHARED = "shared"
    SYSTEM = "system"


class LoopStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class LoopPhase(str, Enum):
    IDLE = "idle"
    INTAKE = "intake"
    ANALYZE = "analyze"
    PLAN = "plan"
    APPROVE = "approve"
    EXECUTE = "execute"
    VERIFY = "verify"
    PERSIST = "persist"


class ToolKind(str, Enum):
    NATIVE = "native"
    MCP = "mcp"
    HTTP = "http"
    SHELL = "shell"


class ToolSafetyLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class ToolExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class MCPConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


class MCPSchemaStatus(str, Enum):
    UNKNOWN = "unknown"
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"


class DaemonName(str, Enum):
    TELEMETRY = "telemetry"
    MAINTENANCE = "maintenance"
    REPORTING = "reporting"


class DaemonPriority(str, Enum):
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


class TelemetryLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SecurityDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


class SemanticColor(str, Enum):
    PRIMARY = "primary"
    SAFE = "safe"
    WARNING = "warning"
    ERROR = "error"
    MUTED = "muted"


class UIPane(str, Enum):
    NAV = "nav"
    CHAT = "chat"
    TELEMETRY = "telemetry"


class UIView(str, Enum):
    CHAT = "chat"
    WORKBENCH = "workbench"
    MEMORY = "memory"
    TOOLS = "tools"
    MCP = "mcp"
    DAEMONS = "daemons"
    SECURITY = "security"
    SETTINGS = "settings"


class HealthStatusValue(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
