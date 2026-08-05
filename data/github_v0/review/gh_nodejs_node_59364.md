# Review: gh_nodejs_node_59364

**Node.js 22.18 enables experimental type stripping and breaks Mocha 10 tests**

- source: https://github.com/nodejs/node/issues/59364
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_nodejs_node_59364.json` · raw thread: `data/github_v0/raw/gh_nodejs_node_59364.json`

```mermaid
flowchart LR
    N0["<b>N0 Node 22.18 CI failure reported</b><br/><small>info: 4</small>"]
    N1["<b>N1 concrete failures collected</b><br/><small>info: 6</small>"]
    N2["<b>N2 Mocha 10 loader interaction isolated</b><br/><small>info: 8</small>"]
    N2_x["<b>N2_x Node handler-change revert aftermath</b><br/><small>info: 9</small>"]
    N3["<b>N3 Mocha 11 installed (unverified)</b><br/><small>info: 8</small>"]
    N_terminal["<b>terminal resolved</b><br/><small>info: 12</small>"]
    N0 -.->|"❓ reporter_saw_dirname_undefined_in_commonjs_expected_project, affected_mocha_run_throws_err_internal_assertion"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ reporter_project_uses_mocha_10, minimal_repro_uses_mocha_with_ts_node_register"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"💥 blind: Treat the `.js` handler changes from Node.js PR #58657 as the direct cause and revert that Node change."| N2_x
    linkStyle 2 stroke:#ef4444,stroke-width:2px
    N2 ==>|"⚡ Upgrade the affected project from Mocha 10 to Mocha 11 or the latest compatible Mocha, whose module-loading fallback works with Node.js 22.18 type stripping, instead of permanently disabling the Node feature."| N3
    linkStyle 3 stroke:#f97316,stroke-width:2px
    N3 -.->|"❓ latest_mocha_test_passes_without_disabling_type_stripping"| N_terminal
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
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

> After updating from Node.js 22.17 to 22.18.0, our builds consistently fail across Linux, Windows, and Azure DevOps agents. The same project works on 22.17. Adding `--no-experimental-strip-types` to the Node command line makes it work again. I would not expect an experimental feature to become enabled by default in a minor release of the existing Node 22 LTS line.

## Satisfaction conditions

1. Must identify the resolved reporter-specific root cause: Node.js 22.18's default type stripping changed TypeScript module handling and the error seen during import, while Mocha 10's loader retry logic did not handle `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`, preventing the intended require/TypeScript-hook path.
2. The diagnosis must be grounded in the collected evidence: the Node 22.17-to-22.18 change, success with type stripping disabled, the affected project's Mocha 10 dependency, the Mocha/ts-node reproduction, and the successful latest-Mocha test.
3. Must recommend upgrading from Mocha 10 to Mocha 11 or the latest compatible Mocha as the durable fix; `--no-experimental-strip-types` may be mentioned only as the temporary workaround that exposed the interaction.
4. Must not prescribe reverting Node.js PR #58657 as the fix because that revert was tested in the thread and the reproduced failure persisted.
5. Must not generalize the Mocha 10 resolution to every later tsx, ts-node/esm, SWC, Jest, Jasmine, or node:test report in the thread; those involve separate loader integrations and may require their own reproductions or dependency updates.
6. Must treat the original issue as resolved only after the reporter verifies that the upgraded Mocha runs the tests on Node.js 22.18 without `--no-experimental-strip-types`.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: reporter_saw_dirname_undefined_in_commonjs_expected_project, affected_mocha_run_throws_err_internal_assertion | What I saw was that `__dirname` was suddenly not defined. We do not specify `type` in our package.json files,  / In another affected Mocha run I get `Error [ERR_INTERNAL_ASSERTION]: Unexpected status of a module that is imp |
| `e2_N1__N2` | clarification_only | asks: reporter_project_uses_mocha_10, minimal_repro_uses_mocha_with_ts_node_register | I found that we use Mocha 10 in our project. / I can reproduce the same class of failure while executing tests with `mocha --require ts-node/register`. A min |
| `e4_N2__N2_x` | solution_only **BLIND** | req_info: no_experimental_strip_types_flag_avoids_failure, minimal_repro_uses_mocha_with_ts_node_register<br>elements: recommends_reverting_node_pr_58657 | Treat the `.js` handler changes from Node.js PR #58657 as the direct cause and revert that Node change. |
| `e3_N2__N3` | solution_only | req_info: node_22_18_ci_builds_fail_after_22_17_worked, no_experimental_strip_types_flag_avoids_failure, reporter_saw_dirname_undefined_in_commonjs_expected_project, affected_mocha_run_throws_err_internal_assertion, reporter_project_uses_mocha_10, minimal_repro_uses_mocha_with_ts_node_register<br>elements: identifies_mocha_10_loader_compatibility_as_the_reporter_case, explains_changed_typescript_error_or_fallback_behavior, recommends_upgrading_to_mocha_11_or_latest, does_not_require_permanently_disabling_type_stripping | Upgrade the affected project from Mocha 10 to Mocha 11 or the latest compatible Mocha, whose module-loading fallback works with Node.js 22.18 type stripping, instead of permanently disabling the Node feature. |
| `e5_N3__terminal` | clarification_only | asks: latest_mocha_test_passes_without_disabling_type_stripping | Upgrading to the latest Mocha fixes the initial problem. The tests now run on Node.js 22.18 and I do not have  |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | Our CI builds consistently fail on Node.js 22.18.0 even though they worked on 22.17. The builds run again when I add `--no-experimental-stri |
| `N1` |  | 0 | 0 | In my project, `__dirname` suddenly becomes undefined on Node.js 22.18 even though our package.json files do not specify a module type and w |
| `N2` |  | 0 | 0 | The test suite still fails on Node.js 22.18 with its existing Mocha 10 setup, while disabling type stripping lets it run. |
| `N2_x` |  | 1 | 0 | Nothing has changed on my side — my repro still fails exactly as before. |
| `N3` |  | 0 | 0 | I've upgraded Mocha to 11 in the project; I haven't re-run the full suite yet. |
| `N_terminal` | ✓ | 0 | 0 | The project test suite runs successfully on Node.js 22.18 with the current Mocha version and without disabling Node's type-stripping feature |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **minor_issues** · 2 of 2 findings survived independent refutation.

