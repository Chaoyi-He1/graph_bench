from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.judge.models import (
    BatchAggregate,
    TestcaseJudgment,
)

if TYPE_CHECKING:
    from graph_bench.judge.models import RubricSet, TierResolution
    from graph_bench.recorder.models import TestcaseMetrics

_RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')

# §9.2 per-step weights for solution-call modes. Mixed-efficient calls
# classify as 'informed' (info check passes with the same-turn clarify
# folded in), so both 1.0 modes share the 'informed' bucket. A
# 'degrade_to_shortcut' that never got a judge resolution scores like a
# blind shortcut (§8.8: only-L3-missing degrades to the shortcut
# judgment); 'needs_inference_check' likewise only remains when no
# resolution arrived. Forced reveals earn nothing.
STEP_SCORES: dict[str, float] = {
    'informed': 1.0,
    'inferred_shortcut': 0.8,
    'blind_shortcut': 0.4,
    'degrade_to_shortcut': 0.4,
    'needs_inference_check': 0.4,
    'blind_guess': 0.1,
    'forced_reveal': 0.0,
}


def _step_score(dist: dict[str, int]) -> float | None:
    """Weighted mean §9.2 step score over a resolved tier distribution."""
    total = sum(dist.values())
    if not total:
        return None
    return (
        sum(STEP_SCORES.get(tier, 0.0) * n for tier, n in dist.items()) / total
    )


def _shortcut_groundedness(dist: dict[str, int]) -> float | None:
    """§9.2: inferred / (inferred + blind) shortcut calls."""
    inferred = dist.get('inferred_shortcut', 0)
    blind = dist.get('blind_shortcut', 0)
    if inferred + blind == 0:
        return None
    return inferred / (inferred + blind)


def _resolved_tier_distribution(
    metrics: TestcaseMetrics, resolutions: list[TierResolution]
) -> dict[str, int]:
    dist = metrics.tier_counts.model_dump()
    # Replace resolved needs_inference_check counts with their labels.
    # Calls the judge never resolved STAY in the deferred bucket (at
    # the conservative 0.4 step weight) instead of vanishing.
    dist['needs_inference_check'] = max(
        0, dist['needs_inference_check'] - len(resolutions)
    )
    for res in resolutions:
        dist[res.resolved] = dist.get(res.resolved, 0) + 1
    return dist


def _grounded_rate_resolved(dist: dict[str, int]) -> float | None:
    """
    §9.2: (informed + inferred_shortcut + mixed) / total decisions.

    Mixed-efficient calls classify as 'informed' already; forced
    reveals are excluded — they are the simulator's decisions.
    """
    total = sum(n for tier, n in dist.items() if tier != 'forced_reveal')
    if not total:
        return None
    grounded = dist.get('informed', 0) + dist.get('inferred_shortcut', 0)
    return grounded / total


def combine(
    task_id: str,
    metrics: TestcaseMetrics,
    verdicts: RubricSet,
    resolutions: list[TierResolution],
) -> TestcaseJudgment:
    rate = metrics.info_grounded_decision_rate or 0.0
    dist = _resolved_tier_distribution(metrics, resolutions)
    components: dict = {
        'info_grounded_rate': rate,
        'proactiveness': verdicts.proactiveness.score,
        'non_hallucination': 1.0 - verdicts.hallucination.score,
        'explanation': verdicts.explanation.score,
        'recovery': verdicts.recovery.score,
        'tier_distribution_resolved': dist,
        # §9.2 extras — reported alongside the grade, not folded into it,
        # so grades stay comparable with earlier runs.
        'solution_step_score': _step_score(dist),
        'shortcut_groundedness': _shortcut_groundedness(dist),
        # §9.2 formula over RESOLVED tiers: unlike the recorder-side
        # info_grounded_rate (which cannot see inference judgments),
        # this credits inferred shortcuts.
        'info_grounded_rate_resolved': _grounded_rate_resolved(dist),
    }
    numeric = [
        components['info_grounded_rate'],
        components['proactiveness'],
        components['non_hallucination'],
        components['explanation'],
        components['recovery'],
    ]
    grade = sum(numeric) / len(numeric)
    return TestcaseJudgment(
        task_id=task_id,
        rubrics=verdicts,
        tier_resolutions=resolutions,
        grade=grade,
        grade_components=components,
    )


def aggregate(judgments: dict[str, TestcaseJudgment]) -> BatchAggregate:
    if not judgments:
        return BatchAggregate()
    grades = [j.grade for j in judgments.values()]
    rubric_means: dict[str, float] = {
        name: sum(getattr(j.rubrics, name).score for j in judgments.values())
        / len(judgments)
        for name in _RUBRICS
    }
    totals: dict[str, int] = {}
    for j in judgments.values():
        for tier, n in j.grade_components.get(
            'tier_distribution_resolved',
            {},
        ).items():
            totals[tier] = totals.get(tier, 0) + n
    # §9.2 pooled over the summed distribution: every call weighs
    # equally instead of averaging per-case means over unequal counts.
    return BatchAggregate(
        n_testcases=len(judgments),
        mean_grade=sum(grades) / len(grades),
        rubric_means=rubric_means,
        tier_distribution_resolved=totals,
        solution_step_score=_step_score(totals),
        shortcut_groundedness=_shortcut_groundedness(totals),
    )
