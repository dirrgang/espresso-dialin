# Live prospective acquisition

Phase 3 provides a local Streamlit application backed by Python's standard SQLite driver.
Grinder setting remains your manual choice. The application reuses the two existing dose
controllers; neither is declared the winner. There is no extraction optimisation, Learning
Mode, retention model, hardware integration, or historical-data import into live history.

## Install and start

From a fresh checkout, use Python 3.12 or newer. PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pre-commit install
python -m streamlit run app.py --server.address 127.0.0.1
```

On Linux/macOS, create the environment with `python3.12 -m venv .venv` and activate it
with `. .venv/bin/activate`; the remaining commands are the same. Open the local URL
printed by Streamlit, normally `http://127.0.0.1:8501`.

The database is created automatically at `data/live.sqlite3`, relative to the checkout
containing `app.py`. Set `ESPRESSO_DIALIN_DB` to a different path before launching if needed:

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
2. Enter the exact grinder label you intend to use, such as `3E`. Labels are opaque and
   matched exactly, including case and spacing; use a consistent spelling.
3. Review the available durations and choose a strategy, or choose **manual** and enter
   your planned duration. When compatible history is insufficient, the UI says so and
   requires a manual duration. No estimated rate or expected output is invented.
4. Click **Freeze plan before grinding**. Wait for the saved-plan confirmation before
   grinding. All available model candidates and the selected plan are saved together.
   Merely displaying the preview does not persist it.
5. Grind, then record the **actual** setting, duration and raw grinder output. The duration
   field starts empty: a planned 9.74 s and actual 9.70 s remain different facts.
   Record the correction mode and save the grinding result.
6. Brew, then enter measured brew duration and actual final beverage yield. Optional
   purge and obviously-bad flags and notes record what happened; purging is not required.
   Click **Complete shot**. Bad shots are retained.
7. Review recent history or start the next shot. The next model history uses eligible
   earlier completed observations. Restarting the server or browser preserves saved
   plans and intermediate grinding results. Unsaved form entries are not durable.

There is no time-critical entry. Each physical phase can finish before entering its results,
but the plan must be frozen before grinding. Timestamps are UTC, timezone-aware **entry
timestamps**, not measurements of the exact physical grinder/pump start or stop time.

## Required and optional values

| Stage | Required | Optional |
| --- | --- | --- |
| Session | Bean name/identity, grinder, machine, positive recipe targets and ordered time bounds | Roaster, roast date; end the session later |
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

`app.py` handles forms and display; `application.py` assembles compatible history and calls
the unchanged dose controllers; typed records and validation live in `domain.py`;
`repository.py` owns all SQL and transactions.

A freeze transaction checks the session and next sequence, inserts all candidate records,
and creates a pending shot linked to exactly one selected candidate. Foreign keys include
session and target sequence. A unique index allows only one selected candidate per shot
and one unfinished shot per session. Concurrent/stale freezes are rejected atomically.
Outcome entry cannot create or replace a recommendation. SQLite triggers reject updates
and deletes of recommendations, late candidates, shot relinking, deletion of shots, and
changes to completed outcomes or session context. The application also treats saved
grinding results as final. This protects against application mistakes; it is not a
tamper-proof ledger against someone deliberately modifying the database or dropping triggers.

Only completed shots in the same session and current contiguous run of the exact **actual**
setting are eligible. Changing setting, including changing away and later returning,
starts a new block. A new session starts empty even for a previously used bean. One
compatible completed observation is sufficient for both existing controllers. Bad-brew
flags do not discard raw grinder-output data; they do not diagnose a grinder-output fault.

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

This minimal application has no editing/deletion, cancellation, or retrospective entry flow.
Review entries before saving each phase. An unfinished shot remains resumable and blocks
the next shot in that session; a new session can still be created. Abandoned physical shots
can remain unfinished rather than receiving invented brew measurements. A future correction
or abandonment workflow needs an explicit audit trail. Session context and completed
outcomes are intentionally fixed to preserve source observations for frozen predictions.
