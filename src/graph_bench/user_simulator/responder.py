from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_bench.oncall_graph import (
        Edge,
        Graph,
        Node,
    )
    from graph_bench.user_simulator.models import (
        BaseResponse,
        MatchResult,
        SimEvent,
        SimulatorConfig,
        SolutionCall,
    )
    from graph_bench.user_simulator.state import (
        SimulatorSession,
    )


# §10.1 neutral follow-ups: each points only at what the agent said and
# adds no new info (§10.3). missing_elements is NEVER rendered.
_PARTIAL_TEMPLATES: dict[str, str] = {
    'direction_correct_method_missing': 'OK — how exactly do I do that?',
    'method_correct_target_unclear': 'Which one do you mean I should change?',
    'concept_correct_tool_different': (
        'What does that mean, and how do I use it?'
    ),
    'multi_step_partial': (
        'I made the change you described; the first part looks better, '
        'but something still seems off.'
    ),
    'keyword_correct_direction_wrong': (
        "I tried that; I don't see any difference."
    ),
}
_PARTIAL_DEFAULT = 'How exactly would I do that?'
# Fix 3: what the follow-up presses for when the gap is not a missing step.
_PARTIAL_BY_KIND: dict[str, str] = {
    'why': (
        'I can follow the steps, but I still do not understand what is '
        'actually going wrong here — what is causing this?'
    ),
    'both': (
        'Before I change anything: what is actually causing this, and what '
        'exactly should I do about it?'
    ),
}
# Corrective escalation (A + C-light): used when the agent is stuck on a
# wrong-direction edge or has lingered below the advance bar, in place of the
# soft §10.3 follow-up.
_CORRECTIVE_PARTIAL = (
    "I've tried along these lines a few times without any visible "
    'improvement — should we take a different angle?'
)

# Leak-safe per-case reply intents for the 3 non-advancing cases. These
# instruct the online Speaker's LLM what the reply should accomplish; they
# contain NO graph/answer/missing-element/dead-end facts.
_INTENT_NOMATCH_SOLUTION = (
    'You tried what the agent suggested and the symptoms did not change. '
    "Say it didn't help; you may keep observing or ask what to try next. "
    'Do NOT name a root cause or propose a concrete fix yourself.'
)
_INTENT_NOMATCH_CLARIFICATION = (
    "What the agent asks about doesn't line up with anything on your side "
    "and doesn't feel like the key point right now. Politely say it "
    "doesn't match and suggest trying a different angle. Do NOT point out "
    'the correct direction or the answer for them.'
)
# Fix 2: said instead of the "nothing changed" line when the case models no
# fix attempt from this state at all. The user has not run it, so the reply
# must not report an outcome — it states that, and offers what it CAN give.
_NOT_TRIED_YET = (
    "I haven't run that yet. Before I start changing things, what else do "
    'you need to know about my setup or what I am seeing?'
)
_INTENT_NOMATCH_UNTRIED = (
    'You have NOT tried what the agent proposed, and you must not claim any '
    'result for it — do not say it did or did not help. Say plainly that you '
    "haven't done it yet, that you would rather pin the problem down first, "
    'and offer to answer questions about your setup or the symptoms. Do NOT '
    'name a root cause, propose a fix, or hint at the right direction.'
)
_INTENT_PARTIAL_RIGHT = (
    "The agent's direction is right but they haven't said concretely how "
    'to do it. Follow up asking for the concrete step ("how exactly? '
    'change which part?"). Be encouraging, but do NOT fill in the missing '
    'method or name the answer for them.'
)
# Right direction, but the agent keeps stalling without a concrete step.
# Press harder for the actionable next step — must NOT tell it to change
# direction (that's the blind/dead-end case). Still leak-free.
_INTENT_PARTIAL_RIGHT_STALLED = (
    'The direction is right, but after several rounds of asking there is '
    'still no actionable step. Push harder this time: "I trust the '
    'direction — just tell me exactly which part to change, how, and what '
    'data to check afterwards to verify." A slightly impatient tone is '
    'fine. Do NOT tell them to change direction, and do NOT fill in the '
    'missing method or name the answer.'
)
# Fix 3: pressed when what the answer still lacks is the ACCOUNT of the
# problem rather than the steps. Naming the kind of gap is leak-safe (it
# says nothing about the cause); demanding steps the agent already gave is
# not merely useless, it drives the agent to repeat itself into insurance.
_INTENT_PARTIAL_WHY = (
    'The agent has told you what to do but has not explained what is '
    'actually going wrong. Say the steps are clear enough, but you do not '
    'understand the cause yet, and ask them to explain what is happening '
    'before you change anything. Do NOT guess the cause yourself, do NOT '
    'name any mechanism, and do NOT tell them where to look.'
)
_INTENT_PARTIAL_WHY_STALLED = (
    'Several rounds in, the agent still has not explained what is actually '
    'going wrong — only what to type. Press once more, a little impatient: '
    'you want to understand the cause before making further changes. Do '
    'NOT guess the cause, name a mechanism, or point them anywhere.'
)
_INTENT_PARTIAL_BOTH = (
    'The agent has neither explained what is going wrong nor given you a '
    'complete concrete step. Ask for both, in that order. Do NOT guess the '
    'cause or fill in any step yourself.'
)
_INTENT_PARTIAL_BLIND = (
    'You tried a few times along the direction the agent suggested and '
    "saw no clear improvement. Say it isn't working and suggest a "
    'different line of thinking. Do NOT explain why it is wrong, and do '
    'NOT reveal that it is a known dead end or where the root cause is.'
)
# Escalated form: the agent keeps circling the same unhelpful direction.
# Fed when the node's stall count is past the first corrective, so the LLM
# generates a more direct / slightly impatient reply instead of repeating
# the gentle line. Still leak-free.
_INTENT_PARTIAL_BLIND_ESCALATED = (
    'You already tried this direction earlier and said it did not help, '
    'yet the agent keeps circling back to it. Be more direct this time: '
    '"we already went down this path and it still did not work" — ask '
    'them to stop returning to the old direction and take a genuinely '
    'different approach. An impatient tone is fine. Still do NOT explain '
    'why it is wrong, and do NOT reveal the known dead end or the root '
    'cause.'
)


