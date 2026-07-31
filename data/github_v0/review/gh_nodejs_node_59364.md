# Review: gh_nodejs_node_59364

**Node.js 22.18 breaks CI tests after experimental type stripping becomes enabled by default**

- source: https://github.com/nodejs/node/issues/59364
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_nodejs_node_59364.json` · raw thread: `data/github_v0/raw/gh_nodejs_node_59364.json`

```mermaid
flowchart LR
    N0["<b>N0 Node 22.18 CI failure reported</b><br/><small>info: 3</small>"]
    N1["<b>N1 exact failure and module expectation collected</b><br/><small>info: 6</small>"]
    N2["<b>N2 Mocha 10 compatibility cause isolated</b><br/><small>info: 11</small>"]
    N2_x["<b>N2_x handler-revert aftermath</b><br/><small>info: 12</small>"]
    N3["<b>N3 Mocha upgrade verified</b><br/><small>info: 12</small>"]
    N_terminal["<b>terminal resolved with Mocha upgrade</b><br/><small>info: 12</small>"]
    N0 -.->|"❓ observed_dirname_not_defined_error, package_json_has_no_type_and_project_expected_commonjs, same_flag_also_avoids_problem_on_node_24"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ project_uses_mocha_10, minimal_repro_uses_mocha_10_with_ts_node_register"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"💥 blind: Revert the suspected Node.js `.js` handler change from PR 58657 on the assumption that it caused the loader incompatibility."| N2_x
    linkStyle 2 stroke:#ef4444,stroke-width:2px
    N2 -.->|"❓ upgrading_to_latest_mocha_verified_fix_without_opt_out"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"⚡ Resolve the reporter's project by adopting the latest Mocha release, whose module-loading order is compatible with Node.js 22.18 type stripping, rather than permanently disabling the Node feature."| N_terminal
    linkStyle 4 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N2_x normal
    class N3 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> After updating from Node.js 22.17 to 22.18, our builds consistently fail on Linux, Windows, and Azure DevOps agents. The code works again only if we add `--no-experimental-strip-types` to the Node.js command line. I would not expect a minor release of an existing LTS line to enable an experimental feature by default when it breaks existing projects.

## Satisfaction conditions

1. Must identify the reporter-specific root cause: Node.js 22.18 enabling type stripping changed TypeScript module-loading behavior and the error from an attempted import, while the project's Mocha 10 fallback logic did not recognize the new `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` path; current Mocha tries `require()` first so the registered TypeScript hook can handle the file.
2. Must ground the diagnosis in the collected evidence: the failure starts on Node.js 22.18, disappears with `--no-experimental-strip-types`, the project uses Mocha 10, and upgrading to the latest Mocha fixes the original problem without that flag.
3. Must not recommend reverting PR 58657 as the resolution, because that revert was tested and the issue persisted.
4. Must distinguish the reporter's verified Mocha 10 issue from later reports involving different combinations such as latest Mocha with custom ts-node loaders, tsx, swc, Jest, or node:test; those may require their own reproductions or dependency patches.
5. Must treat `--no-experimental-strip-types` as a temporary workaround rather than the final reporter-specific fix, and must not declare resolution until the upgraded Mocha setup is verified in CI on Node.js 22.18 without the flag.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: observed_dirname_not_defined_error, package_json_has_no_type_and_project_expected_commonjs, same_flag_also_avoids_problem_on_node_24 | The immediate error I saw was that `__dirname` was suddenly not defined. / We do not specify `type` in our package.json files, so the project was expected to fall back to CommonJS as it / Yes. I had also struggled with the latest Node.js 24.5.0, and `--no-experimental-strip-types` solves those pro |
| `e2_N1__N2` | clarification_only | asks: project_uses_mocha_10, minimal_repro_uses_mocha_10_with_ts_node_register | I found that our project uses Mocha 10. / A minimal reproduction from another affected participant uses Mocha 10 with `mocha --require ts-node/register` |
| `e3_N2__N2_x` | solution_only **BLIND** | req_info: ci_builds_fail_on_node_22_18_but_work_on_22_17, project_uses_mocha_10<br>elements: reverts_the_suspected_js_handler_change | Revert the suspected Node.js `.js` handler change from PR 58657 on the assumption that it caused the loader incompatibility. |
| `e4_N2__N3` | clarification_only | asks: upgrading_to_latest_mocha_verified_fix_without_opt_out | Upgrading to the latest Mocha fixes the initial problem. I no longer have to specify `--no-experimental-strip- |
| `e5_N3__N_terminal` | solution_only | req_info: observed_dirname_not_defined_error, project_uses_mocha_10, node_type_stripping_changes_typescript_import_error_code, mocha_10_retry_logic_does_not_handle_new_error_code, mocha_11_tries_require_first_allowing_typescript_hook_to_run, minimal_repro_uses_mocha_10_with_ts_node_register, upgrading_to_latest_mocha_verified_fix_without_opt_out<br>elements: identifies_mocha_10_as_the_reporter_specific_incompatible_dependency, recommends_upgrading_to_current_mocha, explains_changed_typescript_error_and_fallback_behavior, removes_permanent_need_for_no_experimental_strip_types, requires_ci_verification_without_the_flag | Resolve the reporter's project by adopting the latest Mocha release, whose module-loading order is compatible with Node.js 22.18 type stripping, rather than permanently disabling the Node feature. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 3 | 0 | CI builds consistently fail with Node.js 22.18 after working with 22.17; adding `--no-experimental-strip-types` makes them run again. |
| `N1` |  | 0 | 0 | Under Node.js 22.18, tests report that `__dirname` is not defined even though the package has no `type` field and previously behaved as Comm |
| `N2` |  | 0 | 0 | The project still fails on Node.js 22.18 without the opt-out flag, and it is running its tests with Mocha 10. |
| `N2_x` |  | 1 | 0 | The failure remains after testing a revert of the suspected `.js` handler change. |
| `N3` |  | 0 | 0 | With the latest Mocha, the original tests run successfully on Node.js 22.18 without `--no-experimental-strip-types`. |
| `N_terminal` | ✓ | 0 | 0 | The project uses the updated Mocha release, and its CI tests pass on Node.js 22.18 without disabling experimental type stripping. |

## Review checklist

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
