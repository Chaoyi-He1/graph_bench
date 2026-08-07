# Review: gh_haproxy_haproxy_2004

**QUIC protocol errors and HTTP/2 fallback with Chromium image-heavy pages**

- source: https://github.com/haproxy/haproxy/issues/2004
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_haproxy_haproxy_2004.json` · raw thread: `data/github_v0/raw/gh_haproxy_haproxy_2004.json`

```mermaid
flowchart LR
    N0["<b>N0 Chromium QUIC image failures reported</b><br/><small>info: 6</small>"]
    N1["<b>N1 complete QUIC trace captured</b><br/><small>info: 7</small>"]
    N2_x["<b>N2_x STOP_SENDING patch aftermath</b><br/><small>info: 9</small>"]
    N3["<b>N3 combined protocol traces captured</b><br/><small>info: 10</small>"]
    N4_x["<b>N4_x first RESET_STREAM patch aftermath</b><br/><small>info: 13</small>"]
    N5_x["<b>N5_x old patch on newer master aftermath</b><br/><small>info: 14</small>"]
    N6_x["<b>N6_x refined experimental patch aftermath</b><br/><small>info: 15</small>"]
    N7["<b>N7 intermittent local reproducer available</b><br/><small>info: 18</small>"]
    N_terminal["<b>terminal dev reproducer no longer fails</b><br/><small>info: 21</small>"]
    N0 -.->|"❓ unfiltered_haring_trace_contains_two_error_events"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Prevent HAProxy from sending STOP_SENDING frames on HTTP/3 control and other unidirectional streams."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ combined_quic_qmux_h3_trace_captured"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"🔀 ❓chrome_still_disables_h3_after_first_reset_patch, full_trace_with_h3_minimal_verbosity_captured + ⚡Avoid sending an unnecessary RESET_STREAM when the QUIC mux shuts down its write side."| N4_x
    linkStyle 3 stroke:#a855f7,stroke-width:2px
    N4_x ==>|"💥 blind: Retest the earlier mux reset-suppression patch on the newer master build containing the recent HTTP/3 connection-shutdown changes."| N5_x
    linkStyle 4 stroke:#ef4444,stroke-width:2px
    N5_x ==>|"💥 blind: Replace the earlier patch with the refined experimental stream-shutdown patch that conditionally sends RESET_STREAM instead of an empty STREAM frame with FIN."| N6_x
    linkStyle 5 stroke:#ef4444,stroke-width:2px
    N6_x ==>|"💥 blind: Move to a current unpatched 2.8-dev build and provide a locally runnable proxy configuration so maintainers can exercise the intermittent failure without the obsolete experimental patches."| N7
    linkStyle 6 stroke:#ef4444,stroke-width:2px
    N7 ==>|"⚡ Use a HAProxy build containing the two later fixes that remove or reduce spurious RESET_STREAM emissions, then verify the previously failing Chromium image workload before declaring the issue resolved."| N_terminal
    linkStyle 7 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2_x normal
    class N3 normal
    class N4_x normal
    class N5_x normal
    class N6_x normal
    class N7 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> In our QUIC-enabled development environment, Chromium-based browsers regularly fail to serve images with `net::ERR_QUIC_PROTOCOL_ERROR 200`. After enough failures, the browser refuses to use QUIC with the origin for a while. The best reproducer is to force QUIC for the origin, open a page containing many images, switch to the grid view so larger thumbnails load, and paginate once or twice. Plain HTML and smaller payloads do not trigger it as regularly. We are running a customized HAProxy 2.8-dev build on Linux with an HTTP/3 QUIC listener, `allow-0rtt`, per-thread shards, a 32768-byte buffer, and QUIC developer tracing to a ring.

## Satisfaction conditions

