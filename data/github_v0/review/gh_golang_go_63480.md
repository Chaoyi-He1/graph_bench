# Review: gh_golang_go_63480

**x/build: add LUCI openbsd-ppc64 builder**

- source: https://github.com/golang/go/issues/63480
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_golang_go_63480.json` · raw thread: `data/github_v0/raw/gh_golang_go_63480.json`

```mermaid
flowchart LR
    N0["<b>N0 builder enrollment requested</b><br/><small>info: 3</small>"]
    N1["<b>N1 certificate and builder definition ready</b><br/><small>info: 5</small>"]
    N2["<b>N2 initial swarming handshake rejected</b><br/><small>info: 8</small>"]
    N3["<b>N3 transient authentication error cleared</b><br/><small>info: 10</small>"]
    N4["<b>N4 updated bootstrap command rejects obsolete flag</b><br/><small>info: 12</small>"]
    N5["<b>N5 bot starts but bootstrap package is absent</b><br/><small>info: 14</small>"]
    N6["<b>N6 builds execute but expose resource and kernel limits</b><br/><small>info: 18</small>"]
    N6_x["<b>N6_x larger data limit aftermath</b><br/><small>info: 19</small>"]
    N_terminal["<b>terminal LUCI migration complete</b><br/><small>info: 23</small>"]
    N0 ==>|"🔀 ❓certificate_installed_and_token_json_generated + ⚡Issue the machine certificate and define the requested openbsd-ppc64 builder in the LUCI configuration so onboarding can continue."| N1
    linkStyle 0 stroke:#a855f7,stroke-width:2px
    N1 ==>|"⚡ Proceed with the documented machine-side setup and start bootstrapswarm using the generated machine token."| N2
    linkStyle 1 stroke:#f97316,stroke-width:2px
    N2 -.->|"❓ same_invocation_later_handshakes_without_403, swarming_task_reports_missing_openbsd_ppc64_cipd_package"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"🔀 ❓rebuilt_bootstrapswarm_rejects_removed_token_file_flag + ⚡Add server-side package-building support for the new openbsd/ppc64 platform so LUCI tasks can resolve their required tools."| N4
    linkStyle 3 stroke:#a855f7,stroke-width:2px
    N4 ==>|"🔀 ❓build_fails_missing_bootstrap_go_openbsd_ppc64_1_21 + ⚡Use LUCI_MACHINE_TOKEN as the supported token-file path configuration and remove the obsolete bootstrapswarm command-line flag."| N5
    linkStyle 4 stroke:#a855f7,stroke-width:2px
    N5 ==>|"⚡ Publish and select a Go 1.22 bootstrap package for openbsd/ppc64, because the requested Go 1.21 bootstrap predates support for the new port."| N6
    linkStyle 5 stroke:#f97316,stroke-width:2px
    N6 ==>|"💥 blind: Treat the post-test failure as a simple per-process memory ceiling and raise the swarming account's data-size limit to 8 GB."| N6_x
    linkStyle 6 stroke:#ef4444,stroke-width:2px
    N6_x ==>|"🔀 ❓luci_builder_stable_enough_and_old_buildlet_stopped + ⚡Finish the migration by tuning the builder for realistic OpenBSD resource and performance limits, while treating the independently reproducible kernel panic as an OS issue rather than a LUCI packaging failure."| N_terminal
    linkStyle 7 stroke:#a855f7,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3 normal
    class N4 normal
    class N5 normal
    class N6 normal
    class N6_x normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I'm following the Dashboard builders instructions to add hostname openbsd-ppc64-reporter. I attached the CSR after renaming it because GitHub would not allow the requested openbsd-ppc64-reporter.csr filename.

## Satisfaction conditions

