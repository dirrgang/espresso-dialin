# espresso-dialin

Experimental, local-first proof of concept for adaptive espresso dial-in.

**Assisted and Learning modes are usable for prospective collection:** a local Streamlit + SQLite app freezes
dose recommendations before grinding and records actual grinding/brewing results separately.
Grinder settings remain manually chosen. Start with the [live workflow guide](docs/live-workflow.md).

For development, install `mise` once, then bootstrap the repository with:

```powershell
mise run setup
mise run app
```

`mise.toml` provides the repository-scoped Python 3.14 runtime plus uv and prek versions; `uv.lock` pins the Python environment. Python 3.14 is the supported project runtime; newer minor versions are adopted deliberately after the locked environment and quality gates have been validated. See [`DEVELOPMENT.md`](DEVELOPMENT.md) for shell integration, quality checks, VS Code integration, and migration notes for older clones.

The database is created at `data/live.sqlite3` and is gitignored. The guide covers backups,
manual fallback, required fields, restarting between phases, and recommendation provenance.

The project is not intended to be another generic espresso diary. Its primary research question is whether a small learning model can use the measurements a home barista already makes to reach a target recipe with fewer wasted shots and less manual trial-and-error than simple heuristics.

## Current target

Default recipe target for the initial proof of concept:

- **Puck dose:** 18.0 g
- **Final beverage yield:** 36.0 g
- **Brew time:** 30–35 s (nominal center: 32.5 s)

The first real setup is a **Baratza Sette 270** grinder and **Sage/Breville Dual Boiler (BES920/SES920)** espresso machine. Grinder-specific behavior must nevertheless be abstracted rather than hard-coded into the statistical model.

## User workflow

The MVP must work without Bluetooth scales, machine telemetry, pressure sensors, power monitoring, or time-critical data entry.

For each shot the user can enter data at leisure:

1. Before grinding: choose the intended grinder setting, review/select a model recommendation or manual grind duration, and freeze that plan.
2. After grinding: record the **actual** grinder setting, actual grind duration, and raw grinder output mass.
3. Record whether the puck dose was left unchanged, corrected approximately to target (normally 18 g), or separately measured after correction.
4. After brewing: record brew duration and final beverage yield.

The current application stores the observation and offers dose-duration recommendations
for your manually chosen next setting when compatible live history exists. Automatic
grinder-setting selection and extraction optimisation remain future work.

### Dose correction is intentional

During dial-in, manually correcting grinder output to 18 g is considered a useful controlled intervention rather than an error. It decouples two problems:

- learning how grinder setting affects extraction while puck dose is approximately fixed;
- learning how grind duration and grinder state affect grinder output.

The system therefore distinguishes **grinder output** from **actual puck dose**. Historical shots for which the output was corrected to approximately 18 g remain useful for both models.

## Why final yield remains a measured variable

The user aims for 36 g but cannot stop the brew at exactly 36 g because of reaction time and post-stop flow. Therefore brew time must not be interpreted independently of the observed final yield.

A shot such as `31 s / 34 g` does not imply the same flow behavior as `31 s / 38 g`. The model should use `(brew duration, final yield)` jointly to estimate behavior around the 36 g target instead of assuming that every logged brew time corresponds to exactly 36 g.

Measuring the exact scale weight at the instant the pump is stopped is a possible future hardware-assisted feature, but explicitly **out of scope for the MVP**.

## Key modelling goals

The proof of concept should investigate, rather than assume, the value of the following model complexity:

- robust dose prediction from grind duration and grinder setting;
- extraction prediction using grinder setting, actual puck dose, brew duration, and final yield;
- robust down-weighting of anomalous shots (e.g. channeling from poor puck preparation);
- learning from all previous shots instead of reacting only to the immediately preceding shot;
- optional retention / dead-space model using previous grinder settings as a latent dynamic state;
- grinder-independent representation of stepped, stepless, and macro/micro adjustment systems.

Retention-aware operation is intended to make **purging optional**, not mandatory. This is currently a hypothesis to test, not an assumption that the extra complexity is worthwhile.

## Research methodology

The project is being treated primarily as a **system-identification and adaptive-control problem with an optimisation layer**, not as a generic black-box machine-learning exercise.

The preferred direction is **gray-box modelling**: use known process structure where it improves sample efficiency, and learn the unknown parameters, residuals, drift, or latent state from data.

Two operating objectives are explicit:

- **Normal / assisted mode:** prioritize a good next drink with minimal waste.
- **Learning / experiment mode:** deliberately request informative, controlled shots to identify process behaviour efficiently.

Learning Mode offers frozen fixed-condition replication, balanced local duration response and categorical extraction-setting contrasts. See [experiment designs and evidence](docs/experiments.md). Real designed data collection and empirical validation remain outstanding. Gaussian-process / Bayesian-optimisation methods are later candidates once the action-space representation and uncertainty model are trustworthy.

See:

