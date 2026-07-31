from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class RubricVerdict(BaseModel):
    score: float
    label: str | None = None
    rationale: str = ''
    evidence_turn_indices: list[int] = Field(default_factory=list)


class RubricSet(BaseModel):
    proactiveness: RubricVerdict
    hallucination: RubricVerdict
    explanation: RubricVerdict
    recovery: RubricVerdict


class TierResolution(BaseModel):
    turn_index: int
    edge_id: str
    resolved: str  # 'inferred_shortcut' | 'blind_shortcut'
    rationale: str = ''


class TestcaseJudgment(BaseModel):
    task_id: str
    rubrics: RubricSet
    tier_resolutions: list[TierResolution] = Field(default_factory=list)
    grade: float
    grade_components: dict = Field(default_factory=dict)


class BatchAggregate(BaseModel):
    n_testcases: int = 0
    mean_grade: float | None = None
    rubric_means: dict = Field(default_factory=dict)
    tier_distribution_resolved: dict = Field(default_factory=dict)
    # §9.2 pooled over the summed resolved-tier distribution.
    solution_step_score: float | None = None
    shortcut_groundedness: float | None = None


class BatchJudgments(BaseModel):
    run_id: str
    judge_model: str
    created_at: str
    testcases: dict[str, TestcaseJudgment] = Field(default_factory=dict)
    aggregate: BatchAggregate = Field(default_factory=BatchAggregate)


class JudgeConfig(BaseModel):
    model: str
    online: bool = False
    concurrency: int = 8
    force: bool = False


class JudgeBackend(Protocol):
    async def evaluate(self, rubric: str, context: dict) -> RubricVerdict: ...

    async def resolve_tier(self, context: dict) -> str: ...


class StubBackend:
    """Deterministic offline backend — no LLM. For CI + offline runs."""

    async def evaluate(self, rubric: str, context: dict) -> RubricVerdict:  # noqa: ARG002
        return RubricVerdict(
            score=0.5,
            label='stub',
            rationale=f'offline stub: {rubric}',
        )

    async def resolve_tier(self, context: dict) -> str:
        # Deterministic §8.8 stand-in: non-empty private reasoning, or a
        # reply that explicitly narrates an inference (推断/infer), counts
        # as displayed inference.
        reasoning = str(context.get('reasoning', '')).strip()
        reply = str(context.get('reply', ''))
        shows_inference = (
            bool(reasoning) or ('推断' in reply) or ('infer' in reply.lower())
        )
        return 'inferred_shortcut' if shows_inference else 'blind_shortcut'
