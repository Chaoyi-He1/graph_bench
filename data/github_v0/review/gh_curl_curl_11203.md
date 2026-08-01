# Review: gh_curl_curl_11203

**Hyper slowness issue**

- source: https://github.com/curl/curl/issues/11203
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_curl_curl_11203.json` · raw thread: `data/github_v0/raw/gh_curl_curl_11203.json`

```mermaid
flowchart LR
    N0["<b>N0 Hyper transfers reported extremely slow</b><br/><small>info: 5</small>"]
    N1["<b>N1 current dependencies and cross-platform reproduction confirmed</b><br/><small>info: 7</small>"]
    N2_x["<b>N2_x initial Hyper polling patch aftermath</b><br/><small>info: 9</small>"]
    N2["<b>N2 protocol trace and packet evidence collected</b><br/><small>info: 12</small>"]
    N3["<b>N3 HTTP/1.1 fallback verified on current master</b><br/><small>info: 13</small>"]
    N_terminal["<b>terminal Hyper minute-long stalls resolved</b><br/><small>info: 16</small>"]
    N0 -.->|"❓ linux_hyper_build_reproduces_slowness"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Apply the initial Hyper polling and wake-handling changes from PR #11344 to make completed Hyper tasks available without waiting for a later transfer-loop poll."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ trace_shows_two_approximately_30_second_idle_periods, packet_capture_shows_repeated_h2_preface_per_request, forcing_http11_completes_in_about_300ms"| N2
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ master_with_hyper_http2_disabled_finishes_near_one_second"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"⚡ Disable HTTP/2 in curl's Hyper integration and use HTTP/1.1 as the safe temporary path, because curl creates a Hyper client connection per request and sends a new HTTP/2 connection preface on an already reused connection; restoring Hyper HTTP/2 requires connection-scoped lifecycle integration."| N_terminal
    linkStyle 4 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2_x normal
    class N2 normal
    class N3 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I'm transferring three flight-information URLs with curl on Windows 10. With a build using `-DUSE_HYPER`, the command takes at least a minute, with long pauses between URLs, whether the URLs come from a config file or the command line and whether or not I use `--parallel`. The curl bundled with Windows completes the same three requests in under a second. My build is curl 8.2.0-DEV with Hyper 1.0.0-rc.3.

## Satisfaction conditions

1. Must identify the root cause: curl's Hyper integration created a new `hyper_clientconn` for each request on a reused HTTP/2 connection, sending repeated HTTP/2 connection prefaces and provoking server GOAWAY/error handling that caused long delays or dropped requests.
2. The diagnosis must be grounded in the collected trace, packet capture, and protocol comparison: two roughly 30-second idle periods, repeated HTTP/2 prefaces, and fast completion when forcing HTTP/1.1.
3. The practical fix must disable HTTP/2 for the Hyper backend and fall back to HTTP/1.1 until the Hyper client/executor lifecycle can be redesigned for connection-scoped multiplexing.
4. Must not present PR #11344's polling changes as the resolution; they were tested in-case and the reporter still observed a roughly 61-second runtime and missing output.
5. Must require user verification on a rebuilt fixed version, with all three requests completing without the long pauses, before declaring the issue resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: linux_hyper_build_reproduces_slowness | I can reproduce it on Linux too. Normal curl takes one or two seconds, while curl with Hyper takes about a min |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: hyper_build_three_urls_take_at_least_one_minute<br>elements: mentions_initial_hyper_polling_patch | Apply the initial Hyper polling and wake-handling changes from PR #11344 to make completed Hyper tasks available without waiting for a later transfer-loop poll. |
| `e3_N2_x__N2` | clarification_only | asks: trace_shows_two_approximately_30_second_idle_periods, packet_capture_shows_repeated_h2_preface_per_request, forcing_http11_completes_in_about_300ms | The first response arrives quickly. Then `Curl_hyper_stream` is called about once per second with `select_res` / In my decrypted capture, normal curl sends one HTTP/2 connection preface, settings/window update, and then req / Yes. The default Hyper run takes more than 60 seconds for this endpoint, while `curl --http1.1` completes the  |
| `e4_N2__N3` | clarification_only | asks: master_with_hyper_http2_disabled_finishes_near_one_second | After rebuilding the latest Hyper and curl master, it is much faster and no longer takes over a minute. One ru |
| `e5_N3__N_terminal` | solution_only | req_info: hyper_build_three_urls_take_at_least_one_minute, parallel_mode_does_not_remove_delays, trace_shows_two_approximately_30_second_idle_periods, packet_capture_shows_repeated_h2_preface_per_request, forcing_http11_completes_in_about_300ms, master_with_hyper_http2_disabled_finishes_near_one_second<br>elements: identifies_per_request_hyper_clientconn_as_source_of_repeated_h2_prefaces, disables_http2_for_hyper_as_temporary_fix, uses_http11_fallback, notes_connection_lifecycle_rearchitecture_needed_before_restoring_h2 | Disable HTTP/2 in curl's Hyper integration and use HTTP/1.1 as the safe temporary path, because curl creates a Hyper client connection per request and sends a new HTTP/2 connection preface on an already reused connection; restoring Hyper HTTP/2 requires connection-scoped lifecycle integration. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | My curl build with `-DUSE_HYPER` takes at least a minute to fetch three small HTTPS URLs, with long pauses between them. The same requests f |
| `N1` |  | 1 | 0 | The long pauses remain after updating Rust, pulling Hyper master, and rebuilding everything. I can also reproduce the roughly one-minute run |
| `N2_x` |  | 2 | 0 | After rebuilding with the proposed changes, the three-URL command still takes about 61 seconds instead of about 1.5 seconds with the Windows |
| `N2` |  | 0 | 0 | The first response arrives immediately, followed by pauses of about 30 seconds before the later responses. Forcing HTTP/1.1 makes the same t |
| `N3` |  | 0 | 0 | With the latest Hyper and curl master, the three requests complete in about one second without the two 30-second pauses. My latest measureme |
| `N_terminal` | ✓ | 0 | 0 | The three URLs now complete in about one second with the Hyper-enabled build, all three responses are returned, and the 30-second pauses are |

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
