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

## Open decisions

The following are intentionally unresolved:

- exact representation of target-time behavior when final yield differs from 36 g;
- best robust regression/error model;
- whether retention features add meaningful predictive value;
- exact grinder-setting representation/calibration for the Sette 270;
- acceptable target bands for dose/yield when benchmarking “dialed in”;
- how much uncertainty to assign to a puck dose that was manually corrected “to approximately 18 g”;
- whether the first usable application needs Streamlit immediately or should begin as notebook/CLI analysis over historical data;
- whether taste/preference optimization is worth pursuing after objective dial-in works.
