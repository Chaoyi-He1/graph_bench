# Related Work Survey (as of 2026-07)

Compiled from a four-track literature and data-source survey (2026-07-29). Every load-bearing claim carries its source. Working conclusion up front:

> **The combination {real support/debugging threads} × {execution-free judging} × {graph/state-machine-constrained, leak-safe user simulation} has no occupant as of 2026-07.** Each neighbor holds one or two axes.

## 1. Closest neighbors, axis by axis

| Work | Holds | Missing vs. this work |
|---|---|---|
| CodeAssistBench (CAB) — AWS, NeurIPS 2025 D&B ([arXiv:2507.10646](https://arxiv.org/abs/2507.10646), [code](https://github.com/amazon-science/CodeAssistBench)) | Real GitHub issues → multi-turn; 3,286 cases / 214 repos; User/Maintainer/Judge roles | Docker execution required where available; **self-admitted selection bias** ("only includes issues with successfully synthesized Docker environments… bias toward actively maintained, modern repositories"); judge–human agreement 65.92%; cost-capped to a 544-case eval subset |
| Dialogue SWE-Bench — UCSC 2026-06 ([arXiv:2606.13995](https://arxiv.org/abs/2606.13995)) | Persona-grounded anti-leak user sim (no verbatim paste, self-revision check) | Execution-based resolve rate; hidden-text info model, no graph/state semantics |
| CirrusBench — 2026-03, KDD'26 sub ([arXiv:2603.28569](https://arxiv.org/html/2603.28569)) | Real cloud-service tickets, multi-turn, checkpoint scoring | Checkpoints are LLM-annotated linear anchors, not causal graphs; no leak-safe sim design; tool-execution dependent |
| JFTA-Bench — 2026-03 ([arXiv:2603.22978](https://arxiv.org/abs/2603.22978)) | Execution-free multi-turn troubleshooting on fault trees (126 trees, ~140 nodes each, 3,130 paths, avg 40.75 turns); simulated user with rollback/changed-mind injections | Trees are predefined domain knowledge, not empirically extracted from real threads; no (system,info) state semantics, no known-blind-path edges; **data release not found** |
| τ/τ²/τ³-bench — Sierra ([arXiv:2406.12045](https://arxiv.org/abs/2406.12045), [arXiv:2506.07982](https://arxiv.org/abs/2506.07982), [repo](https://github.com/sierra-research/tau2-bench), MIT) | DB/world final-state comparison (no code sandbox); dual-control telecom troubleshooting; pass^k | Hand-built synthetic domains, no real threads; τ² self-audit found simulator violates instructions in 22% of Airline dialogues; τ³ fixed 75+ faulty tasks |
| Beyond IVR — 2026-01 ([arXiv:2601.00596](https://arxiv.org/pdf/2601.00596)) | SOP digraph/state machine drives scenario generation + compliance judging | Prescriptive SOPs, synthetic scenarios; grades policy compliance, not diagnostic progress |
| IntellAgent — Plurai 2025-01 ([arXiv:2501.11067](https://arxiv.org/abs/2501.11067), [code](https://github.com/plurai-ai/intellagent)) | Policy-graph → synthetic dialogues → fine-grained critique | Graph synthesized from policy text, not from cases; judge-based only |
| ExCyTIn-Bench — Microsoft, ICML 2026 ([arXiv:2507.14201](https://arxiv.org/abs/2507.14201)) | Incident-graph path-aware scoring over recorded logs | SOC domain; interaction is SQL querying, not dialogue with a user |
| LLM-as-an-Investigator — 2026-06 ([arXiv:2606.13220](https://arxiv.org/abs/2606.13220)) | Forum-thread-derived cases; GT-holding evaluator plays the user and hides the known fix | Mechanical/electrical/hydraulic domain; code and data not released |

## 2. Multi-turn / user-simulator benchmark landscape

- **UserBench** (Salesforce, [arXiv:2507.22034](https://arxiv.org/abs/2507.22034), Apache-2.0): gym-style travel planning, preferences revealed incrementally; top models surface <30% of hidden preferences.
- **ToolSandbox** (Apple, [arXiv:2408.04682](https://arxiv.org/abs/2408.04682)): stateful tools, on-policy sim, milestone/minefield trajectory matching (light in-process execution).
- **BFCL v3/v4** (Berkeley, [leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html), Apache-2.0): per-turn state comparison; criticized for read-only-function blindness ([issue #914](https://github.com/ShishirPatil/gorilla/issues/914)) and single-gold rejection of legal alternatives.
- **MultiChallenge** (Scale, [arXiv:2501.17399](https://arxiv.org/abs/2501.17399), CC-BY-4.0, 266 items): instance-rubric LLM judge, pre-scripted history — no interactive elicitation.
- **MINT** ([arXiv:2309.10691](https://arxiv.org/abs/2309.10691)); **ColBench/SWEET-RL** (Meta, [arXiv:2503.15478](https://arxiv.org/abs/2503.15478), CC-BY-NC); **MTRAG/MTRAG-UN** (IBM, [arXiv:2501.03468](https://arxiv.org/abs/2501.03468), [arXiv:2602.23184](https://arxiv.org/abs/2602.23184), Apache-2.0).
- Flow/graph-guided dialogue lineage: **ABCD** ([NAACL 2021](https://aclanthology.org/2021.naacl-main.239/), action-sequence matching), **MultiWOZ/SGD**, **FlowBench** ([arXiv:2406.14884](https://arxiv.org/abs/2406.14884)), **PFDial** ([arXiv:2503.06706](https://arxiv.org/abs/2503.06706)), **CausalDialogue** ([arXiv:2212.10515](https://arxiv.org/abs/2212.10515)).
- Clarification-behavior line: **IN3/Tell-Me-More** ([arXiv:2402.09205](https://arxiv.org/abs/2402.09205)), **ClarifyGPT** ([arXiv:2310.10996](https://arxiv.org/abs/2310.10996)), **CodeClarQA** ([arXiv:2212.09885](https://arxiv.org/abs/2212.09885)), **Ambig-SWE** (ICLR 2026, [arXiv:2502.13069](https://arxiv.org/abs/2502.13069)), **Ask or Assume?** ([arXiv:2603.26233](https://arxiv.org/abs/2603.26233)), **ClarifyMT-Bench** ([arXiv:2512.21120](https://arxiv.org/abs/2512.21120), 6,120 dialogues, systematic under-clarification), **RegretBench** ([arXiv:2607.21143](https://arxiv.org/abs/2607.21143), clarification as policy with regret objective), **DiscoBench** ([arXiv:2606.01815 sibling, deep-search clarification](https://arxiv.org/abs/2606.27669)).
- Simulator-fidelity critique (must-cite for defense): **Lost in Conversation** (Microsoft, [arXiv:2505.06120](https://arxiv.org/pdf/2505.06120), MIT, fully reproducible sharded-disclosure protocol; multi-turn −39%); **Lost in Simulation** ([arXiv:2601.17087](https://arxiv.org/html/2601.17087), swapping simulators moves success up to 9 pts, demographic bias); **UserLM-8b / Flipping the Dialogue** (assistant-LMs are poor simulators: GPT-4o-as-user 74.6% vs trained UserLM 57.4%); **SimulatorArena**; **CRAB-Bench** ([arXiv:2606.01815](https://arxiv.org/abs/2606.01815), RUSE persona engine drops pass@1 up to 57%).

## 3. The execution-free evidence base (motivation section material)

- **"To Run or Not to Run"** (ISSTA 2026, [arXiv:2606.26978](https://arxiv.org/abs/2606.26978)): with a commercial agent and SOTA models, forbidding execution costs only 1.25 pts resolve-rate (not significant), while execution averages 8.8 runs/task.
- **Execution-free judge toolchain**: LLM Critics predict SWE-bench build status at 82.1% ([arXiv:2501.16655](https://arxiv.org/abs/2501.16655)); SWE-Judge/SE-Jury ([arXiv:2505.20854](https://arxiv.org/abs/2505.20854)); CodeJudgeBench ([arXiv:2507.10535](https://arxiv.org/abs/2507.10535)); survey ([arXiv:2510.24367](https://arxiv.org/abs/2510.24367)).
- **Live-environment retreat in ops**: ITBench (IBM, [arXiv:2502.05352](https://arxiv.org/abs/2502.05352)) required push-button K8s fault injection; IBM×Artificial Analysis shipped the offline snapshot variant **ITBench-AA** ([blog](https://huggingface.co/blog/ibm-research/itbench-aa), 59 incidents, all frontier models <50%). **Cloud-OpsBench** ([arXiv:2603.00468](https://arxiv.org/html/2603.00468v1), 452 cases, CC BY 4.0) freezes control-plane state + pre-renders ~487 tool responses per case, explicitly citing live injection's non-determinism and "tens of machine-hours per evaluation cycle".
- SWE-bench family never dropped execution — it cheapened it (SWE-bench-Live monthly ~50 verified adds, MIT, [arXiv:2505.23419](https://arxiv.org/abs/2505.23419); SWE-rebench monthly decontamination tagging, [arXiv:2505.20411](https://arxiv.org/abs/2505.20411)) or relocated it (SWE-bench Multimodal hidden test split behind sb-cli, [arXiv:2410.03859](https://arxiv.org/abs/2410.03859)). The execution-free slot in that family is open.

## 4. SRE/RCA adjacency (second-domain candidates)

- **OpenRCA** (Microsoft, ICLR 2025, [code MIT](https://github.com/microsoft/OpenRCA); telemetry CC BY-NC 4.0; 335 cases / 68 GB) — one-shot triple prediction over recorded telemetry; **OpenRCA 2.0** adds step-wise causal-path labels ([arXiv:2606.27154](https://arxiv.org/abs/2606.27154); outcome-only masks failures: 76% root-cause hit vs 61.5% on verified paths).
- Recorded fault datasets: **RCAEval** (735 cases, [repo](https://github.com/phamquiluan/RCAEval)); **Nezha** (FSE'23, MIT, code-region-level GT, [repo](https://github.com/IntelligentDDS/Nezha)); **GAIA** ([repo](https://github.com/CloudWise-OpenSource/GAIA-DataSet)); AIOps Challenge series.
- Narrative sources for graph seeds: GitLab gl-infra production tracker public incident reviews ([example](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18491)) — genuine step-by-step public investigation threads; VOID; danluu/post-mortems; k8s.af.
- **No SRE benchmark has the agent elicit evidence from a *person***; interaction is uniformly tool/API querying. A dialogue-RCA extension over pre-recorded observations is white space.

## 5. What the 2026 debate is actually about (defense checklist)

Execution-free scoring itself no longer needs defending (τ final-state, BFCL state-match, MultiChallenge rubric-judge are all mainstream). The live critiques target:

1. **Simulator fidelity/bias** → answered structurally (node-scoped conditioning), plus release artifacts: simulator-compliance self-audit (baseline: τ²'s 22%), multi-simulator stability report (baseline: ±9 pts), assistant-LM-as-user caveats.
2. **Gold quality / multiple legal solutions** → answered by explicit multi-path graphs with known-blind-path edges, versioned gold revision (baseline: τ³'s 75+ fixes), and the culprit-commit objective anchor.
3. **Contamination** → frozen vs rolling splits (SWE-bench-Live precedent), counterfactual variants (graph-native), canary strings.

## 6. License precedents for release

MIT/Apache-2.0 dominate protocol code (τ family, MTRAG, UserBench, lost_in_conversation); data released as CC-BY-4.0 has precedent for real-thread content (MultiChallenge; **BugsRepo**: 119,585 Mozilla threads, Zenodo CC-BY-4.0, [arXiv:2504.18806](https://arxiv.org/abs/2504.18806)); Mozilla itself redistributes its full bug DB via **bugbug** ([data docs](https://github.com/mozilla/bugbug/blob/master/docs/data.md)). GitHub-sourced follow-ups: full-text republication precedents (SWE-bench; [the-stack-github-issues](https://huggingface.co/datasets/bigcode/the-stack-github-issues), ~31M conversations, usernames masked) under the GitHub AUP research exemption (results must be open-access). Known negative precedent: GHTorrent's GDPR complaints over email distribution — pseudonymize and keep a takedown channel.
