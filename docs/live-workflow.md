# Live prospective acquisition

Phases 3.1 and 4 provide a local Streamlit application backed by Python's standard SQLite driver.
Grinder setting remains your manual choice. The application reuses the two existing dose
controllers; neither is declared the winner. Learning mode adds predefined experiments. There is
no extraction optimisation, retention model, hardware integration, or historical-data import.

## Install and start

From a fresh checkout, install `mise` once, then bootstrap the Python 3.14 environment and start the app:

```powershell
mise run setup
mise run app
```

`mise run setup` installs the repository-scoped Python, uv, and prek versions, synchronizes the
locked development environment, and installs the Git hook. See [`../DEVELOPMENT.md`](../DEVELOPMENT.md)
for shell integration and migration notes for older clones. Open the local URL printed by
Streamlit, normally `http://127.0.0.1:8501`.

The database is created automatically at `data/live.sqlite3`, relative to the checkout
containing `streamlit_app.py`. Set `ESPRESSO_DIALIN_DB` to a different path before launching if needed:

```powershell
$env:ESPRESSO_DIALIN_DB = 'C:\espresso-data\live.sqlite3'
```

SQLite databases, their journal/WAL/shared-memory companions, virtual environments,
Python caches, test coverage, and Streamlit secrets are gitignored. Historical CSVs
remain versioned; neither historical source is modified or automatically pooled into live data.

## Making an espresso

1. Create or select a session. The bean selector offers **REWE Bio Espresso ganze Bohnen,
   1000 g** as an explicit shortcut, along with previously recorded beans and a new-bean
   option. It is not automatically selected for every session. Review the grinder,
   machine, and recipe targets. Start a new session when bean, setup, or targets change.
   The optional bag-open date describes the physical package, not the bean product or its
   roast date. A roast date is not required, including for supermarket coffee. Start a new
   session for a new bag if you want separate context; no pooling is inferred from these dates.
2. Enter the exact grinder label you intend to use, such as `3E`. Labels are opaque and
   matched exactly, including case and spacing; use a consistent spelling.
3. Review the available durations and choose a strategy, or choose **manual** and enter
   your planned duration. When compatible history is insufficient, the UI says so and
   requires a manual duration. No estimated rate or expected output is invented.
4. Click **Freeze plan before grinding**. Wait for the saved-plan confirmation before
   grinding. All available model candidates and the selected plan are saved together.
   Merely displaying the preview does not persist it. If the wrong plan was frozen and the
   grinder has not been run, use **Cancel frozen plan — no grinding performed** instead of
   inventing measurements or deleting the frozen intent.
5. Grind, then record the **actual** setting, duration and raw grinder output. The duration
   field starts empty: a planned 9.74 s and actual 9.70 s remain different facts.
   Record the correction mode and save the grinding result.
6. Brew, then enter measured brew duration and actual final beverage yield. Optional
   purge and obviously-bad flags and notes record what happened; purging is not required.
   Click **Complete shot**. Bad shots are retained.
7. Review recent history or start the next shot. The next model history uses eligible
   earlier valid terminal observations (completed or abandoned with a retained grinder result).
   Restarting the server or browser preserves saved plans and intermediate grinding results.
   Unsaved form entries are not durable.

On a fresh browser connection or server restart, the app selects the newest session that
has not been ended (or the newest session if all are ended). You can select another session;
that choice remains active through normal reruns and validation errors. Session, grinding,
and brewing forms require an explicit submit-button click: pressing Enter in a field does
not save the form. Invalid entries show an error while keeping the rest of the page available.

There is no time-critical entry. Each physical phase can finish before entering its results,
but the plan must be frozen before grinding. Timestamps are UTC, timezone-aware **entry
timestamps**, not measurements of the exact physical grinder/pump start or stop time.

## Required and optional values

| Stage | Required | Optional |
| --- | --- | --- |
| Session | Bean name/identity, grinder, machine, positive recipe targets and ordered time bounds | Roaster, roast date, bag-open date; end the session later |
| Plan | Manual setting, strategy choice, manual duration if manual is selected | Model predictions are available only with compatible history |
| Grinding | Actual setting, positive finite duration and output, correction mode | Separately measured puck dose, required only for `MEASURED` |
| Brewing/completion | Positive finite brew duration and final yield | Purge/bad flags (default false), notes |

Correction modes keep raw output and puck dose distinct:

- `NONE`: all grinder output was brewed without intentional correction. The separate
  measured-puck field stays null; brewed mass can be derived from raw output under this declaration.
- `TO_TARGET`: the puck was corrected approximately to the session target. The measured
  puck field stays null. Neither a precise mass nor a numerical uncertainty is invented.
- `MEASURED`: enter the actual separately weighed final puck mass. Raw output remains intact.