# Fix 3: leading verbs that mark a required element as EXPLANATORY — the
# element asks the answer to establish what is going on, not what to type.
# Anything else is treated as procedural (the pre-existing default).
_EXPLANATORY_VERBS = (
    'identifies',
    'explains',
    'connects',
    'grounds',
    'distinguishes',
    'attributes',
    'recognizes',
    'relates',
    'diagnoses',
    'links',
    'separates',
    'traces',
    'acknowledges',
    'treats',
    'understands',
    'describes',
    'rules_out',
    'confirms',
    'records',
    'keeps',
    'preserves',
)


def missing_kind(missing_elements: list[str]) -> str:
    """
    Classify what a partial is still short of: ``'why'``, ``'how'``, or
    ``'both'``.

    The simulator may not name a missing element — that would hand over the
    answer. It may say which KIND of thing is still missing, and it must:
    a follow-up demanding concrete steps from an agent that already gave
    concrete steps is feedback the agent cannot act on, and three of those
    in a row is the single largest source of forced reveals.
    """
    explanatory = procedural = False
    for element in missing_elements:
        head = element.lower().lstrip('_')
        if head.startswith(_EXPLANATORY_VERBS):
            explanatory = True
        else:
            procedural = True
    if explanatory and procedural:
        return 'both'
    if explanatory:
        return 'why'
    return 'how'


def partial_followup_draft(match: MatchResult) -> str:
    """
    Neutral §10.3 follow-up: echoes only the agent's own words.

    The phrasing is chosen by ``subtype``; where a subtype calls for it we
    interpolate the FIRST ``agent_mentioned_correctly`` term (the agent's
    own correctly-stated word — echoing it leaks nothing). ``missing_elements``
    is never rendered.
    """
    term = (
        match.agent_mentioned_correctly[0]
        if match.agent_mentioned_correctly
        else None
    )
    if term and match.subtype == 'method_correct_target_unclear':
        return f'{term} — which one? I have several here.'
    if term and match.subtype == 'concept_correct_tool_different':
        return f'What is {term}, and how do I use it?'
    kind = missing_kind(list(match.missing_elements))
    if kind != 'how':
        return _PARTIAL_BY_KIND[kind]
    return _PARTIAL_TEMPLATES.get(match.subtype or '', _PARTIAL_DEFAULT)


