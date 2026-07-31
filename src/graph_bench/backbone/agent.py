from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from graph_bench.backbone.models import (
        AgentTurn,
        RecoveryMode,
    )
    from graph_bench.recorder.models import AgentTelemetry


class AgentError(Exception):
    """Recoverable agent failure — the backbone escalates the ladder."""


class UnrecoverableTurn(Exception):  # noqa: N818
    """All recovery modes exhausted for a turn."""

    def __init__(self, task_id: str, turn_index: int) -> None:
        super().__init__(f'{task_id}: turn {turn_index} unrecoverable')
        self.task_id = task_id
        self.turn_index = turn_index


class Agent(Protocol):
    async def respond(
        self, turn: AgentTurn, *, mode: RecoveryMode = 'normal'
    ) -> AgentTelemetry: ...

    async def aclose(self) -> None: ...
