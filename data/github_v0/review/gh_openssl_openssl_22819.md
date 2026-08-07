# Review: gh_openssl_openssl_22819

**[BUG] evp_extra_test fails on NonStop builds in openssl-3.0**

- source: https://github.com/openssl/openssl/issues/22819
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_openssl_openssl_22819.json` · raw thread: `data/github_v0/raw/gh_openssl_openssl_22819.json`

```mermaid
flowchart LR
    N0["<b>N0 NonStop evp_extra_test failure reported</b><br/><small>info: 3</small>"]
    N1["<b>N1 build mode and module layout established</b><br/><small>info: 7</small>"]
    N2["<b>N2 exit-time SIGSEGV isolated</b><br/><small>info: 11</small>"]
    N2_x["<b>N2_x trace cleanup hypotheses falsified</b><br/><small>info: 13</small>"]
    N3["<b>N3 duplicate cleanup registration observed</b><br/><small>info: 16</small>"]
    N4["<b>N4 NonStop mixed-linkage exit failure explained</b><br/><small>info: 20</small>"]
    N_terminal["<b>terminal fix merged without reporter verification</b><br/><small>info: 22</small>"]
    N0 -.->|"❓ failure_occurs_in_all_nonstop_build_modes, unthreaded_64_bit_monitor_build_affected, modules_makefile_and_build_outputs_include_dasync, configured_engine_path_points_to_build_tree"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ runtime_dlopen_paths_are_correct, standalone_context_run_exits_139, standalone_backtrace_segv_in_process_atexit_functions, all_individual_tests_finish_before_exit_crash"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"🔀 ❓openssl_no_trace_build_same_exit_segv + ⚡Treat the duplicate trace_data_stack declaration in testutil_init as the source of the exit corruption and remove it."| N2_x
    linkStyle 2 stroke:#a855f7,stroke-width:2px
    N2_x -.->|"❓ instrumentation_shows_cleanup_registered_twice, second_registration_occurs_during_keylen_test, cleanup_not_reached_before_second_process_crash"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ static_and_shared_libcrypto_have_distinct_run_once_state, nonstop_cre_retains_atexit_entries_after_dll_unload, nonstop_exit_reinvokes_inaccessible_dll_callback_address, legacy_provider_load_creates_mixed_static_dynamic_libcrypto_case"| N4
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"⚡ Avoid loading a second dynamically linked libcrypto instance in evp_extra_test by statically linking the legacy provider into that test, matching the established treatment for tests that combine static and dynamic linkage on NonStop."| N_terminal
    linkStyle 5 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N2_x normal
    class N3 normal
    class N4 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> The openssl-3.0 branch started failing tests on NonStop at or near commit 48fe8d4e53d5572ff77215e3336a1c71b0b4517b. The failure occurs in test/evp_extra_test. I have included the test results and configuration and need assistance diagnosing it.

## Satisfaction conditions

