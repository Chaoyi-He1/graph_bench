# Review: gh_flutter_flutter_178602

**Flutter 3.38.1: App Store Connect rejects iOS archive with invalid LC_ENCRYPTION_INFO**

- source: https://github.com/flutter/flutter/issues/178602
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_flutter_flutter_178602.json` · raw thread: `data/github_v0/raw/gh_flutter_flutter_178602.json`

```mermaid
flowchart LR
    N0["<b>N0 App Store validation failure reported</b><br/><small>info: 4</small>"]
    N1_x["<b>N1_x update and clean aftermath</b><br/><small>info: 5</small>"]
    N2["<b>N2 project evidence and validation mode collected</b><br/><small>info: 9</small>"]
    N3["<b>N3 stale simulator native asset isolated</b><br/><small>info: 12</small>"]
    N4["<b>N4 workaround and fixed toolchain verified</b><br/><small>info: 14</small>"]
    N_terminal["<b>terminal resolved</b><br/><small>info: 14</small>"]
    N0b["<b>N0b opening evidence gathered</b><br/><small>info: 6</small>"]
    N0 ==>|"💥 blind: Treat the failure as stale build output that can be resolved by updating Flutter to 3.38.2 and running flutter clean before rebuilding."| N1_x
    linkStyle 0 stroke:#ef4444,stroke-width:2px
    N1_x -.->|"❓ project_dependencies_include_sqlite3_native_assets, complete_content_delivery_log_has_same_validation_error, validate_app_fails_independently_of_distribution"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"⚡ Reproduce and inspect the archive to isolate whether a simulator-only sqlite3 native framework is being retained and embedded in a device archive."| N3
    linkStyle 2 stroke:#f97316,stroke-width:2px
    N3 -.->|"❓ clean_config_only_before_archive_verified_workaround, fixed_main_channel_build_verified_by_affected_user"| N4
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"⚡ Use a Flutter toolchain containing the native-assets embedding fix so device archives include only frameworks selected for the current build; until then, generate a clean config-only device archive without first running a simulator build."| N_terminal
    linkStyle 4 stroke:#f97316,stroke-width:2px
    N0 -.->|"❓ project_dependencies_include_sqlite3_native_assets, complete_content_delivery_log_has_same_validation_error"| N0b
    linkStyle 5 stroke:#3b82f6,stroke-width:2px
    N0b -.->|"❓ validate_app_fails_independently_of_distribution, project_support_files_shared"| N2
    linkStyle 6 stroke:#3b82f6,stroke-width:2px
    class N0 start
    class N1_x normal
    class N2 normal
    class N3 normal
    class N4 normal
    class N_terminal terminal
    class N0b normal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> After upgrading to Flutter 3.38.1, submitting my iOS archive to App Store Connect fails validation with: “The binary is invalid. The encryption info in the LC_ENCRYPTION_INFO load command is either missing or invalid, or the binary is already encrypted. This binary does not seem to have been built with Apple's linker.” This did not happen before the upgrade. I am on macOS 15.6.1 with Xcode 16.3, and flutter doctor reports no issues.

## Satisfaction conditions