def describe_symptoms(node: Node, *, first_arrival: bool) -> str:
    parts = list(node.symptoms_visible)
    if first_arrival:
        parts.extend(node.volunteered_info)
    return ' '.join(p for p in parts if p)


def compute_solution_call(
    edge: Edge,
    node_before: Node,
    gathered_info_ids: list[str],
    *,
    mixed: bool,
) -> SolutionCall:
    from graph_bench.user_simulator.models import (  # noqa: PLC0415
        MissingRequiredInfo,
        SolutionCall,
    )

    solution = edge.solution
    if solution is None:  # defensive: only called on solution edges
        msg = f'{edge.edge_id}: compute_solution_call needs a solution'
        raise ValueError(msg)

    grounding: set[str] = set(node_before.info_state) | set(gathered_info_ids)
    if mixed:
        grounding |= {c.info_id for c in edge.clarifications}

    req = solution.required_info
    missing = MissingRequiredInfo(
        L1=[i for i in req.L1 if i not in grounding],
        L2=[i for i in req.L2 if i not in grounding],
        L3=[i for i in req.L3 if i not in grounding],
    )
    return SolutionCall(
        edge_id=edge.edge_id,
        is_shortcut=solution.is_shortcut,
        shortcut_skipped_info=list(solution.shortcut_skipped_info),
        grounding_set=sorted(grounding),
        missing_required_info=missing,
        required_info_satisfied=missing.empty(),
        inference_hint=solution.inference_hint,
    )


