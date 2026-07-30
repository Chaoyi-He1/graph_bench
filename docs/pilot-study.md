# Pilot Study: Annotating Mozilla Bugzilla Threads into the Causal-Graph Schema

Date: 2026-07-29. Question: do real, public, environment-bound support threads annotate cleanly into the causal-graph schema (`docs/method.md`), and at what cost? Four resolved bugzilla.mozilla.org threads were selected, annotated, and machine-validated.

## Verdict

1. **The schema transfers as-is.** All four English threads validate on first pass against the pydantic schema including the information-containment validator; the machine layers of our reference harness (rollback auto-generation, shortcut expansion with blind-flag inheritance and skipped-info accounting, terminal-distance maps) ran unmodified on the annotated graphs.
2. **Public threads are structurally *richer* than expected for this method.** Mozilla's standardized measurement tooling (mozregression, try builds, about:config probes, about:support) yields dense, user-executable clarification edges with verifiable answers; falsified attempts are recorded explicitly and become blind-path edges without invention.
3. **One P0 schema gap:** non-image artifacts (about:support text, bisection logs, profiler links, screen recordings) have no first-class field; the pilot transcribed them into answer text, violating the deliver-the-original-evidence principle. Fix: add `Clarification.artifacts` / `Node.symptom_artifacts` (path, content type, description) — a small change.
4. **Annotation cost:** 45–75 min/case human-equivalent (thread reading 15–30, graph drafting 20–40, machine validation <5). An LLM-draft + human-review pipeline should reduce the human share to ~20–30 min/case.

## Selection funnel (measured)

| Stage | Filter | Yield |
|---|---|---|
| Bugzilla advanced search | `resolution=FIXED` · `longdescs.count>25` · has image attachment (`attachments.mimetype substring "image"`) · exclude `Intermittent` (CI-bot noise) · user-facing components (Firefox product; Core Graphics*/Widget*/Layout/AV/Panning) · created ≥2023 | 2 queries × 30 = 60 candidates |
| Thread profiling | fetch full comments; compute reporter participation, distinct humans, image attachments, diagnostic-keyword hits | 10 profiled |
| Annotatability | `reporter_comments ≥ 7` and at least one ask→report evidence loop | ≥6/10 |
| Annotated | balanced across four shapes (below) | 4 (+1 backup) |

The two filters that flip results from developer-internal discussion to user-support threads: the image-attachment predicate and the `Intermittent` exclusion. Reporter participation is not queryable server-side; it requires the profiling pass.

## The four cases

| Case | Shape | Thread | Graph |
|---|---|---|---|
| [bmo_1865928](../data/trial/graphs/bmo_1865928.json) — YouTube videos render all-green (FF120, ageing AMD GPU) | Deep clarification chain: wrong-preset profile corrected → mozregression window → pref-confirmation probe → find-fix + beta build verification | 59 comments, reporter 24, 8 images | 7 nodes, 6 edges, 1 blind path (three ineffective NV12 prefs) |
| [bmo_1829487](../data/trial/graphs/bmo_1829487.json) — hardware-accelerated UI corruption (SandyBridge) | Expert reporter volunteered a full self-bisection (mozregression + 11 one-at-a-time pref probes) at filing; canonical path runs **through** two falsified fixes before the device-scoped blocklist fix | 46, reporter 20, 4 images | 5 nodes, 4 edges, 2 blind paths |
| [bmo_1913022](../data/trial/graphs/bmo_1913022.json) — `network.IDN_show_punycode` stopped working | Non-expert, security-anxious reporter; two brush-off resolutions (wrong duplicate closure; ineffective extension recommendation) rejected with evidence; premature verification resolved by explaining nightly cadence | 46, reporter 20, 2 GIFs | 6 nodes, 5 edges, 2 blind paths |
| [bmo_1822845](../data/trial/graphs/bmo_1822845.json) — macOS Automator service broken by FF111 | Compact regression: permission-theory falsified → regression established → bisected → try-build verified → partial revert with honest GA timeline | 26, reporter 7, 2 images | 6 nodes, 5 edges, 1 blind path |

