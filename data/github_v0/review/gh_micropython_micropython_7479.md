# Review: gh_micropython_micropython_7479

**USB transmission gradually slowing down in a sawtooth pattern on Raspberry Pi Pico**

- source: https://github.com/micropython/micropython/issues/7479
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_micropython_micropython_7479.json` · raw thread: `data/github_v0/raw/gh_micropython_micropython_7479.json`

```mermaid
flowchart LR
    N0["<b>N0 repeating USB slowdown reported</b><br/><small>info: 7</small>"]
    N1["<b>N1 thermal throttling checked</b><br/><small>info: 9</small>"]
    N1_x["<b>N1_x preallocated-buffer aftermath</b><br/><small>info: 11</small>"]
    N2["<b>N2 version and host comparisons completed</b><br/><small>info: 15</small>"]
    N3["<b>N3 MicroPython-specific comparison established</b><br/><small>info: 18</small>"]
    N_terminal["<b>terminal fix landed without reporter retest</b><br/><small>info: 23</small>"]
    N0 -.->|"❓ pico_surface_temperature_below_35c, sawtooth_plot_supplied"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Avoid allocating a new 10 kB object for every write by constructing the bytes buffer once and reusing it."| N1_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N1_x -.->|"❓ clock_comparison_preserves_repeating_pattern, fresh_v1_16_48_build_has_same_sawtooth, different_pc_has_same_general_slowdown, one_kb_receive_chunks_reveal_finer_same_trend"| N2
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N2 -.->|"❓ forced_gc_each_write_does_not_remove_cycle, small_write_sizes_change_sawtooth_structure, compiled_c_usb_cdc_test_sustains_770kbs"| N3
    linkStyle 3 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"⚡ Use a current MicroPython RP2 build containing the refreshed pico-sdk and TinyUSB integration that removes the sawtooth, continue using `sys.stdout.buffer.write()` for raw bytes, and ask the reporter to verify the result on that build."| N_terminal
    linkStyle 4 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N1_x normal
    class N2 normal
    class N3 normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I am using a Raspberry Pi Pico as a scientific data-acquisition platform and sending data to a computer through MicroPython stdout over USB CDC. With the Pico overclocked to 250 MHz, `usys.stdout.buffer.write()` initially sends 10 kB in about 0.015 seconds, but the time gradually rises to roughly 0.05 seconds and then abruptly returns to the initial value. This repeating sawtooth limits sustained throughput. The same behavior occurs without overclocking at roughly half the speed. The Pico does not reset, a one-second pause does not reset the slowdown, `micropython.mem_info()` does not show significant changes, and the Pico-side loop timing follows the computer's receive timing, so packets do not appear to be dropped. I would like consistently high USB throughput.

## Satisfaction conditions

1. Must identify the accepted resolution at the level established by the thread: refreshing MicroPython's RP2 pico-sdk and/or TinyUSB integration removes the USB CDC sawtooth; the exact lower-level defect was not bisected.
2. Must ground the diagnosis in the collected evidence: the slowdown survives buffer reuse, explicit garbage collection, a fresh pre-fix MicroPython build, another computer, and different read sizes, while an equivalent compiled C USB CDC test remains steady.
3. Must not present preallocating the output buffer or forcing garbage collection as the complete fix; preallocation produced only a small improvement and neither action removed the cycle.
4. For raw binary data, should retain `sys.stdout.buffer.write()` rather than treating formatted `print()` output as the preferred high-throughput path.
5. Must ask the reporter to verify the original flood test on a build containing the dependency update before declaring the reporter's own system resolved; maintainer and other-operator confirmation must not be misrepresented as the reporter's retest.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: pico_surface_temperature_below_35c, sawtooth_plot_supplied | The Pico's surface temperature stays well below 35 °C throughout the test, including while overclocked, so I d / I plotted it. The receive time rises repeatedly and then drops sharply back to the fast value. |
| `e2_N1__N1_x` | solution_only **BLIND** | req_info: rp2_usb_cdc_sawtooth_slowdown<br>elements: preallocates_and_reuses_the_output_buffer | Avoid allocating a new 10 kB object for every write by constructing the bytes buffer once and reusing it. |
| `e3_N1_x__N2` | clarification_only | asks: clock_comparison_preserves_repeating_pattern, fresh_v1_16_48_build_has_same_sawtooth, different_pc_has_same_general_slowdown, one_kb_receive_chunks_reveal_finer_same_trend | At 125 MHz the delays are roughly twice those at 250 MHz. Related repeating features remain, although the curv / I tested MicroPython v1.16-48-g0b3332c8e and saw no change whatsoever. The sawtooth is still present. / I measured it on a different computer. The curve differs slightly in shape, but the same general sawtooth slow / I changed the computer script to receive 1 kB chunks and normalized the result to 10 kB. It reveals finer dela |
| `e4_N2__N3` | clarification_only | asks: forced_gc_each_write_does_not_remove_cycle, small_write_sizes_change_sawtooth_structure, compiled_c_usb_cdc_test_sustains_770kbs | I reused a prepared buffer and called `gc.collect()` after every write. It only slows transmission by a consta / With writes of 13 bytes or less, the sawtooth repeats more frequently relative to total bytes transmitted. Fro / I ran a simple compiled C USB CDC program on the Pico. It sustained about 770 kB/s and the graph stayed flat i |
| `e5_N3__N_terminal` | solution_only | req_info: rp2_usb_cdc_sawtooth_slowdown, stdout_buffer_initially_near_usb_full_speed, fresh_v1_16_48_build_has_same_sawtooth, forced_gc_each_write_does_not_remove_cycle, compiled_c_usb_cdc_test_sustains_770kbs<br>elements: attributes_resolution_to_updated_pico_sdk_and_or_tinyusb_integration, does_not_claim_an_exact_unidentified_dependency_bug, recommends_sys_stdout_buffer_write_for_raw_binary_data, asks_user_to_verify_on_a_build_containing_the_dependency_update | Use a current MicroPython RP2 build containing the refreshed pico-sdk and TinyUSB integration that removes the sawtooth, continue using `sys.stdout.buffer.write()` for raw bytes, and ask the reporter to verify the result on that build. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | Sending 10 kB through `usys.stdout.buffer.write()` initially takes about 0.015 seconds, gradually slows to roughly 0.05 seconds, and then ab |
| `N1` |  | 0 | 0 | The plotted receive times repeatedly rise and then drop back to the fast value. The Pico surface remains below 35 °C while this happens, inc |
| `N1_x` |  | 2 | 1 | Preparing the byte buffer once improves throughput by only a few percent; the same sawtooth remains and repeats after about 418 chunks, or 4 |
| `N2` |  | 0 | 0 | The repeating slowdown remains on MicroPython v1.16-48-g0b3332c8e and when measured on a different computer. At 125 MHz the delays are rough |
| `N3` |  | 0 | 0 | Calling `gc.collect()` after every write adds a constant delay but does not remove the speed cycle. Very short writes alter the shape or rep |
| `N_terminal` | ✓ | 0 | 0 | A maintainer reports that a build with the updated RP2 USB dependencies sustains about 7 Mbit/s without the sawtooth, and another operator c |

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
