# Paper Outline (working)

Working title candidates (pick late):
- *Leak-Aware Multi-Turn Evaluation: From Real Support Threads to Causal Graphs*
- *Clarification as a First-Class Citizen: Beyond Success Rate in Conversational Debugging Benchmarks*
- *TraceGraph-Bench: Causal-Graph-Grounded, Execution-Free Evaluation of Conversational Debugging Agents*

Primary venue: NeurIPS Datasets & Benchmarks (CAB's venue). Fallbacks: ICLR (methodology framing), ACL/EMNLP (dialogue evaluation), ICSE/FSE (SE framing).

## Abstract skeleton

Multi-turn benchmarks for debugging assistants either require executable environments — excluding precisely the environment-bound problems users actually bring (drivers, devices, OS integrations, cloud account state) — or condition their simulated users on resolved transcripts, leaking future knowledge and inflating scores. We formalize future-knowledge leakage and present a benchmark built from real public support threads annotated as causal graphs: nodes are (system-state, information-state) pairs, edges are assistant moves (clarifications — including user-executable measurements — solutions, and known blind paths). The same graph structurally constrains the user simulator (it can only reveal what its node contains), grounds an execution-free judge (edge matching with five-tier solution-call grading), and yields causal metrics (information-grounded decision rate; counterfactual sensitivity). [Pilot/scale numbers.] [Leakage quantification: score inflation under transcript-conditioned simulation.] [Model results + reliability report.]

## 1. Introduction

- Hook: the CAB gap — 70–83% on single-turn Stack-Overflow-style vs 7–16% on real multi-turn project issues; but CAB itself must drop every thread it cannot containerize, and its own limitations section names the bias. Meanwhile "To Run or Not to Run" (ISSTA'26): execution adds 1.25 pts (n.s.) at 8.8 runs/task.
- The two-failure framing: execution-dependence (coverage bias + cost) and simulator leakage (validity).
- One artifact solves both: the causal graph. Contributions list.

## 2. Contributions

1. **Formalization of future-knowledge (vertical) leakage** in simulated-user evaluation + graph-position constraint as a structural (not prompt-level) defense.
2. **The unified causal graph**: three edge types; (system,info) node semantics; known-blind-path edges with aftermath states; auto-generated rollback closure; shortcut expansion with skipped-info accounting and inferred-vs-blind shortcut grading.
3. **Clarification as a first-class citizen**, including the measurement-class rule (bisections, test builds, config probes are clarifications), and the information-grounded decision rate metric.
4. **Empirical graph extraction from real public threads** (vs. predefined fault trees à la JFTA-Bench / SOP graphs à la Beyond IVR): annotation protocol, funnel, agreement, cost.
5. **Execution-free judging with objective anchors** (culprit commit/PR localization) and a released reliability report (noise floor, simulator-compliance audit, gold-revision process).
6. **The benchmark itself**: environment-bound threads no execution-based benchmark can host; frozen + rolling splits; counterfactual variants.

## 3. Method (from docs/method.md)

Graph definition → leak model & simulator conditioning → judge (multi-match, partial subtypes, terminal semantics) → metrics (grounded rate, counterfactual sensitivity, five-tier solution calls) → machine closure (rollback/shortcut) → annotation pipeline (LLM draft + human review + validators).

## 4. Dataset

Wave-1 Mozilla corpus (target 50 → 100+): selection funnel with measured yields; shape balancing (persona × domain × blind-path species); scrubbing & licensing (docs/data-collection-and-privacy.md); data card incl. single-user-merge convention.

## 5. Experiments

- **E1 Leakage quantification (headline):** same agents under simulator settings A (full-transcript conditioning, CAB-style) / B (satisfaction-conditions only) / C (graph-node only, ours). A−C = leakage inflation. Optionally replicate on JFTA-Bench data to show generality.
- **E2 Oracle-agent separability:** scripted blind-guesser / conservative clarifier / inferred-shortcut expert / blind-shortcut gambler — the metric suite must separate them at equal correctness.
- **E3 Counterfactual sensitivity:** extreme vs minor vs irrelevant interventions; classify agents as causal reasoner / pattern matcher / oversensitive.
- **E4 Reliability:** repeated-run noise floor; simulator-model swap (Lost-in-Simulation-style ±); judge–human agreement on a stratified sample; culprit-localization anchor vs graph-judge correlation.
- **E5 Model study:** frontier + open models; per-metric profiles (elicitation vs decision vs recovery-from-blind-path); qualitative failure taxonomy (ask-forever, hollow re-paste, premature solution, brush-off).
- **E6 Human baseline (stretch):** experienced triagers on a case subset.

## 6. Threats & limitations

Single-user merge convention; measurement-vs-solution edge cases; judge LLM dependence (mitigated by anchors + audit); pretraining contamination (frozen/rolling + counterfactuals + canary); domain breadth (Mozilla first; GitHub/Discourse and dialogue-RCA waves as generality evidence).

## 7. Timeline (from design est.)

Pipeline + wave-1 data 2–4 wk → experiments 3–4 wk → human eval 2 wk → writing 2–3 wk. Workshop first if venue timing requires.

## Assets checklist for submission

- [ ] dataset (scrubbed) + data card + licenses
- [ ] protocol code (simulator, judge, validators, expansions)
- [ ] reliability report trio
- [ ] annotation guidelines + agreement numbers
- [ ] leakage experiment scripts (settings A/B/C)
