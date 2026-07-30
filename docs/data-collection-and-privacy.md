# Data Collection & Privacy Plan

v1 (2026-07-29), grounded in the survey (`related-work.md` §6) and the pilot (`pilot-study.md`).

## 0. Stance

- The main dataset is public: original thread snapshots + attachments + graph annotations + evaluation protocol. No executable environments are shipped — evaluation is execution-free by design.
- Privacy posture: sources are public, identified-by-design systems (Bugzilla, GitHub) with official full redistribution precedents (bugbug; BugsRepo CC-BY-4.0). The goal is therefore **minimization + pseudonymization + a takedown channel**, not absolute anonymity.

## 1. Sources and waves

| Wave | Source | Content | License basis |
|---|---|---|---|
| W1 | Mozilla Bugzilla | resolved, multi-turn, attachment-bearing user support threads | bugbug official full-dump precedent; BugsRepo CC-BY-4.0 academic precedent (Zenodo 15004067) |
| W2a | GitHub issues (Flutter / React Native / Expo / Electron / Tauri / Home Assistant core / Terraform providers) | environment-irreproducible issue threads | GitHub AUP research exemption (open-access results required); SWE-bench / the-stack-github-issues full-text precedents |
| W2b | Home Assistant community forum (Discourse) | user-voice help threads with solved markers | site ToS grants CC BY-NC-SA 3.0 on user contributions (per-site check mandatory; skip sites on the new default ToS that bars scraping) |
| W3 | SRE evidence packs (Nezha / RCAEval telemetry + GitLab gl-infra public incident reviews) | dialogue-RCA second domain | MIT / public downloads; AIOps-series data is CC BY-NC — compliance check before inclusion |

W1 first because: cleanest license chain, server-stable attachments, standardized measurement tooling (dense clarification edges), and `resolution=FIXED` gives a definite outcome.

## 2. Selection funnel (frozen from the pilot)

1. **Coarse (search API):** `resolution=FIXED`; `longdescs.count > 25`; has image attachment; `short_desc` excludes "Intermittent"; user-facing component allowlist; creation window as configured.
2. **Profiling (comments API):** reporter_comments, distinct human participants (strip *bot accounts), image count, diagnostic-keyword hits (mozregression / about:support / try build / pref / "no change"). Threshold: `reporter_comments ≥ 7` plus at least one ask→report loop.
3. **Shape balancing:** persona (expert↔non-expert) × component domain × blind-path species × clarification-chain depth.
4. Measured yield: 60 candidates → 10 profiled → ≥6 annotatable. Wave-1 target of 50 cases ⇒ ~500 candidates, 80–100 profiles.

## 3. Harvesting pipeline

- **Thread bodies:** bugbug official dump (`project.bugbug.data_bugs.latest` artifact, ~2.7 GB zst, line-JSON with embedded comments/attachment metadata/history) as the base + BMO REST incremental top-up. BugsRepo is used only as a structured-subset selection index.
- **REST discipline:** ≤1 req/s with an API key; endpoints `rest/bug/<id>`, `rest/bug/<id>/comment`, `rest/bug/<id>/attachment?exclude_fields=data`.
- **Attachments:** archive at crawl time, always (GitHub signed URLs expire in minutes; Bugzilla is stable today but archived anyway). Images ship in the dataset; files >1 MB and all video go to object storage with an in-dataset manifest (attachment_id, sha256, content type, byte size, source URL).
- **Provenance (per case, mandatory):** source URL, ids, crawl timestamp, upstream metadata snapshot (creator/resolution/last-resolved/regressed-by), tool version. This underpins attribution, takedown lookup, and contamination layering.

## 4. Data & annotation schema

- Task/Graph/Node/Edge schema as in `src/tracegraph_bench/models.py` (pilot passed unchanged).
- **P0 extension:** first-class non-image artifacts (`Clarification.artifacts` / `Node.symptom_artifacts`: {path, content_type, description}) for logs, support reports, profiler links, recordings.
- Annotation flow: LLM draft → machine validation (schema + containment + expansion dry-run) → human review with a defect checklist; `hitl_reviewed` marks reviewed cases. Multi-user threads are merged into a single simulated user side, declared in the data card.
- Per-case anchors: satisfaction conditions must include a verification step (fix landed ≠ user-confirmed); every blind-path edge must correspond to an attempt actually falsified (or brushed-off and rejected) in the thread — never invented.

