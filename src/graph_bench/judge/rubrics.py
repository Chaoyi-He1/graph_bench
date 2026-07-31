from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.judge.models import RubricSet, TierResolution
from graph_bench.recorder.reader import to_transcript

if TYPE_CHECKING:
    from graph_bench.judge.models import (
        JudgeBackend,
        RubricVerdict,
    )
    from graph_bench.recorder.models import (
        SessionSnapshot,
        TestcaseMetrics,
        TurnRecord,
    )

_RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')


def _coerce(verdict: RubricVerdict, valid: set[int]) -> RubricVerdict:
    # honesty layer: drop evidence referencing turns not in the trace.
    kept = [i for i in verdict.evidence_turn_indices if i in valid]
    if kept != verdict.evidence_turn_indices:
        return verdict.model_copy(update={'evidence_turn_indices': kept})
    return verdict


def _agent_reasoning(turns: list[TurnRecord]) -> str:
    parts = [
        t.agent.reasoning
        for t in turns
        if t.agent is not None and t.agent.reasoning
    ]
    return '\n'.join(parts)


async def judge_all(
    turns: list[TurnRecord],
    metrics: TestcaseMetrics,
    snapshot: SessionSnapshot,
    backend: JudgeBackend,
) -> RubricSet:
    valid = {t.turn_index for t in turns}
    context = {
        'transcript': to_transcript(turns),
        'reasoning': _agent_reasoning(turns),
        'termination_reason': snapshot.termination_reason,
        'final_user_satisfaction': metrics.final_user_satisfaction,
    }
    verdicts = {
        name: _coerce(await backend.evaluate(name, context), valid)
        for name in _RUBRICS
    }
    return RubricSet(**verdicts)


async def resolve_tiers(
    turns: list[TurnRecord],
    metrics: TestcaseMetrics,
    backend: JudgeBackend,
) -> list[TierResolution]:
    by_index = {t.turn_index: t for t in turns}
    out: list[TierResolution] = []
    for sol in metrics.per_solution:
        if sol.tier != 'needs_inference_check':
            continue
        turn = by_index.get(sol.turn_index)
        agent = turn.agent if turn is not None else None
        reasoning = (agent.reasoning if agent is not None else '') or ''
        # §8.8 judges what the agent DISPLAYED: the reply text is the
        # primary evidence for an inferred shortcut, private reasoning
        # telemetry is supplementary (many agents surface inference only
        # in the reply).
        reply = (agent.text if agent is not None else '') or ''
        call = turn.event.solution_call if turn is not None else None
        context = {
            'reply': reply,
            'reasoning': reasoning,
            'shortcut_skipped_info': (
                call.shortcut_skipped_info if call is not None else []
            ),
            'inference_hint': call.inference_hint if call is not None else None,
        }
        resolved = await backend.resolve_tier(context)
        out.append(
            TierResolution(
                turn_index=sol.turn_index,
                edge_id=sol.edge_id,
                resolved=resolved,
            ),
        )
    return out