Coverage across: device/driver specificity, expert↔non-expert persona spectrum, graphics/non-graphics, and both blind-path species (genuinely falsified attempts vs. brush-off handling).

## Findings

**F1 — The measurement-class rule holds without exceptions.** mozregression runs, try-build verifications, pref-confirmation probes and benchmarks produced 9 clarification items across the four cases; every one mapped to `clarification_only` under the rule "handler-initiated measurements change knowledge, not the system". No special-casing needed.

**F2 — Expert reporters compress progressive disclosure.** bmo_1829487 opens with 8 info items in `info_state` (self-bisection volunteered at filing). The schema absorbs this via `volunteered_info`, but the case's difficulty shifts from information-gathering to decision scoping. Selection must balance personas or the corpus skews expert.

**F3 — Multi-user threads need a declared merge convention.** In two cases, key measurements came from a second affected user. The pilot folds all affected users into one simulated user side (declared per-graph in `comment` fields and in the data card). Faithful multi-user simulation would be a schema extension with real annotation cost; deferred.

**F4 — Through-failure canonical paths are legal and machine-clean.** bmo_1829487's history is N0 → failed fix (N1_x) → failed fix (N2_x) → clarifications → fix. Aftermath nodes carry evolved symptoms ("partially improved; backgrounds still broken"); rollback generation and shortcut expansion behave correctly, including blind-flag inheritance on expanded copies and correct `shortcut_skipped_info` accounting.

**F5 — Engineer-side inference has a home.** Root-cause readings (e.g., "service breaks because `writeSelectionToPasteboard` passes only `NSStringPboardType`") map to extra info gains on destination nodes plus `info_inferred_by_engineer` references; the containment validator permits destination gains beyond source ∪ asked.

**F6 — Attachments are the main engineering difference (P0).** Bugzilla attachment URLs (`attachment.cgi?id=`) are server-side stable and anonymously downloadable — all 17 image attachments archived successfully (see `data/trial/images/MANIFEST.json` with sha256 + provenance). Contrast: GitHub's `user-attachments` URLs redirect to signed S3 links that expire in minutes, so any GitHub-sourced wave must archive at crawl time. Non-image artifacts need the first-class field (verdict 3); large media (two GIFs, 6.2 MB) should live in object storage with manifest checksums in the released dataset.

**F7 — English content passes the offline stack; the online loop is unverified.** Schema, validators, expansions and distance maps are language-agnostic. The judge/matcher online path (simulator + LLM edge-matching on English) was not exercised in this pilot — it is the first item of future work, before any scale-up claim.

**F8 — Practical source notes.** The BugsRepo dataset (Zenodo, CC-BY-4.0) is best used as a selection index and license precedent, not as the thread corpus: its comments dump contains a duplicated 1.6 GB part, its CTQRS quality file lacks a bug-id column, and it carries no attachment bodies. Thread bodies should come from Mozilla's official bugbug dump (~2.7 GB zst, comments/attachment metadata/history embedded) or the BMO REST API (≤1 req/s, API key).

**F9 — Terminal semantics match reality.** All four resolutions exhibit "fix landed → user verified too early → verified after update" rhythms (bmo_1913022: tested 1 h after landing; nightly builds twice daily). The schema's separation of fixed vs. `user_perceives_resolved`, and satisfaction conditions that require explicit verification, encode this without strain.

## Next steps

1. Online replay smoke: English-persona simulator + judge over bmo_1822845 (closes F7).
2. `artifacts` schema extension (closes F6).
3. Port the LLM graph-drafting prompt to Bugzilla thread input; humans review only.
4. Script the selection funnel; wave-1 target: 50 cases (see `data-collection-and-privacy.md`).
