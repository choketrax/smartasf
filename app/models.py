from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Tuple

@dataclass
class RegistryEntry:
    """Information about a running tenant container."""

    tenant_id: str
    repo_name: str
    container_id: str
    host_port: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

class Registry:
    """In-memory registry for running containers."""

    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str], RegistryEntry] = {}

    def add(self, entry: RegistryEntry) -> None:
        self._entries[(entry.tenant_id, entry.repo_name)] = entry

    def get(self, tenant_id: str, repo_name: str) -> RegistryEntry | None:
        return self._entries.get((tenant_id, repo_name))

    def remove(self, tenant_id: str, repo_name: str) -> None:
        self._entries.pop((tenant_id, repo_name), None)

    def list(self) -> list[RegistryEntry]:
        return list(self._entries.values())

    def update_last_active(self, tenant_id: str, repo_name: str) -> None:
        entry = self.get(tenant_id, repo_name)
        if entry:
            entry.last_active = datetime.utcnow()
