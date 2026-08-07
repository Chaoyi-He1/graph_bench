# Review: gh_helix-editor_helix_6778

**Opening a network file on Windows**

- source: https://github.com/helix-editor/helix/issues/6778
- kind: LLM draft (needs review)
- reviewed: `True`
- graph: `data/github_v0/graphs/gh_helix-editor_helix_6778.json` · raw thread: `data/github_v0/raw/gh_helix-editor_helix_6778.json`

```mermaid
flowchart LR
    N0["<b>N0 UNC file cannot be opened normally</b><br/><small>info: 6</small>"]
    N1["<b>N1 launch and clipboard environment established</b><br/><small>info: 9</small>"]
    N2_x["<b>N2_x console paste enabled but core issue remains</b><br/><small>info: 10</small>"]
    N3["<b>N3 delay isolated to UNC input in open prompt</b><br/><small>info: 14</small>"]
    N4_x["<b>N4_x bracketed-paste explanation falsified</b><br/><small>info: 18</small>"]
    N_terminal["<b>terminal efficient clipboard-register workaround confirmed</b><br/><small>info: 20</small>"]
    N0 -.->|"❓ standalone_hx_exe_opens_windows_console_window"| N1
    linkStyle 0 stroke:#3b82f6,stroke-width:2px
    N1 ==>|"💥 blind: Enable the Windows console Ctrl-Shift-C/V option so the console can paste clipboard text into Helix."| N2_x
    linkStyle 1 stroke:#ef4444,stroke-width:2px
    N2_x -.->|"❓ leading_double_backslash_triggers_delay, same_backslashes_without_unc_prefix_paste_quickly, unc_path_pastes_quickly_into_editor_but_not_open_prompt, vcs_log_reports_no_git_repository_for_unc_directory"| N3
    linkStyle 2 stroke:#3b82f6,stroke-width:2px
    N3 ==>|"💥 blind: Attribute the behavior entirely to the lack of bracketed paste in the default Windows console and advise starting Helix in a terminal emulator that supports bracketed paste."| N4_x
    linkStyle 3 stroke:#ef4444,stroke-width:2px
    N4_x ==>|"⚡ Open the copied network path through Helix's system-clipboard register expansion in the `:open` prompt instead of pasting or dragging the UNC path character by character."| N_terminal
    linkStyle 4 stroke:#f97316,stroke-width:2px
    class N0 start
    class N1 normal
    class N2_x normal
    class N3 normal
    class N4_x normal
    class N_terminal terminal
    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000
    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000
    classDef normal fill:#fef3c7,stroke:#a16207,color:#000
```

## Opening (body)

> I'm a new Helix user, accustomed to nvim on Unix, using hx 23.03 on Windows 10 by double-clicking hx.exe. I can't open a file from my synced network desktop. Dragging a UNC file such as "\\1.2.3.4\UsersFiles\me\Desktop\file.txt" onto Helix leaves malformed text on the command line and does not open it. Dragging a local file also does not open it unless I first enter `:o `. A local path then opens, but entering or dragging the network path after `:o ` freezes and advances only one character about every ten seconds. I also cannot paste the copied path: Ctrl-V inserts a literal `v`, Ctrl-Shift-V inserts a literal `V`, and mouse clicks do nothing. Is there any way for me to open this file?

## Satisfaction conditions

1. Must recognize that the extreme delay is specific to entering a UNC path in Helix's valid `:o` prompt, especially as it reaches a network directory with many subdirectories; it is not a general inability to paste backslashes.
2. Diagnosis must be grounded in the reporter's comparisons: the same UNC text pastes immediately into the editor, a non-UNC-prefixed backslash path is fast, invalid `:e` receives the path immediately, and the issue reproduces in bracketed-paste-capable Windows Terminal.
3. Must not treat enabling Ctrl-Shift-V or switching to a bracketed-paste-capable terminal as the complete fix; both directions were tested and the UNC `:o` slowdown remained.
4. The practical resolution must use Helix's system clipboard register in the open prompt, `:o <C-r>*`, rather than feeding the UNC path character by character.
5. Must ask the user to verify that the copied network file opens efficiently and only treat the issue as resolved after that confirmation.

