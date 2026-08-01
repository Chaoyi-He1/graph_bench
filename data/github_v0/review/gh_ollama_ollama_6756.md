# Review: gh_ollama_ollama_6756

**Yet another "segmentation fault" issue with AMD GPU**

- source: https://github.com/ollama/ollama/issues/6756
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_ollama_ollama_6756.json` · raw thread: `data/github_v0/raw/gh_ollama_ollama_6756.json`

```mermaid
flowchart LR
    N0["<b>N0 large AMD models segfault</b><br/><small>info: 5</small>"]
    N1["<b>N1 configuration and loading log collected</b><br/><small>info: 8</small>"]
    N1_x["<b>N1_x GPU-overhead workaround aftermath</b><br/><small>info: 9</small>"]
    N2["<b>N2 temporary downgrade works</b><br/><small>info: 10</small>"]
    N2_x["<b>N2_x official bundled ROCm aftermath</b><br/><small>info: 11</small>"]
    N3["<b>N3 regression boundary confirmed</b><br/><small>info: 12</small>"]
    N4["<b>N4 reproducible environment matrix collected</b><br/><small>info: 14</small>"]
    N5["<b>N5 fix verified on release candidate</b><br/><small>info: 15</small>"]
    N_terminal["<b>terminal resolved</b><br/><small>info: 17</small>"]
    N0 -.->|"❓ no_custom_model_parameters, runner_log_all_41_layers_rocm_no_mmap_then_segfault"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Treat the crash as inaccurate VRAM prediction and reserve progressively more GPU memory with `OLLAMA_GPU_OVERHEAD` or reduce `num_gpu` so fewer layers are loaded."| N1_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N1_x ==>|"🚀 Use Ollama 0.3.6 temporarily because the reporter recalls that an older release could load the same large models. (skip 2)"| N2
    linkStyle 2 stroke:#0ea5e9,stroke-width:2px
    N2 ==>|"💥 blind: Replace the distribution package and system ROCm libraries with Ollama's official build and bundled ROCm, on the theory that the crash is a packaging or runtime-library mismatch."| N2_x
    linkStyle 3 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ version_boundary_036_works_037_segfaults"| N3
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ detailed_arch_kernel_rocm_model_matrix, latest_log_shows_model_fits_and_runner_crashes_during_load"| N4
    linkStyle 5 stroke:#3b82f6,stroke-width:2px
    N4 -.->|"❓ ollama_0314_rc0_verified_large_model_works"| N5
    linkStyle 6 stroke:#3b82f6,stroke-width:2px
    N5 ==>|"⚡ Update to Ollama 0.3.14 or newer, which contains the correction for the main ROCm runner build regression introduced in 0.3.7; do not treat GPU-overhead tuning, a permanent downgrade, or swapping ROCm packages as the fix."| N_terminal
    linkStyle 7 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N1_x normal
    class N2 normal
    class N2_x normal
    class N3 normal
    class N4 normal
    class N5 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> On Linux with an RX 7900 XTX and Ollama 0.3.10, loading larger models fails with `Error: llama runner process has terminated: signal: segmentation fault (core dumped)`, even though Ollama reports enough VRAM. For example, `command-r:35b-08-2024-q4_K_M` is about 19 GB and my GPU has 24 GB; `gemma2:27b-instruct-q4_K_M` also fails, while models around 13 GB or smaller load. The logs report about 23.5 GiB available. I think models this size used to work on an older Ollama version, but I do not know which version last worked.

## Satisfaction conditions

