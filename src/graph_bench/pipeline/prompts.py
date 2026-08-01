"""Prompts for the CAB-style filter stage and the graph-drafting stage."""

from __future__ import annotations

FILTER_PROMPT = """\
You screen resolved GitHub issue threads for a conversational-debugging \
benchmark. The benchmark replays each thread as a dialogue between a \
simulated user and an assistant, so a usable thread must be a genuine \
diagnostic conversation with a confirmed outcome.

Answer strictly as one JSON object with these boolean keys plus "reason" \
(one sentence):
- resolved_with_confirmed_fix: the problem was actually fixed or given a \
definitive resolution IN the thread (linked PR/commit/release, or the \
reporter confirms the fix works). "Closed as stale/duplicate/won't fix" \
is false.
- technically_specific: concrete software problem with observable \
symptoms, not a discussion/feature request/question about docs.
- multi_turn_diagnostic: at least two ask->report loops between the \
reporter (or other affected users) and maintainers (requests for logs, \
versions, repro attempts, test builds, config probes...).
- environment_bound: the failure depends on the reporter's environment \
(device, OS version, driver, hardware, account/network state) so a \
maintainer could not trivially reproduce it in a container.
- reporter_engaged: the reporter (or another affected user) keeps \
responding with requested evidence.
- safe_content: no security-sensitive exploit detail, no harassment, no \
heavy personal data beyond ordinary usernames.
- annotatable: overall, the thread can be rewritten as a state-machine of \
(symptoms, collected info) with clarification steps, failed attempts, and \
a final fix.

THREAD:
{thread}
"""