class Responder:
    def __init__(
        self,
        graph: Graph,
        index: dict[str, list[Edge]],
        canonical: dict[str, Edge | None],
        config: SimulatorConfig,
        session: SimulatorSession,
    ) -> None:
        self.graph = graph
        self.index = index
        self.canonical = canonical
        self.config = config
        self.session = session
        from graph_bench.user_simulator.loader import (  # noqa: PLC0415
            build_info_answer_map,
            build_info_image_map,
            distance_to_terminal,
        )

        self.info_answers = build_info_answer_map(graph)
        # §9.6 counterfactual interventions replace authored answers on
        # every reveal path for the overridden info_id.
        self.info_answers.update(config.answer_overrides)
        self.info_images = build_info_image_map(graph)
        self.distance_map = distance_to_terminal(graph)
        # Fix 3b: info_id -> edge_id map for overlay backfill.
        # First occurrence wins (a given info_id lives on exactly one edge
        # in well-formed graphs, but be defensive).
        self.info_edge: dict[str, str] = {}
        for e in graph.edges:
            for c in e.clarifications:
                if c.info_id not in self.info_edge:
                    self.info_edge[c.info_id] = e.edge_id

    def claim_images(self, candidates: list[str]) -> list[str]:
        """
        Filter ``candidates`` down to images not yet sent this session and
        mark them sent. A given original screenshot is attached at most
        once per conversation.

        Returns nothing at all under ``send_images: false`` — the ablation
        that asks how much of the benchmark's difficulty the reporter's
        screenshots actually carry. Every other image path funnels through
        here, so the single check covers the opening, node arrivals,
        clarification answers and forced reveals alike.
        """
        if not self.config.send_images:
            return []
        fresh: list[str] = []
        for path in candidates:
            if path and path not in self.session.sent_images:
                self.session.sent_images.append(path)
                fresh.append(path)
        return fresh

    def _node_arrival_images(
        self, node_id: str, *, first_arrival: bool
    ) -> list[str]:
        if not first_arrival:
            return []
        return self.claim_images(list(self.graph.nodes[node_id].symptom_images))

    def _edge(self, edge_id: str | None) -> Edge | None:
        if edge_id is None:
            return None
        for edges in self.index.values():
            for edge in edges:
                if edge.edge_id == edge_id:
                    return edge
        return None

    def _edge_wrong_direction(self, edge_id: str | None) -> bool:
        """
        A matched edge is 'wrong direction' (C-light) if it is a known
        blind path or does not strictly reduce hops-to-terminal.
        """
        edge = self._edge(edge_id)
        if edge is None or edge.solution is None:
            return False
        if edge.solution.is_known_blind_path:
            return True
        unreachable = 1 << 30
        d_to = self.distance_map.get(edge.to_node, unreachable)
        d_from = self.distance_map.get(edge.from_node, unreachable)
        return d_to >= d_from

    def _new_event(
        self, match: MatchResult, node_before: str, node_after: str
    ) -> SimEvent:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            SimEvent,
        )

        return SimEvent(
            turn_index=self.session.turn_index,
            match=match,
            node_before=node_before,
            node_after=node_after,
            revealed_by_simulator=self.session.revealed_latch,
            stall_count_after=self.session.stall_counts.get(node_after, 0),
        )

    def respond(
        self,
        match: MatchResult,
        agent_turn: str,
        ride_along_info_ids: list[str] | None = None,
    ) -> tuple[BaseResponse, SimEvent]:
        completion_prefix = ''
        if self.session.pending_completion:
            items = self.session.pending_completion
            completion_prefix = 'Oh, one more thing: ' + '; '.join(items) + '.'
            self.session.pending_completion = []
        base, event = self._dispatch(match, agent_turn)
        # A turn that proposed an accepted fix AND asked something gets its
        # question answered too — but only here, after _dispatch has already
        # graded the solution call against the pre-turn info set, so the
        # answer cannot retroactively ground the proposal.
        if ride_along_info_ids:
            answers = self._grant_info(ride_along_info_ids)
            if answers:
                base.payload = f'{" ".join(answers)} {base.payload}'.strip()
                event.info_gained = list(event.info_gained) + [
                    i
                    for i in ride_along_info_ids
                    if i in self.session.gathered_info_ids
                ]
        if completion_prefix:
            base.must_convey = completion_prefix
        return base, event

    def _grant_info(self, info_ids: list[str]) -> list[str]:
        """Reveal authored answers for ``info_ids`` not yet given."""
        answers: list[str] = []
        for info_id in info_ids:
            if info_id in self.session.gathered_info_ids:
                continue
            answer = self.info_answers.get(info_id)
            if answer is None:
                continue
            self.session.gathered_info_ids.append(info_id)
            answers.append(answer)
        return answers

    def _dispatch(
        self, match: MatchResult, agent_turn: str
    ) -> tuple[BaseResponse, SimEvent]:
        node_before = self.session.current_node_id

        # §12.2: mixed exact match completes in ONE turn — reveal
        # clarification answer(s) AND emit solution_call together.
        # Must be checked BEFORE the clarification_only branch.
        if match.type == 'exact' and match.edge_type == 'mixed':
            edge = self._edge(match.matched_edge_id)
            if edge is not None:
                return self._respond_mixed(match, edge, node_before)

        if (
            match.type == 'exact'
            and match.edge_type == 'clarification_only'
            and match.matched_info_ids
        ):
            return self._respond_clarification(match, node_before)

        if match.type == 'exact' and match.edge_type == 'solution_only':
            sol = self._edge(match.matched_edge_id)
            if sol is not None and sol.solution is not None:
                return self._respond_solution(
                    match, sol, node_before, agent_turn
                )

        if match.type == 'partial':
            return self._respond_partial(match, agent_turn, node_before)

        return self._respond_no_match(match, agent_turn, node_before)

    def _apply_satisfaction(self, event: SimEvent, node_after: str) -> None:
        # Only called on NON-forced advances (clarification/solution).
        # Satisfaction is read off the DESTINATION node: a forward fix that
        # lands on a terminal is 'resolved' even when it passed through (or
        # started at) an n_partial node, so recovery never reports premature.
        node = self.graph.nodes[node_after]
        if node.is_terminal:
            event.user_satisfaction = 'resolved'
            self.session.termination_reason = 'terminal_resolved'
        elif node.user_perceives_resolved:
            event.user_satisfaction = 'premature'
            self.session.termination_reason = 'premature_satisfaction'

    def _respond_clarification(
        self, match: MatchResult, node_before: str
    ) -> tuple[BaseResponse, SimEvent]:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
        )

        gathered = self.session.gathered_info_ids
        newly: list[str] = []
        answers: list[str] = []
        images: list[str] = []
        for info_id in match.matched_info_ids:
            if info_id in gathered:
                continue
            answer = self.info_answers.get(info_id)
            if answer is None:
                continue
            gathered.append(info_id)
            newly.append(info_id)
            answers.append(answer)
            images.extend(self.info_images.get(info_id, []))
        # Flag-guarded: a productive turn clears this node's stall, making
        # the counter a streak rather than a lifetime total. A re-ask
        # yields no new info and deliberately does not reset. See
        # SimulatorConfig.reset_stall_on_progress for why this is off by
        # default despite being the more intuitive semantics.
        if self.config.reset_stall_on_progress and newly:
            self.session.stall_counts.pop(node_before, None)
        # Fix 3b: backfill matched_edge_id from info_edge map when it is None
        # so the frontend overlay can highlight the real clarification edge.
        if match.matched_info_ids and match.matched_edge_id is None:
            match.matched_edge_id = self.info_edge.get(
                match.matched_info_ids[0]
            )
        newly_visited = self._advance_cascade()
        # Rule 4b: voice volunteered_info of nodes first entered via this
        # clarification (ids are compressed English; the online speaker
        # renders them naturally, same as describe_symptoms does).
        arrival_images: list[str] = []
        for nid in newly_visited:
            node = self.graph.nodes[nid]
            for vid in node.volunteered_info:
                if vid not in self.session.gathered_info_ids:
                    self.session.gathered_info_ids.append(vid)
                if vid not in newly:
                    newly.append(vid)
                    answers.append(vid.replace('_', ' '))
            # already claimed inside — must not pass through claim again
            arrival_images += self._node_arrival_images(
                nid, first_arrival=True
            )
        node_after = self.session.current_node_id
        event = self._new_event(match, node_before, node_after)
        event.info_gained = newly
        if node_after != node_before:
            self._apply_satisfaction(event, node_after)
        payload = ' '.join(answers)
        # Fix 2: when all matched_info_ids were already gathered (re-ask or
        # granted via cascade info_state), answers is [] and payload is ''.
        # Emit a brief acknowledgement instead of an empty turn.
        if not payload:
            payload = (
                'I think I already mentioned that earlier — please go on '
                'from there.'
            )
        base = BaseResponse(
            directive='answer',
            payload=payload,
            images=self.claim_images(images) + arrival_images,
        )
        return base, event

    def _advance_cascade(self) -> list[str]:
        """
        Walk forward while the current node has a clarification/mixed
        out-edge whose entire bundle is gathered. Grants each destination
        node's full info_state (engineer-inferred entries included).

        Returns the node ids visited for the FIRST time during this walk:
        rule 4b puts facts a user volunteers alongside an answer into the
        target node's volunteered_info, so the clarification reply must
        voice them on arrival (previously only solution/mixed arrivals
        spoke volunteered_info, silencing clarification-entered nodes).
        """
        gathered = set(self.session.gathered_info_ids)
        seen: set[str] = set()
        newly_visited: list[str] = []
        while True:
            node_id = self.session.current_node_id
            # Fix 1: cycle backstop — stop if we've already visited this node
            # in the current cascade walk (prevents infinite loops in cyclic
            # authored graphs; acyclic behavior is unchanged).
            if node_id in seen:
                return newly_visited
            seen.add(node_id)
            advanced = False
            for edge in self.index.get(node_id, []):
                if not edge.clarifications:
                    continue
                bundle = {c.info_id for c in edge.clarifications}
                if bundle <= gathered and edge.to_node != node_id:
                    self.session.current_node_id = edge.to_node
                    if edge.to_node not in self.session.visited:
                        self.session.visited.append(edge.to_node)
                        newly_visited.append(edge.to_node)
                    for i in self.graph.nodes[edge.to_node].info_state:
                        if i not in self.session.gathered_info_ids:
                            self.session.gathered_info_ids.append(i)
                    gathered = set(self.session.gathered_info_ids)
                    advanced = True
                    break
            if not advanced:
                return newly_visited

    def _respond_mixed(
        self, match: MatchResult, edge: Edge, node_before: str
    ) -> tuple[BaseResponse, SimEvent]:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
        )

        # 1. Reveal clarification answer(s) for matched_info_ids and
        #    record them in the ledger (dedup, no multi-turn accumulation).
        answer_by_id = {
            c.info_id: self.config.answer_overrides.get(
                c.info_id, c.user_answer_in_this_oncall
            )
            for c in edge.clarifications
        }
        images_by_id = {c.info_id: list(c.images) for c in edge.clarifications}
        ledger = self.session.revealed_info_ids.setdefault(edge.edge_id, [])
        newly: list[str] = []
        answers: list[str] = []
        images: list[str] = []
        for info_id in match.matched_info_ids:
            if info_id in answer_by_id and info_id not in ledger:
                ledger.append(info_id)
                newly.append(info_id)
                answers.append(answer_by_id[info_id])
                images.extend(images_by_id.get(info_id, []))

        # 2. Compute solution_call with mixed=True (grounding augmented by
        #    the edge's clarification info_ids per §12.2).
        before_node = self.graph.nodes[node_before]
        call = compute_solution_call(
            edge, before_node, self.session.gathered_info_ids, mixed=True
        )

        # 3. Advance to to_node; record first-arrival.
        node_after = edge.to_node
        first_arrival = node_after not in self.session.visited
        self.session.current_node_id = node_after
        if first_arrival:
            self.session.visited.append(node_after)

        # 4. Symptoms directive (optionally prefixed with clar answers).
        to_node = self.graph.nodes[node_after]
        symptoms = describe_symptoms(to_node, first_arrival=first_arrival)
        prefix = ' '.join(answers)
        payload = f'{prefix} {symptoms}'.strip() if prefix else symptoms

        event = self._new_event(match, node_before, node_after)
        event.solution_call = call
        event.info_gained = newly
        self._apply_satisfaction(event, node_after)
        base = BaseResponse(
            directive='symptoms',
            payload=payload,
            images=self.claim_images(images)
            + self._node_arrival_images(
                node_after, first_arrival=first_arrival
            ),
        )
        return base, event

    def _respond_solution(
        self,
        match: MatchResult,
        edge: Edge,
        node_before: str,
        agent_turn: str = '',
    ) -> tuple[BaseResponse, SimEvent]:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
        )

        # A (flag-guarded): oscillation escape. If revisits have already
        # driven this node's stall to threshold and it has a canonical
        # forward edge, fire the insurance to force-walk the canonical path
        # out of the blind<->rollback thrash. Guarded by canonical presence
        # so a genuine dead-end never trips failed_dead_end here.
        if self.config.count_revisits_toward_stall:
            counts = self.session.stall_counts
            if (
                counts.get(node_before, 0) >= self.config.stall_reveal_threshold
                and self.canonical.get(node_before) is not None
            ):
                fired = self._fire_insurance(match, agent_turn, node_before)
                if fired is not None:
                    # Mark this rescue as coming from the oscillation patch
                    # (vs the pre-existing partial/no-match stall insurance).
                    fired[1].oscillation_insurance = True
                    return fired

        before_node = self.graph.nodes[node_before]
        call = compute_solution_call(
            edge, before_node, self.session.gathered_info_ids, mixed=False
        )

        if 0.0 < match.match_pct < 1.0:
            missing = list(match.missing_elements)
            ungrounded = (
                call.missing_required_info.L1
                + call.missing_required_info.L2
                + call.missing_required_info.L3
            )
            for info_id in ungrounded:
                if info_id not in missing:
                    missing.append(info_id)
            if missing:
                self.session.pending_completion = missing

        node_after = edge.to_node
        first_arrival = node_after not in self.session.visited
        self.session.current_node_id = node_after
        if first_arrival:
            self.session.visited.append(node_after)

        # A (flag-guarded): a revisit (exact solution match landing on an
        # already-visited node — i.e. oscillation/rollback) accrues stall on
        # the revisited node so repeated bouncing eventually trips insurance.
        if self.config.count_revisits_toward_stall and not first_arrival:
            counts = self.session.stall_counts
            counts[node_after] = counts.get(node_after, 0) + 1

        to_node = self.graph.nodes[node_after]
        symptoms = describe_symptoms(to_node, first_arrival=first_arrival)
        gained = [
            i for i in to_node.info_state if i not in before_node.info_state
        ]

        event = self._new_event(match, node_before, node_after)
        event.solution_call = call
        event.info_gained = gained
        self._apply_satisfaction(event, node_after)
        base = BaseResponse(
            directive='symptoms',
            payload=symptoms,
            images=self._node_arrival_images(
                node_after, first_arrival=first_arrival
            ),
        )
        return base, event

    def _respond_partial(
        self,
        match: MatchResult,
        agent_turn: str,
        node_before: str,
    ) -> tuple[BaseResponse, SimEvent]:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
        )

        # A: a persistent partial counts toward the shared node stall and, at
        # stall_reveal_threshold, fires the canonical forced-reveal. (Revises
        # the 2026-06-23 §10.3 'soft partial / no counter change' decision —
        # multi-match made partials the dominant per-turn outcome.)
        counts = self.session.stall_counts
        counts[node_before] = counts.get(node_before, 0) + 1
        if counts[node_before] >= self.config.stall_reveal_threshold:
            fired = self._fire_insurance(match, agent_turn, node_before)
            if fired is not None:
                return fired

        # C-light: only a wrong-direction (blind/dead-end) edge is ever told to
        # change direction; a right-direction edge — even when stalling — is
        # pressed for the concrete step, never told to abandon it. Each side
        # escalates once the node has stalled more than once.
        wrong = self._edge_wrong_direction(match.matched_edge_id)
        stalled = counts[node_before] > 1
        if wrong:
            draft = _CORRECTIVE_PARTIAL
            intent = (
                _INTENT_PARTIAL_BLIND_ESCALATED
                if stalled
                else _INTENT_PARTIAL_BLIND
            )
        else:
            draft = partial_followup_draft(match)
            kind = missing_kind(list(match.missing_elements))
            if kind == 'why':
                intent = (
                    _INTENT_PARTIAL_WHY_STALLED
                    if stalled
                    else _INTENT_PARTIAL_WHY
                )
            elif kind == 'both':
                intent = _INTENT_PARTIAL_BOTH
            else:
                intent = (
                    _INTENT_PARTIAL_RIGHT_STALLED
                    if stalled
                    else _INTENT_PARTIAL_RIGHT
                )
        event = self._new_event(match, node_before, node_before)
        event.stall_count_after = counts[node_before]
        base = BaseResponse(
            directive='neutral_followup', payload=draft, intent=intent
        )
        return base, event

    def _respond_no_match(
        self, match: MatchResult, agent_turn: str, node_before: str
    ) -> tuple[BaseResponse, SimEvent]:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
            HitlEntry,
        )

        counts = self.session.stall_counts
        counts[node_before] = counts.get(node_before, 0) + 1

        if counts[node_before] >= self.config.stall_reveal_threshold:
            fired = self._fire_insurance(match, agent_turn, node_before)
            if fired is not None:
                return fired

        hitl = HitlEntry(
            node=node_before,
            agent_turn=agent_turn,
            edge_type_attempted=match.edge_type,
            context=[],
        )
        self.session.hitl_queue.append(hitl)

        _OFF_TARGET_HINT = (  # noqa: N806
            "Hmm… what you're asking about doesn't match anything on my "
            "side; it doesn't feel like the key point right now. Could we "
            'try a different angle?'
        )
        is_clar = match.edge_type == 'clarification_only'
        # The user may only report an outcome the case actually establishes.
        # From a node with no authored solution edge, nothing is known about
        # what applying a fix would do, so claiming "I tried it and nothing
        # changed" invents an experimental result — and a fabricated negative
        # is worse than no answer: it argued agents off correct paths.
        has_solution_exit = any(
            e.edge_type != 'clarification_only'
            for e in self.index.get(node_before, [])
        )
        if is_clar:
            phrasing, intent = _OFF_TARGET_HINT, _INTENT_NOMATCH_CLARIFICATION
        elif has_solution_exit:
            phrasing, intent = (
                'I tried that; nothing seems to have changed.',
                _INTENT_NOMATCH_SOLUTION,
            )
        else:
            phrasing, intent = _NOT_TRIED_YET, _INTENT_NOMATCH_UNTRIED
        event = self._new_event(match, node_before, node_before)
        event.stall_count_after = counts[node_before]
        event.hitl = hitl
        base = BaseResponse(
            directive=(
                'neutral_nochange'
                if phrasing is not _NOT_TRIED_YET
                else 'not_attempted'
            ),
            payload=phrasing,
            intent=intent,
        )
        return base, event

    def _fire_insurance(
        self, match: MatchResult, agent_turn: str, node_before: str
    ) -> tuple[BaseResponse, SimEvent] | None:
        from graph_bench.user_simulator.models import (  # noqa: PLC0415
            BaseResponse,
            HitlEntry,
        )

        edge = self.canonical.get(node_before)
        if edge is None:
            # Dead-end node (e.g. N3_x): no canonical path -> fail.
            self.session.termination_reason = 'failed_dead_end'
            return None  # fall through to the normal no_match reply

        before_node = self.graph.nodes[node_before]
        node_after = edge.to_node
        first_arrival = node_after not in self.session.visited
        to_node = self.graph.nodes[node_after]

        info_gained: list[str] = []
        images: list[str] = []
        solution_call = None
        if edge.solution is not None and not edge.clarifications:
            # Solution canonical reveal: intent + concrete_example + symptoms.
            solution_call = compute_solution_call(
                edge, before_node, self.session.gathered_info_ids, mixed=False
            )
            symptoms = describe_symptoms(to_node, first_arrival=first_arrival)
            example = edge.solution.concrete_example or ''
            payload = ' '.join(
                p for p in (edge.solution.intent, example, symptoms) if p
            )
            info_gained = [
                i for i in to_node.info_state if i not in before_node.info_state
            ]
            images = self._node_arrival_images(
                node_after, first_arrival=first_arrival
            )
        else:
            # Multi-clarification reveal: dump ALL bundled answers at once.
            ledger = self.session.revealed_info_ids.setdefault(edge.edge_id, [])
            answers: list[str] = []
            for clar in edge.clarifications:
                if clar.info_id not in ledger:
                    ledger.append(clar.info_id)
                info_gained.append(clar.info_id)
                answers.append(
                    self.config.answer_overrides.get(
                        clar.info_id, clar.user_answer_in_this_oncall
                    )
                )
                images.extend(clar.images)
            payload = ' '.join(answers)
            images = self.claim_images(images)

        # Advance + latch + flags.
        self.session.current_node_id = node_after
        if first_arrival:
            self.session.visited.append(node_after)
        self.session.revealed_latch = True
        if to_node.is_terminal:
            self.session.termination_reason = 'forced_walk_to_terminal'

        hitl = HitlEntry(
            node=node_before,
            agent_turn=agent_turn,
            edge_type_attempted=match.edge_type,
            context=[],
            forced_advance=True,
        )
        self.session.hitl_queue.append(hitl)

        event = self._new_event(match, node_before, node_after)
        event.forced_reveal = True
        event.revealed_by_simulator = True
        event.info_gained = info_gained
        event.solution_call = solution_call
        event.hitl = hitl
        base = BaseResponse(
            directive='forced_reveal', payload=payload, images=images
        )
        return base, event
