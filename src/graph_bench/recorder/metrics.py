from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.recorder.models import (
    AgentCost,
    BatchAggregate,
    MixedStats,
    ShortcutStats,
    SolutionTier,
    TestcaseMetrics,
    TierCounts,
)
from graph_bench.recorder.tiers import classify_tier

if TYPE_CHECKING:
    from graph_bench.recorder.models import (
        SessionSnapshot,
        TestcaseEntry,
        TurnRecord,
    )

_REACHED_TERMINAL = frozenset(
    {'terminal_resolved', 'forced_walk_to_terminal'},
)

# §8.11 难题 B diminishing-returns trigger: this many consecutive
# clarification-attempt turns marks the agent as stuck in an asking loop.
CLARIFICATION_LOOP_THRESHOLD = 4


def _final_satisfaction(reason: str) -> str:
    if reason == 'terminal_resolved':
        return 'resolved'
    if reason == 'premature_satisfaction':
        return 'premature'
    return 'none'


def compute_testcase_metrics(
    turns: list[TurnRecord],
    snapshot: SessionSnapshot,
) -> TestcaseMetrics:
    per_solution: list[SolutionTier] = []
    tier_counts = TierCounts()
    shortcut = ShortcutStats()
    mixed = MixedStats()
    cost = AgentCost()
    forced_reveal_count = 0
    n_agent_turns = 0
    grounded_num = 0
    grounded_den = 0
    earned_info = 0
    clar_info = 0
    n_clarification_asks = 0
    n_ask_attempts = 0
    clar_ask_turns: list[int] = []
    solution_turns: list[int] = []
    clar_run = 0
    max_clar_run = 0
    turns_to_terminal: int | None = None

    for turn in turns:
        event = turn.event
        if turn.agent is not None:
            n_agent_turns += 1
            usage = turn.agent.usage
            if usage is not None and usage.total_tokens is not None:
                cost.total_tokens += usage.total_tokens
            if turn.agent.latency_ms is not None:
                cost.total_latency_ms += turn.agent.latency_ms
            cost.n_tool_calls += len(turn.agent.tool_calls)

        if event.forced_reveal:
            # Count every forced-reveal turn, including forced clarification
            # reveals where solution_call is None.  tier_counts.forced_reveal
            # only counts solution attempts (call is not None), because tiers
            # grade solution calls — the two counters intentionally differ.
            forced_reveal_count += 1

        if event.match.edge_type == 'mixed':
            mixed.n_attempts += 1
            if event.match.type == 'exact':
                mixed.n_both_matched += 1

        earned = not event.forced_reveal and not event.revealed_by_simulator
        if earned:
            earned_info += len(event.info_gained)
        # §8.11: a clarification ATTEMPT (matched or not) extends the
        # asking streak; anything else — a solution attempt or a forced
        # advance — breaks it.
        is_clar_attempt = (
            turn.agent is not None
            and event.match.edge_type == 'clarification_only'
            and not event.forced_reveal
        )
        if is_clar_attempt:
            clar_run += 1
            max_clar_run = max(max_clar_run, clar_run)
        elif turn.agent is not None:
            clar_run = 0
        # Question-quality denominator: every ASK counts — including
        # ones that earned nothing (repeat / off-target questions must
        # drag the average down, not vanish from it).
        is_mixed_ask = (
            earned
            and event.match.edge_type == 'mixed'
            and event.match.type == 'exact'
        )
        if is_clar_attempt or is_mixed_ask:
            n_ask_attempts += 1
        if (
            earned
            and event.info_gained
            and event.match.edge_type
            in (
                'clarification_only',
                'mixed',
            )
        ):
            n_clarification_asks += 1
            clar_info += len(event.info_gained)
            clar_ask_turns.append(event.turn_index)

        call = event.solution_call
        if call is not None:
            if not event.forced_reveal:
                solution_turns.append(event.turn_index)
            tier = classify_tier(call, forced_reveal=event.forced_reveal)
            per_solution.append(
                SolutionTier(
                    turn_index=event.turn_index,
                    edge_id=call.edge_id,
                    tier=tier,
                    is_shortcut=call.is_shortcut,
                    required_info_satisfied=call.required_info_satisfied,
                ),
            )
            _bump_tier(tier_counts, tier)
            if call.is_shortcut:
                shortcut.n_calls += 1
                if call.required_info_satisfied:
                    shortcut.n_required_satisfied += 1
            if not event.forced_reveal and not event.revealed_by_simulator:
                grounded_den += 1
                if call.required_info_satisfied:
                    grounded_num += 1

    mixed.efficiency = (
        mixed.n_both_matched / mixed.n_attempts if mixed.n_attempts else None
    )
    rate = grounded_num / grounded_den if grounded_den else None
    # §9.1: agent turns spent when the agent itself resolved the case
    # (forced walks don't count as the agent's own efficiency).
    if snapshot.termination_reason == 'terminal_resolved':
        turns_to_terminal = n_agent_turns
    # §8.11: a clarification ask "cashed in" iff some solution attempt
    # happened on the same turn (mixed edge) or later.
    utilization = (
        sum(1 for t in clar_ask_turns if any(s >= t for s in solution_turns))
        / n_clarification_asks
        if n_clarification_asks
        else None
    )
    # §9.2 usage ratios over the agent's own solution decisions
    # (forced reveals are the simulator acting, not the agent).
    n_decisions = sum(1 for s in per_solution if s.tier != 'forced_reveal')

    return TestcaseMetrics(
        task_id=snapshot.task_id,
        n_turns=len(turns),
        n_agent_turns=n_agent_turns,
        reached_terminal=snapshot.termination_reason in _REACHED_TERMINAL,
        termination_reason=snapshot.termination_reason,
        final_user_satisfaction=_final_satisfaction(
            snapshot.termination_reason,
        ),
        info_grounded_decision_rate=rate,
        per_solution=per_solution,
        tier_counts=tier_counts,
        shortcut=shortcut,
        mixed=mixed,
        forced_reveal_count=forced_reveal_count,
        stall_histogram=dict(snapshot.stall_counts),
        agent_cost=cost,
        info_efficiency=(
            earned_info / n_agent_turns if n_agent_turns else None
        ),
        question_quality=(
            clar_info / n_ask_attempts if n_ask_attempts else None
        ),
        info_utilization_rate=utilization,
        shortcut_usage_rate=(
            shortcut.n_calls / n_decisions if n_decisions else None
        ),
        mixed_usage_rate=(
            mixed.n_both_matched / n_decisions if n_decisions else None
        ),
        max_consecutive_clarifications=max_clar_run,
        stuck_in_clarification=max_clar_run >= CLARIFICATION_LOOP_THRESHOLD,
        turns_to_terminal=turns_to_terminal,
    )


