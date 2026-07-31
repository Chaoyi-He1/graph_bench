from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.backbone.agent import AgentError
from graph_bench.recorder.models import AgentTelemetry

if TYPE_CHECKING:
    from graph_bench.backbone.models import (
        AgentTurn,
        RecoveryMode,
    )


class ScriptedAgent:
    """
    Reference Agent: replies from a canned list keyed by ``turn_index``.

    ``fail_modes`` (a set of ``(turn_index, mode)`` pairs) makes ``respond``
    raise ``AgentError`` for those calls, to exercise the backbone's
    recovery ladder. Ignores the session (it is stateless).
    """

    def __init__(
        self,
        replies: list[str],
        *,
        fail_modes: set[tuple[int, str]] | None = None,
        default_reply: str = 'ok',
    ) -> None:
        self._replies = replies
        self._fail_modes = fail_modes or set()
        self._default = default_reply
        self.closed = False

    async def respond(
        self, turn: AgentTurn, *, mode: RecoveryMode = 'normal'
    ) -> AgentTelemetry:
        if (turn.turn_index, mode) in self._fail_modes:
            msg = f'scripted fail: turn {turn.turn_index} mode {mode}'
            raise AgentError(msg)
        idx = turn.turn_index - 1
        text = (
            self._replies[idx]
            if 0 <= idx < len(self._replies)
            else self._default
        )
        return AgentTelemetry(text=text, model='scripted')

    async def aclose(self) -> None:
        self.closed = True


from graph_bench.backbone.registry import (
    register_agent,
)


def _scripted_factory(cfg: dict) -> ScriptedAgent:
    return ScriptedAgent(
        replies=cfg.get('replies', []),
        default_reply=cfg.get('default_reply', 'ok'),
    )


register_agent('scripted', _scripted_factory)