The selected flag records pre-shot intent. It does not assert that the operator exactly
executed the recommendation. Actual setting and duration are the execution evidence.

## Freezing and chronology

`streamlit_app.py` handles forms and display; `application.py` assembles compatible history and calls
the unchanged dose controllers; typed records and validation live in `domain.py`;
`repository.py` owns all SQL and transactions.

A freeze transaction checks the session and next sequence, inserts all candidate records,
and creates a pending shot linked to exactly one selected candidate. Foreign keys include
session and target sequence. A unique index allows only one selected candidate per shot;
a trigger allows only one unresolved pending shot per session. Concurrent/stale freezes are
rejected atomically.
Outcome entry cannot create or replace a recommendation. SQLite triggers reject updates
and deletes of recommendations, late candidates, shot relinking, deletion of shots, and
changes to completed outcomes or session context. The application also treats saved
grinding results as final. This protects against application mistakes; it is not a
tamper-proof ledger against someone deliberately modifying the database or dropping triggers.

Only completed shots or abandoned brews with a retained valid grinder result in the same
session and current contiguous run of the exact **actual** setting are observations. A
pre-grind abandonment is transparent to that physical grinder history only when the operator
explicitly confirms that no physical grinding occurred and that confirmation is persisted.
Legacy or otherwise unconfirmed `ABANDONED` rows without grinder evidence remain conservative
continuity breaks. Invalidated shots always break continuity, including when their measurements
are missing, because execution or evidence is wrong or uncertain. Changing actual setting,
including changing away and later returning, starts a new block. A frozen planned setting is
intent, not physical execution, and cannot by itself change grinder state. A new session starts
empty even for a previously used bean. One compatible observation is sufficient for both
existing controllers. Bad-brew flags do not discard raw grinder-output data; they do not diagnose
a grinder-output fault.

Both available model predictions are saved, even if manual is selected. Each includes its
model version, frozen rate, expected output at its proposed duration, block identity, exact
source shot IDs, observation count and history-through sequence. Completed source rows
are retained and immutable through the app, so these IDs resolve to the original measurements.

Later analysis can use the existing `score_recommendation` function on each stored `Plan.model`
at the shot's **actual duration**, provided its actual setting matches the prediction's setting.
If the setting differs, the prediction is outside its applicable context and should not be scored
as a compatible prediction. A shadow prediction does not reveal the output that would have
occurred at its unexecuted recommended duration. No comparative scoring dashboard or
closed-loop coffee-savings claim is included in this phase.

## Backups and current limitations

Stop Streamlit with Ctrl+C, ensure no other process is using this database, and copy
`data/live.sqlite3` to a dated backup on another drive. For example, after stopping the app:

```powershell
Copy-Item -LiteralPath .\data\live.sqlite3 -Destination E:\Backups\espresso-2026-09-14.sqlite3
```

Use your actual configured database path and backup destination. To restore, stop the app
and copy the backup to the configured path. For backups while the application is running,
use SQLite's online backup API rather than copying a potentially active database file.
Backups are your responsibility; Git does not preserve runtime data.

## Abandonment and invalidation

Use **Abandon or invalidate a shot** below recent history. Select the shot and action,
enter a required reason, check the confirmation, and click **Confirm shot resolution**.
The selector includes older shots, not just the 20 shown in the recent-history table.

- **Abandon before grinding — confirm no physical grinding occurred:** ends an unexecuted
  frozen plan. The explicit physical confirmation is persisted, the session is released,
  no controller observation is created, and grinder continuity is preserved.
- **Abandon brew — keep valid grinder result:** explicitly declares the saved grinding result
  valid while ending the brew attempt. The actual-setting continuity rules apply normally and
  the grinder result can inform later dose predictions.
- **Invalidate — execution or evidence is uncertain:** use when execution or recorded evidence
  is wrong or uncertain, including a completed shot. It excludes the entire shot from future
  controller history and always breaks continuity. The wrong value remains visible alongside
  the invalidation reason and timestamp; it is never overwritten.

Both actions release a pending shot so another physical espresso can start normally in the
same session. Existing frozen recommendations remain unchanged, even if a source observation
is invalidated later. Do not re-enter a past espresso as a new prospective shot: a new freeze
would occur after its outcome was known. This phase provides exclusion rather than a replacement
measurement/editor flow. Describe a known correction in the reason; it is not used as numeric data.

Each shot supports one irreversible resolution: there is no undo, repeat resolution, or second
invalidation after abandonment. Choose invalidation if the grinder measurement is uncertain.
Completed shots can be invalidated but not abandoned. Resolved shots cannot be completed or
receive more measurements. Session context remains fixed. There is no generic editing/deletion
or retrospective-entry UI.

Missing measurements alone never prove non-execution. Only the persisted explicit confirmation
has that meaning. Arbitrary missing or invalid data must not be bridged.

