# Review: gh_qdrant_qdrant_4195

**terminate called without an active exception terminate called recursively terminate called recursively**

- source: https://github.com/qdrant/qdrant/issues/4195
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_qdrant_qdrant_4195.json` · raw thread: `data/github_v0/raw/gh_qdrant_qdrant_4195.json`

```mermaid
flowchart LR
    N0["<b>N0 recursive termination and refused ports reported</b><br/><small>info: 6</small>"]
    N1["<b>N1 startup memory exhaustion checked</b><br/><small>info: 7</small>"]
    N2["<b>N2 affected deployment characterized</b><br/><small>info: 12</small>"]
    N3_x["<b>N3_x upgrade aftermath</b><br/><small>info: 16</small>"]
    N4_x["<b>N4_x collection consolidation aftermath</b><br/><small>info: 18</small>"]
    N5["<b>N5 high-volume reproduction documented</b><br/><small>info: 24</small>"]
    N_terminal["<b>terminal stable after write throttling</b><br/><small>info: 26</small>"]
    N0 -.->|"❓ memory_not_exhausted_during_startup_after_expansion"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ original_version_qdrant_1_6_0, three_machine_sharded_cluster, approximately_429_gb_per_machine, production_compose_and_storage_config_shared, cannot_reproduce_on_small_new_cluster"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"💥 blind: Upgrade and rebuild the affected cluster on the current Qdrant version in case the old 1.6.0 build is responsible for the restart failure."| N3_x
    linkStyle 2 stroke:#ef4444,stroke-width:2px
    N3_x ==>|"💥 blind: Replace the 33-collection layout with one multi-tenant collection to avoid the collection-per-partition usage pattern suspected of causing the failure."| N4_x
    linkStyle 3 stroke:#ef4444,stroke-width:2px
    N4_x -.->|"❓ reproduction_used_parallel_batches_of_one_thousand, observed_ingest_rate_five_to_ten_thousand_points_per_second, backup_import_rate_about_twenty_million_vectors_per_hour, shard_degradation_preceded_restart_failure, collection_used_three_shards_three_replicas_consistency_two, vectors_are_512_dimensions_with_three_payload_fields"| N5
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N5 ==>|"⚡ Throttle sustained ingestion so the deployment does not return to the shard-degraded state, using bounded concurrency, retries, or a queue, and verify that shards, ports, and restarts remain healthy under the controlled workload."| N_terminal
    linkStyle 5 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
    class N3_x normal
    class N4_x normal
    class N5 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> Our Qdrant service had been running normally, but now every restart logs "terminate called without an active exception" and "terminate called recursively." Docker reports the container as running, but ports 6333, 6334, and 6335 refuse connections, so reads, writes, and the dashboard are unavailable. We have 33 collections. Memory usage was high, but doubling the available memory did not restore the service. I need to understand the cause and get the service back to normal.

## Satisfaction conditions

