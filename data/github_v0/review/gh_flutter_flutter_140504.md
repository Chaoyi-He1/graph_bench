# Review: gh_flutter_flutter_140504

**Flutter web Shader compilation error**

- source: https://github.com/flutter/flutter/issues/140504
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_flutter_flutter_140504.json` · raw thread: `data/github_v0/raw/gh_flutter_flutter_140504.json`

```mermaid
flowchart LR
    N0["<b>N0 published CanvasKit app fails</b><br/><small>info: 4</small>"]
    N1["<b>N1 browser and architecture scope established</b><br/><small>info: 8</small>"]
    N2["<b>N2 Flutter master also affected</b><br/><small>info: 9</small>"]
    N3["<b>N3 GPU and shader evidence collected</b><br/><small>info: 12</small>"]
    N4["<b>N4 network JPEG trigger isolated</b><br/><small>info: 13</small>"]
    N4_x["<b>N4_x canvas rasterization flag aftermath</b><br/><small>info: 14</small>"]
    N5["<b>N5 browser image decoding workaround verified</b><br/><small>info: 14</small>"]
    N6["<b>N6 Chrome-side correction verified (fix applied, unverified)</b><br/><small>info: 14</small>"]
    N_terminal["<b>terminal resolved</b><br/><small>info: 17</small>"]
    N5_x2["<b>N5_x2 newer-beta aftermath</b><br/><small>info: 15</small>"]
    N0 -.->|"❓ failure_specific_to_chrome_beta_121_x86_64, other_browsers_work, chrome_stable_120_and_canary_122_work, canvaskit_only"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ flutter_master_build_has_same_failure"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ about_gpu_hardware_webgl_and_intel_workarounds, raw_console_context_loss_and_circle_texture_shader, reduced_example_still_fails_with_circle_avatars"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ network_jpeg_triggers_while_png_webp_gif_work"| N4
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N4 -.->|"❓ disabling_browser_image_decoding_avoids_failure"| N5
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"💥 blind: Enable Chrome's Out-of-process 2D canvas rasterization flag and relaunch the browser to avoid the rendering failure."| N4_x
    linkStyle 5 stroke:#ef4444,stroke-width:2px
    N5 ==>|"⚡ Treat this as a Chromium ANGLE-on-Metal regression on Intel macOS, not a Flutter shader defect; have affected users update to a Chrome build containing the Chrome-side rollback or fix. Use disabled browser image decoding only as a temporary application-controlled workaround."| N6
    linkStyle 6 stroke:#f97316,stroke-width:2px
    N6 -.->|"❓ chrome_122_0_6261_129_update_verified_working"| N_terminal
    linkStyle 7 stroke:#3b82f6,stroke-width:2px
    N5 ==>|"💥 blind: Try the newer Chrome Beta (v123) to see whether the upstream fix has reached it."| N5_x2
    linkStyle 8 stroke:#ef4444,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3 normal
    class N4 normal
    class N4_x normal
    class N5 normal
    class N6 normal
    class N_terminal terminal
    class N5_x2 normal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I built my Flutter web app with `flutter build web --web-renderer canvaskit` and published it to Firebase Hosting. The published website does not work and Chrome DevTools reports a shader compilation error, although the app works in debugging mode. My reproduction is at https://github.com/reporter/flutter_webgl_error and the deployed site is https://flutter-webgl-error.web.app. I am using Flutter stable 3.16.4 on an Intel Mac.

## Satisfaction conditions

