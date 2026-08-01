# Review: gh_moby_moby_49498

**Docker 28 stops containers communicating with Tailscale network**

- source: https://github.com/moby/moby/issues/49498
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_moby_moby_49498.json` · raw thread: `data/github_v0/raw/gh_moby_moby_49498.json`

```mermaid
flowchart LR
    N0["<b>N0 Tailscale communication regression reported</b><br/><small>info: 4</small>"]
    N1["<b>N1 direct-IP failure and firewall evidence collected</b><br/><small>info: 7</small>"]
    N1_x["<b>N1_x DOCKER-USER rule-move aftermath</b><br/><small>info: 8</small>"]
    N2["<b>N2 Tailscale stateful-filtering setting confirmed</b><br/><small>info: 9</small>"]
    N3["<b>N3 configuration interaction reproduced</b><br/><small>info: 10</small>"]
    N4["<b>N4 Docker 28.0.1 verified on affected hosts</b><br/><small>info: 11</small>"]
    N_terminal["<b>terminal resolved</b><br/><small>info: 13</small>"]
    N0 -.->|"❓ direct_tailscale_ip_traffic_also_fails, affected_containers_use_custom_bridge, docker28_iptables_dump_with_docker_and_ts_forward_counters"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Move Tailscale's ts-forward jump into DOCKER-USER so Tailscale processes forwarded packets before Docker's other forwarding rules."| N1_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N1_x -.->|"❓ tailscale_stateful_filtering_was_enabled"| N2
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ docker28_works_when_tailscale_stateful_filtering_disabled"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ docker2801_verified_restores_affected_forwarding_setups"| N4
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"⚡ Update to Docker 28.0.1 or later, which restructures Docker's forwarding rules to avoid the Docker 28.0.0 ordering conflict with Tailscale and other pre-existing firewall rules; use disabling Tailscale stateful filtering only as a security-aware temporary workaround."| N_terminal
    linkStyle 5 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N1_x normal
    class N2 normal
    class N3 normal
    class N4 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I use Tailscale so containers and services can communicate with containers on different hosts. After updating Docker Engine to 28, containers can no longer communicate with Tailscale computers. Docker 27.5.1 used the host's Tailscale-managed resolver in the container, and rolling back to 27.5.1 restores communication. I expected this to continue working after the upgrade.

## Satisfaction conditions

1. Must identify the root cause as a Docker 28.0.0 firewall/FORWARD rule-ordering regression interacting with Tailscale stateful filtering, not a DNS resolver regression; direct Tailscale-IP traffic failed too.
2. The diagnosis must be grounded in the Docker 28 versus 27.5.1 behavior, the iptables rule/counter evidence, confirmation that stateful filtering was enabled, and the successful stateful-filtering toggle probe.
3. Must recommend Docker 28.0.1 or later as the durable fix; disabling Tailscale stateful filtering may be offered only as a temporary workaround with acknowledgement of its security implications.
4. Must not present moving ts-forward into DOCKER-USER as the complete fix, because that exact attempt was tried and did not restore connectivity.
5. Must not recommend indiscriminately flushing firewall chains or permanently deleting Docker's protective DROP rules.
6. Must treat the issue as resolved only after an affected user verifies forwarding on Docker 28.0.1 or later.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: direct_tailscale_ip_traffic_also_fails, affected_containers_use_custom_bridge, docker28_iptables_dump_with_docker_and_ts_forward_counters | Yes. One of my metrics nodes was already using only the Tailscale IP and that stopped working too. I also cann / I use a custom bridge network named traefik. It has IPv4 subnet 172.18.0.0/16 and IPv6 subnet fd6b:7060:8f07:: / After trying failed connections on Docker 28, my dump has DOCKER-USER first in FORWARD, followed by Docker's e |
| `e2_N1__N1_x` | solution_only **BLIND** | req_info: direct_tailscale_ip_traffic_also_fails, docker28_iptables_dump_with_docker_and_ts_forward_counters<br>elements: moves_ts_forward_jump_to_docker_user | Move Tailscale's ts-forward jump into DOCKER-USER so Tailscale processes forwarded packets before Docker's other forwarding rules. |
| `e3_N1_x__N2` | clarification_only | asks: tailscale_stateful_filtering_was_enabled | Yes, stateful filtering was enabled on my node. I did not enable it by hand; this installation had passed thro |
| `e4_N2__N3` | clarification_only | asks: docker28_works_when_tailscale_stateful_filtering_disabled | I disabled it with `tailscale set --stateful-filtering=false`, upgraded to Docker 28, and everything is runnin |
| `e5_N3__N4` | clarification_only | asks: docker2801_verified_restores_affected_forwarding_setups | I applied Docker 28.0.1 to an affected host and its container routing works again. On the other affected hosts |
| `e6_N4__N_terminal` | solution_only | req_info: docker2751_rollback_restores_communication, direct_tailscale_ip_traffic_also_fails, docker28_iptables_dump_with_docker_and_ts_forward_counters, tailscale_stateful_filtering_was_enabled, docker28_works_when_tailscale_stateful_filtering_disabled, docker2801_verified_restores_affected_forwarding_setups<br>elements: identifies_docker28_firewall_rule_ordering_interaction, connects_failure_to_tailscale_stateful_filtering, recommends_update_to_docker_2801_or_later, treats_disabling_stateful_filtering_as_security_sensitive_workaround, does_not_recommend_deleting_docker_drop_rules_as_permanent_fix | Update to Docker 28.0.1 or later, which restructures Docker's forwarding rules to avoid the Docker 28.0.0 ordering conflict with Tailscale and other pre-existing firewall rules; use disabling Tailscale stateful filtering only as a security-aware temporary workaround. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 3 | 0 | After upgrading to Docker Engine 28, my containers can no longer communicate with computers over Tailscale. After rolling back to Docker 27. |
| `N1` |  | 0 | 0 | With Docker 28, containers cannot reach a Tailscale device even by its IP address. The same custom-bridge containers can reach Tailscale dev |
| `N1_x` |  | 1 | 0 | Tailscale communication from the container still fails after I insert a jump to ts-forward in DOCKER-USER and remove the existing FORWARD ju |
| `N2` |  | 0 | 0 | Container traffic to Tailscale devices still fails with Docker 28 while Tailscale stateful filtering is enabled. |
| `N3` |  | 0 | 0 | After setting Tailscale stateful filtering to false and upgrading to Docker 28, my containers can communicate over Tailscale normally. The d |
| `N4` |  | 0 | 0 | After updating an affected host to Docker 28.0.1, container forwarding and internal routing work again without manually rearranging the fire |
| `N_terminal` | ✓ | 0 | 0 | Containers can communicate over the affected forwarded network paths after updating to Docker 28.0.1. |

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
