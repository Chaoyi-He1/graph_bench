# Data License & Attribution

## Curation layer

The annotation/curation layer of this dataset — task graphs, satisfaction conditions, persona hints, info-state structure, counterfactual candidates, manifests, and selection indices — is licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.

## Underlying content

Thread texts and attachments under `data/*/raw/` and `data/*/images/` originate from the public Mozilla Bugzilla database (bugzilla.mozilla.org). Copyright in that content remains with its original authors. Each case records its source (`metadata.created_from`, plus per-attachment `source_url` in `images/MANIFEST.json`).

Redistribution of Mozilla Bugzilla content follows established precedent:
- Mozilla's own **bugbug** project publishes full database dumps for model training (https://github.com/mozilla/bugbug/blob/master/docs/data.md);
- **BugsRepo** republishes 119,585 complete threads under CC BY 4.0 (https://zenodo.org/records/15004067, arXiv:2504.18806).

Users of this dataset must also respect the source site's terms.

## Takedown

If you are an author of included content and want it removed or amended, open an issue titled `takedown: bug <id>` or contact the maintainers. Requests are honored within 30 days; removals ship as a new dataset version with a changelog entry.

## Note on the current snapshot

`data/trial/` is a **pre-pseudonymization pilot snapshot** intended for internal method development. The scrubbing pipeline described in `docs/data-collection-and-privacy.md` §5 must run before public release.