1. Must identify the root cause as a Chromium ANGLE-on-Metal regression on Intel macOS that crashes or loses the GPU/WebGL context while compiling the relevant Skia shader path; it is not fundamentally a Flutter application shader or Flutter master/stable defect.
2. The diagnosis must be grounded in the collected evidence: the Chrome channel and x86_64 specificity, raw GPU/context-loss and shader output, network-JPEG trigger, browser-image-decoding bypass, and successful corrected-Chrome verification.
3. The durable resolution must be updating to a Chrome build containing Chromium's rollback or fix for the Intel Mac ANGLE-Metal rollout; `BROWSER_IMAGE_DECODING_ENABLED=false` may be offered only as a temporary workaround with its UI-thread decoding and jank risk.
4. Must not present enabling Out-of-process 2D canvas rasterization as a reliable customer fix: it was not deployable by the app and an affected user explicitly reported that it did not work.
5. Must not require converting all JPEGs, abandoning CanvasKit, or upgrading Flutter as the root fix, although image conversion or another renderer may be mentioned as temporary mitigations.
6. Must treat the issue as resolved only after the reporter or another affected Intel Mac user verifies that the hosted application works in the corrected Chrome version.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: failure_specific_to_chrome_beta_121_x86_64, other_browsers_work, chrome_stable_120_and_canary_122_work, canvaskit_only | It fails in Chrome Beta 121.0.6167.16, the x86_64 build, on my 2020 Intel MacBook Pro. / I tried all my other browsers and the site works there. I only see this failure in the affected Chrome build. / On the same Intel Mac, Chrome Stable 120 works, Chrome Beta 121 does not work, and Chrome Canary 122 works. / Yes, I only see it with CanvasKit rendering. |
| `e2_N1__N2` | clarification_only | asks: flutter_master_build_has_same_failure | I tested Flutter master 3.18.0-18.0.pre.39 with engine afd214dccc, and I get the same result. |
| `e3_N2__N3` | clarification_only | asks: about_gpu_hardware_webgl_and_intel_workarounds, raw_console_context_loss_and_circle_texture_shader, reduced_example_still_fails_with_circle_avatars | My Chrome Beta `about:gpu` output says Canvas, compositing, rasterization, WebGL, and WebGL2 are hardware acce / The console prints `CONTEXT_LOST_WEBGL: loseContext: context lost`, `INVALID_OPERATION: delete: object does no / I cut the page down to basically just the circle avatars — the reduced example still crashes the same way. |
| `e4_N3__N4` | clarification_only | asks: network_jpeg_triggers_while_png_webp_gif_work | I tested network images separately. JPG and JPEG make the app fail, while PNG, WebP, and GIF work. Changing th |
| `e5_N4__N5` | clarification_only | asks: disabling_browser_image_decoding_avoids_failure | This works for me. The release build compiled with `--dart-define=BROWSER_IMAGE_DECODING_ENABLED=false` render |
| `e6_N4__N4_x` | solution_only **BLIND** | req_info: published_canvaskit_release_blank_with_shader_error, about_gpu_hardware_webgl_and_intel_workarounds<br>elements: mentions_enabling_out_of_process_canvas_rasterization | Enable Chrome's Out-of-process 2D canvas rasterization flag and relaunch the browser to avoid the rendering failure. |
| `e7_N5__N6` | solution_only | req_info: published_canvaskit_release_blank_with_shader_error, chrome_stable_120_and_canary_122_work, canvaskit_only, about_gpu_hardware_webgl_and_intel_workarounds, raw_console_context_loss_and_circle_texture_shader, disabling_browser_image_decoding_avoids_failure, network_jpeg_triggers_while_png_webp_gif_work<br>elements: identifies_chromium_angle_metal_regression_on_intel_macos, explains_that_the_failure_is_not_fixed_by_updating_flutter, recommends_a_chrome_build_with_the_chromium_correction, labels_disabled_browser_image_decoding_as_temporary_with_performance_cost | Treat this as a Chromium ANGLE-on-Metal regression on Intel macOS, not a Flutter shader defect; have affected users update to a Chrome build containing the Chrome-side rollback or fix. Use disabled browser image decoding only as a temporary application-controlled workaround. |
| `e8_N6__N_terminal` | clarification_only | asks: chrome_122_0_6261_129_update_verified_working | I can confirm it is working for me after the corrected Chrome rollout. The hosted example renders again, and o |
| `e9_N5__N5_x2` | solution_only **BLIND** | req_info: <br>elements: mentions_trying_newer_chrome_beta | Try the newer Chrome Beta (v123) to see whether the upstream fix has reached it. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 1 | 0 | My published CanvasKit website does not work and the Chrome console reports a shader compilation error, while the same app works in debuggin |
| `N1` |  | 0 | 0 | The deployed app fails in Chrome Beta 121 on my Intel Mac, but it works in the other browsers I tried, including Chrome Stable 120 and Chrom |
| `N2` |  | 0 | 0 | The same deployed CanvasKit example still fails in the affected Chrome browser when built with Flutter master. |
| `N3` |  | 0 | 0 | The failing browser reports `CONTEXT_LOST_WEBGL`, invalid WebGL operations, and a shader compilation error for a fragment shader that sample |
| `N4` |  | 0 | 0 | Loading a JPG or JPEG image from the network makes the release app go blank with the shader error on affected Intel Macs, while equivalent P |
| `N4_x` |  | 1 | 0 | After enabling Out-of-process 2D canvas rasterization and relaunching Chrome, the same hosted example still throws the exception on my affec |
| `N5` |  | 0 | 0 | The default release build still fails with network JPEG images, but a profile or release build compiled with `--dart-define=BROWSER_IMAGE_DE |
| `N6` |  | 0 | 0 | I've updated Chrome to 122.0.6261.129; I haven't re-run the avatar page yet. |
| `N_terminal` | ✓ | 0 | 0 | The published Flutter CanvasKit website renders normally in the corrected Chrome version on Intel macOS, including its network JPEG images,  |
| `N5_x2` |  | 1 | 0 | I tried the newer Chrome Beta (v123) and the page still goes blank with the same error. |

