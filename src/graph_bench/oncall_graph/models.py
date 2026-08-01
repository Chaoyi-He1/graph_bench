"""
Pydantic models for the oncall causal-graph schema.

Mirrors §12.1 of `dsl-oncall-benchmark-design.md`:
- A `Node` is a `(system_state_id, info_state)` pair plus what symptoms
  the user can see at that point.
- An `Edge` is one agent turn. Three flavors:
    * `clarification_only` — agent asked; info accumulates, system
      unchanged.
    * `solution_only` — agent acted; system state changes.
    * `mixed` — both in one turn.
- A `Task` is graph + satisfaction conditions + persona hint + metadata.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InfoLevel = Literal['L1_basic', 'L2_inferable', 'L3_specific']
EdgeType = Literal['clarification_only', 'solution_only', 'mixed']


class RequiredInfo(BaseModel):
    L1: list[str] = Field(default_factory=list)
    L2: list[str] = Field(default_factory=list)
    L3: list[str] = Field(default_factory=list)

    def flat(self) -> set[str]:
        return set(self.L1) | set(self.L2) | set(self.L3)


class CounterfactualCandidate(BaseModel):
    type: Literal['extreme', 'minor', 'irrelevant']
    answer: str
    solution_should_change: bool


class Clarification(BaseModel):
    info_id: str
    level: InfoLevel | None = None
    question_patterns: list[str] = Field(default_factory=list)
    user_answer_in_this_oncall: str
    # Original oncall screenshots that carried (part of) this answer.
    # Paths relative to the bench package root (data/oncalls/images/...).
    # Revealed together with the answer text so the agent sees the same
    # evidence the real engineer saw, not a pre-digested transcription.
    images: list[str] = Field(default_factory=list)
    counterfactual_candidates: list[CounterfactualCandidate] = Field(
        default_factory=list
    )


class Solution(BaseModel):
    intent: str
    approach_keywords: list[str] = Field(default_factory=list)
    concrete_example: str | None = None
    required_elements_for_full_match: list[str] = Field(default_factory=list)
    required_info: RequiredInfo = Field(default_factory=RequiredInfo)
    info_inferred_by_engineer: list[str] = Field(default_factory=list)
    is_composite: bool = False
    composed_of: list[str] = Field(default_factory=list)
    is_known_blind_path: bool = False

    # §8.2: shortcut solution edges let an agent bypass clarification
    # chain. `is_shortcut=True` means the `from` node has insufficient
    # info_state for the solution's `required_info`; matcher then judges
    # the call as `inferred_shortcut` or `blind_shortcut` per §8.8 based
    # on whether the agent's reply shows reasoning about
    # `shortcut_skipped_info`.
    is_shortcut: bool = False
    shortcut_skipped_info: list[str] = Field(default_factory=list)
    # Free-text hint authored at extraction time describing what kind of
    # inference the agent should display to count as `inferred_shortcut`.
    inference_hint: str | None = None


class Node(BaseModel):
    system_state_id: str
    info_state: list[str] = Field(default_factory=list)
    symptoms_visible: list[str] = Field(default_factory=list)
    is_terminal: bool = False
    # Optional human-readable label for visualization.
    label: str | None = None
    # JSON-only fields (Decision B): info the user volunteers on first
    # arrival, and the §8.10 premature-satisfaction marker. Graphs
    # predating these fields default safely (no volunteered info, never
    # premature).
    volunteered_info: list[str] = Field(default_factory=list)
    user_perceives_resolved: bool = False
    # Original oncall screenshots evidencing this node's visible symptoms
    # (error dialogs, wrong renders, console output). Shown to the agent on
    # first arrival, alongside symptoms_visible. Paths relative to the
    # bench package root (data/oncalls/images/...).
    symptom_images: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """
    One agent turn = one edge.

    Uses `from`/`to` in JSON to match the design doc; Python attributes
    are `from_node`/`to_node` because `from` is a reserved keyword.
    """

    model_config = ConfigDict(populate_by_name=True)

    edge_id: str
    edge_type: EdgeType
    from_node: str = Field(alias='from')
    to_node: str = Field(alias='to')
    clarifications: list[Clarification] = Field(default_factory=list)
    solution: Solution | None = None
    # Free-text annotation (e.g. "auto-generated shortcut from N0").
    comment: str | None = None

    @model_validator(mode='after')
    def _check_components_match_type(self) -> Edge:
        has_clar = len(self.clarifications) > 0
        if self.edge_type == 'clarification_only' and (
            not has_clar or self.solution is not None
        ):
            msg = (
                f'{self.edge_id}: clarification_only edge needs '
                f'clarifications and no solution'
            )
            raise ValueError(msg)
        if self.edge_type == 'solution_only' and (
            self.solution is None or has_clar
        ):
            msg = (
                f'{self.edge_id}: solution_only edge needs solution '
                f'and no clarifications'
            )
            raise ValueError(msg)
        if self.edge_type == 'mixed' and (
            not has_clar or self.solution is None
        ):
            msg = (
                f'{self.edge_id}: mixed edge needs both clarifications '
                f'and solution'
            )
            raise ValueError(msg)
        return self


class Graph(BaseModel):
    start_node: str
    nodes: dict[str, Node]
    edges: list[Edge]

    @model_validator(mode='after')
    def _check_references(self) -> Graph:
        if self.start_node not in self.nodes:
            msg = f'start_node {self.start_node!r} not in nodes'
            raise ValueError(msg)
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                msg = (
                    f'edge {edge.edge_id}: from {edge.from_node!r} not in nodes'
                )
                raise ValueError(msg)
            if edge.to_node not in self.nodes:
                msg = f'edge {edge.edge_id}: to {edge.to_node!r} not in nodes'
                raise ValueError(msg)
        # info_state accumulation (Decision B — containment, not
        # equality): every info_id asked on a clarification/mixed edge
        # must appear in the destination's info_state. The destination
        # may also gain engineer-inferred/volunteered info_ids not
        # introduced by any edge clarification (e.g. on e2_N1__N2 the
        # destination N2 gains
        # `screen_size_adaptation_doc_mentions_popup_page`).
        for edge in self.edges:
            if edge.edge_type not in ('clarification_only', 'mixed'):
                continue
            if not edge.clarifications:
                continue
            src = set(self.nodes[edge.from_node].info_state)
            dst = set(self.nodes[edge.to_node].info_state)
            asked = {c.info_id for c in edge.clarifications}
            expected = src | asked
            if not expected <= dst:
                missing = sorted(expected - dst)
                msg = (
                    f'edge {edge.edge_id}: clarification info_state '
                    f'containment violated.\n'
                    f'  from.info_state: {sorted(src)}\n'
                    f'  to.info_state:   {sorted(dst)}\n'
                    f'  asked info_ids:  {sorted(asked)}\n'
                    f'  missing downstream: {missing}'
                )
                raise ValueError(msg)
        # Required-info availability: every non-shortcut solution must be
        # satisfiable at its from-node — each required id either collected
        # (from-node info_state) or explicitly engineer-inferred. Without
        # this, the judge demands evidence the simulated user was never
        # scripted to provide, producing unwinnable cases.
        for edge in self.edges:
            sol = edge.solution
            if sol is None or sol.is_shortcut:
                continue
            need = sol.required_info.flat()
            have = set(self.nodes[edge.from_node].info_state) | set(
                sol.info_inferred_by_engineer
            )
            missing_req = sorted(need - have)
            if missing_req:
                msg = (
                    f'edge {edge.edge_id}: solution required_info '
                    f'{missing_req} is not available at from-node '
                    f'{edge.from_node!r} (neither in its info_state nor in '
                    f'info_inferred_by_engineer)'
                )
                raise ValueError(msg)
        # Orphan-info check: information cannot be hand-placed into a
        # node's info_state — every id must be introduced somewhere: the
        # start node's seed, a clarification on some edge, a node's
        # volunteered_info, or a solution's info_inferred_by_engineer
        # declaration. (The internal reference pipeline derives info_state
        # by fixpoint so this holds by construction; here it is a check.)
        introduced = set(self.nodes[self.start_node].info_state)
        for edge in self.edges:
            for clar in edge.clarifications:
                introduced.add(clar.info_id)
            if edge.solution is not None:
                introduced.update(edge.solution.info_inferred_by_engineer)
        for node in self.nodes.values():
            introduced.update(node.volunteered_info)
        for node_id, node in self.nodes.items():
            orphans = sorted(set(node.info_state) - introduced)
            if orphans:
                msg = (
                    f'node {node_id!r}: info_state ids {orphans} are '
                    f'introduced by no start seed, clarification, '
                    f'volunteered_info, or info_inferred_by_engineer '
                    f'declaration — later-established facts must not be '
                    f'hand-placed onto nodes'
                )
                raise ValueError(msg)
        return self


class PersonaHint(BaseModel):
    experience_level: str | None = None
    communication_style: str | None = None


class Metadata(BaseModel):
    graph_version: str = 'v1'
    created_from: str | None = None
    hitl_reviewed: bool = False


class Task(BaseModel):
    task_id: str
    title: str | None = None
    body: str | None = None
    graph: Graph
    satisfaction_conditions: list[str] = Field(default_factory=list)
    persona_hint: PersonaHint | None = None
    metadata: Metadata = Field(default_factory=Metadata)
    # Original screenshots the reporter attached to the opening message(s)
    # of this oncall. Sent with the simulator's opening turn. Paths
    # relative to the bench package root (data/oncalls/images/...).
    opening_images: list[str] = Field(default_factory=list)
