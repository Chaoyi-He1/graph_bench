# Review: gh_curl_curl_11203

**Hyper slowness issue**

- source: https://github.com/curl/curl/issues/11203
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_curl_curl_11203.json` · raw thread: `data/github_v0/raw/gh_curl_curl_11203.json`

```mermaid
flowchart LR
    N0["<b>N0 Hyper transfer slowness reported</b><br/><small>info: 5</small>"]
    N1["<b>N1 cross-platform reproduction and executor observation</b><br/><small>info: 7</small>"]
    N2_x["<b>N2_x PR 11344 aftermath</b><br/><small>info: 8</small>"]
    N3["<b>N3 delay isolated to Hyper HTTP2 path</b><br/><small>info: 12</small>"]
    N4["<b>N4 repeated HTTP2 prefaces identify lifecycle defect</b><br/><small>info: 16</small>"]
    N5["<b>N5 temporary fix verified on master</b><br/><small>info: 17</small>"]
    N_terminal["<b>terminal Hyper slowness mitigated</b><br/><small>info: 17</small>"]
    N0 -.->|"❓ linux_reproduces_hyper_slowness, second_executor_poll_returns_response_immediately"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Apply the initial Hyper integration changes from PR 11344, based on the executor and waker observations, as the fix for the long pauses."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ first_response_immediate_then_thirty_second_gaps, some_responses_can_be_dropped, http11_fast_while_hyper_http2_slow, trace_shows_no_replacement_connection"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ packet_capture_shows_h2_preface_before_every_request"| N4
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N4 -.->|"❓ master_with_hyper_http2_disabled_verified_fast"| N5
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N5 ==>|"⚡ Ship the safe temporary mitigation from PR 12191: disable HTTP/2 in the Hyper backend so requests use reusable HTTP/1.1 connections, while documenting that restoring Hyper HTTP/2 requires a connection-lifecycle rearchitecture."| N_terminal
    linkStyle 5 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
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

> I built curl with -DUSE_HYPER on Windows 10. Fetching three ADSB route URLs takes at least a minute, with long pauses between responses, whether the URLs are supplied on the command line or through a config file and whether or not I use --parallel. The curl bundled with Windows completes the same transfers in under a second. Updating Rust and rebuilding current Hyper did not help.

## Satisfaction conditions

1. Must identify the true root cause: curl's Hyper integration created a hyper_clientconn for each request on a reused HTTP/2 connection, causing a new HTTP/2 connection preface and settings to be sent before every request; this invalid sequence can provoke server GOAWAY behavior, delayed retries, or dropped requests.
2. Must ground the diagnosis in the collected evidence: HTTP/1.1 is fast while the Hyper HTTP/2 path has approximately 30-second gaps, no replacement connection appears in the trace, and the packet capture shows repeated HTTP/2 prefaces.
3. Must not present updating Rust or Hyper, polling the executor twice, or PR 11344 as the resolution; fresh rebuilds and PR 11344 did not resolve the reporter's case.
4. The accepted mitigation must disable HTTP/2 for the Hyper backend and fall back to HTTP/1.1, while acknowledging that restoring Hyper HTTP/2 requires correct connection-lifetime persistence or a connection-filter rearchitecture.
5. Must require reporter verification of the patched master build, showing the transfer reduced from over a minute to about one second without the long gaps, before declaring the slowness resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: linux_reproduces_hyper_slowness, second_executor_poll_returns_response_immediately | Yes. Other affected testers reproduce it on Linux: normal curl finishes in one or two seconds, while curl with / After socket input is processed, the first hyper_executor_poll returns HYPER_TASK_EMPTY. Calling it a second t |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: linux_reproduces_hyper_slowness, second_executor_poll_returns_response_immediately<br>elements: applies_pr11344_or_equivalent_initial_executor_changes | Apply the initial Hyper integration changes from PR 11344, based on the executor and waker observations, as the fix for the long pauses. |
| `e3_N2_x__N3` | clarification_only | asks: first_response_immediate_then_thirty_second_gaps, some_responses_can_be_dropped, http11_fast_while_hyper_http2_slow, trace_shows_no_replacement_connection | The first response arrives immediately. Then there is a pause of about 30 seconds before the second response a / In some runs one of the three responses is missing as well as the run taking about a minute. / Yes. With Hyper, the default HTTP/2 path takes over 60 seconds for these endpoints, while adding --http1.1 com / No. The trace shows no new connection, and curl does not report a failed transfer followed by a reconnect. |
| `e4_N3__N4` | clarification_only | asks: packet_capture_shows_h2_preface_before_every_request | The normal backend sends one HTTP/2 connection preface, settings/window update, and then requests 1, 2, and 3. |
| `e5_N4__N5` | clarification_only | asks: master_with_hyper_http2_disabled_verified_fast | Yes. After updating Hyper and curl master, the same three transfers take about 1.137 seconds instead of over a |
| `e6_N5__N_terminal` | solution_only | req_info: hyper_three_url_transfer_takes_over_minute, nonhyper_windows_curl_completes_under_second, http11_fast_while_hyper_http2_slow, packet_capture_shows_h2_preface_before_every_request, master_with_hyper_http2_disabled_verified_fast<br>elements: identifies_per_request_hyper_clientconn_as_root_cause, explains_repeated_http2_preface_is_invalid, disables_http2_for_hyper_as_verified_temporary_fix, notes_long_term_connection_lifecycle_rearchitecture | Ship the safe temporary mitigation from PR 12191: disable HTTP/2 in the Hyper backend so requests use reusable HTTP/1.1 connections, while documenting that restoring Hyper HTTP/2 requires a connection-lifecycle rearchitecture. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 5 | 0 | A curl build using Hyper takes at least one minute to fetch three route URLs, with long pauses between them; the Windows-bundled curl comple |
| `N1` |  | 0 | 0 | The same Hyper-specific delay is reproducible on Linux; tracing shows a response becomes available immediately when the Hyper executor is po |
| `N2_x` |  | 1 | 0 | After rebuilding with the changes from PR 11344, the reporter still sees roughly minute-long transfers and long pauses between responses. |
| `N3` |  | 0 | 0 | The first response arrives immediately, followed by approximately 30-second pauses before later responses; in some runs a response is absent |
| `N4` |  | 0 | 0 | A packet capture shows the Hyper build sending an HTTP/2 connection preface and settings before each of the three requests on the same conne |
| `N5` |  | 0 | 0 | After rebuilding current Hyper and curl master with Hyper HTTP/2 disabled, the three transfers complete in about one second instead of over  |
| `N_terminal` | ✓ | 0 | 0 | Curl master uses HTTP/1.1 for the Hyper backend, and the reporter's three-URL test now completes in about one second without the previous 30 |

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
