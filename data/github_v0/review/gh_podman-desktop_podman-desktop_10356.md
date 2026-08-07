# Review: gh_podman-desktop_podman-desktop_10356

**Podman Desktop consumes increasing CPU and memory while idle on Windows**

- source: https://github.com/podman-desktop/podman-desktop/issues/10356
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_podman-desktop_podman-desktop_10356.json` · raw thread: `data/github_v0/raw/gh_podman-desktop_podman-desktop_10356.json`

```mermaid
flowchart LR
    N0["<b>N0 idle resource growth reported</b><br/><small>info: 7</small>"]
    N1["<b>N1 environment and idle machine established</b><br/><small>info: 11</small>"]
    N2["<b>N2 repeated connection errors captured</b><br/><small>info: 14</small>"]
    N3["<b>N3 Podman extension path isolated</b><br/><small>info: 16</small>"]
    N4["<b>N4 VM load and firewall ruled out</b><br/><small>info: 19</small>"]
    N5_x["<b>N5_x Podman Desktop downgrade aftermath</b><br/><small>info: 21</small>"]
    N_terminal["<b>terminal resolved by Podman downgrade</b><br/><small>info: 23</small>"]
    N0 -.->|"❓ podman_vm_is_running, podman_machine_uses_wsl_and_rootless_mode, no_kind_docker_openshift_or_kubernetes_cluster_running"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ process_monitor_shows_host_usage_growing_from_300mb_toward_1gb, logs_repeat_pipe_enoent_and_reconnect_every_5_seconds"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ all_extensions_disabled_avoids_problem, podman_extension_alone_with_machine_running_reproduces_problem"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ machine_probe_shows_zero_cpu_and_about_554mb_used, disabling_windows_firewall_makes_no_difference"| N4
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"💥 blind: Treat the regression as a Podman Desktop application-version problem and revert Podman Desktop to an earlier release."| N5_x
    linkStyle 4 stroke:#ef4444,stroke-width:2px
    N5_x ==>|"⚡ Treat the original report as a regression associated with the newer Podman engine's interaction with Podman Desktop: roll Podman back to the prior working engine build, then verify that the pipe-error retry loop and idle resource growth stop."| N_terminal
    linkStyle 5 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3 normal
    class N4 normal
    class N5_x normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I updated Podman and Podman Desktop on my Windows 11 machine, and Podman Desktop 1.14.2 installed through Scoop now consistently uses 20–30% CPU and up to 4 GB of memory while doing nothing. I have no images or containers in use. After it has been running for a while, the UI becomes almost unresponsive and sluggish, and my PC's fans run at full speed. Is this expected?

## Satisfaction conditions

