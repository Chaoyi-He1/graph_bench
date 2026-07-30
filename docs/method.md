# Method: Causal-Graph-Grounded, Execution-Free Evaluation of Conversational Debugging Agents

Working notes for the paper. Formal definitions live here before they move into the paper body.

## 1. Problem

We evaluate chatbot-style agents that help a user diagnose and fix a software problem over multiple turns. The user executes actions; the agent cannot run anything. Two properties make existing benchmark recipes inapplicable:

1. **No executable environment.** The target class of problems is environment-bound — device drivers, OS integrations, hardware revisions, account state — so container-replay evaluation (SWE-bench-style tests, CAB-style Docker sessions) is impossible or misleadingly selective. Benchmarks that require a buildable environment systematically exclude exactly these threads (CAB's own limitation section documents the bias).
2. **Future-knowledge leakage.** If the user simulator is conditioned on the full resolved thread (CAB) or on hidden gold answers, it leaks information from the future of the conversation — through phrasing, unprompted disclosures, or over-cooperative confirmation — inflating agent scores. We call this vertical leakage, distinct from horizontal leakage (revealing more per answer than a real user would).

Design goal: an evaluation where a simulated user can only reveal what a real user at the same investigative state could have revealed, and where scoring needs no execution.

## 2. The causal graph

Each resolved real-world support thread is annotated as a state machine.

**Node = (system_state_id, info_state).** `system_state_id` changes only when the user's world actually changes (a fix applied and kept, a release installed). Most nodes share one system state; what evolves during investigation is `info_state` — the monotonically growing set of surfaced information ids. Each node carries `symptoms_visible`: only observable phenomena, never diagnoses or advice. Nodes may carry `volunteered_info` (revealed on first arrival) and attachments evidencing the symptoms.

**Edge = one assistant turn.** Three types:

- `clarification_only`: the assistant asks for information or for a *user-executable measurement* (a bisection run, a test build, a config-toggle probe, a benchmark). Measurement-class actions are clarifications by rule, even when the probed toggle doubles as a workaround: they change knowledge, not the system.
- `solution_only`: the assistant proposes an action that changes the user's system. Attempts known (from the thread) not to resolve the case carry `is_known_blind_path=True` and land on *aftermath* nodes — live states with their own symptoms (possibly evolved: "partially improved, backgrounds still broken") from which the dialogue continues. The canonical thread itself may run *through* failures: real cases often reach the fix only after several falsified attempts.
- `mixed`: both in one turn.

**Information levels.** Each required info id is graded L1 (basic, any user states it), L2 (inferable), or L3 (specific evidence). Only proposing a solution while L3-critical information is missing counts as a blind guess.

**Answer keys, not transcripts.** The out-edges of a node are the case's answer key for that state — known attempts with known outcomes, the known fix, clarifications with authored answers — not a replay of what the historical participants happened to do there.

## 3. Machine-generated closure

Two derived layers are generated, not hand-authored:

- **Rollback edges**: for every blind edge X→D, an automatic undo edge D→X′ to the aftermath state's equal-or-smaller-information investigation twin — escape hatches that keep every aftermath state solvable.
- **Shortcut expansion**: a copy of a canonical solution edge A→T is planted at node C iff C shares A's system state, C is non-terminal, and either info(C) ⊆ info(A) (the gap recorded in `shortcut_skipped_info`) or info(A) ⊂ info(C) ⊆ info(T). Copies inherit the blind-path flag. This lets an agent legitimately skip clarifications — but the judge grades the skip: a shortcut whose reply demonstrates reasoning over the skipped information is an *inferred shortcut*; one that does not is a *blind shortcut*.

## 4. Leak-constrained user simulation

The simulator is conditioned **only on the current node**: its visible symptoms, its info_state (ids and authored answers), and a persona hint. It never sees the graph, the future of the thread, or satisfaction conditions. Consequences:

- Answers to matched clarifications reveal exactly the authored `user_answer` (plus the original attachment, when one exists — evidence is delivered as the artifact the real user posted, not a curated transcription).
- Off-target questions receive neutral, non-directive replies; unmatched proposals receive "tried it, no change" only via graph transitions, never invented outcomes.
- Stalls escalate along authored structure (corrective vs encouraging phrasing keyed to whether the agent's direction is a known blind path), with a bounded forced-reveal insurance to terminate degenerate loops.

Leakage becomes *structurally impossible* rather than prompt-discouraged: the simulator cannot reveal information absent from its node.

## 5. Execution-free judging

Every agent turn is matched against the current node's out-edges (proposals) and the whole graph's clarifications (information requests), producing exact / partial / none at the edge level with deterministic keyword coverage plus an LLM verification pass; multiple proposals in one turn are matched independently. Terminal scoring separates "symptoms gone" from "resolved and verified" (`user_perceives_resolved`), and grades solution calls on five tiers: informed / mixed-efficient / inferred shortcut / blind shortcut / blind guess. Additional signals:

- **Information-grounded decision rate**: fraction of solution calls whose required info (esp. L3) was actually surfaced first.
- **Counterfactual sensitivity**: interventions on clarification answers (extreme / minor / irrelevant, authored per edge) test whether the agent's proposal *causally depends* on the information it collected — a pattern-matcher keeps its answer under extreme interventions; an over-sensitive agent changes it under irrelevant ones.
- **Objective anchor**: each case links the real fix commit/PR; culprit-artifact localization is checkable without execution and calibrates the graph judge.

## 6. Positioning in one line

Prior work occupies at most two of the three axes {real support threads, execution-free judging, structurally leak-safe simulation}; the graph is the single artifact that provides all three, because the same structure that constrains the simulator (anti-leak) also grounds the judge (edge matching) and the metrics (grounded-decision rate, counterfactual sensitivity).

See `related-work.md` for the axis-by-axis comparison and `pilot-study.md` for evidence that real public threads annotate cleanly into this schema.
