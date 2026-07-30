# Trial data (pilot, 2026-07-29)

Four resolved bugzilla.mozilla.org threads annotated into the causal-graph schema, plus one backup thread (bmo_1815481, raw only).

- `graphs/` — annotated Task JSONs (validate with `uv run scripts/validate.py`)
- `raw/` — Bugzilla REST snapshots ({meta, comments, attachments-metadata}); `bugsrepo_structured_subset_bug_ids.csv` is the selection index extracted from the BugsRepo structured subset (8,522 unique bug ids)
- `images/` — archived image attachments; `MANIFEST.json` records all 27 attachments (16 archived in-repo, 11 external-refetch via stable `attachment.cgi` source URLs) with sha256 + provenance

**PRE-SCRUB SNAPSHOT** — contains reporter emails/usernames as published on the public Bugzilla. Run the scrub pipeline (docs/data-collection-and-privacy.md §5) before any public release.