- [`docs/research-methods.md`](docs/research-methods.md) — mathematical foundations, RLS/adaptive control, DoE, state-space methods, Gaussian processes and Bayesian optimisation;
- [`docs/research.md`](docs/research.md) — related software, espresso research and control/process analogies;
- [`docs/model.md`](docs/model.md) — current mathematical project model and hypotheses;
- [`docs/decision-log.md`](docs/decision-log.md) — decisions versus unresolved questions.

## Working style

The project intentionally separates **research/explanation** from **implementation execution**.

Repository-aware interactive ChatGPT sessions are used primarily for mathematical explanations, literature review, interpretation of results, exploration of model assumptions, and preparation/review of implementation tasks. Codex/coding agents are used primarily for bounded implementation, tests, refactoring, and reproducible execution against explicit acceptance criteria.

The separation is about objectives, not a hard tool boundary. Production code should remain concise and maintainable rather than becoming tutorial material, while important mathematical assumptions and design rationale discovered in either workflow should be committed to durable repository documentation.

See `AGENTS.md` for the detailed agent-facing conventions.

## Proof-of-concept architecture

Start deliberately small in Python. The uncertainty is in the model, not in the UI.

Suggested stack:

- Python
- Streamlit for the local UI
- SQLite for persistent shot/recommendation storage
- NumPy / SciPy for numerical work
- notebooks for exploratory analysis and backtesting
- pytest for deterministic model tests

Suggested structure:

```text
espresso-dialin/
├── streamlit_app.py
├── src/espresso_dialin/
│   ├── domain.py
│   ├── repository.py
│   └── optimizer/
│       ├── base.py
│       ├── heuristic.py
│       ├── regression.py
│       └── retention.py
├── tests/
├── notebooks/
├── docs/
└── data/
```

The optimizer must be independent of Streamlit and SQLite. It should consume domain objects / shot history and return a recommendation. This allows the Python core to survive a later migration to a proper web frontend/API if the concept proves useful.

## Evaluation principle

Do not judge a model by fitting historical shots and then showing that it explains those same shots. Store recommendations **before** the outcome is known and use chronological / rolling validation.

Useful metrics include:

- dose prediction error;
- estimated time-to-36-g prediction error;
- calibration / uncertainty quality;
- number of shots required to reach the target region;
- total coffee consumed before reaching the target region;
- information gained per deliberately designed Learning-Mode shot where that objective applies.

Simple models are baselines, not straw men. If a heuristic or linear model performs as well as a retention-aware/Bayesian model, prefer the simpler model.

## Existing work / baseline

**EspressoPost** is the closest known existing project. It already learns a grinder/time relationship using Bayesian linear regression and recommends grind settings. Therefore “use regression to recommend grind size” is not novel by itself.

This project is only worthwhile if the extra information already available in the intended workflow — especially actual grinder output, actual final yield, dose correction, and possibly previous grinder state — produces measurably better or lower-waste dial-in.

EspressoPost should be treated as a conceptual baseline rather than something to reproduce.

## Historical data

The repository retains both the original transcription and a corrected analysis dataset:

- `data/historical_shots_staging.csv` is the auditable initial transcription and should not be silently repaired or imputed;
- `data/historical_shots_corrected.csv` is the authoritative source for current historical analysis and incorporates later user-supplied corrections/recovered entries.

The known historical bean blocks are now identified as:

- sequences 1–39: **Café Intención Espresso Intensivo**;
- sequences 40–51: **REWE Bio Espresso ganze Bohnen, 1000 g**.

The REWE Bio Espresso is also the current bean for the start of prospective/live data collection.

For these historical entries, grinder output was generally manually corrected to approximately 18 g before brewing when necessary. Analysis must therefore preserve:

- recorded grinder output as the dose-model observation;
- puck dose as approximately 18 g with explicit uncertainty / correction status;
- chronological order, because it is required to test retention / previous-setting effects;
- bean/session boundaries where known;
- genuinely unknown values as missing/uncertain rather than guessed.

The historical dataset remains useful as an observational warm start, baseline/regression fixture and source of hypotheses. It should not be retrospectively treated as a designed experiment. Existing analysis artifacts created against the staging transcription are historical snapshots and should be rerun against the corrected dataset before their numeric findings are treated as current.

See [`data/README.md`](data/README.md) for provenance and dataset semantics.

## Current scope boundaries

Explicitly **not required for the initial proof of concept**:

- user accounts;
- cloud sync;
- PostgreSQL;
- public REST API;
- Bluetooth scales;
- machine telemetry;
- pump-stop weight measurement;
- grinder purging as a mandatory prerequisite;
- taste optimization;
- neural networks or complex ML for their own sake;
- a large database of grinder-specific calibration curves.

See `docs/` for the current modelling assumptions, data model, experiment plan, and decision log.

## Development

The repository is bootstrapped as a typed Python 3.14 project using a `src/` layout, mise, uv, Ruff, mypy, pytest, prek, and GitHub Actions. See [`DEVELOPMENT.md`](DEVELOPMENT.md) for environment setup and quality-check commands.
