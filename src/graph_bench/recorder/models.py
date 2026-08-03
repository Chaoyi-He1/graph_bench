from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Runtime imports (not just typing) — these names appear in pydantic field
# annotations and must resolve at model-build time.
from graph_bench.user_simulator.models import (
    HitlEntry,
    SimEvent,
    SimulatorConfig,
)

Tier = Literal[
    'informed',
    'degrade_to_shortcut',
    'blind_guess',
    'forced_reveal',
    'needs_inference_check',
]


class ToolCall(BaseModel):
    name: str
    args: dict | str | None = None
    result_summary: str | None = None
    error: str | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None


class AgentTelemetry(BaseModel):
    text: str
    raw_output: str | None = None
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str | None = None
    usage: TokenUsage | None = None
    latency_ms: float | None = None
    retries: int = 0
    error: str | None = None


class UserSide(BaseModel):
    text: str
    base_directive: str
    # Screenshot attachments (bench-local paths) sent with this user turn.
    images: list[str] = Field(default_factory=list)


class TurnRecord(BaseModel):
    turn_index: int
    agent: AgentTelemetry | None = None
    user: UserSide
    event: SimEvent
    ts: str


class RunMeta(BaseModel):
    run_id: str
    agent_id: str
    agent_config: dict = Field(default_factory=dict)
    sim_config: SimulatorConfig = Field(default_factory=SimulatorConfig)
    max_turns: int
    git_sha: str | None = None
    started_at: str
    ended_at: str | None = None


class SessionSnapshot(BaseModel):
    task_id: str
    graph_version: str = 'v1'
    termination_reason: str
    is_terminal: bool
    is_satisfied: bool
    turn_index: int
    visited: list[str] = Field(default_factory=list)
    revealed_info_ids: dict[str, list[str]] = Field(default_factory=dict)
    stall_counts: dict[str, int] = Field(default_factory=dict)
    hitl_queue: list[HitlEntry] = Field(default_factory=list)


class SolutionTier(BaseModel):
    turn_index: int
    edge_id: str
    tier: Tier
    is_shortcut: bool
    required_info_satisfied: bool


class TierCounts(BaseModel):
    informed: int = 0
    degrade_to_shortcut: int = 0
    blind_guess: int = 0
    forced_reveal: int = 0
    needs_inference_check: int = 0


class ShortcutStats(BaseModel):
    n_calls: int = 0
    n_required_satisfied: int = 0


class MixedStats(BaseModel):
    n_attempts: int = 0
    n_both_matched: int = 0
    efficiency: float | None = None


class AgentCost(BaseModel):
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    n_tool_calls: int = 0


class TestcaseMetrics(BaseModel):
    # Not a pytest test class despite the ``Test`` prefix (benchmark
    # "testcase", not a unit test).
    __test__ = False

    task_id: str
    n_turns: int
    n_agent_turns: int
    reached_terminal: bool
    termination_reason: str
    final_user_satisfaction: str
    info_grounded_decision_rate: float | None = None
    per_solution: list[SolutionTier] = Field(default_factory=list)
    tier_counts: TierCounts = Field(default_factory=TierCounts)
    shortcut: ShortcutStats = Field(default_factory=ShortcutStats)
    mixed: MixedStats = Field(default_factory=MixedStats)
    forced_reveal_count: int = 0
    stall_histogram: dict[str, int] = Field(default_factory=dict)
    agent_cost: AgentCost = Field(default_factory=AgentCost)
    # §9.2 information dimensions (deterministic, agent-earned only —
    # forced reveals excluded).
    info_efficiency: float | None = None
    question_quality: float | None = None
    # §9.2 usage ratios: share of the agent's solution decisions that
    # were shortcut calls / one-turn mixed clarify+solve calls.
    shortcut_usage_rate: float | None = None
    mixed_usage_rate: float | None = None
    # §8.11 problem B: did clarification chains eventually cash in on a
    # solution attempt, and did the agent get stuck only-asking?
    info_utilization_rate: float | None = None
    max_consecutive_clarifications: int = 0
    stuck_in_clarification: bool = False
    # §9.1 turn efficiency: agent turns spent when the terminal was
    # reached (None when it never was).
    turns_to_terminal: int | None = None


class TestcaseEntry(BaseModel):
    # Not a pytest test class despite the ``Test`` prefix.
    __test__ = False

    snapshot: SessionSnapshot
    metrics: TestcaseMetrics


class BatchAggregate(BaseModel):
    n_testcases: int = 0
    mean_info_grounded_rate: float | None = None
    tier_totals: TierCounts = Field(default_factory=TierCounts)
    total_tokens: int = 0
    mean_info_efficiency: float | None = None
    mean_question_quality: float | None = None
    mean_info_utilization: float | None = None
    mean_turns_to_terminal: float | None = None
    n_stuck_in_clarification: int = 0


class BatchMetrics(BaseModel):
    run_id: str
    agent_id: str
    created_at: str
    testcases: dict[str, TestcaseEntry] = Field(default_factory=dict)
    aggregate: BatchAggregate = Field(default_factory=BatchAggregate)
