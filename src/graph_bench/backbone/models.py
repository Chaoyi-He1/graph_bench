from __future__ import annotations

import os

from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field

from graph_bench.user_simulator.models import (
    SimulatorConfig,
)

RecoveryMode = Literal['normal', 'recover_session', 'replay_history']


class TranscriptMsg(BaseModel):
    role: Literal['user', 'agent']
    text: str
    # Screenshot attachments for a user message (bench-local paths).
    # Delivery is adapter-specific: the codex agent pushes them into the
    # sandbox and references sandbox paths; offline agents ignore them.
    images: list[str] = Field(default_factory=list)


class AgentTurn(BaseModel):
    task_id: str
    session_id: str
    turn_index: int
    latest_user_text: str
    latest_user_images: list[str] = Field(default_factory=list)
    transcript: list[TranscriptMsg] = Field(default_factory=list)
    workspace: Path | None = None


class BackboneConfig(BaseModel):
    run_id: str
    out_dir: Path
    agent_name: str
    agent_config: dict = Field(default_factory=dict)
    max_turns: int = 20
    concurrency: int = 4
    # Gateway 502/ReadTimeout bursts (notably on the CN upstream) can
    # burn both attempts on an otherwise fine case, and an exhausted
    # ledger writes agent_failed — which silently shrinks a model's
    # sample and breaks cross-model comparability. Env-overridable.
    max_testcase_retries: int = Field(
        default_factory=lambda: int(
            os.environ.get('BENCH_MAX_TESTCASE_RETRIES', 4)
        )
    )
    graph_version: str = 'v1'
    sim_config: SimulatorConfig = Field(default_factory=SimulatorConfig)
    workspace_root: Path | None = None

    def workspace_for(self, task_id: str) -> Path | None:
        if self.workspace_root is None:
            return None
        return self.workspace_root / task_id