## Machine review (audit pass, adversarially verified)

Auditor verdict: **minor_issues** · 1 of 5 findings survived independent refutation.

_The case tests a Flutter-web CanvasKit failure that turns out to be a Chromium ANGLE-on-Metal regression on Intel macOS, triggered specifically by network JPEG decoding, and finally fixed browser-side (Chrome 122.0.6261.129 / chromium issue 328302269). The graph is a faithful and unusually well-constructed rendering of that arc: the browser/channel narrowing, master-channel test, about:gpu + raw shader dump, JPEG-vs-PNG/WebP/GIF isolation, the BROWSER_IMAGE_DECODING_ENABLED=false probe, and the corrected-Chrome verification all map to real thread turns in the right order, and the root cause and satisfaction conditions match what participant3 and participant23 established. No blind path is mislabeled in a way that inverts the answer, and every required_info id is obtainable. The remaining issues are fidelity-level: the one blind path presents a one-sided outcome for a workaround that the thread says worked for most reporters, it dead-ends, and a couple of state/merge bookkeeping details are loose._

### Confirmed findings

- [ ] 🟡 **graph_shape** (low) — `nodes.N4_x (no outgoing edges) / edges[e6_N4__N4_x]`
  - claim: N4_x is a non-terminal aftermath node with no outgoing edge at all, so an agent that takes the blind path has no modeled route back toward the terminal; the edge is also hung downstream of the JPEG isolation even though the attempt happened much earlier in the thread.
  - thread evidence: The flag attempt and its falsification are c25 (2024-02-01) through c30/c35 (2024-02-06/08), whereas the JPEG-format isolation that defines N4 is c42-c50 (2024-03-01). The edge's own comment says "Thread c25-c35", contradicting its placement after N4. In the thread the investigation continued after the flag failed (c31 reporter keeps asking participant5 for a minimum example).
  - suggested fix: Either add a recovery clarification edge from N4_x back onto the canonical line (e.g. to N5, matching c31 "Do you have a minimum example for which widget makes this crash?"), or re-anchor the blind edge at N3, whose info_state matches what was actually known when the flag was suggested.
  - verifier: Half confirmed, half refuted. CONFIRMED: N4_x is is_terminal=false with zero out-edges, and this has a real runtime consequence - responder.py:620 comments "Dead-end node (e.g. N3_x): no canonical path -> fail" and sets termination_reason='failed_dead_end'. src/graph_bench/oncall_graph/rollbacks.py exists precisely because "the graph builder never emitted those return edges, leaving decoy destinat

### Refuted claims (auditor was wrong — do not act on these)

- ~~unfaithful_reveal~~: The aftermath node states flatly that enabling Out-of-process 2D canvas rasterization still throws the exception, but in the thread that flag worked for the clear majority of affected Intel-Mac users and failed for only 
  - why refuted: The reviewer's census of the thread is accurate (c25/c35/c43/c49/c53/c71 report the flag working; only participant5 falsifies it), but that does not make the encoding unfaithful. c30 ("I tried this workaround but its not working for me") plus c32 ("No its throwing the same exception", with screenshot, on Chrome/Mac Int
- ~~graph_shape~~: system_state_id does not advance where the user's system actually changed: N6 describes the machine after Chrome was updated to the corrected rollout yet stays on S1, and N4_x describes Chrome after a flags change and re
  - why refuted: This is a critique of a uniform corpus convention, not of this graph. All 14 github_v0 graphs use exactly two system states - S1 for every investigation node and S2 for the terminal only - and all 22 blind-path aftermath nodes in the corpus keep their source node's system_state_id (0 of 22 advance it), so N4_x on S1 is
- ~~multi_user_merge_undeclared~~: The BROWSER_IMAGE_DECODING_ENABLED=false result is spoken by the single simulated user, but in the thread the probe was answered by a different affected user than the reporter, and this edge's comment does not declare th
  - why refuted: The factual half is right - c63 participant3 asks for the build, c64 participant14 answers "This works for me", and the reporter never reports running it - but the contract requires that the merge be declared in AN edge comment, not in every edge that consumes it. This graph declares it plainly and more than once: e4's
- ~~graph_shape~~: A genuinely falsified attempt - 'update to the Chrome 123 Beta, it is fixed there' - exists in the thread but is only mentioned inside e7's comment, so an agent that proposes exactly that premature browser-update advice 
  - why refuted: c69/c70 are quoted correctly (participant22 proposes the v123 Beta; the reporter answers "It still exists in Chrome v123 Beta for me" with a screenshot), so this would be an authorable blind path. But omitting it is not a defect: nothing in the contract requires exhaustive enumeration of every falsified suggestion, and


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