def _bump_tier(counts: TierCounts, tier: str) -> None:
    setattr(counts, tier, getattr(counts, tier) + 1)


def _mean_of(testcases: dict[str, TestcaseEntry], field: str) -> float | None:
    values = [
        getattr(e.metrics, field)
        for e in testcases.values()
        if getattr(e.metrics, field) is not None
    ]
    return sum(values) / len(values) if values else None


def compute_aggregate(
    testcases: dict[str, TestcaseEntry],
) -> BatchAggregate:
    totals = TierCounts()
    total_tokens = 0
    for entry in testcases.values():
        tc = entry.metrics.tier_counts
        totals.informed += tc.informed
        totals.degrade_to_shortcut += tc.degrade_to_shortcut
        totals.blind_guess += tc.blind_guess
        totals.forced_reveal += tc.forced_reveal
        totals.needs_inference_check += tc.needs_inference_check
        total_tokens += entry.metrics.agent_cost.total_tokens
    return BatchAggregate(
        n_testcases=len(testcases),
        mean_info_grounded_rate=_mean_of(
            testcases, 'info_grounded_decision_rate'
        ),
        tier_totals=totals,
        total_tokens=total_tokens,
        mean_info_efficiency=_mean_of(testcases, 'info_efficiency'),
        mean_question_quality=_mean_of(testcases, 'question_quality'),
        mean_info_utilization=_mean_of(testcases, 'info_utilization_rate'),
        mean_turns_to_terminal=_mean_of(testcases, 'turns_to_terminal'),
        n_stuck_in_clarification=sum(
            1 for e in testcases.values() if e.metrics.stuck_in_clarification
        ),
    )
