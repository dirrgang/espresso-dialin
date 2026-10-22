# Read-only prospective evidence inventory

For [#18](https://github.com/dirrgang/espresso-dialin/issues/18), inspect the owner's supplied
runtime source rather than inferring its contents from implementation documentation. Runtime
databases, raw exports and detailed reports remain local unless the owner authorizes publishing
them. The completed 2026-10-22 inventory is saved locally as
`data/local-inventory/2026-10-22.md`, alongside its fingerprinted JSON export. The directory is
gitignored; the report is intentionally unavailable in a public checkout. Its measurements and
the owner's recollections are not copied into public issues or PRs.

## Reproduce an inventory

From the repository root, using the project Python environment:

```sh
mkdir -p data/local-inventory
python scripts/inventory_prospective.py data/live.sqlite3 > data/local-inventory/current.json
```

The script supports schemas v4 and v5 and requires an existing file. It opens SQLite with
`mode=ro`, enables `query_only`, and reads all relevant tables in one transaction. It never
constructs `Repository`, initializes a schema, migrates, saves feedback or launches Streamlit.
Unsupported schema and missing-source errors are explicit; missing access is never reported
as zero observations. V4 extraction feedback is unavailable, not counted as zero v5 evidence.
Do not use `immutable=1` for a possibly live database: it can ignore committed WAL contents.

The JSON includes source path, observation time in UTC, schema version, quick integrity and
foreign-key checks, table counts and ordered raw rows, including NULLs and immutable links.
The logical SHA-256 covers schema definitions and the raw rows visible to that transaction,
including committed WAL data. It identifies the inspected evidence rather than depending on
the main SQLite file alone. Keep a supplied snapshot/backup if later reproduction of that
exact state is needed; an export does not guarantee a changing runtime source remains available.

## Report and interpretation

Use [data-model.md](data-model.md), [experiments.md](experiments.md),
[validation.md](validation.md) and the corrected-source findings in
[historical-analysis.md](historical-analysis.md). Record:

- Source identity/fingerprint, schema, snapshot time, access limitations and owner confirmation
  of known source completeness. Keep unknown physical or unlogged events unknown.
- Sessions, bean/setup/target context, Assisted versus Experiment/unknown intent, experiment
  families, frozen steps, terminal attempts, completed brews, early stops and unstarted steps.
- Primary measurement missingness, correction evidence, bad-shot/purge flags, resolutions,
  actual-versus-planned deviations and selected/shadow/source recommendation links.
- Within-session sequence and phase-recording chronology. Recording timestamps are not exact
  physical event times; historical bean blocks are not verified sessions.
- Raw observations separately from derived rates, target-time approximations or recalled
  corrections. Preserve uncertain values; do not silently turn plans into actual measurements.
- Concrete remaining gaps against the corrected historical baseline and one useful next
  question, with required owner inputs. Inventory completion is separate from collection,
  identification, uncertainty calibration and efficacy evaluation.

The 2026-10-22 report records owner clarification and the data-quality limitation locally;
[correction/exclusion follow-up #26](https://github.com/dirrgang/espresso-dialin/issues/26)
owns the general workflow requirement. No runtime correction or invalidation was performed.
[#19](https://github.com/dirrgang/espresso-dialin/issues/19) owns protocol selection and
[#20](https://github.com/dirrgang/espresso-dialin/issues/20) owns physical collection/assessment.
Current bean/setup, useful operating conditions, coffee budget and timing still require
confirmation before freezing that protocol; an older session is not current-setup evidence.