1. Must identify the accepted root cause: evp_extra_test combines a statically linked libcrypto with a shared libcrypto loaded through the legacy provider, giving separate RUN_ONCE state and duplicate exit-handler registration.
2. Must explain the NonStop-specific failure: the CRE retains a DLL callback entry after unload and attempts to invoke its now-inaccessible address again at main-process exit, causing SIGSEGV in __process_atexit_functions.
3. Diagnosis must be grounded in the direct exit status and backtrace plus the instrumentation showing two OPENSSL_cleanup registrations; it must not remain focused on an incorrect engine path or a missing dasync.so.
4. Must not present disabling tracing or removing the duplicate trace_data_stack declaration as the fix, because both were tried without changing the SIGSEGV.
5. The corrective build change must statically link the legacy provider into evp_extra_test so the test avoids the mixed static/shared libcrypto initialization path.
6. Must ask the reporter to rerun the NonStop build and tests with the merged change and must not claim reporter-verified resolution, because the thread ends after a maintainer reports the merge without a posted successful retest.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: failure_occurs_in_all_nonstop_build_modes, unthreaded_64_bit_monitor_build_affected, modules_makefile_and_build_outputs_include_dasync, configured_engine_path_points_to_build_tree | It happens in all of my builds. We normally monitor with the unthreaded 64-bit build, and it happens there too / Yes, the unthreaded 64-bit monitoring build is affected. / The top-level Makefile lists engines/dasync.so in MODULES. The build contains capi.so, dasync.so, loader_attic / The recipe prints OPENSSL_ENGINE=/home/<user>/.jenkins/workspace/OpenSSL-3.0_Monitor/engines, which is the cor |
| `e2_N1__N2` | clarification_only | asks: runtime_dlopen_paths_are_correct, standalone_context_run_exits_139, standalone_backtrace_segv_in_process_atexit_functions, all_individual_tests_finish_before_exit_crash | With a printf at dlopen I get ../../providers/fips.so, /home/<user>/.jenkins/workspace/OpenSSL-3.0_Monitor/eng / The direct -context run reaches the last listed tests and then receives signal 11. The wrapper reports '../../ / The debugger says 'received non-deferrable signal SIGSEGV (number: 11)'. The backtrace starts in __process_ate / The run prints ok 57 and ok 58 before the SIGSEGV. The hang I previously saw was in the debugger, not in the t |
| `e3_N2__N2_x` | mixed **BLIND** | req_info: all_individual_tests_finish_before_exit_crash, standalone_backtrace_segv_in_process_atexit_functions<br>elements: removes_duplicate_trace_data_stack_declaration | Treat the duplicate trace_data_stack declaration in testutil_init as the source of the exit corruption and remove it. |
| `e4_N2_x__N3` | clarification_only | asks: instrumentation_shows_cleanup_registered_twice, second_registration_occurs_during_keylen_test, cleanup_not_reached_before_second_process_crash | The failing middle process prints 'Enter ossl_init_register_atexit(OPENSSL_cleanup)' and its exit message once / The second OPENSSL_cleanup registration appears inside the test_keylen_change subtest, just before its first i / No. In the failing -context process all 58 tests finish, then it receives SIGSEGV. My 'Enter into OPENSSL_clea |
| `e5_N3__N4` | clarification_only | asks: static_and_shared_libcrypto_have_distinct_run_once_state, nonstop_cre_retains_atexit_entries_after_dll_unload, nonstop_exit_reinvokes_inaccessible_dll_callback_address, legacy_provider_load_creates_mixed_static_dynamic_libcrypto_case | As I understand RUN_ONCE, it uses a static variable. That variable has one address in the statically linked mo / NonStop has one atexit list in the CRE. When a DLL unloads, its callback entries are invoked but the list is n / At main-program exit, the runtime traverses the same list again. The DLL procedure address is no longer access / The application has the static libcrypto instance, and loading the legacy provider brings in the shared libcry |
| `e6_N4__N_terminal` | solution_only | req_info: failure_occurs_in_all_nonstop_build_modes, legacy_provider_load_creates_mixed_static_dynamic_libcrypto_case, standalone_backtrace_segv_in_process_atexit_functions, instrumentation_shows_cleanup_registered_twice, static_and_shared_libcrypto_have_distinct_run_once_state, nonstop_cre_retains_atexit_entries_after_dll_unload, nonstop_exit_reinvokes_inaccessible_dll_callback_address<br>elements: statically_links_the_legacy_provider_into_evp_extra_test, explains_that_this_avoids_the_static_and_shared_libcrypto_combination, asks_user_to_verify_on_a_build_containing_the_static_provider_link_change | Avoid loading a second dynamically linked libcrypto instance in evp_extra_test by statically linking the legacy provider into that test, matching the established treatment for tests that combine static and dynamic linkage on NonStop. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | On NonStop, the openssl-3.0 test run fails in test/evp_extra_test; the failure began at or near commit 48fe8d4e53d5572ff77215e3336a1c71b0b45 |
| `N1` |  | 0 | 0 | The same test failure occurs in all of my NonStop builds, including the unthreaded 64-bit build. The expected engine modules exist in the bu |
| `N2` |  | 0 | 0 | The runtime loads dasync.so and legacy.so from my build tree, not from /usr/local. Running evp_extra_test -context directly completes its li |
| `N2_x` |  | 1 | 0 | The test still finishes its cases and then receives the same SIGSEGV in __process_atexit_functions when built with OPENSSL_NO_TRACE. Removin |
| `N3` |  | 0 | 0 | My trace prints two registrations of OPENSSL_cleanup during the failing -context process, with the second appearing during test_keylen_chang |
| `N4` |  | 0 | 0 | The failing process still completes the test cases and crashes only while the NonStop runtime processes exit callbacks after a loaded librar |
| `N_terminal` | ✓ | 2 | 0 | A maintainer reports that the change was merged and closes the issue; I have not posted a successful NonStop retest of the merged change. |

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
