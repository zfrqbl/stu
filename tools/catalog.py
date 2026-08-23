"""Universal Tool Catalog."""

from __future__ import annotations

from ..config import ToolsConfig
from ..constants import ToolKind
from ..models import ToolDescriptor
from .native import NATIVE_TOOL_IMPLS


class ToolCatalog:
    def __init__(self, config: ToolsConfig):
        self.config = config
        self._entries = {entry.name: entry for entry in config.catalog}
        self._implementations = {}
        self._arg_models = {}

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

        return descriptors

    def get_descriptor(self, name: str) -> ToolDescriptor | None:
        entry = self._entries.get(name)
        if not entry:
            return None

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

    def get_enabled_descriptor(self, name: str) -> ToolDescriptor | None:
        descriptor = self.get_descriptor(name)
        if not descriptor or not descriptor.enabled:
            return None
        return descriptor

    def get_implementation(self, name: str):
        return self._implementations.get(name)

    def get_arg_model(self, name: str):
        return self._arg_models.get(name)
