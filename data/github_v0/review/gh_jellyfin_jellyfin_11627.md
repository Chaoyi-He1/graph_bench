# Review: gh_jellyfin_jellyfin_11627

**Jellyfin no longer binds to all local addresses after updating from 10.8.13 to 10.9.1**

- source: https://github.com/jellyfin/jellyfin/issues/11627
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_jellyfin_jellyfin_11627.json` · raw thread: `data/github_v0/raw/gh_jellyfin_jellyfin_11627.json`

```mermaid
flowchart LR
    N0["<b>N0 local interface omitted at startup</b><br/><small>info: 8</small>"]
    N1["<b>N1 interface inventory collected</b><br/><small>info: 9</small>"]
    N2["<b>N2 startup context and dummy interface checked</b><br/><small>info: 11</small>"]
    N2_x["<b>N2_x virtual-interface setting aftermath</b><br/><small>info: 12</small>"]
    N3["<b>N3 boot timing established</b><br/><small>info: 13</small>"]
    N4["<b>N4 late discovery does not update listener</b><br/><small>info: 16</small>"]
    N5["<b>N5 startup-delay workaround active</b><br/><small>info: 17</small>"]
    N_terminal["<b>terminal diagnosis accepted but permanent fix not reporter-verified</b><br/><small>info: 19</small>"]
    N0 -.->|"❓ ip_addr_lists_physical_lan_dummy_vpn_and_docker_interfaces"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 -.->|"❓ fake0_created_by_cockpit_and_removal_did_not_help, startup_plot_shared"| N2
    linkStyle 1 stroke:#3b82f6,stroke-width:2px
    N2 ==>|"💥 blind: Include virtual interfaces in Jellyfin's interface selection by setting IgnoreVirtualInterfaces to false."| N2_x
    linkStyle 2 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ boot_log_shows_jellyfin_started_before_lan_ipv4_assignment"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ debug_log_refreshes_and_discovers_lan_address_after_startup, later_interface_discovery_does_not_make_web_ui_reachable, service_restart_after_interfaces_up_restores_access"| N4
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N4 ==>|"⚡ Work around the boot race by ordering Jellyfin after a service that only starts once the required network connectivity is available."| N5
    linkStyle 5 stroke:#f97316,stroke-width:2px
    N5 ==>|"⚡ Fix the regression by using wildcard listeners when bind-all is configured, so the web server can accept connections on addresses that appear after process startup instead of relying on a startup-time enumeration of interfaces."| N_terminal
    linkStyle 6 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2 normal
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

> After updating Jellyfin from 10.8.13 to 10.9.1 on Ubuntu Jammy bare metal, it no longer binds to my local 192.168.1.109 address. It still binds to localhost, my VPN address, and unexpectedly 1.2.3.4. Networking is configured to bind to all addresses, and removing networking.xml so it would be recreated did not change this. Explicitly listing every relevant address under Networking > Bind to local network address is a workaround, but this was not required in 10.8.13. The startup log lists the normal private LAN ranges but reports bind addresses of 127.0.0.1, 1.2.3.4, and 10.1.1.2.

## Satisfaction conditions

