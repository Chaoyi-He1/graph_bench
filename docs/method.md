# Method: Causal-Graph-Grounded, Execution-Free Evaluation of Conversational Debugging Agents

Working notes for the paper. Formal definitions live here before they move into the paper body.

## 1. Problem

We evaluate chatbot-style agents that help a user diagnose and fix a software problem over multiple turns. The user executes actions; the agent cannot run anything. Two properties make existing benchmark recipes inapplicable:

1. **No executable environment.** The target class of problems is environment-bound — device drivers, OS integrations, hardware revisions, account state — so container-replay evaluation (SWE-bench-style tests, CAB-style Docker sessions) is impossible or misleadingly selective. Benchmarks that require a buildable environment systematically exclude exactly these threads (CAB's own limitation section documents the bias).
2. **Future-knowledge leakage.** If the user simulator is conditioned on the full resolved thread (CAB) or on hidden gold answers, it leaks information from the future of the conversation — through phrasing, unprompted disclosures, or over-cooperative confirmation — inflating agent scores. We call this vertical leakage, distinct from horizontal leakage (revealing more per answer than a real user would).

Design goal: an evaluation where a simulated user can only reveal what a real user at the same investigative state could have revealed, and where scoring needs no execution.

## 2. The causal graph

**The graph is the case's ANSWER KEY, not a transcript.** Edge order need not mirror thread chronology, and a node's out-edges are the known moves with known outcomes at that state — reviewers and auditors repeatedly mistake chronology mismatch for a defect, so this is stated up front. What must mirror the thread exactly is *who knew what, when*.

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
- Off-target questions receive neutral, non-directive replies; unmatched proposals receive "tried it, no change" only via graph transitions, never invented outcomes. Where the case models no fix attempt from the current state at all — a node whose out-edges are all clarifications — the user reports no outcome whatsoever, and says it has not run the step: asserting a negative result the case never established is itself a leak of false evidence, and one that argues agents off correct paths.
- Stalls escalate along authored structure (corrective vs encouraging phrasing keyed to whether the agent's direction is a known blind path), with a bounded forced-reveal insurance to terminate degenerate loops. The insurance reveals the first edge of the node's canonical path, searched in two tiers: over the subgraph without blind paths, then — only for nodes that tier cannot route — with blind paths re-admitted. Most real threads reach their fix *through* a failed attempt, so an early node's only route to the terminal often crosses one blind edge into its aftermath state; a single-tier search leaves such nodes with nothing to reveal, and the insurance then terminates a solvable case as a dead end with most of its turn budget unspent. Shortcut copies stay excluded in both tiers, since walking one would hand the agent a later state it never worked for.
- A follow-up to a partial match names the *kind* of gap, never its content: an answer that gave complete steps but no account of the fault is pressed for the account, not for the steps it already gave. Demanding what the agent has already supplied is feedback it cannot act on, and repeating that demand until the insurance fires measures the simulator, not the agent.

Leakage becomes *structurally impossible* rather than prompt-discouraged: the simulator cannot reveal information absent from its node.

## 5. Execution-free judging

Every agent turn is matched against the current node's out-edges (proposals) and the whole graph's clarifications (information requests), producing exact / partial / none at the edge level with deterministic keyword coverage plus an LLM verification pass; multiple proposals in one turn are matched independently. A turn is scored on **both** acts, not on whichever one dominates: asking for evidence while floating a hypothesis is the normal shape of a diagnostic reply, and routing such a turn to the proposal side alone leaves it unmatchable at any state whose modeled way forward is a question — which penalises a turn *format* rather than diagnostic ability. The two acts fold in one order: an exact proposal advances the state and any question it carried is answered afterwards, so a question can never retroactively ground a proposal made without its answer; otherwise a question that surfaces new information advances the information state; otherwise the proposal outcome stands. Terminal scoring separates "symptoms gone" from "resolved and verified" (`user_perceives_resolved`), and grades solution calls on five tiers: informed / mixed-efficient / inferred shortcut / blind shortcut / blind guess. Additional signals:

- **Information-grounded decision rate**: fraction of solution calls whose required info (esp. L3) was actually surfaced first.
- **Counterfactual sensitivity**: interventions on clarification answers (extreme / minor / irrelevant, authored per edge) test whether the agent's proposal *causally depends* on the information it collected — a pattern-matcher keeps its answer under extreme interventions; an over-sensitive agent changes it under irrelevant ones.
- **Objective anchor**: each case links the real fix commit/PR; culprit-artifact localization is checkable without execution and calibrates the graph judge.

## 6. Positioning in one line

Prior work occupies at most two of the three axes {real support threads, execution-free judging, structurally leak-safe simulation}; the graph is the single artifact that provides all three, because the same structure that constrains the simulator (anti-leak) also grounds the judge (edge matching) and the metrics (grounded-decision rate, counterfactual sensitivity).

See `related-work.md` for the axis-by-axis comparison and `pilot-study.md` for evidence that real public threads annotate cleanly into this schema.