1. Must identify sustained high-volume ingestion as the empirically demonstrated trigger in this deployment, grounded in the parallel-batch reproduction, shard dead/partial states, and the restart failure that followed; must not present the reporter's proposed internal sharding-collapse mechanism as proven.
2. Must recommend limiting or applying backpressure to the write rate, with bounded concurrency and optionally retries or a queue, as the operational fix that restored stability.
3. Must not treat increasing memory alone as the fix: memory was doubled and was not exhausted during startup, yet the failure remained.
4. Must not treat upgrading to Qdrant 1.9.1 or merging 33 collections into one as sufficient fixes: the issue recurred on 1.9.1 and with one collection under large writes.
5. Must ask the reporter to verify sustained shard health, reachable service ports, and a controlled restart under the limited write workload before declaring the issue resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: memory_not_exhausted_during_startup_after_expansion | I checked during startup. After expanding the memory, it was not exhausted, but the result was still the same. |
| `e2_N1__N2` | clarification_only | asks: original_version_qdrant_1_6_0, three_machine_sharded_cluster, approximately_429_gb_per_machine, production_compose_and_storage_config_shared, cannot_reproduce_on_small_new_cluster | The affected compose file uses qdrant/qdrant:v1.6.0. / I am using three machines for sharding. / The data volume on a single machine is approximately 429 G. / I cannot reproduce it on the smallest new cluster, but I can provide the affected data volume, version, compos / There is no way for me to reproduce it on the smallest new cluster. |
| `e3_N2__N3_x` | solution_only **BLIND** | req_info: original_version_qdrant_1_6_0, three_machine_sharded_cluster<br>elements: mentions_upgrading_and_rebuilding_the_cluster | Upgrade and rebuild the affected cluster on the current Qdrant version in case the old 1.6.0 build is responsible for the restart failure. |
| `e4_N3_x__N4_x` | solution_only **BLIND** | req_info: deployment_has_33_collections, three_machine_sharded_cluster<br>elements: mentions_consolidating_to_one_multitenant_collection | Replace the 33-collection layout with one multi-tenant collection to avoid the collection-per-partition usage pattern suspected of causing the failure. |
| `e5_N4_x__N5` | clarification_only | asks: reproduction_used_parallel_batches_of_one_thousand, observed_ingest_rate_five_to_ten_thousand_points_per_second, backup_import_rate_about_twenty_million_vectors_per_hour, shard_degradation_preceded_restart_failure, collection_used_three_shards_three_replicas_consistency_two, vectors_are_512_dimensions_with_three_payload_fields | I write batches of 1,000 points to the three machines, with about five to ten batches running in parallel. / Approximately 5,000 to 10,000 points are written every second, and after running like that overnight the shard / During this backup import I wrote about 20 million vector records per hour, and it took more than ten hours to / The shard dead and shard partial states appear first. If they are not restored for a long time, restarting the / The collection uses shard_number 3, replication_factor 3, and write_consistency_factor 2. I posted the full co / Each vector is 512 dimensions and has three payload parameters. |
| `e6_N5__N_terminal` | solution_only | req_info: memory_doubled_without_initial_recovery, one_collection_still_degraded_under_large_writes, shard_degradation_preceded_restart_failure, reproduction_used_parallel_batches_of_one_thousand, observed_ingest_rate_five_to_ten_thousand_points_per_second, collection_used_three_shards_three_replicas_consistency_two<br>elements: recommends_limiting_the_sustained_write_rate, grounds_the_recommendation_in_the_reproduced_import_and_shard_sequence, does_not_claim_upgrade_memory_or_collection_merging_alone_is_the_fix, asks_user_to_verify_shard_health_port_access_and_restart_stability | Throttle sustained ingestion so the deployment does not return to the shard-degraded state, using bounded concurrency, retries, or a queue, and verify that shards, ports, and restarts remain healthy under the controlled workload. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 3 | 0 | Every restart logs "terminate called without an active exception" followed by "terminate called recursively." Docker reports the container a |
| `N1` |  | 0 | 0 | After expanding the memory, it is not exhausted during startup, but Qdrant still logs the recursive termination messages and its ports remai |
| `N2` |  | 0 | 0 | The affected three-machine deployment still refuses connections after restart, while I cannot reproduce the behavior on a small new cluster. |
| `N3_x` |  | 4 | 0 | On the rebuilt Qdrant 1.9.1 cluster, shards became dead or partial during the data import. Restarting after the shard degradation again prod |
| `N4_x` |  | 2 | 0 | After merging the 33 collections into one multi-tenant collection, shard problems still occurred when I wrote a large amount of data. |
| `N5` |  | 0 | 0 | With parallel batches of 1,000 points and about 5,000 to 10,000 points written each second overnight, shards became dead or partial; restart |
| `N_terminal` | ✓ | 2 | 0 | After I limited the write rate, the cluster remained available and everything looked fine. The problem had still occurred with one collectio |

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