1. Must identify the final accepted root cause as HAProxy emitting spurious or unjustified RESET_STREAM frames in the QUIC/HTTP/3 stream handling path, grounded in the collected QUIC, qmux, and h3 traces and the patch-test outcomes.
2. Must recommend a build containing both later fixes that remove or reduce those spurious RESET_STREAM emissions, rather than relying on the earlier experimental stream-shutdown patches.
3. Must not present suppressing STOP_SENDING on HTTP/3 unidirectional streams as the fix; the reporter reproduced the same errors after installing that patch.
4. Must not present either earlier mux reset patch as resolved: one only reduced error frequency while introducing stalls and HTTP/2 fallback, and the later tested combinations ended in handshake failures.
5. Must ask the reporter to verify the image-grid workload on a build containing the final fixes before declaring resolution.
6. Resolution may rely on the reporter's confirmation that the development reproducer stopped failing, but must not claim comprehensive production verification because the reporter lacked detailed browser-error monitoring.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: unfiltered_haring_trace_contains_two_error_events | I captured the ring without filtering it. There should be two events, one around 09:26–09:27 and another aroun |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: chromium_images_fail_with_quic_protocol_error_200, unfiltered_haring_trace_contains_two_error_events<br>elements: suppresses_stop_sending_on_http3_unidirectional_streams | Prevent HAProxy from sending STOP_SENDING frames on HTTP/3 control and other unidirectional streams. |
| `e3_N2_x__N3` | clarification_only | asks: combined_quic_qmux_h3_trace_captured | I enabled the requested qmux and h3 developer traces on the same ring sink and captured another occurrence. He |
| `e4_N3__N4_x` | mixed **BLIND** | req_info: image_grid_pagination_reproduces_quickly, combined_quic_qmux_h3_trace_captured<br>elements: changes_mux_stream_shutdown_reset_behavior | Avoid sending an unnecessary RESET_STREAM when the QUIC mux shuts down its write side. |
| `e5_N4_x__N5_x` | solution_only **BLIND** | req_info: chrome_still_disables_h3_after_first_reset_patch, full_trace_with_h3_minimal_verbosity_captured<br>elements: combines_newer_master_with_earlier_mux_patch | Retest the earlier mux reset-suppression patch on the newer master build containing the recent HTTP/3 connection-shutdown changes. |
| `e6_N5_x__N6_x` | solution_only **BLIND** | req_info: current_master_with_old_patch_immediate_handshake_failures<br>elements: uses_refined_conditional_stream_shutdown_patch | Replace the earlier patch with the refined experimental stream-shutdown patch that conditionally sends RESET_STREAM instead of an empty STREAM frame with FIN. |
| `e7_N6_x__N7` | solution_only **BLIND** | req_info: image_grid_pagination_reproduces_quickly, current_master_with_refined_patch_stalls_then_handshake_failures<br>elements: uses_current_development_build, provides_local_forced_quic_reproducer | Move to a current unpatched 2.8-dev build and provide a locally runnable proxy configuration so maintainers can exercise the intermittent failure without the obsolete experimental patches. |
| `e8_N7__N_terminal` | solution_only | req_info: chromium_images_fail_with_quic_protocol_error_200, browser_temporarily_falls_back_from_quic, image_grid_pagination_reproduces_quickly, haproxy_logs_failed_requests_at_error_level, unfiltered_haring_trace_contains_two_error_events, combined_quic_qmux_h3_trace_captured, chrome_still_disables_h3_after_first_reset_patch, full_trace_with_h3_minimal_verbosity_captured<br>elements: identifies_spurious_reset_stream_emission_as_the_final_root_cause, uses_both_later_stream_reset_fixes, asks_user_to_verify_on_a_build_containing_the_fixes, does_not_claim_broad_production_confirmation_beyond_available_monitoring | Use a HAProxy build containing the two later fixes that remove or reduce spurious RESET_STREAM emissions, then verify the previously failing Chromium image workload before declaring the issue resolved. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 1 | 0 | In Chromium-based browsers, images regularly fail with `net::ERR_QUIC_PROTOCOL_ERROR 200` when loaded over HTTP/3 through HAProxy. After rep |
| `N1` |  | 0 | 0 | The Chromium QUIC protocol errors remain reproducible while the browser stays open. |
| `N2_x` |  | 2 | 1 | With the patch that stops sending STOP_SENDING on HTTP/3 unidirectional streams, Chromium still reports QUIC protocol errors. The correspond |
| `N3` |  | 0 | 0 | The same image requests continue to fail while QUIC, qmux, and HTTP/3 tracing are enabled. |
| `N4_x` |  | 1 | 0 | With the first mux patch, failures become less frequent, changing from roughly one per 30 images to roughly one per 150 images, but some req |
| `N5_x` |  | 1 | 1 | On the newer master build with the older patch applied, Chromium reports a QUIC handshake failure within the first 11 small-image requests. |
| `N6_x` |  | 1 | 1 | With the refined patch on the newer master build, about 220 requests initially succeed, then some requests stall for about five seconds, and |
| `N7` |  | 3 | 1 | A later 2.8-dev build still produces QUIC protocol errors. With the local proxy reproducer, roughly half of Chromium sessions encounter QUIC |
| `N_terminal` | ✓ | 2 | 0 | After installing a build containing the two later RESET_STREAM fixes, my previous development-environment reproducer no longer triggers the  |

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