_The case tests whether an agent can drive a vague "Node 22.18 broke our CI, --no-experimental-strip-types fixes it" report down to the reporter-specific cause (Mocha 10's ESM-retry logic not recognizing the new ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX error) and recommend a Mocha upgrade rather than permanently disabling the Node feature. The canonical path (N0→N1→N2→N3→terminal) is a faithful compression of the thread: c3 (__dirname), c2 (ERR_INTERNAL_ASSERTION), c11 (mocha + ts-node/register repro), c19 (reporter finds Mocha 10, upgrade fixes it), with the root-cause statement lifted essentially verbatim from participant8's c15 analysis. The single blind path (revert Node PR #58657) is correctly labeled — c30 really did try it and the failure persisted — so no blind-path inversion. The one substantive fidelity problem is that this blind path's aftermath is written in the reporter's voice and pinned to the Mocha/ts-node repro, whereas the thread shows a Node maintainer performing the revert against the tsx reproduction._

### Confirmed findings

- [ ] 🟡 **unfaithful_reveal** (low) — `graph.nodes.N2_x (symptoms_visible[0], volunteered_info) and edge e4_N2__N2_x`
  - claim: The aftermath of the #58657 revert is voiced as the user reporting that "My Mocha/ts-node repro still fails exactly as before on my side", but in the thread the revert was built and tested by a Node core maintainer, and the failure it did not remove was the tsx reproduction, not the Mocha/ts-node one.
  - thread evidence: c30 [participant6, 2025-08-11]: "Tried reverting https://github.com/nodejs/node/pull/58657 and the issue persists. I think the issue falls on the fact that we added the 'module-typescript' and 'commonjs-typescript' format to loaders. This patch fixes it, I sent a PR to TSX https://github.com/privatenumber/tsx/pull/733" — the surrounding investigation is participant11's tsx repro (c22, c26), and by then the reporter's own Mocha case was already resolved (c19, 2025-08-07: "Upgrading to latest mocha does fix the initial problem"). The reporter never built Node from source anywhere in the thread; persona_hint itself describes someone "comfortable managing CI flags and dependency upgrades" on a "seven-year-old" project (c9: "this is one gigantius project, that is 7 years old").
  - suggested fix: Reword N2_x.symptoms_visible to the observation actually available to the user side, e.g. "I tried a Node build with that change reverted and my test run fails exactly the same way" only if you keep it user-executed; otherwise re-anchor the aftermath to the tsx/loader-format finding and add a declaring comment on e4 that this attempt and its negative result come from the Node maintainer's own experiment (c30), folded into the single user side like the c2/c3 merge already declared on e1.
  - verifier: I tried to refute this and could not. The revert experiment lives only in c30 (participant6, 2025-08-11): "Tried reverting https://github.com/nodejs/node/pull/58657 and the issue persists. I think the issue falls on the fact that we added the 'module-typescript' and 'commonjs-typescript' format to loaders. This patch fixes it, I sent a PR to TSX ..." — the patch in that same comment is a diff agai
- [ ] 🟡 **node_label_inconsistency** (low) — `graph.nodes.N3.label`
  - claim: N3's label contradicts itself: "N3 Mocha upgrade verified (fix applied, unverified)" — the node is explicitly the pre-verification state.
  - thread evidence: The thread has no intermediate "upgraded but not yet re-run" report; c19 is a single message combining both ("Upgrading to latest mocha does fix the initial problem. And I do not have to specify --no-experimental-strip-types any more."), and the graph correctly splits it so the verification lands on e5/N_terminal — only the word "verified" in the label is wrong.
  - suggested fix: Rename to "N3 Mocha upgraded (fix applied, not yet re-run)".
  - verifier: Confirmed directly from the graph, and the reviewer's reading of the thread is right too. graph.nodes.N3 has symptoms_visible "I've upgraded Mocha to 11 in the project; I haven't re-run the full suite yet.", is_terminal=false, user_perceives_resolved=false, and its info_state does NOT yet contain latest_mocha_test_passes_without_disabling_type_stripping — that id is only added by e5's clarificatio


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
