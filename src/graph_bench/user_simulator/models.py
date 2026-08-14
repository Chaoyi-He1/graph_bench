from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PartialSubtype = Literal[
    'direction_correct_method_missing',
    'method_correct_target_unclear',
    'concept_correct_tool_different',
    'multi_step_partial',
    'keyword_correct_direction_wrong',
]
MatchType = Literal['exact', 'partial', 'none', 'opening']
EdgeTypeName = Literal['clarification_only', 'solution_only', 'mixed']
Directive = Literal[
    'opening',
    'answer',
    'symptoms',
    'neutral_followup',
    'neutral_nochange',
    # The user has NOT run what the agent proposed and reports no outcome
    # for it — distinct from neutral_nochange, which reports a real one.
    'not_attempted',
    'forced_reveal',
    'satisfied',
]
Satisfaction = Literal['none', 'premature', 'resolved']


class SimulatorConfig(BaseModel):
    stall_reveal_threshold: int = 4
    bm25_top_k: int = 3
    bm25_corpus_name: str = 'user_style'
    online: bool = False
    advance_match_threshold: float = 0.8
    # When True, an exact solution match that lands back on an
    # already-visited node (oscillation, e.g. a rollback edge bouncing the
    # agent to a fork) counts toward that node's stall. Once a fork with a
    # canonical forward edge crosses stall_reveal_threshold the insurance
    # fires and force-walks the canonical path — converting the blind<->
    # rollback thrash (which never touches stall, so burns to max-turns and
    # ends `none`) into a `forced_walk_to_terminal`. Default OFF keeps the
    # historical behavior byte-identical.
    count_revisits_toward_stall: bool = False
    # When True, a turn that surfaces information the user had not yet
    # given clears that node's stall count, making the counter a streak of
    # unproductive turns rather than their lifetime total at the node.
    # This is arguably what the counter always meant — but measured on the
    # 50-case paired subset it did not pay: forced reveals barely moved
    # (126 -> 122) and mean grade came out below the same configuration
    # with the flag off (+0.033 vs +0.067 over baseline). Once a case can
    # use its whole budget, most late turns gather no new information, so
    # there is little left to reset. Kept off by default and exposed for
    # the ablation table.
    reset_stall_on_progress: bool = False
    # Ablation: attach the reporter's original screenshots, or none of them.
    send_images: bool = True
    # §9.6 counterfactual intervention: info_id -> replacement answer.
    # Every reveal path for that info_id (clarification reply, mixed
    # edge, forced reveal) serves the replacement instead of the
    # authored `user_answer_in_this_oncall`. Persisted in RunMeta via
    # sim_config so the analyzer can tell which run intervened on what.
    answer_overrides: dict[str, str] = Field(default_factory=dict)
    # §13.5 experiment 1 leakage settings. 'C' (default) is the
    # leak-safe production profile: the online speaker sees only the
    # current node's symptoms + info_state. 'B' additionally exposes
    # the satisfaction conditions (CAB-style), 'A' the full canonical
    # conversation reconstruction. A and B exist ONLY to quantify
    # leakage inflation — never use them to report agent scores.
    leak_profile: Literal['A', 'B', 'C'] = 'C'


class TurnComponents(BaseModel):
    has_clarification: bool
    has_solution: bool
    extracted_question: str | None = None
    extracted_proposal: str | None = None


class MatchResult(BaseModel):
    type: MatchType
    edge_type: EdgeTypeName | None = None
    matched_edge_id: str | None = None
    matched_info_ids: list[str] = Field(default_factory=list)
    subtype: PartialSubtype | None = None
    missing_elements: list[str] = Field(default_factory=list)
    agent_mentioned_correctly: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    match_pct: float = 0.0
    proposal_matches: list[ProposalMatch] = Field(default_factory=list)
    proposed_n: int = 0
    matched_m: int = 0


class ProposalMatch(BaseModel):
    summary: str = ''
    matched_edge_id: str | None = None
    match_pct: float = 0.0
    missing_elements: list[str] = Field(default_factory=list)


class MultiMatchOutcome(BaseModel):
    intent: Literal['clarification', 'solution']
    clar_match: MatchResult | None = None
    proposals: list[ProposalMatch] = Field(default_factory=list)


class MissingRequiredInfo(BaseModel):
    L1: list[str] = Field(default_factory=list)
    L2: list[str] = Field(default_factory=list)
    L3: list[str] = Field(default_factory=list)

    def empty(self) -> bool:
        return not (self.L1 or self.L2 or self.L3)


class SolutionCall(BaseModel):
    edge_id: str
    is_shortcut: bool
    shortcut_skipped_info: list[str] = Field(default_factory=list)
    grounding_set: list[str] = Field(default_factory=list)
    missing_required_info: MissingRequiredInfo = Field(
        default_factory=MissingRequiredInfo,
    )
    required_info_satisfied: bool
    inference_hint: str | None = None


class HitlEntry(BaseModel):
    node: str
    agent_turn: str
    edge_type_attempted: EdgeTypeName | None = None
    context: list[str] = Field(default_factory=list)
    forced_advance: bool = False


class SimEvent(BaseModel):
    turn_index: int
    match: MatchResult
    node_before: str
    node_after: str
    info_gained: list[str] = Field(default_factory=list)
    solution_call: SolutionCall | None = None
    stall_count_after: int = 0
    forced_reveal: bool = False
    revealed_by_simulator: bool = False
    # True only when the forced reveal was triggered by the flag-guarded
    # oscillation escape (count_revisits_toward_stall) firing at a fork —
    # distinguishes THAT path from the pre-existing partial/no-match stall
    # insurance (both set forced_reveal=True). Lets a run cleanly attribute
    # how many rescues came from the oscillation patch specifically.
    oscillation_insurance: bool = False
    user_satisfaction: Satisfaction = 'none'
    hitl: HitlEntry | None = None


class BaseResponse(BaseModel):
    directive: Directive
    payload: str | None = None
    intent: str | None = None
    must_convey: str | None = None
    # Screenshot attachments for this reply (original oncall images).
    # Structured, never fed through the speaker LLM — the speaker only
    # polishes text; attachments are appended verbatim downstream.
    images: list[str] = Field(default_factory=list)


class UserTurn(BaseModel):
    text: str
    base_directive: Directive
    event: SimEvent
    # Screenshot attachments accompanying this user turn. Each agent
    # adapter decides delivery (codex: pushed into the sandbox and
    # referenced by path; offline agents: ignored).
    images: list[str] = Field(default_factory=list)
