# Review: gh_micropython_micropython_7479

**USB transmission gradually slowing down in a sawtooth pattern on Raspberry Pi Pico**

- source: https://github.com/micropython/micropython/issues/7479
- kind: LLM draft (needs review)
- reviewed: `False`
- graph: `data/github_v0/graphs/gh_micropython_micropython_7479.json` · raw thread: `data/github_v0/raw/gh_micropython_micropython_7479.json`

```mermaid
flowchart LR
    N0["<b>N0 repeating USB throughput slowdown reported</b><br/><small>info: 8</small>"]
    N1["<b>N1 thermal throttling evidence collected</b><br/><small>info: 10</small>"]
    N2_x["<b>N2_x preallocated buffer aftermath</b><br/><small>info: 12</small>"]
    N3["<b>N3 firmware and workload probes completed</b><br/><small>info: 17</small>"]
    N4["<b>N4 standalone TinyUSB comparison collected</b><br/><small>info: 19</small>"]
    N5["<b>N5 candidate dependency update verified</b><br/><small>info: 20</small>"]
    N_terminal["<b>terminal sustained USB throughput restored</b><br/><small>info: 21</small>"]
    N0 -.->|"❓ pico_surface_temperature_below_35c"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Avoid allocating a new 10 kB object for every write by constructing the bytes buffer once and reusing it."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ latest_v1_16_development_firmware_same_sawtooth, clock_comparison_retains_pattern_with_changed_timing, one_kbyte_reads_reveal_finer_slowdown_structure, small_write_sizes_change_pattern_but_not_general_slowdown, explicit_gc_collect_does_not_remove_cycle"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 -.->|"❓ uart_test_has_different_small_periodic_oscillation, standalone_c_tinyusb_test_sustains_770_kbytes_per_second"| N4
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N4 -.->|"❓ candidate_dependency_update_sustains_about_7_mbit_per_second"| N5
    linkStyle 4 stroke:#3b82f6,stroke-width:2px
    N5 ==>|"⚡ Update the RP2 MicroPython firmware to a build containing the newer bundled Pico SDK and TinyUSB revisions, which remove the repeating USB CDC throughput slowdown; retain sys.stdout.buffer.write for raw byte data."| N_terminal
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

> I am using a Raspberry Pi Pico with MicroPython as a scientific data-acquisition platform. The Pico repeatedly writes byte data through usys.stdout.buffer.write(), while a Linux computer reads 10 kB chunks from /dev/ttyACM0. At 250 MHz, a 10 kB read initially takes about 0.015 seconds, but it gradually rises to roughly 0.05 seconds before suddenly returning to the fast rate; this sawtooth pattern repeats. At 125 MHz the speeds are roughly halved. The Pico does not reset, inserting a one-second pause does not reset the slowdown, micropython.mem_info() remains stable, and the measured Pico loop period follows the computer's receive time without apparent packet loss. I would like consistently high USB throughput.

## Satisfaction conditions

1. Must identify the accepted root cause at the level established by the thread: the sawtooth came from the older Pico SDK and/or TinyUSB revisions bundled with the RP2 MicroPython port; maintainers did not bisect the dependencies far enough to name a more precise mechanism.
2. The diagnosis must be grounded in the collected evidence: thermal throttling was absent, preallocating the Python buffer and forcing garbage collection did not remove the cycle, standalone C/TinyUSB sustained a flat transfer rate, and the candidate dependency update removed the sawtooth.
3. Must recommend using RP2 MicroPython firmware containing the updated Pico SDK and TinyUSB dependencies while using sys.stdout.buffer.write for raw bytes.
4. Must not present repeated Python allocation, heap garbage collection, or endpoint-buffer tuning alone as the root fix; buffer preallocation only improved speed slightly, explicit collection did not remove the cycle, and endpoint sizing was a separate throughput optimization.
5. Must ask the user to verify sustained throughput with the original reproduction on a build containing the dependency update before declaring the issue resolved.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: pico_surface_temperature_below_35c | The Pico's surface temperature stays well below 35 °C throughout the test, even while overclocked, so I do not |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: usb_receive_time_repeats_sawtooth_slowdown<br>elements: preallocates_and_reuses_the_transmit_buffer | Avoid allocating a new 10 kB object for every write by constructing the bytes buffer once and reusing it. |
| `e3_N2_x__N3` | clarification_only | asks: latest_v1_16_development_firmware_same_sawtooth, clock_comparison_retains_pattern_with_changed_timing, one_kbyte_reads_reveal_finer_slowdown_structure, small_write_sizes_change_pattern_but_not_general_slowdown, explicit_gc_collect_does_not_remove_cycle | I tried the newer MicroPython v1.16 development build and saw no change whatsoever. The sawtooth still repeats / The delays are roughly doubled at 125 MHz, so the bottleneck appears to be on the Pico side. Some curve featur / I changed the computer script to receive 1 kB chunks and normalized the times to 10 kB. It reveals finer struc / With writes of 13 bytes or less, the sawtooth repeats after fewer total bytes. Writes from about 14 to 30 byte / I reused a fixed bytes object and called gc.collect() in every cycle. It only slows transmission by a constant |
| `e4_N3__N4` | clarification_only | asks: uart_test_has_different_small_periodic_oscillation, standalone_c_tinyusb_test_sustains_770_kbytes_per_second | Over UART, a 10000-byte block at 921600 baud oscillates between about 0.10767 and 0.1131 seconds, with a peak  / I built a small Arduino C program based on the Adafruit TinyUSB CDC example and flooded Serial.printf(). It su |
| `e5_N4__N5` | clarification_only | asks: candidate_dependency_update_sustains_about_7_mbit_per_second | I reproduced the sawtooth with the original scripts, then ran the same test with the candidate build. That bui |
| `e6_N5__N_terminal` | solution_only | req_info: usb_receive_time_repeats_sawtooth_slowdown, 125mhz_throughput_roughly_half_of_250mhz, preallocated_bytes_improves_speed_only_slightly, pico_surface_temperature_below_35c, latest_v1_16_development_firmware_same_sawtooth, explicit_gc_collect_does_not_remove_cycle, standalone_c_tinyusb_test_sustains_770_kbytes_per_second, candidate_dependency_update_sustains_about_7_mbit_per_second<br>elements: attributes_the_resolved_regression_to_the_old_bundled_pico_sdk_or_tinyusb_integration, recommends_firmware_containing_the_updated_rp2040_usb_dependencies, does_not_claim_python_buffer_allocation_or_garbage_collection_is_the_root_cause, asks_user_to_verify_on_a_build_containing_the_dependency_update | Update the RP2 MicroPython firmware to a build containing the newer bundled Pico SDK and TinyUSB revisions, which remove the repeating USB CDC throughput slowdown; retain sys.stdout.buffer.write for raw byte data. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | Reading each 10 kB block from /dev/ttyACM0 initially takes about 0.015 seconds, then gradually takes around 0.05 seconds before suddenly bec |
| `N1` |  | 1 | 1 | The USB transfer time repeatedly climbs and drops back down while the Pico surface remains below 35 °C. |
| `N2_x` |  | 2 | 1 | After I create the bytes object once and reuse it, throughput improves by a few percent but still cycles with the same period, approximately |
| `N3` |  | 0 | 0 | The same sawtooth remains on the newer MicroPython development firmware and on a different computer. Explicitly collecting garbage in every  |
| `N4` |  | 0 | 0 | A standalone C program flooding USB through TinyUSB sustains about 770 kB/s without the MicroPython sawtooth. A UART comparison has a differ |
| `N5` |  | 0 | 0 | With the candidate MicroPython build, the original Pico and PC scripts sustain about 7 Mbit/s and the sawtooth no longer appears. |
| `N_terminal` | ✓ | 0 | 0 | On MicroPython firmware containing the updated RP2040 USB dependencies, Pico-to-PC transmission remains fast and the repeating sawtooth slow |

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
