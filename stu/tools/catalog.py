"""Universal Tool Catalog with dynamic MCP tool registration."""

from __future__ import annotations

from typing import Any, Callable

from ..config import ToolsConfig
from ..constants import ToolKind, ToolSafetyLevel
from ..models import ToolDescriptor
from .native import NATIVE_TOOL_IMPLS


class ToolCatalog:
    def __init__(self, config: ToolsConfig):
        self.config = config
        self._entries = {entry.name: entry for entry in config.catalog}
        self._implementations = {}
        self._arg_models = {}
        self._dynamic_tools: dict[str, ToolDescriptor] = {}
        self._dynamic_implementations: dict[str, Callable] = {}
        self._dynamic_arg_models: dict[str, Any] = {}

        self._register_native_tools()
        self._validate()

    def _register_native_tools(self) -> None:
        for name, (impl, arg_model) in NATIVE_TOOL_IMPLS.items():
            self._implementations[name] = impl
            self._arg_models[name] = arg_model

    def _validate(self) -> None:
        for name in self._entries:
            if name not in self._implementations:
                raise ValueError(f"Catalog tool '{name}' has no registered implementation.")

    @property
    def core_fallback_names(self) -> list[str]:
        return list(self.config.core_fallback)

    def register_mcp_tool(
        self,
        full_name: str,
        description: str,
        implementation: Callable,
        arg_model: Any,
        safety_level: ToolSafetyLevel = ToolSafetyLevel.MODERATE,
    ) -> None:
        if full_name in self._entries or full_name in self._dynamic_tools:
            raise ValueError(f"Tool '{full_name}' already exists in catalog")

        descriptor = ToolDescriptor(
            name=full_name,
            kind=ToolKind.MCP,
            safety_level=safety_level,
            description=description,
            input_schema=arg_model.model_json_schema() if hasattr(arg_model, "model_json_schema") else {},
            enabled=True,
        )

        self._dynamic_tools[full_name] = descriptor
        self._dynamic_implementations[full_name] = implementation
        self._dynamic_arg_models[full_name] = arg_model

    def unregister_mcp_tools(self, prefix: str = "mcp_") -> None:
        names_to_remove = [
            name for name in self._dynamic_tools if name.startswith(prefix)
        ]
        for name in names_to_remove:
            del self._dynamic_tools[name]
            self._dynamic_implementations.pop(name, None)
            self._dynamic_arg_models.pop(name, None)

    def list_tools(self, include_disabled: bool = True) -> list[ToolDescriptor]:
        descriptors: list[ToolDescriptor] = []

        for name, entry in self._entries.items():
            enabled = self.config.enabled and entry.enabled

            if not include_disabled and not enabled:
                continue

            arg_model = self._arg_models.get(name)
            input_schema = arg_model.model_json_schema() if arg_model else {}

            descriptors.append(
                ToolDescriptor(
                    name=name,
                    kind=ToolKind.NATIVE,
                    safety_level=entry.safety_level,
                    description=entry.description,
                    input_schema=input_schema,
                    enabled=enabled,
                )
            )

        for name, descriptor in self._dynamic_tools.items():
            if not include_disabled and not descriptor.enabled:
                continue
            descriptors.append(descriptor)

        return descriptors

    def get_descriptor(self, name: str) -> ToolDescriptor | None:
        entry = self._entries.get(name)
        if entry:
            arg_model = self._arg_models.get(name)
            input_schema = arg_model.model_json_schema() if arg_model else {}

            return ToolDescriptor(
                name=name,
                kind=ToolKind.NATIVE,
                safety_level=entry.safety_level,
                description=entry.description,
                input_schema=input_schema,
                enabled=self.config.enabled and entry.enabled,
            )

        return self._dynamic_tools.get(name)

    def get_enabled_descriptor(self, name: str) -> ToolDescriptor | None:
        descriptor = self.get_descriptor(name)
        if not descriptor or not descriptor.enabled:
            return None
        return descriptor

    def get_implementation(self, name: str):
        impl = self._implementations.get(name)
        if impl:
            return impl
        return self._dynamic_implementations.get(name)

    def get_arg_model(self, name: str):
        model = self._arg_models.get(name)
        if model:
            return model
        return self._dynamic_arg_models.get(name)