1. Must identify the main issue as an Ollama ROCm runner build regression introduced between 0.3.6 and 0.3.7, associated with the compile-flag change restored by commit 0b03b9c, rather than concluding that the 19–21 GB model simply exceeds the RX 7900 XTX's VRAM.
2. Diagnosis must be grounded in the collected evidence: Ollama calculated that the model fit and selected all GPU layers, 0.3.6 worked while 0.3.7 failed, and both system ROCm and Ollama's bundled ROCm reproduced the newer-version crash.
3. Must not present `OLLAMA_GPU_OVERHEAD`, reducing GPU layers, or switching to the official bundled ROCm build as the resolution; GPU overhead up to 10 GB and the official bundled build were both tried without removing the segmentation fault.
4. Downgrading to 0.3.6 may be offered only as a temporary workaround; the permanent recommendation is to update to Ollama 0.3.14 or newer.
5. Must require user verification with the original large-model workload before declaring resolution; the reporter verified that Ollama 0.3.14-rc0 worked.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: no_custom_model_parameters, runner_log_all_41_layers_rocm_no_mmap_then_segfault | I'm not specifying a custom context size or any other parameters. A plain `ollama run command-r:35b-08-2024-q4 / The log says 22.7 GiB is available and 21.7 GiB is required, requests and offloads all 41 layers to ROCm, and  |
| `e2_N1__N1_x` | solution_only **BLIND** | req_info: ollama_reports_over_22gb_available_vram, runner_log_all_41_layers_rocm_no_mmap_then_segfault<br>elements: mentions_reserving_vram_or_reducing_gpu_layers | Treat the crash as inaccurate VRAM prediction and reserve progressively more GPU memory with `OLLAMA_GPU_OVERHEAD` or reduce `num_gpu` so fewer layers are loaded. |
| `e3_N1_x__N2` | solution_only | req_info: reporter_recall_of_older_working_version_uncertain, gpu_overhead_up_to_10gb_still_segfaults<br>elements: mentions_temporary_downgrade_to_0.3.6 | Use Ollama 0.3.6 temporarily because the reporter recalls that an older release could load the same large models. |
| `e4_N2__N2_x` | solution_only **BLIND** | req_info: arch_rocm_602_and_32gb_system_ram, ollama_036_loads_command_r_entirely_on_gpu<br>elements: mentions_testing_official_build_with_bundled_rocm | Replace the distribution package and system ROCm libraries with Ollama's official build and bundled ROCm, on the theory that the crash is a packaging or runtime-library mismatch. |
| `e5_N2_x__N3` | clarification_only | asks: version_boundary_036_works_037_segfaults | Confirmed with the affected workload: Ollama 0.3.6 works, while 0.3.7 segfaults. |
| `e6_N3__N4` | clarification_only | asks: detailed_arch_kernel_rocm_model_matrix, latest_log_shows_model_fits_and_runner_crashes_during_load | I'm on Arch Linux with kernel 6.11.3 and its bundled amdgpu driver, an RX 7900 XTX, and 32 GB of RAM. I normal / On Ollama 0.3.12, the log says the model fits in one GPU: 22.7 GiB available and 20.1 GiB required, with all 4 |
| `e7_N4__N5` | clarification_only | asks: ollama_0314_rc0_verified_large_model_works | Ollama 0.3.14-rc0 works great with my setup and the large model. |
| `e8_N5__N_terminal` | solution_only | req_info: ollama_036_loads_command_r_entirely_on_gpu, runner_log_all_41_layers_rocm_no_mmap_then_segfault, official_build_with_bundled_rocm_also_segfaults, latest_log_shows_model_fits_and_runner_crashes_during_load, version_boundary_036_works_037_segfaults, ollama_0314_rc0_verified_large_model_works<br>elements: identifies_regression_as_introduced_in_0.3.7_rocm_runner_build_change, recommends_ollama_0.3.14_or_newer, distinguishes_root_cause_from_simple_vram_overallocation, mentions_reporter_verification_on_0.3.14_rc0 | Update to Ollama 0.3.14 or newer, which contains the correction for the main ROCm runner build regression introduced in 0.3.7; do not treat GPU-overhead tuning, a permanent downgrade, or swapping ROCm packages as the fix. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 2 | 0 | Loading `command-r:35b-08-2024-q4_K_M` or `gemma2:27b-instruct-q4_K_M` ends with `llama runner process has terminated: signal: segmentation  |
| `N1` |  | 1 | 0 | A plain `ollama run command-r:35b-08-2024-q4_K_M` starts loading all 41 layers through ROCm and then the runner exits with a segmentation fa |
| `N1_x` |  | 1 | 0 | The same model still ends in a segmentation fault after setting `OLLAMA_GPU_OVERHEAD` as high as 10 GB. |
| `N2` |  | 1 | 0 | After downgrading to Ollama 0.3.6, `command-r:35b-08-2024-q4_K_M` loads successfully and `ollama ps` reports a 21 GB model running 100% on t |
| `N2_x` |  | 1 | 0 | After removing the Arch package and installing Ollama's official build with bundled ROCm, the same large model still ends in a segmentation  |
| `N3` |  | 0 | 0 | The affected large-model workload runs on Ollama 0.3.6 but segfaults on Ollama 0.3.7. |
| `N4` |  | 0 | 0 | On Arch Linux with kernel 6.11.3, the plain command still segfaults during model loading on Ollama 0.3.12, with either ROCm 6.0.2 or the off |
| `N5` |  | 0 | 0 | The same large model loads and runs correctly with Ollama 0.3.14-rc0. |
| `N_terminal` | ✓ | 0 | 0 | Large models that previously crashed now load and run on the RX 7900 XTX with Ollama 0.3.14 or newer. |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **needs_rework** · 2 of 5 findings survived independent refutation.

_The case tests whether an agent resists the "19 GB model on a 24 GB card must be a VRAM/memory-prediction problem" framing and instead bisects to an Ollama version regression (0.3.6 works, 0.3.7+ segfault on AMD/ROCm), fixed in 0.3.14. The graph is a largely faithful rendering of the thread: both blind paths are real falsified attempts, the log-based clarification answers are near-verbatim, and the chain order matches the conversation. The main problem is that the answer key hard-requires attributing the regression to commit 0b03b9c, which the maintainer only floated conditionally and the thread never confirmed. Secondary issues are a frozen system_state_id across four real system changes, plus smaller fidelity slips in the merged 0.3.7 confirmation and in bundling num_gpu reduction into the overhead blind path._

### Confirmed findings

- [ ] 🟠 **wrong_root_cause** (medium) — `satisfaction_conditions[0] (and edges[e8_N5__N_terminal].solution.required_elements_for_full_match[0] / concrete_example)`
  - claim: The scoring rubric makes attribution of the regression to commit 0b03b9c (a "compile-flag change") a hard requirement, but the thread only ever floats it as an untested maintainer hypothesis and never confirms it — nor does anyone say it was backed out for 0.3.14.
  - thread evidence: c43 (participant2, maintainer): "Does anyone have confirmation the regression was in v0.3.7? If so, it may be this commit, which brought back a compile flag ... but if that's causing regressions for a broader set of people, maybe we need to back that out. [0b03b9c...]" — purely conditional. c52 (participant5): "this is solved in the main branch currently when you git pull" and c53 (participant2): "It's possible there might be a couple distinct root causes in here, but the main issue should be resolved in 0.3.14" — neither identifies what the fix was. No comment in the thread ever confirms 0b03b9c as the cause.
  - suggested fix: Soften satisfaction_conditions[0] to require only what the thread established: an Ollama-side regression introduced between 0.3.6 and 0.3.7 in the ROCm path (not a VRAM-capacity problem), fixed in 0.3.14; mention commit 0b03b9c as an unconfirmed maintainer hypothesis rather than a must-state fact, and relax required_elements_for_full_match[0] to "identifies_regression_as_introduced_in_0.3.7".
  - verifier: Confirmed against the thread. c43 (participant2, maintainer) is purely conditional: "Does anyone have confirmation the regression was in v0.3.7? If so, it MAY be this commit ... but if that's causing regressions for a broader set of people, MAYBE we need to back that out." The only follow-ups are c44 ("Can confirm. ollama 3.6 works, 3.7 segfaults") — which confirms the VERSION boundary, not the co
- [ ] 🟠 **graph_shape** (medium) — `nodes.N2 / N2_x / N4 / N5 .system_state_id (all "S1")`
  - claim: system_state_id is held constant at S1 across four real, persistent system changes, so the node key stops meaning (system_state, info_state) and the whole investigation collapses into one world state until the terminal.
  - thread evidence: c20 (reporter): "I bit the bullet on downgrading to v0.3.6 and things are working again" (persistent version change → N2 still S1). c34 (reporter): "I installed the official build after uninstalling the arch package" (package set replaced → N2_x still S1). c50 (reporter): "ollama v0.3.12" with fresh logs (upgraded again → N4 still S1). c56 (reporter): "Ollama 0.3.14-rc0 works great!" (fixed build installed → N5 still S1, while N_terminal, describing the same world, is S2).
  - suggested fix: Assign distinct system_state_ids at N2 (0.3.6 installed), N2_x (official bundled-ROCm build installed), N4 (0.3.12), and N5 (0.3.14-rc0 installed); N5 and N_terminal can share the post-fix state since e8 only formalizes the recommendation.
  - verifier: Verified in both files. Graph lines 78/103/154/181 hold S1 at N2, N2_x, N4, N5; only N_terminal is S2 (line 209). Every cited change is a genuine, persistent alteration of the reporter's machine: c20 "I bit the bullet on downgrading to v0.3.6 and things are working again" (ollama ps shows 21 GB / 100% GPU); c34 "I installed the official build after uninstalling the arch package"; c50 reports runni

### Refuted claims (auditor was wrong — do not act on these)

- ~~measurement_class_violation~~: The bundled-ROCm build swap was explicitly requested as a differential diagnostic, i.e. a handler-initiated try-build, yet it is modeled purely as a proposed solution rather than a measurement.
  - why refuted: The quotes are accurate (c22 rule-out framing, c34 "the same error is still reproducible"), but this is a legitimate encoding, not a defect. The measurement-class rule exists for actions that "change knowledge, not the system"; this one persistently replaced the installed package set (reporter uninstalled the Arch pack
- ~~unfaithful_reveal~~: The merged user side says "Confirmed with the affected workload: Ollama 0.3.6 works, while 0.3.7 segfaults", but the reporter explicitly refused to claim a 0.3.7 test; the 0.3.7 data point came from other participants.
  - why refuted: The factual observation is right (c37 reporter: "Might as well be narrowed down to v0.3.6...v0.3.7, but I didn't test v0.3.7"; the confirmation is c44 participant9 and c48's docker matrix), but it is not a defect under the contract, which states multi-user threads are folded into ONE simulated user side and that the me
- ~~fabricated_blind_path~~: The blind edge bundles "reduce num_gpu so fewer layers are loaded" with the OLLAMA_GPU_OVERHEAD attempt, but only the overhead value was actually reported as falsified by the reporter.
  - why refuted: Refuted on the contract's own terms: an edge is ONE assistant turn, and c5 (participant2) proposed both branches in a single turn — "you can set num_gpu to a smaller value (try 40, 39, ...) or use the new env-var OLLAMA_GPU_OVERHEAD to reserve some VRAM so our algorithm calculates less layers to load". e2's intent is a


## Review checklist

> The graph is the case's ANSWER KEY, not a transcript: edge order need
> not mirror thread chronology. Do not file chronology mismatch as a
> defect; what must be faithful is who knew what, when.

Structural (machine-checked by `scripts/validate.py`, re-verify after edits):

- [ ] validates: schema + info-containment + terminal reachability

Semantic (the defect catalog — check each against the source thread):

- [ ] **Faithful blind paths** — every `is_known_blind_path` edge corresponds
  to an attempt actually falsified in the thread (or a brush-off the
  reporter rejected). No invented failures; no ACCEPTED fix mislabeled as
  a blind path (the most common LLM defect class).
- [ ] **Gettable required info** — every id in any `solution.required_info`
  is obtainable: a clarification on some edge, or in the start node's
  info_state, or volunteered (with matching `volunteered_info` text).
  Engineer-only inference belongs in `info_inferred_by_engineer` /
  `inference_hint`, not in hard required_info.
- [ ] **Measurement-class rule** — handler-initiated measurements the user
  executed (bisections, test builds, config probes, version checks) are
  clarification edges, not solutions; their answers state what the
  measurement showed.
- [ ] **No logistics gates** — `required_elements_for_full_match` encode the
  technical diagnostic→fix chain, not release/packaging/scheduling
  remarks the engineer merely mentioned.
- [ ] **Coherent reveals** — each `user_answer_in_this_oncall` is consistent
  with the thread, delivers what it promises, and stays in the user's
  voice (no future knowledge, no diagnosis the user never made).
- [ ] **Symptoms are observations** — `symptoms_visible` contains only what
  the user can see; no causes or advice.
- [ ] **Terminal semantics** — satisfaction_conditions demand root cause +
  evidence grounding + prohibition of falsified moves + user verification;
  the terminal node is the verified-resolved state.
- [ ] **Image assignment** — referenced attachments exist and sit on the
  right hook (opening / node symptom / clarification evidence).
- [ ] **Persona** — matches the reporter's actual expertise and style.

## How to sign off

1. Edit the graph JSON if needed (authored fields only; keep
   `concrete_example` as the factual record).
2. `uv run scripts/validate.py '<graph path>'`
3. Set `metadata.hitl_reviewed: true` in the graph JSON.
4. Re-run `uv run scripts/make_review_docs.py` to refresh this page.