1. Must identify the opening reporter's accepted diagnosis as a regression in the newer Podman engine's interaction with Podman Desktop, evidenced by the repeated missing named-pipe errors and five-second reconnection loop while the Podman machine itself remains idle.
2. Must ground the diagnosis in the collected evidence: quiet VM statistics, reproduction with only the Podman extension enabled, repeated ENOENT/reconnect logs, no effect from disabling the firewall, and no effect from reverting only Podman Desktop.
3. Must recommend rolling the Podman engine back to the prior working build, rather than claiming that downgrading Podman Desktop alone fixes the issue.
4. Must not present restarts, firewall changes, or a Podman Desktop-only downgrade as the resolution; they did not stop the original reporter's symptoms.
5. Must not conflate the opening report with the later participant's independent Kubernetes-context and Azure CLI Python-process problem or score toggling that participant's experimental feature as the original reporter's fix.
6. Must ask the reporter to verify that the repeated pipe errors and long-term idle CPU and memory growth are gone before declaring the issue resolved.
7. May describe uncollected Dockerode instances as a hypothesis only, not as a proven memory-leak mechanism.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: podman_vm_is_running, podman_machine_uses_wsl_and_rootless_mode, no_kind_docker_openshift_or_kubernetes_cluster_running | Yes, the Podman VM is running. / It is using WSL, and I configured the machine in rootless mode. / I have nothing else running: no Kind, no Docker, no OpenShift Local, and no Kubernetes cluster. |
| `e2_N1__N2` | clarification_only | asks: process_monitor_shows_host_usage_growing_from_300mb_toward_1gb, logs_repeat_pipe_enoent_and_reconnect_every_5_seconds | I tracked it with Process Monitor. It kept growing from around 300 MB toward 1 GB before I stopped the trace,  / The logs repeatedly say `connect ENOENT \\.\pipe\podman-machine-default`, `Error when handling events`, and `W |
| `e3_N2__N3` | clarification_only | asks: all_extensions_disabled_avoids_problem, podman_extension_alone_with_machine_running_reproduces_problem | When everything is disabled, I do not get the problem. / With only the Podman extension enabled, starting the Podman machine brings back all the log errors, and CPU an |
| `e4_N3__N4` | clarification_only | asks: machine_probe_shows_zero_cpu_and_about_554mb_used, disabling_windows_firewall_makes_no_difference | The machine reports 100% idle CPU. It has about 554 MiB used out of 7.7 GiB, about 7.2 GiB available, and no s / I disabled the firewall, and it made no difference. |
| `e5_N4__N5_x` | solution_only **BLIND** | req_info: podman_and_desktop_recently_updated, logs_repeat_pipe_enoent_and_reconnect_every_5_seconds, podman_extension_alone_with_machine_running_reproduces_problem<br>elements: recommends_reverting_only_podman_desktop | Treat the regression as a Podman Desktop application-version problem and revert Podman Desktop to an earlier release. |
| `e6_N5_x__terminal` | solution_only | req_info: podman_and_desktop_recently_updated, podman_5_3_1_installed_before_engine_downgrade, podman_machine_top_shows_very_low_cpu, second_laptop_after_update_has_same_errors_and_resource_growth, logs_repeat_pipe_enoent_and_reconnect_every_5_seconds, all_extensions_disabled_avoids_problem, podman_extension_alone_with_machine_running_reproduces_problem, machine_probe_shows_zero_cpu_and_about_554mb_used, disabling_windows_firewall_makes_no_difference, podman_desktop_downgrade_to_1_13_3_does_not_change_problem<br>elements: attributes_original_issue_to_newer_podman_engine_interaction, recommends_rolling_back_the_podman_engine_not_only_podman_desktop, connects_the_diagnosis_to_repeated_named_pipe_errors_and_retries, asks_user_to_verify_logs_cpu_and_memory_after_the_engine_change | Treat the original report as a regression associated with the newer Podman engine's interaction with Podman Desktop: roll Podman back to the prior working engine build, then verify that the pipe-error retry loop and idle resource growth stop. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 1 | 0 | While I am doing nothing in Podman Desktop, its CPU stays around 20–30% and its memory grows as high as 4 GB. After a while the UI becomes a |
| `N1` |  | 1 | 0 | Podman Desktop's memory and CPU usage still grow while the WSL-based Podman machine is running, even though the machine itself shows very lo |
| `N2` |  | 1 | 0 | During Process Monitor tracking, Podman Desktop grew from about 300 MB toward 1 GB and continued consuming CPU. The logs repeatedly print th |
| `N3` |  | 0 | 0 | With every extension disabled, the resource problem does not occur. When I enable only the Podman extension and start the Podman machine, th |
| `N4` |  | 1 | 0 | The Podman machine reports 100% idle CPU, about 554 MiB used memory, and no swap use while the Windows application has the problem. Disablin |
| `N5_x` |  | 2 | 0 | After reverting Podman Desktop to 1.13.3, the repeated pipe errors and high CPU and memory use remain. |
| `N_terminal` | ✓ | 1 | 0 | After reverting Podman from 5.3.1 to 5.2.5, the repeated pipe errors stop and Podman Desktop no longer consumes increasing CPU or memory whi |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **n/a** · 0 of 0 findings survived independent refutation.

__


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