## 5. Scrubbing (four layers, pre-release; unscrubbed originals kept encrypted, internal-only, for takedown lookup)

1. **Identity pseudonymization:** usernames/emails/real names → role-stable pseudonyms (`reporter`, `user2`, `dev1`, `triager1`), consistent within a case; mapping table encrypted, never released. Bot accounts keep their names. Attribution points at the source bug URL, not at individuals.
2. **In-text PII:** regex + LLM double-pass for emails, IPs, hostnames, username-bearing paths (`C:\Users\<name>`, `/home/<name>`), phone numbers → consistent placeholders. Field-level cleaning for about:support-class artifacts (drop printers/fonts/account fields; keep GPU/driver/version fields — they are the diagnostic substance).
3. **Attachments:** strip EXIF on all images; human checklist pass on screenshots/recordings (bookmarks bar, other tab titles, desktop, notification popups → mask or drop the attachment); frame-sampled review for GIF/video.
4. **Secret scanning:** gitleaks-class rules over all text bodies and attachments; hits masked and logged.

Negative precedent honored: GHTorrent's GDPR complaints over email redistribution — pseudonymize and keep the takedown channel. Positive precedent: BugsRepo shipped `creator` fields under CC-BY-4.0; our posture is strictly more conservative.

## 6. Licensing & attribution

- Curation layer (graphs, satisfaction conditions, personas, manifests): **CC BY 4.0**. Protocol & code: **Apache-2.0**.
- Underlying thread content: copyright remains with its authors; every case displays its source link ("content from the Mozilla Bugzilla public database, bug <id>"), plus a global notice citing the bugbug and BugsRepo precedents and requiring downstream users to respect source-site terms.
- W2a adds: permissive-license repositories only (CAB's first filter); the project stays open-access to satisfy the GitHub AUP research exemption. W2b: per-site ToS check; CC BY-NC-SA sites shipped as a separately-marked NC subset. Corpora that bar redistribution (e.g., LMSYS-Chat-1M) are never included.

## 7. Anti-contamination

- **Frozen vs rolling splits** by `creation_time`; monthly top-ups of newly resolved threads (SWE-bench-Live pattern); headline metric reported on the recent rolling window.
- **Counterfactual variants** on key clarification edges (extreme/minor candidates are already first-class in the schema) — intervened answers exist in no public thread; this layer is native to the graph method.
- **Canary string** embedded in the dataset; frozen-vs-rolling score gap reported as a contamination signal.

## 8. Release form & evaluation QA

- HuggingFace dataset (data) + GitHub (protocol/judge/simulator code); graphs versioned (`graph_version`) with review status.
- Mandatory release trio (targets the live 2026 critiques): (1) simulator-compliance self-audit (baseline: τ²'s 22% violation self-audit); (2) noise floor across repeated runs and across simulator models (baseline: ±9 pts from Lost in Simulation); (3) versioned gold-revision process (baseline: τ³'s 75+ task fixes).
- Objective anchor: per-case fix commit/PR link; culprit-artifact localization is deterministically checkable and calibrates the graph judge.

## 9. Takedown & governance

Public takedown channel (email + issue template), 30-day SLA; pseudonym map lookup → remove/replace → dataset version bump with changelog (URL stable). Quarterly re-check of source-site ToS (Discourse sites in particular).

## 10. Milestones

| Stage | Content | Exit |
|---|---|---|
| M0 (done) | 4-case pilot + machine validation | `pilot-study.md` |
| M1 | online replay smoke (English simulator + judge) + `artifacts` schema extension | English judging quality confirmed |
| M2 | scripted funnel/harvest/scrub; wave-1 to 50 cases (LLM draft + human review) | 50 reviewed cases, agreement spot-check |
| M3 | QA trio + frozen/rolling layering | scoreable v0.1 |
| M4 | W2a/W2b expansion + monthly rolling updates | public release candidate |
