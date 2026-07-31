from __future__ import annotations

# --- Online matcher/speaker prompts (Task 10) -------------------------------

CLASSIFY_TURN_PROMPT = """You classify a single support-agent turn in a \
technical oncall chat. Decide which components it contains.

Agent turn:
---
{agent_turn}
---

A turn has a CLARIFICATION if it asks the user a question to gather more \
information. It has a SOLUTION if it proposes a concrete fix, code change, \
or action for the user to take. A turn may have both (then both are true).

Return ONLY a JSON object, no prose, with exactly these keys:
{{"has_clarification": <bool>, "has_solution": <bool>,
"extracted_question": <string or null>, "extracted_proposal": <string or null>}}
"""

MATCH_EDGE_PROMPT = """You match a support-agent turn against the user's \
current situation. Only the candidate edges below are valid; never invent an \
edge id. Decide whether the agent's turn is an exact match, a partial match, \
or no match for one of them.

Agent turn:
---
{agent_turn}
---

Classified edge_type: {edge_type}

Candidate edges (JSON list; match against the patterns/keywords shown):
{candidates}

Rules:
- "exact": the turn clearly satisfies one edge's intent.
- "partial": right direction but incomplete; set "subtype" to one of \
[direction_correct_method_missing, method_correct_target_unclear, \
concept_correct_tool_different, multi_step_partial, \
keyword_correct_direction_wrong] and list "missing_elements".
- "none": no candidate fits.

Return ONLY a JSON object with exactly these keys:
{{"type": "exact"|"partial"|"none", "matched_edge_id": <id from the list or \
null>, "subtype": <subtype or null>, "missing_elements": [<string>...], \
"agent_mentioned_correctly": [<string>...], "confidence": <float 0-1>}}
"""

JUDGE_TURN_PROMPT = """You are the USER in an oncall chat, deciding how to \
react to a support-agent turn. First decide the agent's PRIMARY ACT:

- "clarification": the agent is asking YOU to provide information (answer a \
question, paste code/logs, report a version, relay a question to someone). \
This includes requests framed as instructions to fetch info.
- "solution": the agent proposes a concrete fix/change for YOU to apply.
- "both": it does both in one turn.

Agent turn:
---
{agent_turn}
---

Authored clarification questions the user can answer (JSON; match the agent's \
question to these BY MEANING, not wording):
{clarifications}

Candidate solution edges at the current step (JSON; match a proposal against \
approach_keywords / required_elements):
{solution_edges}

Rules:
- If the act is "clarification": set "intent"="clarification" and match the \
question against the clarification list. Set "matched_info_ids" to the info_ids \
the agent is asking about (by meaning, across the whole list). If none fit, \
"type"="none" with empty matched_info_ids. A clarification request must NEVER \
be matched to a solution edge.
- If the act is "solution": set "intent"="solution" and match against the \
solution edges: "exact" (satisfies an edge), "partial" (right direction, set \
"subtype" in [direction_correct_method_missing, method_correct_target_unclear, \
concept_correct_tool_different, multi_step_partial, \
keyword_correct_direction_wrong] + "missing_elements" + \
"agent_mentioned_correctly"), or "none".
- If "both": prefer the solution match if a solution edge fits; otherwise the \
clarification match.

Return ONLY a JSON object with exactly these keys: {{"intent": \
"clarification"|"solution", "type": "exact"|"partial"|"none", \
"matched_info_ids": [<info_id>...], "matched_edge_id": <edge id or null>, \
"subtype": <subtype or null>, "missing_elements": [<string>...], \
"agent_mentioned_correctly": [<string>...], "confidence": <float 0-1>}}
"""

MULTI_MATCH_VERIFY_PROMPT = (
    'You are the USER in an oncall chat, re-verifying how a support-agent '
    'turn maps to your situation.\n\n'
    'First decide the PRIMARY ACT:\n'
    '- "clarification": the agent asks YOU for information.\n'
    '- "solution": the agent proposes one or more concrete fixes to apply.\n\n'
    'Agent turn:\n---\n{agent_turn}\n---\n\n'
    'Authored clarification questions you can answer (JSON; match by '
    'MEANING):\n{clarifications}\n\n'
    'Candidate solution edges. Each lists the elements a FULL match needs and '
    "a deterministic code pre-scan of this turn's coverage (JSON):\n"
    '{candidates}\n\n'
    'Rules:\n'
    '- If the act is "clarification": set "intent"="clarification" and set '
    '"matched_info_ids" to the info_ids the agent asks about (by meaning, '
    'across the whole list). Leave "proposals" empty.\n'
    '- If the act is "solution": set "intent"="solution" and split the turn '
    'into the DISTINCT fixes it proposes. For EACH proposal return one '
    'object: "summary" (<=12 words), "matched_edge_id" (best-fitting '
    'candidate edge id, or null), "match_pct" (0.0-1.0 = fraction of that '
    "edge's required elements this proposal satisfies; use the code pre-scan "
    'as a prior, correct it semantically), "missing_elements" (required '
    'elements still not satisfied).\n'
    '- Never invent an edge id outside the candidate list.\n\n'
    'Return ONLY JSON: {{"intent": "clarification"|"solution", '
    '"matched_info_ids": [<info_id>...], "proposals": [{{"summary": <str>, '
    '"matched_edge_id": <id|null>, "match_pct": <float>, '
    '"missing_elements": [<str>...]}}]}}'
)

SPEAKER_REACT_PROMPT = """You are role-playing the USER in an oncall chat. \
Write the user's next reply. Stay in the user's language (Chinese if the \
symptoms are Chinese). Use ONLY the conversation so far and the reply intent \
below — invent NO new technical facts, name NO root cause, tool, or fix, and \
reveal nothing the user could not already know.

Persona hint: {persona}
Current visible symptoms: {symptoms}
Recent conversation (most recent last):
{history}

Reply intent (what THIS message must accomplish — paraphrase naturally, do \
NOT quote it verbatim):
{intent}

Fallback phrasing (tone reference only, do not copy):
{draft}

Return ONLY the user message as plain text, 1-3 sentences."""

SPEAKER_PERSONA_PROMPT = """You are role-playing the USER in an oncall chat. \
Rewrite the draft reply in the user's voice. Stay in the user's language \
(Chinese if the symptoms are Chinese). Add NO new technical facts beyond the \
draft: you may only restate what the draft already says, more naturally.

Persona hint: {persona}
Current visible symptoms: {symptoms}
Style examples from real users (imitate tone only, NOT content):
{examples}

Draft reply (this is exactly what you must convey):
---
{draft}
---

Return ONLY the rewritten user message as plain text, 1-3 sentences."""
