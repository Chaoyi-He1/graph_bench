"""
Offline heuristic backend for turn classification + edge matching.

Stage-1 content determination. The OFFLINE path (``online=False``) is a
deterministic, network-free, credential-free heuristic used by CI and as
the fallback for the online LLM backend (Task 10). Every decision here is
reproducible from the agent's text alone — no graph state beyond the
current node's projected out-edges.

This module imports NOTHING from ``provider``: the offline heuristic is
the complete implementation. ``classify_turn``/``match_edge`` accept an
``online`` flag only to fix the cross-task signature; their ``if online:``
branch is a documented fallback to the offline result, into which Task 10
inserts the real LLM call in-place.

Offline backend caveats (online-only refinements live in Task 10):
- Solution exact/partial/none is decided on ``approach_keywords``
  coverage, NOT on ``required_elements_for_full_match`` (whose entries
  are descriptor ids like ``mentions_update_screen_metrics`` that never
  appear in natural language). Required elements only populate
  ``missing_elements`` on a partial (a leading ``mentions_`` is stripped
  for readability).
- ALL partial solution subtypes collapse to
  ``'direction_correct_method_missing'``; the five-way ``PartialSubtype``
  split is online-only.
- Clarification matching returns ``matched_info_ids`` (which bundled
  info_ids the agent's question hit this turn) and is reported as
  ``type='exact'``; a question-like turn matching no pattern is ``none``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from graph_bench.user_simulator.models import (
    MatchResult,
    MultiMatchOutcome,
    ProposalMatch,
    TurnComponents,
)

if TYPE_CHECKING:
    from graph_bench.oncall_graph.models import Edge
    from graph_bench.user_simulator.models import EdgeTypeName

# Surface cues for a *question* (clarification request).
_QUESTION_MARKS = ('?', '？')  # noqa: RUF001
_INTERROGATIVES = (
    'what',
    'which',
    'how',
    'why',
    'where',
    'when',
    'who',
    '什么',
    '哪',
    '怎么',
    '为什么',
    '是否',
    '能否',
    '多少',
    '吗',
)
# Surface cues for a *proposal* (solution / imperative suggestion).
_PROPOSAL_CUES = (
    'try',
    'change',
    'use',
    'set',
    'add',
    'replace',
    'fix',
    'should',
    '试',
    '改',
    '换',
    '设置',
    '添加',
    '替换',
    '修改',
    '建议',
    '可以用',
    '应该',
)
# Only a fenced code block is a reliable *solution* cue. Bare code
# punctuation (parens, '=', '<', '{', ';') fires on prose like
# ``reloadTemplate()`` in an info-gathering question, so it is excluded
# (a real proposal also carries a _PROPOSAL_CUES verb).
_CODE_CUES = ('```',)

# Match thresholds (token-overlap ratios against the candidate's terms).
# Solution: exact >= _EXACT_RATIO, partial = at least one keyword present.
# Clarification: a pattern is a "hit" when overlap >= _CLAR_HIT_RATIO.
_EXACT_RATIO = 0.6
_CLAR_HIT_RATIO = 0.5  # tighter threshold to avoid CJK bigram false-positives

_TOKEN_RE = re.compile(r'[A-Za-z0-9_]+')
_CJK_RE = re.compile(r'[一-鿿]')


def _tokenize(text: str) -> set[str]:
    """
    Lowercased word tokens + CJK bigrams (deterministic).

    CJK bigrams (consecutive-char pairs) give more discriminative tokens
    than individual CJK characters, which are too common (e.g. ``么`` in
    many question patterns) and generate false positives.
    """
    lowered = text.lower()
    tokens = set(_TOKEN_RE.findall(lowered))
    # Build bigrams from consecutive CJK chars.
    cjk_chars = _CJK_RE.findall(text)
    for i in range(len(cjk_chars) - 1):
        tokens.add(cjk_chars[i] + cjk_chars[i + 1])
    return tokens


def _looks_like_question(text: str) -> bool:
    if any(mark in text for mark in _QUESTION_MARKS):
        return True
    lowered = text.lower()
    return any(cue in lowered for cue in _INTERROGATIVES)


def _looks_like_proposal(text: str) -> bool:
    lowered = text.lower()
    if any(cue in lowered for cue in _PROPOSAL_CUES):
        return True
    return any(cue in text for cue in _CODE_CUES)


def classify_turn(
    agent_turn: str,
    *,
    online: bool = False,
    llm=None,  # noqa: ANN001
) -> TurnComponents:
    """
    Detect whether the turn asks a question, proposes a fix, or both.

    Offline heuristic: a trailing ``?`` (or fullwidth equivalent) or an
    interrogative keyword
    flags ``has_clarification``; an imperative/solution keyword or code
    fragment flags ``has_solution``. Both => mixed-capable (the matcher
    then routes to the ``mixed`` edge type). Neither => a vague turn.
    """
    if online and llm is not None:
        import json  # noqa: PLC0415

        from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
            CLASSIFY_TURN_PROMPT,
        )
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        try:
            raw = extract_text(
                llm.invoke(CLASSIFY_TURN_PROMPT.format(agent_turn=agent_turn))
            )
            data = json.loads(raw)
            return TurnComponents(
                has_clarification=bool(data['has_clarification']),
                has_solution=bool(data['has_solution']),
                extracted_question=data.get('extracted_question'),
                extracted_proposal=data.get('extracted_proposal'),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            pass  # fall through to the unchanged offline heuristic below

    # --- Task 4 offline heuristic (UNCHANGED) --------------------------------
    has_q = _looks_like_question(agent_turn)
    has_p = _looks_like_proposal(agent_turn)
    return TurnComponents(
        has_clarification=has_q,
        has_solution=has_p,
        extracted_question=agent_turn if has_q else None,
        extracted_proposal=agent_turn if has_p else None,
    )


def _coverage_ratio(turn_tokens: set[str], terms: list[str]) -> float:
    """Fraction of ``terms`` whose tokens are all present in the turn."""
    if not terms:
        return 0.0
    hits = 0
    for term in terms:
        term_tokens = _tokenize(term)
        if term_tokens and term_tokens <= turn_tokens:
            hits += 1
    return hits / len(terms)


def _humanize_element(element: str) -> str:
    """Strip a leading ``mentions_`` from a descriptor id for display."""
    prefix = 'mentions_'
    return element.removeprefix(prefix)


def code_coverage_pct(agent_turn: str, edge: Edge) -> tuple[float, list[str]]:
    """
    Deterministic coverage of an edge's required_elements_for_full_match
    (falling back to approach_keywords) by the turn's tokens. Returns
    (covered/total, humanized missing elements).

    Humanized element ids (e.g. ``use_rpx``) are tokenized with underscores
    replaced by spaces so that ``use_rpx`` matches turns containing both
    ``use`` and ``rpx`` as separate words.
    """
    sol = edge.solution
    if sol is None:
        return 0.0, []
    basis = sol.required_elements_for_full_match or sol.approach_keywords
    if not basis:
        return 0.0, []
    turn_tokens = _tokenize(agent_turn)
    covered = 0
    missing: list[str] = []
    for element in basis:
        human = _humanize_element(element)
        human_tokens = _tokenize(human.replace('_', ' '))
        if human_tokens and human_tokens <= turn_tokens:
            covered += 1
        else:
            missing.append(human)
    return covered / len(basis), missing


def _missing_required_elements(
    turn_tokens: set[str], required: list[str]
) -> list[str]:
    """
    Humanized required elements whose token-subset is absent.

    ``required_elements_for_full_match`` entries are descriptor ids (e.g.
    ``mentions_use_rpx``) that never appear verbatim in natural language;
    they are NOT used for the exact/partial/none decision (see
    ``_match_solution``). Here they only annotate what a partial is
    missing. We test the *humanized* token-subset (``use_rpx`` -> tokens
    ``{use, rpx}``) so the annotation reflects natural-language coverage,
    and always report the humanized form.
    """
    missing: list[str] = []
    for element in required:
        human = _humanize_element(element)
        human_tokens = _tokenize(human)
        if not (human_tokens and human_tokens <= turn_tokens):
            missing.append(human)
    return missing


def _present_terms(turn_tokens: set[str], terms: list[str]) -> list[str]:
    present: list[str] = []
    for term in terms:
        term_tokens = _tokenize(term)
        if term_tokens and term_tokens <= turn_tokens:
            present.append(term)
    return present


def _match_clarification(
    turn_tokens: set[str], out_edges: list[Edge]
) -> MatchResult:
    """
    Match the turn against each clarification's question patterns.

    For every clarification on every out-edge, score its
    ``question_patterns`` by per-pattern token overlap; a clarification is
    "hit" when its best pattern clears ``_CLAR_HIT_RATIO`` (intentionally
    stricter to avoid CJK bigram false-positives in solution matching).
    The winning edge is the one whose hit clarifications have the highest
    combined best-pattern score. ``matched_info_ids`` lists that edge's hit
    ``info_id``s (§7 bundled-clarification ledger). A question-like turn
    that hits no pattern on any edge returns ``none``.
    """
    best_id: str | None = None
    best_total = 0.0
    best_info_ids: list[str] = []
    for edge in out_edges:
        hit_info_ids: list[str] = []
        total = 0.0
        for clar in edge.clarifications:
            clar_best = 0.0
            for pattern in clar.question_patterns:
                pat_tokens = _tokenize(pattern)
                if not pat_tokens:
                    continue
                score = len(turn_tokens & pat_tokens) / len(pat_tokens)
                clar_best = max(clar_best, score)
            if clar_best >= _CLAR_HIT_RATIO:
                hit_info_ids.append(clar.info_id)
                total += clar_best
        if hit_info_ids and total > best_total:
            best_total = total
            best_id = edge.edge_id
            best_info_ids = hit_info_ids
    if best_id is None:
        return MatchResult(type='none', edge_type='clarification_only')
    return MatchResult(
        type='exact',
        edge_type='clarification_only',
        matched_edge_id=best_id,
        matched_info_ids=best_info_ids,
        confidence=round(best_total / len(best_info_ids), 3),
    )


def _match_solution(
    turn_tokens: set[str],
    out_edges: list[Edge],
    edge_type: EdgeTypeName,
) -> MatchResult:
    """
    Score the turn against ``approach_keywords`` coverage.

    The exact/partial/none decision is made on ``approach_keywords``
    coverage only (``required_elements_for_full_match`` entries are
    descriptor ids that never surface in natural language). ``exact`` =
    most/all approach_keywords present (``>= _EXACT_RATIO``); ``partial``
    = at least one keyword present (``best_score > 0``); ``none`` below floor.
    Required elements populate ``missing_elements`` on a partial (humanized).
    The offline backend collapses every partial subtype to
    ``'direction_correct_method_missing'`` (subtype differentiation is
    online-only, Task 10).
    """
    best_id: str | None = None
    best_score = -1.0
    best_edge: Edge | None = None
    for edge in out_edges:
        if edge.solution is None:
            continue
        score = _coverage_ratio(turn_tokens, edge.solution.approach_keywords)
        if score > best_score:
            best_score = score
            best_id = edge.edge_id
            best_edge = edge
    if (
        best_edge is None
        or best_id is None
        or best_edge.solution is None
        or best_score <= 0
    ):
        return MatchResult(type='none', edge_type=edge_type)
    present = _present_terms(turn_tokens, best_edge.solution.approach_keywords)
    if best_score >= _EXACT_RATIO:
        return MatchResult(
            type='exact',
            edge_type=edge_type,
            matched_edge_id=best_id,
            agent_mentioned_correctly=present,
            confidence=round(best_score, 3),
        )
    missing = _missing_required_elements(
        turn_tokens,
        best_edge.solution.required_elements_for_full_match,
    )
    return MatchResult(
        type='partial',
        edge_type=edge_type,
        matched_edge_id=best_id,
        subtype='direction_correct_method_missing',
        missing_elements=missing,
        agent_mentioned_correctly=present,
        confidence=round(best_score, 3),
    )


def match_edge(
    agent_turn: str,
    edge_type: EdgeTypeName,
    out_edges: list[Edge],
    *,
    online: bool = False,
    llm=None,  # noqa: ANN001
) -> MatchResult:
    """
    Match the turn against the current node's out-edges of one type.

    Offline heuristic: ``clarification_only`` edges score per-clarification
    token overlap against their ``question_patterns`` (returning
    ``matched_info_ids``); ``solution_only``/``mixed`` edges score
    ``approach_keywords`` coverage. The online branch invokes the LLM and
    funnels the result through ``_coerce_match``; on any parse failure it
    funnels to ``'none'``. No network call in offline mode.
    """
    if online and llm is not None:
        import json  # noqa: PLC0415

        from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
            MATCH_EDGE_PROMPT,
        )
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        candidates = [
            {
                'edge_id': e.edge_id,
                'question_patterns': [
                    p for c in e.clarifications for p in c.question_patterns
                ],
                'approach_keywords': (
                    list(e.solution.approach_keywords)
                    if e.solution is not None
                    else []
                ),
                'required_elements': (
                    list(e.solution.required_elements_for_full_match)
                    if e.solution is not None
                    else []
                ),
            }
            for e in out_edges
        ]
        prompt = MATCH_EDGE_PROMPT.format(
            agent_turn=agent_turn,
            edge_type=edge_type,
            candidates=json.dumps(candidates, ensure_ascii=False),
        )
        try:
            data = json.loads(extract_text(llm.invoke(prompt)))
        except (ValueError, TypeError, AttributeError):
            data = {}
        return _coerce_match(data, out_edges, edge_type)

    # --- Task 4 offline matching body (UNCHANGED) ----------------------------
    candidates_offline = [e for e in out_edges if e.edge_type == edge_type]
    if not candidates_offline:
        return MatchResult(type='none', edge_type=edge_type)
    turn_tokens = _tokenize(agent_turn)
    if edge_type == 'clarification_only':
        return _match_clarification(turn_tokens, candidates_offline)
    return _match_solution(turn_tokens, candidates_offline, edge_type)


def _offline_judge(agent_turn: str, out_edges: list[Edge]) -> MatchResult:
    """Deterministic fallback: classify then match the routed type."""
    components = classify_turn(agent_turn)
    if components.has_clarification and components.has_solution:
        edge_type: EdgeTypeName = 'mixed'
    elif components.has_solution:
        edge_type = 'solution_only'
    else:
        edge_type = 'clarification_only'
    typed = [e for e in out_edges if e.edge_type == edge_type]
    return match_edge(agent_turn, edge_type, typed)


def _coerce_match_any(raw: dict, out_edges: list[Edge]) -> MatchResult:
    """
    Validate an LLM verdict against the FULL out-edge set (any type).

    Backfills ``edge_type`` from the matched edge; an unknown id or an
    explicit ``none`` downgrades to a safe ``none``.
    """
    by_id = {e.edge_id: e for e in out_edges}
    claimed = raw.get('matched_edge_id')
    if raw.get('type') == 'none' or claimed is None or claimed not in by_id:
        return MatchResult(type='none')
    raw = dict(raw)
    raw['edge_type'] = by_id[claimed].edge_type
    return MatchResult.model_validate(raw)


def judge_turn(
    agent_turn: str,
    *,
    clarifications: list[dict],
    solution_edges: list[Edge],
    llm,  # noqa: ANN001
) -> MatchResult:
    """
    Online intent-first judge.

    Information requests match the whole-graph ``clarifications`` (returning
    ``matched_info_ids``); proposals match the current node's ``solution_edges``
    (§10 exact/partial/none). On any LLM/JSON failure, falls back to the
    deterministic offline matcher over ``solution_edges``.
    """
    import json  # noqa: PLC0415

    from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
        JUDGE_TURN_PROMPT,
    )
    from graph_bench.user_simulator.provider import (  # noqa: PLC0415
        extract_text,
    )

    sol_payload = [
        {
            'edge_id': e.edge_id,
            'approach_keywords': (
                list(e.solution.approach_keywords) if e.solution else []
            ),
            'required_elements': (
                list(e.solution.required_elements_for_full_match)
                if e.solution
                else []
            ),
        }
        for e in solution_edges
    ]
    prompt = JUDGE_TURN_PROMPT.format(
        agent_turn=agent_turn,
        clarifications=json.dumps(clarifications, ensure_ascii=False),
        solution_edges=json.dumps(sol_payload, ensure_ascii=False),
    )
    try:
        data = json.loads(extract_text(llm.invoke(prompt)))
    except Exception:
        return _offline_judge(agent_turn, solution_edges)
    if not isinstance(data, dict):
        return _offline_judge(agent_turn, solution_edges)
    intent = data.get('intent')
    if intent == 'clarification':
        valid = {c['info_id'] for c in clarifications}
        hit = [i for i in data.get('matched_info_ids', []) if i in valid]
        if not hit:
            return MatchResult(type='none', edge_type='clarification_only')
        return MatchResult(
            type='exact',
            edge_type='clarification_only',
            matched_info_ids=hit,
            confidence=float(data.get('confidence', 0.0)),
        )
    return _coerce_match_any(data, solution_edges)


def _match_clarification_dicts(
    agent_turn: str, clarifications: list[dict]
) -> MatchResult:
    """Offline twin of ``_match_clarification`` over the flat dict payload."""
    turn_tokens = _tokenize(agent_turn)
    hits: list[str] = []
    total = 0.0
    for clar in clarifications:
        best = 0.0
        for pattern in clar.get('question_patterns') or []:
            pat_tokens = _tokenize(pattern)
            if pat_tokens:
                best = max(best, len(turn_tokens & pat_tokens) / len(pat_tokens))
        if best >= _CLAR_HIT_RATIO:
            hits.append(clar['info_id'])
            total += best
    if not hits:
        return MatchResult(type='none', edge_type='clarification_only')
    return MatchResult(
        type='exact',
        edge_type='clarification_only',
        matched_info_ids=hits,
        confidence=round(total / len(hits), 3),
    )


def _fallback_outcome(
    agent_turn: str,
    solution_edges: list[Edge],
    clarifications: list[dict] | None = None,
) -> MultiMatchOutcome:
    m = _offline_judge(agent_turn, solution_edges)
    # Dual-act, same as the online path: a question is matched against the
    # clarifications whether or not the turn also proposes something.
    clar = (
        _match_clarification_dicts(agent_turn, clarifications)
        if clarifications and _looks_like_question(agent_turn)
        else None
    )
    if m.edge_type == 'clarification_only' and not solution_edges:
        return MultiMatchOutcome(
            intent='clarification',
            clar_match=clar if clar and clar.type == 'exact' else m,
        )
    if not solution_edges and _looks_like_question(agent_turn):
        # A node with no solution edge cannot produce a proposal match, so a
        # turn that asks something is an unanswered question, not a failed
        # fix. Without this the deterministic backend reported it as
        # solution_only and the responder charged it to the node's stall
        # counter — disagreeing with the online judge, which reports an
        # unmatched question as clarification_only.
        return MultiMatchOutcome(
            intent='clarification',
            clar_match=clar
            if clar and clar.type == 'exact'
            else MatchResult(type='none', edge_type='clarification_only'),
        )
    # For solution intent (or ambiguous vague turns with solution_edges present),
    # build proposals from code_coverage_pct so required_elements_for_full_match
    # is honoured (approach_keywords may be empty).
    proposals: list[ProposalMatch] = []
    best_pct = -1.0
    best_edge: Edge | None = None
    best_missing: list[str] = []
    for e in solution_edges:
        pct, missing = code_coverage_pct(agent_turn, e)
        if pct > best_pct:
            best_pct = pct
            best_edge = e
            best_missing = missing
    if best_edge is not None and best_pct > 0.0:
        proposals.append(
            ProposalMatch(
                summary='(offline fallback)',
                matched_edge_id=best_edge.edge_id,
                match_pct=best_pct,
                missing_elements=best_missing,
            )
        )
    elif m.matched_edge_id and m.edge_type != 'clarification_only':
        pct = (
            1.0
            if m.type == 'exact'
            else (m.confidence if m.type == 'partial' else 0.0)
        )
        proposals.append(
            ProposalMatch(
                summary='(offline fallback)',
                matched_edge_id=m.matched_edge_id,
                match_pct=pct,
                missing_elements=list(m.missing_elements),
            )
        )
    return MultiMatchOutcome(
        intent='solution', clar_match=clar, proposals=proposals
    )


def judge_turn_multi(
    agent_turn: str,
    *,
    clarifications: list[dict],
    solution_edges: list[Edge],
    llm,  # noqa: ANN001
) -> MultiMatchOutcome:
    """
    Hybrid online matcher: deterministic coverage pre-scan + one batched
    gpt-5.5 re-verification. Clarification intent yields ``clar_match``;
    solution intent yields a per-proposal list. LLM/JSON failure falls back
    to the deterministic offline judge.
    """
    import json  # noqa: PLC0415

    from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
        MULTI_MATCH_VERIFY_PROMPT,
    )
    from graph_bench.user_simulator.provider import (  # noqa: PLC0415
        extract_text,
    )

    candidates = []
    for e in solution_edges:
        pct, missing = code_coverage_pct(agent_turn, e)
        candidates.append(
            {
                'edge_id': e.edge_id,
                'required_elements': (
                    list(e.solution.required_elements_for_full_match)
                    if e.solution
                    else []
                ),
                'approach_keywords': (
                    list(e.solution.approach_keywords) if e.solution else []
                ),
                'code_pct': round(pct, 3),
                'code_missing': missing,
            }
        )
    prompt = MULTI_MATCH_VERIFY_PROMPT.format(
        agent_turn=agent_turn,
        clarifications=json.dumps(clarifications, ensure_ascii=False),
        candidates=json.dumps(candidates, ensure_ascii=False),
    )
    try:
        data = json.loads(extract_text(llm.invoke(prompt)))
    except Exception:  # LLM errors must never propagate
        return _fallback_outcome(agent_turn, solution_edges, clarifications)
    if not isinstance(data, dict):
        return _fallback_outcome(agent_turn, solution_edges, clarifications)

    # Both acts are read out of the SAME response. A turn that asks for
    # evidence while also proposing a fix used to be routed to one side
    # only; routed to 'solution' at a node whose out-edges are all
    # clarifications, it could not match anything by construction and
    # accrued stall — which penalised models that bundle question and
    # proposal in one turn (a style, not a capability).
    valid = {c['info_id'] for c in clarifications}
    hit = [i for i in data.get('matched_info_ids', []) if i in valid]
    clar = (
        MatchResult(
            type='exact',
            edge_type='clarification_only',
            matched_info_ids=hit,
        )
        if hit
        else MatchResult(type='none', edge_type='clarification_only')
    )
    intent = (
        'clarification' if data.get('intent') == 'clarification' else 'solution'
    )

    valid_ids = {e.edge_id for e in solution_edges}
    proposals: list[ProposalMatch] = []
    for p in data.get('proposals', []):
        eid = p.get('matched_edge_id')
        if eid not in valid_ids:
            eid = None
        proposals.append(
            ProposalMatch(
                summary=str(p.get('summary', ''))[:200],
                matched_edge_id=eid,
                match_pct=float(p.get('match_pct', 0.0)) if eid else 0.0,
                missing_elements=[
                    str(x) for x in p.get('missing_elements', [])
                ],
            )
        )
    return MultiMatchOutcome(
        intent=intent, clar_match=clar, proposals=proposals
    )


def select_advancing_match(
    proposals: list[ProposalMatch],
    solution_edges: list[Edge],
    distance_map: dict[str, int],
    threshold: float,
) -> MatchResult:
    """
    Pick the advancing match: eligible (match_pct >= threshold) proposal
    whose target node is closest to a terminal (advances furthest). Below threshold
    falls to a 'partial' on the best proposal; nothing matched -> 'none'.
    """
    unreachable = 1 << 30
    by_id = {e.edge_id: e for e in solution_edges}
    proposed_n = len(proposals)
    matched_m = sum(
        1 for p in proposals if p.matched_edge_id and p.match_pct > 0
    )
    eligible = [
        p for p in proposals if p.matched_edge_id and p.match_pct >= threshold
    ]
    if eligible:

        def _key(p: ProposalMatch) -> tuple[int, float]:
            edge = by_id.get(p.matched_edge_id or '')
            dist = (
                distance_map.get(edge.to_node, unreachable)
                if edge
                else unreachable
            )
            return (dist, -p.match_pct)

        win = min(eligible, key=_key)
        return MatchResult(
            type='exact',
            edge_type='solution_only',
            matched_edge_id=win.matched_edge_id,
            match_pct=win.match_pct,
            missing_elements=list(win.missing_elements),
            proposal_matches=proposals,
            proposed_n=proposed_n,
            matched_m=matched_m,
            confidence=win.match_pct,
        )
    best = max(proposals, key=lambda p: p.match_pct, default=None)
    if best is not None and best.match_pct > 0:
        return MatchResult(
            type='partial',
            edge_type='solution_only',
            matched_edge_id=best.matched_edge_id,
            subtype='direction_correct_method_missing',
            missing_elements=list(best.missing_elements),
            match_pct=best.match_pct,
            proposal_matches=proposals,
            proposed_n=proposed_n,
            matched_m=matched_m,
            confidence=best.match_pct,
        )
    return MatchResult(
        type='none',
        edge_type='solution_only',
        match_pct=0.0,
        proposal_matches=proposals,
        proposed_n=proposed_n,
        matched_m=matched_m,
    )


def _coerce_match(
    raw: dict,
    out_edges: list[Edge],
    edge_type: EdgeTypeName,
) -> MatchResult:
    """
    Validate a raw (LLM) match claim against the real out-edge set.

    If ``raw['matched_edge_id']`` is not the id of an out-edge of
    ``edge_type``, the claimed match is a hallucination and is downgraded
    to a safe ``none``. Otherwise the raw dict is parsed into a
    ``MatchResult`` as-is. The matcher never invents an edge.
    """
    valid_ids = {e.edge_id for e in out_edges if e.edge_type == edge_type}
    claimed = raw.get('matched_edge_id')
    if claimed is None or claimed not in valid_ids:
        return MatchResult(type='none', edge_type=edge_type)
    return MatchResult.model_validate(raw)