1. Must identify the reporter's root cause: a simulator build generated sqlite3arm64ios_sim.framework, and Flutter later embedded that stale simulator-only native asset into a device archive because the embedding step copied the whole shared native-assets iOS directory instead of only assets selected for the current build.
2. The diagnosis must be grounded in the sqlite3 dependency, the failure of both Validate App and distribution, the simulator-then-device reproduction, and inspection of the archived Frameworks directory.
3. Must recommend using a Flutter toolchain containing the native-assets embedding fix; flutter clean followed by flutter build ios --config-only before archiving, without first running a simulator build, is acceptable as a temporary workaround.
4. Must not present upgrading to Flutter 3.38.2 plus a generic flutter clean as sufficient, because that exact attempt left the reporter's error unchanged.
5. Must scope the diagnosis to this project's native-assets frameworks rather than claiming a universal AOT/App.framework defect.
6. Must require successful archive validation by an affected user before declaring the issue resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1_x` | solution_only **BLIND** | req_info: app_store_validation_lc_encryption_error_after_flutter_3381<br>elements: mentions_updating_flutter_and_cleaning_build_output | Treat the failure as stale build output that can be resolved by updating Flutter to 3.38.2 and running flutter clean before rebuilding. |
| `e2_N1_x__N2` | clarification_only | asks: project_dependencies_include_sqlite3_native_assets, complete_content_delivery_log_has_same_validation_error, validate_app_fails_independently_of_distribution | My pubspec includes sqflite_sqlcipher, sqflite, and an override for sqlite3 version 3.0.1, along with the rest / Here is my ContentDelivery.log. It reports status 409 and says the binary's LC_ENCRYPTION_INFO is missing or i / I originally saw it while distributing. I didn't try validating at first, I thought they were the same. I then |
| `e3_N2__N3` | solution_only | req_info: complete_content_delivery_log_has_same_validation_error, project_dependencies_include_sqlite3_native_assets, validate_app_fails_independently_of_distribution<br>elements: checks_for_simulator_only_sqlite_framework_in_device_archive, compares_archive_after_simulator_build_with_clean_device_archive | Reproduce and inspect the archive to isolate whether a simulator-only sqlite3 native framework is being retained and embedded in a device archive. |
| `e4_N3__N4` | clarification_only | asks: clean_config_only_before_archive_verified_workaround, fixed_main_channel_build_verified_by_affected_user | That option works for me. After flutter clean and flutter build ios --config-only, I archived in Xcode and val / I tested the fixed main channel and it does the trick; I was able to validate and deploy my app. |
| `e5_N4__N_terminal` | solution_only | req_info: app_store_validation_lc_encryption_error_after_flutter_3381, project_dependencies_include_sqlite3_native_assets, validate_app_fails_independently_of_distribution, clean_config_only_before_archive_verified_workaround, fixed_main_channel_build_verified_by_affected_user<br>elements: identifies_stale_simulator_native_framework_as_reporter_case_root_cause, explains_flutter_embedded_all_assets_instead_of_only_current_device_assets, recommends_a_flutter_build_with_the_native_assets_fix, allows_clean_config_only_sequence_as_temporary_workaround | Use a Flutter toolchain containing the native-assets embedding fix so device archives include only frameworks selected for the current build; until then, generate a clean config-only device archive without first running a simulator build. |
| `e0_N0__N0b` | clarification_only | asks: project_dependencies_include_sqlite3_native_assets, complete_content_delivery_log_has_same_validation_error | My pubspec includes sqflite_sqlcipher, sqflite, and an override for sqlite3 version 3.0.1, along with the rest / Here is my ContentDelivery.log. It reports status 409 and says the binary's LC_ENCRYPTION_INFO is missing or i |
| `e0b_N0b__N2` | clarification_only | asks: validate_app_fails_independently_of_distribution, project_support_files_shared | I originally saw it while distributing. I didn't try validating at first, I thought they were the same. I then / Shared the project support files as requested. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | After upgrading to Flutter 3.38.1, App Store Connect rejects my iOS archive because LC_ENCRYPTION_INFO is missing or invalid and says the bi |
| `N1_x` |  | 1 | 0 | The same LC_ENCRYPTION_INFO validation error still appears after updating to Flutter 3.38.2 and running flutter clean. |
| `N2` |  | 1 | 0 | Both Xcode's Validate App operation and distribution produce the same invalid-encryption-information error. I am still having the same issue |
| `N3` |  | 0 | 0 | The upload still fails with the same App Store validation error for the sqlite3 framework; nothing in my project changed. |
| `N4` |  | 0 | 0 | After running flutter clean and flutter build ios --config-only immediately before archiving, my archive validates successfully. An affected |
| `N_terminal` | ✓ | 0 | 0 | The iOS device archive contains only the native frameworks needed by that build and passes App Store Connect validation without the LC_ENCRY |
| `N0b` |  | 0 | 0 | After upgrading to Flutter 3.38.1, App Store Connect rejects my iOS archive because LC_ENCRYPTION_INFO is missing or invalid and says the bi |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **minor_issues** · 3 of 4 findings survived independent refutation.

_The case tests whether an agent can drive a Flutter/iOS App Store validation failure (LC_ENCRYPTION_INFO) past the seductive "just upgrade + flutter clean" brush-off to the real native-assets root cause: a simulator-only sqlite3arm64ios_sim.framework left in build/native_assets/ios and then blanket-copied into the device archive by xcode_backend.dart's _embedNativeAssets. The graph is substantively faithful: the one blind edge (3.38.2 + flutter clean) is exactly the attempt the reporter reported as still failing in c9; the root cause, the accepted workaround, and the "don't confuse this with the second, non-native-assets AOT bug" scoping all match participant4's and participant5's conclusions. Defects found are fidelity-level, not scoring-inverting: one clarification answer on the round-3 canonical branch reveals framework-specific knowledge the reporter never had at that point, and N2's info_state carries a fact that is only surfaced on the blind side branch._

### Confirmed findings

- [ ] 🟠 **unfaithful_reveal** (medium) — `n/a`
  - claim: [unfaithful_reveal / medium] e0_N0__N0b.clarifications[1].user_answer_in_this_oncall (complete_content_delivery_log_has_same_validation_error) = 'The complete log shows the same validation error, only for that framework' — dangling reference to a framework the reporter never identified, known only later from an engineer's reproduction.
  - thread evidence: None
  - suggested fix: None
  - verifier: Confirmed against the thread. The reporter's only log post is c9 (2025-11-20): 'Hmmm... I am still having the same issue after updated to Flutter 3.38.2 and after do `flutter clean`' plus the raw 'Validation failed / LC_ENCRYPTION_INFO ... (ID: b9bbf70b-...)' text and a ContentDelivery.log link — no framework is named anywhere in it. participant2's earlier log (c4) likewise names none. The string 
- [ ] 🟡 **provenance_request_vs_volunteer** (low) — `n/a`
  - claim: [measurement_class_violation / low] N2.volunteered_info -> 'project_support_files_shared': the support files were handed over only after an explicit handler request (c13), so modeling them as volunteered gives the agent the evidence without asking.
  - thread evidence: None
  - suggested fix: None
  - verifier: Confirmed verbatim. c13 (participant4): 'Also, could you provide your `Info.plist`, `Runner.xcodeproj`, and `pubspec.lock` to help us debug?'; the reporter complies only in c14: 'Here are the files you requested... [sup-files.zip]'. There is no unprompted disclosure of these files anywhere in the thread, so 'volunteered' misstates provenance and lets the simulated user push the archive out proacti
- [ ] 🟡 **level_inconsistency** (low) — `n/a`
  - claim: [level_inconsistency / low] project_dependencies_include_sqlite3_native_assets is graded L1_basic on e2_N1_x__N2 but L2_inferable on e0_N0__N0b, while e3 and e5 both list it under L2.
  - thread evidence: None
  - suggested fix: None
  - verifier: Confirmed in the graph: e2.clarifications[0].level = 'L1_basic', e0.clarifications[0].level = 'L2_inferable', and both e3.required_info.L2 and e5.required_info.L2 contain the id. Confirmed in the thread that there is exactly one disclosure event behind both edges — participant1's c0 ('please share your pubspec.yaml as well') answered by the reporter in c1 with the full pubspec including sqflite_sq

### Refuted claims (auditor was wrong — do not act on these)

- ~~graph_shape~~: [graph_shape / medium] N2.info_state carries upgrade_3382_and_flutter_clean_still_same_error although on the canonical path N0 -> N0b -> N2 it is never asked for or volunteered; it is granted only on the blind branch, so
  - why refuted: The mechanical observation is accurate (N0b lacks the id, e0b asks only validate_app_fails_independently_of_distribution, and N2.volunteered_info lists only project_support_files_shared), but the conclusion and the proposed fix are wrong. In the thread the reporter VOLUNTEERED that result unprompted at c9 (2025-11-20) 


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
