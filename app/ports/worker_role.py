from __future__ import annotations

from typing import Protocol


class WorkerRolePort(Protocol):
    role_name: str

    async def handle_event(self, event: dict) -> None:
        raise NotImplementedError
