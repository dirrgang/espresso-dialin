# Decision log

This file records current project decisions separately from hypotheses. Change entries when the project learns something materially new.

## 2026-09-10 — Project framing

**Decision:** The project is an experimental adaptive dial-in tool, not primarily a coffee diary.

**Goal:** Reduce manual trial-and-error and ideally reduce the number of shots / grams of coffee needed to reach a target recipe.

**Default target:** 18.0 g puck dose, 36.0 g final yield, 30–35 s brew duration.

## 2026-09-10 — MVP measurement workflow

**Decision:** The MVP must require only measurements that can be entered manually without time pressure.

Required/primary observations:

- grinder setting;
- grind duration;
- grinder output mass;
- brew duration;
- final beverage yield.

**Out of scope:** exact weight at pump stop, Bluetooth-scale telemetry, pump/button event detection and other real-time instrumentation.

Reason: those features create a hardware/integration problem before the statistical concept is validated.

## 2026-09-10 — Manual dose correction

**Decision:** Correcting grinder output to the target puck dose is explicitly supported and likely the default assisted-dial-in workflow.

The system must keep both:

- original grinder output;
- actual/approximate puck dose after correction.

Reason: holding puck dose around 18 g reduces confounding while the grinder-setting model is being learned, while the original output still trains the grind-duration model.

A simple UI checkbox may represent “corrected to target,” but the underlying model should distinguish `NONE`, `TO_TARGET`, and optionally `MEASURED` correction modes.

## 2026-09-10 — Final yield treatment

**Decision:** Do not discard final-yield deviations and do not assume every recorded brew duration corresponds to exactly 36 g.

Use brew duration and final yield jointly. A simple linear normalization may exist as a baseline only.

Reason: the user cannot reliably stop the finished beverage at exactly 36 g because of reaction time and post-stop flow.

## 2026-09-10 — Outliers

**Decision:** The model must be robust to anomalous shots and should down-weight rather than blindly follow them.

Reason: puck preparation/channeling can produce observations such as an unusually fast 15 s shot that should not trigger a huge grinder adjustment.

Manual “obviously bad shot” marking may be optional, not required.

## 2026-09-10 — Purging / retention

**Decision:** Purging is not a mandatory workflow requirement.

**Hypothesis to test:** chronological previous-setting information may let a retention/dead-space model account for the transitional effect after a grinder change.

**Constraint:** do not implement a complicated physical retention model unless out-of-sample data demonstrate useful signal.

## 2026-09-10 — Grinder adjustment abstraction

**Decision:** Separate grinder UI semantics from the statistical model.

The system should eventually accommodate:

- stepped numeric grinders;
- macro + micro systems;
- readable stepless numeric dials;
- relative/uncalibrated stepless adjustments.

Do not assume equal physical spacing between nominal grinder steps. Macro/micro ranges may overlap.

Initial hardware is a Baratza Sette 270, but the model must not become Sette-specific.

## 2026-09-10 — Existing project baseline

**Decision:** EspressoPost is the nearest known existing concept and should be treated as a baseline/reference.

The project is not justified merely by “using Bayesian/linear regression to recommend grind size.” Its potential added value is the use of actual grinder output, final yield, dose correction, robust outlier handling, and possibly chronological grinder state to improve low-waste dial-in.

## 2026-09-10 — Proof-of-concept implementation

**Decision:** Start with a local Python proof of concept instead of a production web architecture.

Preferred initial stack:

- Python;
- Streamlit;
- SQLite;
- NumPy/SciPy;
- notebooks for exploratory work;
- pytest for model tests.

Reason: the main unknown is statistical/model performance, not frontend architecture. Keep optimizer/domain logic independent from Streamlit and persistence so it can later be reused behind a web API if warranted.

## 2026-09-10 — Historical data

**Decision:** Use the existing handwritten shot history as a warm-start/analysis dataset.

Preserve chronological order and bean/session boundaries. Historical grinder-output measurements remain valid even where the puck was subsequently corrected to approximately 18 g.

Uncertain transcription must be represented as uncertain/missing rather than silently guessed.

## 2026-09-10 — Validation

**Decision:** Evaluate chronologically and prospectively. Store recommendations before outcomes are known.

Do not evaluate only by in-sample fit.

Prefer simpler models unless additional complexity demonstrably improves out-of-sample prediction or dial-in cost.

## 2026-09-11 — Methodological strategy

**Decision:** Treat the project primarily as a system-identification / adaptive-control problem with an optimisation layer, not as a generic “throw all inputs into ML” problem.

Prefer **gray-box models** where known process structure can reduce the amount of data required, while allowing unknown parameters, residuals, drift, and latent state to be learned statistically.

Simple proportional/median/heuristic baselines remain mandatory comparison points. Recursive least squares, state-space methods, Gaussian processes, and Bayesian optimisation are candidate methods to evaluate when the data support the corresponding assumptions; none is selected as the final model yet.

Reason: established control/statistical methods provide more interpretable, sample-efficient structure than an unconstrained black box, while still allowing richer behaviour to be learned from prospective data.

See `docs/research-methods.md`.

## 2026-09-11 — Learning / Experiment mode

**Decision:** Plan a first-class **Learning / Experiment mode** distinct from normal assisted dial-in.

Normal mode primarily tries to produce a good next drink with minimal waste. Learning Mode may deliberately prescribe controlled, replicated, or perturbed shots to gain information about the process.

Examples include:

- repeated identical shots to estimate process noise;
- controlled grind-duration changes at fixed setting;
- neighbouring grind-setting comparisons with corrected puck dose held approximately constant;
- first-shot-after-change versus immediate-repeat experiments;
- later return to a reference setting to test drift.

