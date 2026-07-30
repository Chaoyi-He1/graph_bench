"""
Pydantic models for the causal-graph schema of TraceGraph-Bench.

A resolved support thread is annotated as a state machine:

- A ``Node`` is a ``(system_state_id, info_state)`` pair plus the symptoms
  the user can observe at that point. Most nodes share one system state
  (the world is unchanged while the dialogue investigates); ``info_state``
  grows monotonically as clarifications are answered.
- An ``Edge`` is one assistant turn. Three flavors:
    * ``clarification_only`` — the assistant asked for information or for a
      user-executable measurement (bisection run, test build, pref toggle);
      information accumulates, the system is unchanged.
    * ``solution_only`` — the assistant proposed an action that changes the
      user's system; known-failed attempts carry ``is_known_blind_path`` and
      land on aftermath states.
    * ``mixed`` — both in one turn.
- A ``Task`` is graph + satisfaction conditions + persona hint + metadata.

Semantic validators enforced at load time:
1. edge components must match the edge type;
2. all edge endpoints and the start node must exist;
3. information containment — every info_id asked on a clarification/mixed
   edge must appear in the destination's ``info_state`` (the destination may
   also gain engineer-inferred or volunteered info_ids beyond those asked).
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
    """An intervention on a clarification answer, used to probe whether an
    agent's proposal is causally grounded in the collected information."""

    type: Literal['extreme', 'minor', 'irrelevant']
    answer: str
    solution_should_change: bool


class Clarification(BaseModel):
    info_id: str
    level: InfoLevel | None = None
    question_patterns: list[str] = Field(default_factory=list)
    user_answer_in_this_oncall: str
    # Original attachments that carried (part of) this answer, so the agent
    # sees the same evidence the real engineer saw, not a pre-digested
    # transcription. Paths are repository-relative.
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

    # Shortcut solution edges let an agent bypass part of the clarification
    # chain. ``is_shortcut=True`` means the source node's info_state is
    # insufficient for ``required_info``; the judge then grades the call as
    # an inferred shortcut or a blind shortcut depending on whether the
    # agent's reply shows reasoning about ``shortcut_skipped_info``.
    is_shortcut: bool = False
    shortcut_skipped_info: list[str] = Field(default_factory=list)
    inference_hint: str | None = None


class Node(BaseModel):
    system_state_id: str
    info_state: list[str] = Field(default_factory=list)
    symptoms_visible: list[str] = Field(default_factory=list)
    is_terminal: bool = False
    label: str | None = None
    # Info the user volunteers on first arrival at this node, and the
    # premature-satisfaction marker (symptoms gone is not the same as
    # resolved-and-verified).
    volunteered_info: list[str] = Field(default_factory=list)
    user_perceives_resolved: bool = False
    # Original attachments evidencing this node's visible symptoms.
    symptom_images: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """One assistant turn. JSON uses ``from``/``to``; Python attributes are
    ``from_node``/``to_node`` because ``from`` is a reserved keyword."""

    model_config = ConfigDict(populate_by_name=True)

    edge_id: str
    edge_type: EdgeType
    from_node: str = Field(alias='from')
    to_node: str = Field(alias='to')
    clarifications: list[Clarification] = Field(default_factory=list)
    solution: Solution | None = None
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
        # Information containment: src ∪ asked ⊆ dst for clarification and
        # mixed edges; the destination may gain extra ids (engineer-inferred
        # or volunteered information).
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
    # Original attachments the reporter included in the opening message(s).
    opening_images: list[str] = Field(default_factory=list)
