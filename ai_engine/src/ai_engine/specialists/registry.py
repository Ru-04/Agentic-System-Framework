"""Read-only loader for the approved-format AGENT_REGISTRY.yaml.

The registry is the source of truth for capability IDs, specialist categories and tool allowlists.
This loader never edits it and never changes routing policy. Routing stays disabled while
``machine_routing_enabled`` is false (C-05).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import yaml


class UnknownCapabilityError(KeyError):
    """Raised when a capability or agent ID is not in the registry."""


@dataclass(frozen=True)
class RegistryEntry:
    entry_id: str
    name: str
    entry_type: str
    status: str
    version: str
    specialist_category: str | None
    allowed_tools: tuple[str, ...]
    model_config_ref: str | None


class AgentRegistry:
    def __init__(
        self,
        *,
        registry_version: str,
        registry_status: str,
        machine_routing_enabled: bool,
        entries: Mapping[str, RegistryEntry],
    ) -> None:
        self.registry_version = registry_version
        self.registry_status = registry_status
        self.machine_routing_enabled = machine_routing_enabled
        self._entries = dict(entries)

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        registry: dict[str, Any] = document["registry"]
        routing_policy: dict[str, Any] = registry.get("routing_policy", {})
        entries: dict[str, RegistryEntry] = {}
        for raw in registry.get("entries", []):
            entry = RegistryEntry(
                entry_id=str(raw["id"]),
                name=str(raw.get("name", "")),
                entry_type=str(raw.get("type", "")),
                status=str(raw.get("status", "")),
                version=str(raw.get("version", "")),
                specialist_category=raw.get("specialist_category"),
                allowed_tools=tuple(str(tool) for tool in raw.get("allowed_tools", [])),
                model_config_ref=raw.get("model_config_ref"),
            )
            if entry.entry_id in entries:
                raise ValueError(f"duplicate registry entry {entry.entry_id}")
            entries[entry.entry_id] = entry
        return cls(
            registry_version=str(registry["version"]),
            registry_status=str(registry["status"]),
            machine_routing_enabled=bool(routing_policy.get("machine_routing_enabled", False)),
            entries=entries,
        )

    def entry(self, entry_id: str) -> RegistryEntry:
        try:
            return self._entries[entry_id]
        except KeyError as exc:
            raise UnknownCapabilityError(entry_id) from exc

    def entry_for_specialist_category(self, category_id: str) -> RegistryEntry:
        for entry in self._entries.values():
            if entry.specialist_category == category_id:
                return entry
        raise UnknownCapabilityError(category_id)
