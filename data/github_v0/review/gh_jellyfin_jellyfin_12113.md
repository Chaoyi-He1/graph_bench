# Review: gh_jellyfin_jellyfin_12113

**Chromecast mixes subtitle languages and timestamps after upgrading to Jellyfin 10.9.x**

- source: https://github.com/jellyfin/jellyfin/issues/12113
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_jellyfin_jellyfin_12113.json` · raw thread: `data/github_v0/raw/gh_jellyfin_jellyfin_12113.json`

```mermaid
flowchart LR
    N0["<b>N0 Chromecast subtitle mixing reported</b><br/><small>info: 8</small>"]
    N1["<b>N1 playback method established</b><br/><small>info: 10</small>"]
    N2_x["<b>N2_x dependency-bump aftermath</b><br/><small>info: 11</small>"]
    N2["<b>N2 cached files and concurrent parsing examined</b><br/><small>info: 14</small>"]
    N3["<b>N3 fresh parser-instance test succeeds</b><br/><small>info: 15</small>"]
    N_terminal["<b>terminal fix landed with third-party confirmation</b><br/><small>info: 17</small>"]
    N0 -.->|"❓ affected_chromecast_playback_is_transcoded"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Resolve the parser errors by updating the subtitle parsing dependency to a newer build."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ cached_extracted_srt_files_each_contain_one_correct_language, concurrent_parse_logs_for_different_tracks_interleave"| N2
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ fresh_subtitle_format_instances_per_parse_test_correctly"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"⚡ Stop sharing subtitle-format parser instances across concurrent parse calls: cache format types or metadata, then construct a fresh selected parser instance for every subtitle parse, and ask affected users to verify a build containing the change."| N_terminal
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

> After upgrading my Jellyfin server from 10.8.13-1 to 10.9.x, subtitles become unreadable when I cast from the Android client to a Chromecast. Playback usually starts correctly, but after a few subtitle lines, text from multiple language tracks and unrelated timestamps is overlaid or shown randomly even though I selected only one language. The same movies work correctly in a web browser and the Android web player. I confirmed the problem on 10.9.3 and 10.9.6. It is much easier to reproduce with large external SRT tracks and is strongly correlated with server log messages such as `163 errors encountered while parsing 'srt' subtitle using the SubRip format parser`. Enabling or disabling on-the-fly subtitle extraction does not change it. My server runs Debian Bookworm with jellyfin-ffmpeg6, Intel QSV, no plugins or reverse proxy.

## Satisfaction conditions

1. Must identify the accepted root cause: live libse SubtitleFormat parser instances were cached and reused by concurrent subtitle Parse calls, allowing shared mutable parser state to mix otherwise separate subtitle tracks.
2. Diagnosis must be grounded in the collected evidence: cached SRT files contain one language each, parser executions overlap in the logs, and a test using fresh format instances per Parse displays previously affected media correctly.
3. The fix must create a fresh subtitle-format instance for each parse call; caching format types or metadata is acceptable, but reusing live parser instances is not.
4. Must not present a libse version bump, extraction toggle, Subtitle Extract plugin, or subtitle-cache reset as the resolution; each was shown to be ineffective or only temporarily helpful in this case.
5. Must not blame the HTML secondary-subtitle feature as the final root cause; the accepted diagnosis is concurrent reuse of stateful server-side subtitle parser instances.
6. Must ask an affected user to verify a build containing the parser-instance fix before declaring the user's setup resolved. The thread contains confirmation from a different affected user, but no final retest from the original reporter.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: affected_chromecast_playback_is_transcoded | For the example I checked, the log says `PlayMethod=Transcode`. The MKV example gives `ContainerNotSupported`; |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: subtitle_parser_error_strongly_correlates_with_failure<br>elements: recommends_subtitle_parser_dependency_update | Resolve the parser errors by updating the subtitle parsing dependency to a newer build. |
| `e3_N2_x__N2` | clarification_only | asks: cached_extracted_srt_files_each_contain_one_correct_language, concurrent_parse_logs_for_different_tracks_interleave | I checked several files in the subtitle cache. They look reasonable, and each file I examined contains subtitl / The log starts parsing the English SRT, then starts parsing the French SRT before the first call finishes. The |
| `e4_N2__N3` | clarification_only | asks: fresh_subtitle_format_instances_per_parse_test_correctly | I changed the Parse function to call `GetSubtitleFormats()` inside the method. All the media I tested that had |
| `e5_N3__N_terminal` | solution_only | req_info: chromecast_mixes_multiple_subtitle_languages_and_timestamps, subtitle_parser_error_strongly_correlates_with_failure, on_the_fly_extraction_toggle_has_no_effect, cached_extracted_srt_files_each_contain_one_correct_language, concurrent_parse_logs_for_different_tracks_interleave, fresh_subtitle_format_instances_per_parse_test_correctly<br>elements: identifies_shared_subtitle_format_instances_as_the_concurrency_problem, creates_a_fresh_subtitle_format_instance_for_each_parse, may_cache_format_types_but_not_reuse_live_parser_instances, asks_user_to_verify_on_a_build_containing_the_parser_instance_fix | Stop sharing subtitle-format parser instances across concurrent parse calls: cache format types or metadata, then construct a fresh selected parser instance for every subtitle parse, and ask affected users to verify a build containing the change. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | When I cast from Android to Chromecast, playback starts with the selected subtitle language but soon shows lines from multiple languages and |
| `N1` |  | 1 | 0 | The mixed and overlaid subtitles occur during Chromecast playback while the server is transcoding the video. |
| `N2_x` |  | 1 | 0 | After upgrading to the server release containing the libse version bump, the same media still produces the same mixed-language subtitles and |
| `N2` |  | 1 | 0 | The subtitle files in the cache appear to contain one language each, but playback still combines multiple tracks. The server logs overlappin |
| `N3` |  | 0 | 0 | In a test build that obtains fresh subtitle-format objects inside each parse call, media that previously mixed subtitle tracks displays the  |
| `N_terminal` | ✓ | 2 | 0 | Another affected user reports that subtitles display correctly after updating to a build containing the parser-instance fix; I have not rete |

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
