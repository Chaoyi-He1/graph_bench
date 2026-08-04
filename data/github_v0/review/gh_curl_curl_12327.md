# Review: gh_curl_curl_12327

**libcurl.dll memory leak**

- source: https://github.com/curl/curl/issues/12327
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_curl_curl_12327.json` · raw thread: `data/github_v0/raw/gh_curl_curl_12327.json`

```mermaid
flowchart LR
    N0["<b>N0 repeated-download memory growth reported</b><br/><small>info: 4</small>"]
    N1["<b>N1 simplified reproduction measured</b><br/><small>info: 7</small>"]
    N2["<b>N2 growth pattern and version comparison collected</b><br/><small>info: 10</small>"]
    N3["<b>N3 static OpenSSL build isolates the condition</b><br/><small>info: 13</small>"]
    N_terminal["<b>terminal memory growth resolved</b><br/><small>info: 15</small>"]
    N0 -.->|"❓ simplified_single_transfer_thread_reproducer, memory_1600kb_to_6700kb_after_1000_downloads"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ memory_1500kb_6600kb_12000kb_at_0_1000_2000_laps, curl_versions_745_769_stable_782_84_grow"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ self_built_dll_with_static_openssl_grows, same_dll_build_without_ssl_stays_stable"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"⚡ Clean up OpenSSL's per-thread state whenever each short-lived download thread exits when OpenSSL is statically linked into the libcurl DLL, then verify that repeated transfers no longer increase memory."| N_terminal
    linkStyle 3 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I have noticed what looks like a long-standing, version-independent memory leak in libcurl.dll on Windows. My Visual Studio C test project downloads a file repeatedly in an endless loop, using 64 threads to make the problem appear faster. After 15–30 minutes, Task Manager shows memory consumption increasing many times over. I am using curl 8.4.0. If I am failing to release curl resources in time, please tell me what I should change.

## Satisfaction conditions

1. Must identify the root cause as OpenSSL per-thread resources not being released when OpenSSL is statically linked into the Windows libcurl DLL and short-lived application threads repeatedly perform HTTPS transfers.
2. The diagnosis must be grounded in the controlled evidence: memory grows with repeated transfers, the static-OpenSSL build grows, and the otherwise similar no-SSL build remains stable.
3. Must recommend calling OPENSSL_thread_stop for every affected worker thread before it terminates, either through an application-accessible wrapper or suitable DLL thread-detach handling.
4. Must not treat curl_easy_cleanup, curl_global_cleanup, FreeLibrary, or a smaller CURLOPT_BUFFERSIZE as sufficient substitutes for the required per-thread OpenSSL cleanup.
5. Must ask the reporter to rerun the repeated-download test with the rebuilt DLL and only treat the issue as resolved after memory remains stable.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: simplified_single_transfer_thread_reproducer, memory_1600kb_to_6700kb_after_1000_downloads | I made a smaller test. It creates one Windows thread, calls curl_easy_init, downloads a 1.3 MB file with curl_ / The initial memory is about 1.600 MB. After 1,000 downloads it is about 6.700 MB, so the growth is about 5 MB. |
| `e2_N1__N2` | clarification_only | asks: memory_1500kb_6600kb_12000kb_at_0_1000_2000_laps, curl_versions_745_769_stable_782_84_grow | Start memory is 1,500 KB, after 1,000 laps it is 6,600 KB, and after 2,000 laps it is 12,000 KB. / With 8.4 I see the memory growth. With 7.45 and 7.69 I do not see it. With 7.82 I see it. |
| `e3_N2__N3` | clarification_only | asks: self_built_dll_with_static_openssl_grows, same_dll_build_without_ssl_stays_stable | I built the curl DLL myself. This build shows the memory growth: nmake.exe /f Makefile.vc mode=dll VC=14 ENABL / The similar command without WITH_SSL does not show the memory growth: nmake.exe /f Makefile.vc mode=dll VC=14  |
| `e4_N3__N_terminal` | solution_only | req_info: windows_libcurl_dll_memory_grows_during_repeated_downloads, memory_1500kb_6600kb_12000kb_at_0_1000_2000_laps, curl_versions_745_769_stable_782_84_grow, self_built_dll_with_static_openssl_grows, same_dll_build_without_ssl_stays_stable<br>elements: identifies_static_openssl_per_thread_state_as_the_source, calls_OPENSSL_thread_stop_for_each_exiting_worker_thread, distinguishes_thread_cleanup_from_easy_handle_or_global_cleanup, asks_user_to_verify_with_repeated_downloads_after_rebuilding | Clean up OpenSSL's per-thread state whenever each short-lived download thread exits when OpenSSL is statically linked into the libcurl DLL, then verify that repeated transfers no longer increase memory. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | While my Windows program repeatedly downloads a file through libcurl.dll, Task Manager shows its memory consumption increasing many times ov |
| `N1` |  | 1 | 0 | In my simplified test, memory rises from about 1.6 MB to 6.7 MB over 1,000 downloads. If I comment out curl_easy_perform, the gradual memory |
| `N2` |  | 1 | 0 | Memory is about 1.5 MB initially, 6.6 MB after 1,000 downloads, and 12 MB after 2,000 downloads. The same test stays stable with curl 7.45 a |
| `N3` |  | 1 | 0 | My DLL built with static zlib, nghttp2, and OpenSSL shows the memory growth. The otherwise similar DLL built without SSL support does not sh |
| `N_terminal` | ✓ | 1 | 0 | After rebuilding the DLL with a wrapper that calls OPENSSL_thread_stop for the worker threads, I no longer see the memory growth. |

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