1. Must identify the main LUCI onboarding blockers as missing server-side openbsd/ppc64 CIPD and bootstrap artifacts, including the need for a Go 1.22 bootstrap because Go 1.21 does not support the new port.
2. Must account for the client-side invocation change: current bootstrapswarm uses LUCI_MACHINE_TOKEN and no longer accepts -token-file-path.
3. Must ground the diagnosis in the collected raw failures: the missing CIPD package, the missing golang/bootstrap-go/openbsd-ppc64@1.21.0 package, and the later resource-related build behavior.
4. Must not treat the transient HTTP 403, 401, 429, or 500 responses as the final root cause; retries and later successful work showed those errors were temporary.
5. Must not claim that raising the data-size limit to 8 GB resolves the crashes; the machine still panicked after that change.
6. Must distinguish the remaining high-load OpenBSD kernel lock problem, which was reproduced without Go, from the completed LUCI migration.
7. Must tune process and timeout limits, keep machine load reasonable, and have the reporter verify useful work over multiple LUCI builds before declaring the migration complete and retiring the old buildlet.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | mixed | req_info: request_add_openbsd_ppc64_luci_builder, builder_hostname_openbsd_ppc64_n2vi, csr_submitted_after_filename_rename<br>elements: issues_certificate_for_submitted_csr, adds_openbsd_ppc64_builder_definition | Issue the machine certificate and define the requested openbsd-ppc64 builder in the LUCI configuration so onboarding can continue. |
| `e2_N1__N2` | solution_only | req_info: request_add_openbsd_ppc64_luci_builder, certificate_installed_and_token_json_generated<br>elements: proceeds_to_start_swarming_bot_with_generated_token | Proceed with the documented machine-side setup and start bootstrapswarm using the generated machine token. |
| `e3_N2__N3` | clarification_only | asks: same_invocation_later_handshakes_without_403, swarming_task_reports_missing_openbsd_ppc64_cipd_package | I retried the same bootstrapswarm invocation and no longer get the 403. I tried it several more times over the / After it received work, the task printed: 'Could not resolve version infra/tools/cipd/openbsd-ppc64:git_revisi |
| `e4_N3__N4` | mixed | req_info: request_add_openbsd_ppc64_luci_builder, swarming_task_reports_missing_openbsd_ppc64_cipd_package<br>elements: adds_server_side_package_support_for_openbsd_ppc64, uses_toolchain_that_supports_the_new_port | Add server-side package-building support for the new openbsd/ppc64 platform so LUCI tasks can resolve their required tools. |
| `e5_N4__N5` | mixed | req_info: token_flag_and_environment_used_same_path, rebuilt_bootstrapswarm_rejects_removed_token_file_flag<br>elements: drops_removed_token_file_path_flag, keeps_machine_token_path_in_environment | Use LUCI_MACHINE_TOKEN as the supported token-file path configuration and remove the obsolete bootstrapswarm command-line flag. |
| `e6_N5__N6` | solution_only | req_info: server_side_cipd_platform_support_needed, build_fails_missing_bootstrap_go_openbsd_ppc64_1_21<br>elements: provides_bootstrap_package_for_openbsd_ppc64, uses_go_1_22_instead_of_unsupported_go_1_21 | Publish and select a Go 1.22 bootstrap package for openbsd/ppc64, because the requested Go 1.21 bootstrap predates support for the new port. |
| `e7_N6__N6_x` | solution_only **BLIND** | req_info: machine_has_substantial_free_ram<br>elements: raises_swarming_datasize_limit_to_8gb | Treat the post-test failure as a simple per-process memory ceiling and raise the swarming account's data-size limit to 8 GB. |
| `e8_N6_x__N_terminal` | mixed | req_info: openbsd_kernel_panics_under_builder_load, machine_has_substantial_free_ram, build_reaches_runtime_tests_then_hits_resource_failures, build_fails_missing_bootstrap_go_openbsd_ppc64_1_21<br>elements: sets_sufficient_process_limits_for_builder_tests, applies_longer_timeout_scale_for_openbsd_ppc64, avoids_treating_more_ram_as_the_kernel_panic_fix, separates_independent_openbsd_kernel_bug_from_luci_onboarding, asks_user_to_verify_over_multiple_luci_builds_before_declaring_migration_complete | Finish the migration by tuning the builder for realistic OpenBSD resource and performance limits, while treating the independently reproducible kernel panic as an OS issue rather than a LUCI packaging failure. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | I am setting up openbsd-ppc64-reporter as a new Go LUCI builder and have submitted its CSR. |
| `N1` |  | 0 | 0 | Using the issued certificate, I get a plausible-looking luci_machine_tokend/token.json. |
| `N2` |  | 2 | 0 | bootstrapswarm reads my token file and starts the swarming bot, but the handshake returns HTTP 403 Forbidden. |
| `N3` |  | 0 | 0 | The same bootstrapswarm invocation now connects without the earlier 403, but assigned work fails because an openbsd-ppc64 CIPD package canno |
| `N4` |  | 0 | 0 | After rebuilding bootstrapswarm from latest, it exits because -token-file-path is no longer a defined flag. |
| `N5` |  | 0 | 0 | After dropping -token-file-path and keeping LUCI_MACHINE_TOKEN set, bootstrapswarm starts normally, but the build fails to resolve golang/bo |
| `N6` |  | 3 | 0 | With the bootstrap package available, the LUCI build reaches passing runtime tests, but later reports resource failures and the OpenBSD mach |
| `N6_x` |  | 1 | 0 | After raising the swarming login class datasize limit to 8 GB and rebooting, the machine still eventually panics with a kernel allocation fa |
| `N_terminal` | ✓ | 0 | 0 | The openbsd-ppc64 machine receives and completes LUCI work reliably enough for the migration, and I have stopped the old coordinator buildle |

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
