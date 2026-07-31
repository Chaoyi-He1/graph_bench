from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Pydantic field types — runtime import required for model_rebuild(); TC001
# false-positives here because these names appear in field annotations.
from graph_bench.user_simulator.models import (  # noqa: TC001
    HitlEntry,
    SimEvent,
    UserTurn,
)

TerminationReason = Literal[
    'none',
    'terminal_resolved',
    'premature_satisfaction',
    'forced_walk_to_terminal',
    'failed_dead_end',
]


class SimulatorSession(BaseModel):
    task_id: str
    current_node_id: str
    revealed_info_ids: dict[str, list[str]] = Field(default_factory=dict)
    gathered_info_ids: list[str] = Field(default_factory=list)
    visited: list[str] = Field(default_factory=list)
    history: list[UserTurn] = Field(default_factory=list)
    stall_counts: dict[str, int] = Field(default_factory=dict)
    sim_events: list[SimEvent] = Field(default_factory=list)
    hitl_queue: list[HitlEntry] = Field(default_factory=list)
    termination_reason: TerminationReason = 'none'
    turn_index: int = 0
    revealed_latch: bool = False
    pending_completion: list[str] = Field(default_factory=list)
    # Screenshot paths already attached to some earlier user turn — a
    # given original image is sent at most once per conversation.
    sent_images: list[str] = Field(default_factory=list)