## Edges

| edge | type | gates / info | payload |
|---|---|---|---|
| `e1_N0__N1` | clarification_only | asks: standalone_hx_exe_opens_windows_console_window | I'm double-clicking hx.exe from the official Windows release ZIP. I don't launch a separate terminal emulator; |
| `e2_N1__N2_x` | solution_only **BLIND** | req_info: normal_console_paste_shortcuts_do_not_paste, standalone_hx_exe_opens_windows_console_window<br>elements: enables_windows_console_clipboard_shortcut | Enable the Windows console Ctrl-Shift-C/V option so the console can paste clipboard text into Helix. |
| `e3_N2_x__N3` | clarification_only | asks: leading_double_backslash_triggers_delay, same_backslashes_without_unc_prefix_paste_quickly, unc_path_pastes_quickly_into_editor_but_not_open_prompt, vcs_log_reports_no_git_repository_for_unc_directory | The quotes make no difference. Both quoted and unquoted paths take about 13 seconds per character when they st / Yes. `1.2.3.4\UsersFiles\me\Desktop\foo.txt` pastes quickly, while `\\1.2.3.4\UsersFiles\me\Desktop\foo.txt` i / The complete quoted UNC path pastes into the editor pane without trouble. Using the same Ctrl-Shift-V paste in / The log repeats `failed to open git repo`, `NoGitRepository`, `failed to open diff base`, and `failed to obtai |
| `e4_N3__N4_x` | solution_only **BLIND** | req_info: windows10_hx_23_03_launched_by_double_click, standalone_hx_exe_opens_windows_console_window<br>elements: attributes_issue_entirely_to_missing_bracketed_paste, suggests_switching_terminal_emulator | Attribute the behavior entirely to the lack of bracketed paste in the default Windows console and advise starting Helix in a terminal emulator that supports bracketed paste. |
| `e5_N4_x__N_terminal` | solution_only | req_info: open_command_unc_path_arrives_extremely_slowly, open_command_works_quickly_for_local_path, bracketed_paste_capable_windows_terminal_still_reproduces, invalid_command_receives_same_path_immediately, open_prompt_stalls_at_directory_with_many_subdirectories, leading_double_backslash_triggers_delay, same_backslashes_without_unc_prefix_paste_quickly, unc_path_pastes_quickly_into_editor_but_not_open_prompt<br>elements: uses_helix_system_clipboard_register_in_open_prompt, gives_open_command_control_r_star_sequence, asks_user_to_verify_the_network_file_opens_efficiently, does_not_declare_resolution_before_user_confirmation | Open the copied network path through Helix's system-clipboard register expansion in the `:open` prompt instead of pasting or dragging the UNC path character by character. |

## Nodes

| node | terminal | volunteered | images | symptoms |
|---|---|---|---|---|
| `N0` |  | 0 | 0 | Dragging a UNC file onto Helix does not open it and leaves malformed path text on the command line. After `:o `, a local path opens normally |
| `N1` |  | 2 | 0 | The standalone hx.exe window still does not accept the system clipboard through the shortcuts I tried, and the UNC path remains too slow to  |
| `N2_x` |  | 1 | 0 | After enabling Ctrl-Shift-V in the Windows console settings, I can paste into the editor, but pasting the UNC path into `:o` still takes abo |
| `N3` |  | 0 | 0 | The delay occurs only when the path has the leading UNC `\\`; removing that prefix makes the otherwise similar string paste quickly. The com |
| `N4_x` |  | 4 | 0 | The same UNC-path slowdown still occurs in Windows Terminal 1.18 and in Helix 23.10. Dragging the path after an intentionally invalid `:e `  |
| `N_terminal` | ✓ | 1 | 0 | After copying the file path and entering `:o <C-r>*`, the UNC path appears in its extended `\\?\UNC\...` form and the network file opens muc |

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