1. Must identify the final accepted root cause: Jellyfin starts before DHCP assigns the physical LAN IPv4 address, and its web listener is configured from the concrete addresses available at startup; later network refreshes discover the address but do not make Kestrel relisten.
2. The diagnosis must be grounded in the collected boot and debug evidence: 192.168.1.109 is absent when Jellyfin starts, appears in a later interface refresh, remains unreachable, and works after restarting Jellyfin once the interfaces are ready.
3. The durable fix must preserve bind-all behavior by using wildcard listeners rather than depending only on startup-time interface enumeration.
4. May offer delayed systemd startup or a post-boot service restart as a temporary workaround, but must not present it as the application-level fix.
5. Must not recommend deleting networking.xml or setting IgnoreVirtualInterfaces to false as the resolution; both directions were tried without resolving this reporter's problem.
6. Must ask the reporter to test a build containing the wildcard-listener fix under a normal boot without the startup-delay workaround before declaring the permanent issue resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: ip_addr_lists_physical_lan_dummy_vpn_and_docker_interfaces | My ip addr output shows 192.168.1.109/24 on enp5s0, 1.2.3.4/24 on fake0, 10.170.37.84 on airvpn, 10.1.1.2/24 o |
| `e2_N1__N2` | clarification_only | asks: fake0_created_by_cockpit_and_removal_did_not_help, startup_plot_shared | fake0 is a dummy interface created by Cockpit. I removed the interface and Cockpit, but that did not help. / I rebooted, ran systemd-analyze plot > startup.svg, and posted the resulting startup timeline. |
| `e3_N2__N2_x` | solution_only **BLIND** | req_info: local_address_192_168_1_109_not_listening, ip_addr_lists_physical_lan_dummy_vpn_and_docker_interfaces<br>elements: sets_ignore_virtual_interfaces_to_false | Include virtual interfaces in Jellyfin's interface selection by setting IgnoreVirtualInterfaces to false. |
| `e4_N2_x__N3` | clarification_only | asks: boot_log_shows_jellyfin_started_before_lan_ipv4_assignment | At 08:40:49 Jellyfin starts while enp5s0 is up but only has a tentative link-local IPv6 address. It does not h |
| `e5_N3__N4` | clarification_only | asks: debug_log_refreshes_and_discovers_lan_address_after_startup, later_interface_discovery_does_not_make_web_ui_reachable, service_restart_after_interfaces_up_restores_access | Immediately after startup I get 'Network address change detected', followed by 'Refreshing interfaces'. It dis / No. Even though the refreshed log includes 192.168.1.109, I still cannot access Jellyfin there. / Restarting Jellyfin after the interfaces are up fixes it; the web interface then works on 192.168.1.109. |
| `e6_N4__N5` | solution_only | req_info: ubuntu_jammy_bare_metal_environment, boot_log_shows_jellyfin_started_before_lan_ipv4_assignment<br>elements: delays_jellyfin_until_required_network_is_ready, presents_service_ordering_as_a_workaround | Work around the boot race by ordering Jellyfin after a service that only starts once the required network connectivity is available. |
| `e7_N5__N_terminal` | solution_only | req_info: bind_all_addresses_configured, binding_regression_after_update_10_8_13_to_10_9_1, service_restart_after_interfaces_up_restores_access, boot_log_shows_jellyfin_started_before_lan_ipv4_assignment, debug_log_refreshes_and_discovers_lan_address_after_startup, later_interface_discovery_does_not_make_web_ui_reachable<br>elements: identifies_startup_time_listener_snapshot_as_root_cause, uses_wildcard_binding_for_bind_all_configuration, explains_that_late_interface_discovery_does_not_reload_the_web_listener, asks_user_to_verify_on_a_build_containing_the_wildcard_listener_fix | Fix the regression by using wildcard listeners when bind-all is configured, so the web server can accept connections on addresses that appear after process startup instead of relying on a startup-time enumeration of interfaces. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 1 | 0 | After the update, I cannot reach Jellyfin through 192.168.1.109 even though it is configured to bind to all addresses. The startup log lists |
| `N1` |  | 0 | 0 | Jellyfin remains inaccessible at 192.168.1.109, while the address appears on my physical enp5s0 interface when I inspect the system after st |
| `N2` |  | 0 | 0 | Removing the Cockpit-created fake0 interface does not restore access through 192.168.1.109. |
| `N2_x` |  | 1 | 0 | After setting IgnoreVirtualInterfaces to false, Jellyfin is still inaccessible through 192.168.1.109. |
| `N3` |  | 0 | 0 | At the moment Jellyfin starts during boot, enp5s0 has no 192.168.1.109 IPv4 address yet. The local IPv4 address is assigned later, but Jelly |
| `N4` |  | 1 | 0 | Immediately after startup, the debug log reports a network address change and then discovers 192.168.1.109. Even after that refresh lists 19 |
| `N5` |  | 1 | 0 | After delaying Jellyfin startup until my WireGuard service is up, Jellyfin starts after the main address has been assigned and I can access  |
| `N_terminal` | ✓ | 0 | 0 | My startup-delay workaround keeps the web interface reachable at 192.168.1.109. I have not reported testing the normal boot sequence on a bu |

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
