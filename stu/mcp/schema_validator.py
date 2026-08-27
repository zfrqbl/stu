"""SchemaValidator: validates MCP tool schemas before registration."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .transport import MCPToolDefinition


@dataclass
class SchemaValidationResult:
    valid: bool
    error: str | None = None


class SchemaValidator:
    """Validates MCP tool schemas for structural correctness."""

    def __init__(self, strict: bool = True):
        self.strict = strict

    def validate_tool(self, tool: MCPToolDefinition) -> SchemaValidationResult:
        if not tool.name or not tool.name.strip():
            return SchemaValidationResult(valid=False, error="Tool name is empty")

        if not tool.name.replace("_", "").isalnum():
            return SchemaValidationResult(
                valid=False,
                error=f"Tool name '{tool.name}' contains invalid characters",
            )

        if len(tool.name) > 64:
            return SchemaValidationResult(
                valid=False,
                error=f"Tool name '{tool.name}' exceeds 64 characters",
            )

        schema = tool.input_schema
        if not isinstance(schema, dict):
            return SchemaValidationResult(valid=False, error="input_schema is not a dict")

        if schema.get("type") != "object":
            return SchemaValidationResult(
                valid=False,
                error="input_schema root type must be 'object'",
            )

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return SchemaValidationResult(valid=False, error="properties must be a dict")

        required = schema.get("required", [])
        if not isinstance(required, list):
            return SchemaValidationResult(valid=False, error="required must be a list")

        for req_field in required:
            if req_field not in properties:
                return SchemaValidationResult(
                    valid=False,
                    error=f"Required field '{req_field}' not in properties",
                )

        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                return SchemaValidationResult(
                    valid=False,
                    error=f"Property '{prop_name}' definition is not a dict",
                )
            prop_type = prop_def.get("type")
            if prop_type and prop_type not in {"string", "number", "integer", "boolean", "array", "object"}:
                return SchemaValidationResult(
                    valid=False,
                    error=f"Property '{prop_name}' has invalid type '{prop_type}'",
                )

        return SchemaValidationResult(valid=True)

    def validate_tools(self, tools: list[MCPToolDefinition]) -> dict[str, SchemaValidationResult]:
        results = {}
        for tool in tools:
            result = self.validate_tool(tool)
            results[tool.name] = result
            if not result.valid:
                logger.warning(
                    f"Schema validation failed for tool '{tool.name}': {result.error}"
                )
        return results