Experiment intent must be recorded before the shot and remain distinguishable from ordinary-use observations.

Initial Learning Mode should use transparent DoE-style schedules/replication. Bayesian active-learning / acquisition-function selection is a later candidate once the action space and uncertainty model are credible.

Reason: normal dial-in observations are operator-adapted and confounded. Deliberately designed experiments can separate process effects from noise with fewer, more informative shots.

## 2026-09-11 — Research and educational transparency

**Decision:** Mathematical assumptions, model updates, validation logic, and experiment rationale should be documented so that the project is understandable as a learning exercise as well as usable software.

Reason: the project is intentionally being approached as a serious modelling/control problem, and interpretability is valuable both scientifically and for deciding whether extra model complexity is justified.

## 2026-09-11 — Split research/explanation from coding-agent execution

**Decision:** Use a two-track working style by default.

Repository-aware interactive ChatGPT sessions are the preferred venue for conceptual exploration, mathematical explanations, literature synthesis, interpretation of results, and review/preparation of implementation tasks. Codex/coding agents are primarily used for bounded implementation, testing, refactoring, and reproducible execution against explicit acceptance criteria.

This is not a hard restriction on which tool may perform which task. It is a separation of objectives: educational explanation should not force production code or coding-agent prompts to become tutorial-oriented, while durable modelling rationale discovered during either workflow must still be committed to repository documentation.

Reason: this preserves implementation focus and code quality while allowing the project to remain mathematically transparent and useful as a learning exercise.

## 2026-09-14 — Corrected historical dataset is authoritative

**Decision:** Keep `data/historical_shots_staging.csv` as the auditable initial transcription, but use `data/historical_shots_corrected.csv` as the authoritative historical source for current analysis and model development.

The corrected dataset includes later user-supplied recovered/corrected entries that were not reliably inferable from the original handwritten image. Provenance notes should identify those corrections rather than retaining stale notes that claim now-populated values are missing.

Known historical bean identities are:

- sequences 1–39: Café Intención Espresso Intensivo (`cafe_intencion_espresso_intensivo`);
- sequences 40–51: REWE Bio Espresso ganze Bohnen, 1000 g (`rewe_bio_espresso_ganze_bohnen_1000g`).

The REWE Bio Espresso is also the current bean at the start of prospective/live data collection.

Existing historical-analysis metrics produced from the staging CSV remain a reproducible snapshot, not the current benchmark. They must be regenerated against the corrected dataset before being used for new model/experiment decisions.

Reason: corrected observations and known bean identities materially change eligibility/grouping and reduce avoidable uncertainty. Keeping the staging file unchanged preserves the audit trail without forcing current modelling to ignore known information.

## 2026-09-14 — Corrected historical exploration refreshed

**Source correction:** Shots 37–39 are 3D, not 3E, as confirmed by the user; macro/micro fields and provenance agree. The staging source is unchanged.

**Evidence:** [Historical analysis](historical-analysis.md) now uses the corrected source. Adjacent proportional dose MAE no longer improves on carrying output forward overall; the existing rolling median-rate comparator improves historical errors, primarily on Café Intención. Linear yield normalization remains inconsistent, and the same seven immediate transition/repeat pairs leave retention unresolved.

**Decision:** Retain the simple dose baselines for prospective evaluation; do not promote linear normalization or add retention state from these observations. Use the refreshed experiment-gap table to select designed observations. The staging analysis remains archived separately.

## 2026-09-14 — Prospective acquisition and frozen shadow predictions

**Decision:** Phase 3 uses a small local Streamlit application, typed acquisition/domain
records, and standard-library SQLite persistence. An atomic pre-grind freeze stores all
available existing dose-model candidates and exactly one selected plan, then opens a pending
shot. Explicit manual plans have no invented rate or output prediction. Actual action and
outcome entry never overwrite the planned action or frozen model.

Live compatibility remains conservative: same bean/session and the current contiguous run
of the exact actual setting; a setting change or new session resets eligible history. No
historical observations are automatically pooled into live sessions. Both baselines remain
comparators, with no winner declared. Bad-brew flags retain the raw grinder-output observation.

`NONE` and `TO_TARGET` leave the separate measured-puck field null; their declarations retain
unchanged-output versus approximate-target semantics. `MEASURED` requires a separately weighed
mass. Approximate target correction still has no invented numerical precision or uncertainty.

**Rationale:** prospective provenance requires reproducible sources as well as fixed model
records. Session context and completed outcomes therefore have no edit/delete flow in this
phase. Saved grinding results are final through the application; a future correction or
abandonment flow needs an explicit audit trail. Shadow rates can later be scored at the actual
duration only when the actual setting matches; they do not reveal unexecuted action outcomes.

See [live-workflow.md](live-workflow.md). Phase 4, extraction optimisation and automatic
grinder-setting selection remain unimplemented.

## Open decisions

The following are intentionally unresolved:

- exact representation of target-time behavior when final yield differs from 36 g;
- best robust regression/error model;
- whether retention features add meaningful predictive value;
- exact grinder-setting representation/calibration for the Sette 270;
- acceptable target bands for dose/yield when benchmarking “dialed in”;
- how much uncertainty to assign to a puck dose that was manually corrected “to approximately 18 g”;
- exact first Learning-Mode experiment plan and stopping criteria;
- when/if recursive forgetting should be introduced for drift;
- whether a Gaussian-process surrogate has enough prospective data and a defensible grinder-distance representation to be useful;
- when Bayesian optimisation provides enough value over transparent DoE schedules to justify autonomous experiment selection;
- whether taste/preference optimization is worth pursuing after objective dial-in works.