### Narrow maintenance correction

`scripts/reclassify_pregrind_invalidation.py` corrects a known, explicitly identified row that
was invalidated even though the operator confirms the grinder was never run. It is not a general
shot editor. First launch the updated app once so the database is migrated to the current schema
v4. Then stop Streamlit before running the maintenance command. The database path, session ID, and shot ID are
all required; the default is a read-only dry run:

```powershell
uv run python scripts/reclassify_pregrind_invalidation.py .\data\live.sqlite3 `
  --session-id <exact-session-id> --shot-id <exact-shot-id>
```

Apply only after reviewing the candidate and add both `--apply` and
`--confirm-no-physical-grinding`. Before mutation, the command creates a timestamped backup with
SQLite's backup API. It refuses rows that are not currently `INVALIDATED`, already carry a
non-execution confirmation, contain any grinding/brewing evidence, or lack the expected schema-v3
guards. The one transaction temporarily removes the verified resolution-update guard, changes
the resolution to `ABANDONED`, persists `no_physical_grinding_confirmed = 1`, embeds the original
status/reason/timestamp in the corrected reason, restores the guard, and runs SQLite integrity and
foreign-key checks before commit. The shot, frozen recommendations, sequence, and recording
timestamps are not changed. Ordinary app startup never performs this reclassification.

## Schema v4 and recording timestamps

Launching the app automatically migrates valid v1, v2 or v3 databases to v4 in one transaction.
Back up the database before updating (see above). A failed migration rolls back all changes,
including the schema version, and can be retried. Reopening v4 is idempotent; unsupported versions
are rejected. Fresh databases are created directly at v4. Older app versions cannot open the
upgraded database; reverting requires the pre-upgrade backup.

Schema v3 adds nullable `shot_resolutions.no_physical_grinding_confirmed`. New explicit pre-grind
cancellations store `1`. Existing v2 resolution rows migrate with `NULL`; in particular, an old
`ABANDONED` row with no grinder result remains an unknown transition and therefore still breaks
continuity. The migration never infers non-execution from missing measurements or reason text.

| Domain timestamp / flag | Storage | Meaning |
| --- | --- | --- |
| `plan_frozen_at` | Existing shot `created_at` | Plan frozen and pending shot saved |
| `grinding_recorded_at` | Nullable shot column | Grinding result successfully saved |
| `brewing_recorded_at` | Existing `completed_at` | Brew result successfully saved |
| Resolution `recorded_at` | Immutable `shot_resolutions` row | Abandonment/invalidation recorded |
| `no_physical_grinding_confirmed` | Nullable resolution flag | `1` only after explicit confirmation that the frozen plan was not physically executed |

These timestamps are timezone-aware UTC acquisition timestamps, not physical grinder-start/stop
or pump-start/stop measurements. Their precision reflects the recording clock, not physical-event
accuracy. Legacy grinding-entry times remain null: creation/completion times cannot reconstruct
them. Existing v1 creation/completion timestamps retain their original meanings. Legacy
bag-open dates are null. History displays status, recording timestamps, non-execution confirmation,
and resolution reasons.

## Learning / Experiment workflow

Choose **Learning** under **Use mode**. Create an experiment in the selected session, state the
research question, and enter the current reference setting/duration. Review the entire sequence,
held/varied inputs, attempt count, approximate coffee budget and stopping rule. Then click
**Freeze experiment plan**. Previewing alone records nothing. Choose an existing experiment to
resume it after restart; its schedule and membership are durable.

Click **Freeze next experimental shot** before each grind. It uses the same grinding, puck
correction, brewing and resolution forms as Assisted mode. Save actual inputs, even if they
vary from the plan; add an optional **Deviation / interruption note** at grinding entry. The
experiment table and recent history show input mismatches without changing the plan. Brewing
notes can retain additional context.

Cancel a step by freezing its shot and then using the existing explicit no-grinding cancellation
with reason and confirmation. It consumes that planned attempt, retains the frozen plan, and
creates no physical transition. Invalidated or uncertain attempts retain the conservative
continuity break. A failed attempt is never silently replaced. Finish/resolve any pending shot
before stopping the experiment with a reason. Unstarted steps remain unstarted; a stopped
experiment cannot resume. Ending the session prevents further execution; stop unfinished
experiments with a reason when closing their collection.

**FINISHED** means terminal attempts, not successful replication or empirical proof. Counts
separate finished attempts from completed brews. Switching back to Assisted preserves the
experiment and every measurement. Record intervening physical grinds and interruptions; the
experiment schedule alone cannot establish uninterrupted physical execution.

See [experiments.md](experiments.md) for the first-offer rationale, designs, programmatic raw
observation access and deferred protocols. No prospective experiment results are claimed yet.