DRAFT_SYSTEM = """\
You convert one resolved support thread into ONE benchmark task graph for \
an execution-free multi-turn benchmark. The graph is later used to drive a \
leak-safe user simulator and an edge-matching judge, so it must encode the \
case's ANSWER KEY, not a transcript: a node's out-edges are the known moves \
with known outcomes at that state, and edge order need not mirror thread \
chronology. What MUST mirror the thread exactly is who knew what, when — \
the simulated user can only ever say what the real reporter had actually \
produced at that point.

SCHEMA (JSON, exact field names; `from`/`to` are the edge endpoint keys):
Task: {{task_id, title, body, graph, satisfaction_conditions[],
      persona_hint{{experience_level, communication_style}},
      metadata{{graph_version:"v1", created_from, hitl_reviewed:false}},
      opening_images[]}}
Graph: {{start_node, nodes{{id->Node}}, edges[Edge]}}
Node: {{system_state_id, info_state[], symptoms_visible[], is_terminal,
      label, volunteered_info[], user_perceives_resolved,
      symptom_images[]}}
Edge: {{edge_id, edge_type: clarification_only|solution_only|mixed,
      from, to, clarifications[], solution|null, comment}}
Clarification: {{info_id, level: L1_basic|L2_inferable|L3_specific,
      question_patterns[], user_answer_in_this_oncall, images[],
      counterfactual_candidates[{{type: extreme|minor|irrelevant, answer,
      solution_should_change}}]}}
Solution: {{intent, approach_keywords[], concrete_example,
      required_elements_for_full_match[], required_info{{L1,L2,L3}},
      info_inferred_by_engineer[], is_composite:false, composed_of:[],
      is_known_blind_path, is_shortcut:false, shortcut_skipped_info:[],
      inference_hint:null}}

SEMANTIC RULES (violations make the task unusable):
1. Node = (system_state_id, info_state). system_state_id stays "S1" while
   the world is unchanged; the terminal node after the fix ships is "S2".
   info_state grows monotonically along the canonical path, and every id
   in any node's info_state must be INTRODUCED somewhere: the start
   node's seed, a clarification on some edge, a node's volunteered_info,
   or a solution's info_inferred_by_engineer (machine-validated).
   required_info levels grade obtainability from the reporter: L1 = any
   user states it unprompted; L2 = inferable from evidence already
   surfaced; L3 = must be asked for or measured. A fact visible in an
   artifact but only surfaced after a handler told the reporter to go
   check is L3 must-ask, not inferable.
2. symptoms_visible contains ONLY observable phenomena in the user's
   first-person words — never diagnoses, causes, advice, or verdicts on
   an approach ("didn't help", "wrong direction"). The failed status of
   an attempt is recorded ONLY by is_known_blind_path on the edge, never
   in symptom text: the simulated user speaks symptoms aloud, so a
   verdict written into a symptom leaks that a branch is dead before the
   agent reasons. Aftermath nodes state the post-attempt OBSERVATION
   ("backgrounds are still the wrong colour after the update"); the
   terminal node states the observable end state, never release
   management or engineering status.
3. Information containment: for every clarification/mixed edge,
   to.info_state must contain from.info_state plus every asked info_id.
   The destination may additionally gain engineer-inferred ids (also list
   them in info_inferred_by_engineer where a solution relies on them).
4. MEASUREMENT-CLASS RULE: handler-initiated measurements the user
   executes — bisection runs, test/try builds, config-toggle probes,
   version checks, benchmarks — are clarification_only edges (they change
   knowledge, not the system), even when the probed toggle doubles as a
   workaround. THE ANSWER IS THE RAW OUTPUT: the user_answer states only
   what the reporter actually produced and said (dates, pushlog URLs,
   pasted log lines, scores, "I'm not sure which one to report") — NEVER
   the conclusion an engineer later drew from that output (which commit
   is the regressor, which pref/flag is implicated, what the mechanism
   is). The conclusion belongs in the consuming solution's
   info_inferred_by_engineer and, when displaying it should be scored as
   inference, in that solution's inference_hint. This is the single most
   damaging leak class: a bisection answer that names the culprit hands
   the agent the answer key.
4b. USER-VOICE RULE: every user_answer_in_this_oncall is in the
   reporter's own FIRST-PERSON voice — words they actually typed or
   could type. Never third-person narration ("the reporter provided...",
   "a second user ran..."), never handler-action verbs (inspected/found/
   judged/provided), never the artifact described in place of the fact
   ("the screenshot shows the console error" — write what the user would
   say: "the console throws invalid state mutation"). Unprompted facts a
   user adds alongside an answer go into the TARGET node's
   volunteered_info.
4c. DENOISE RULE: logistics and coordination content — release
   scheduling, uplift/backport approvals, GA dates, packaging, thanks,
   bot chatter — never becomes an edge, a required_element, an
   approach_keyword, or a satisfaction condition. Score only the
   technical diagnostic-to-fix chain; release facts may appear in
   concrete_example as factual record.
5. Blind paths: solution_only edges with is_known_blind_path=true are
   ONLY for attempts actually falsified in the thread (tried and did not
   resolve) or brush-off resolutions the reporter rejected with evidence.
   They land on aftermath nodes named like "N2_x" whose symptoms_visible
   describe the (possibly evolved) post-attempt state, and whose
   info_state gains a volunteered id recording the falsification. Never
   invent failures.
6. The canonical path may run THROUGH aftermath nodes when the real
   thread reached the fix only after failures.
7. The final solution edge targets the terminal node (is_terminal=true,
   user_perceives_resolved=true). Its required_info lists the info ids it
   depends on, graded L1 (any user states it), L2 (inferable), L3
   (specific collected evidence). satisfaction_conditions must demand:
   the true root cause, grounding in the collected evidence, prohibition
   of the falsified moves, and user verification before declaring
   resolution.
8. Naming: nodes N0, N1, N2_x, ..., N_terminal; edge_id
   "e{{k}}_{{from}}__{{to}}"; info_ids are snake_case English summaries.
   All free text in the thread's language.
9. Multi-user threads: fold all affected users into ONE simulated user
   side; note the merge in the relevant edge's comment field.
10. Images: use ONLY the provided local attachment paths. opening_images =
    attachments on the opening post; node symptom_images = attachments
    evidencing that state; clarification images = attachments delivered
    with that answer. Reference each attachment at most once. Do not
    reference attachments that are not in the provided list.
11. Keep the graph focused: 5-9 nodes. body = the opening report in the
    reporter's voice (no future knowledge). persona_hint reflects the
    reporter's actual expertise and style. Add 1-3
    counterfactual_candidates on the most decision-relevant
    clarifications.

Study the two example tasks (Mozilla threads annotated and leak-repaired
by hand), then produce the SAME shape for the new thread. Example B shows
the measurement-class rule done right: bisection/test-build answers carry
raw output only, and the culprit identification lives in the final
solution's inference_hint.

EXAMPLE TASK A (compact):
{fewshot_a}

EXAMPLE TASK B (measurement-heavy):
{fewshot_b}

Output exactly one JSON object (the Task). No markdown fences, no prose.
"""

DRAFT_USER = """\
NEW THREAD TO ANNOTATE (repo {repo}, issue #{number}, resolved):

task_id to use: {task_id}
metadata.created_from to use: "{created_from}"
Available local attachments (path -> came from):
{attachments}

{thread}
"""

REPAIR_PROMPT = """\
Your previous Task JSON (the assistant message above) failed machine \
validation. Re-read the thread and the semantic rules, fix the problem at \
its source — do not just rewire fields to silence the validator — and \
output the complete corrected JSON object (no fences, no prose). Keep \
everything that was already valid.

VALIDATION ERROR:
{error}
"""
