# Next steps

Validate modelling assumptions with prospective evidence before investing in richer models or
product architecture. This roadmap records broad phases and priorities; GitHub Issues own
task scope, acceptance criteria, dependencies and current status. See [workflow.md](workflow.md)
and the latest dated [work-log handoff](work-log.md).

## Current work packages

1. [Review and integrate the extraction-direction baseline (#17)](https://github.com/dirrgang/espresso-dialin/issues/17).
2. [Inventory available prospective evidence (#18)](https://github.com/dirrgang/espresso-dialin/issues/18).
3. [Predefine the next pilot (#19)](https://github.com/dirrgang/espresso-dialin/issues/19).
4. [Collect and assess the predefined pilot (#20)](https://github.com/dirrgang/espresso-dialin/issues/20).

Integration review and evidence inventory can proceed independently. The inventory informs
pilot selection; the issue records specify dependencies and physical operator work.

## Phase 0 — Historical dataset

Completed. The [staging CSV](../data/historical_shots_staging.csv) preserves the initial
transcription; the [corrected CSV](../data/historical_shots_corrected.csv) is authoritative
for current analysis. Bean identities and source corrections are documented in
[historical-analysis.md](historical-analysis.md). REWE Bio Espresso ganze Bohnen, 1000 g was
the bean at the start of prospective collection; do not assume it remains the current bean.

## Phase 1 — Historical exploration and gap analysis

Refreshed 2026-09-14 against the corrected source in
[the notebook](../notebooks/01_historical_exploration.ipynb) and
[historical-analysis.md](historical-analysis.md); the original staging report remains archived.
Use the corrected-source gaps and the prospective inventory in #18 to justify further
collection. Operator-adapted historical contrasts do not establish causal responses,
retention or within-session drift.

## Phase 2 — Baseline dose models

Implemented 2026-09-11: proportional dose control and the past-only same-block/exact-setting
median-rate comparator, with frozen prospective predictions and scoring. See
[dose-control-baseline.md](dose-control-baseline.md). Its historical metric values are an
older staging snapshot; current corrected-source benchmarks are in
[historical-analysis.md](historical-analysis.md). Richer grinder-output models must beat
these baselines.

## Phase 3 — Minimal prospective data-acquisition application

Implemented 2026-09-14: local Streamlit + SQLite acquisition with plans frozen before grinding,
separate planned/actual values, manual fallback, dose correction, resumable phase entry and
recent history. [live-workflow.md](live-workflow.md) owns the operating flow;
[data-model.md](data-model.md) owns persistence semantics. Tests establish acquisition
integrity, not prospective efficacy. Grind-setting selection remains manual.

## Phase 3.1 — Acquisition hardening

Implemented 2026-09-15: schema-v2 transactional migration, explicit phase-recording timestamps,
unknown legacy grinding times, bag-open context and immutable lifecycle resolutions.
The same-day schema-v3 follow-up distinguishes confirmed pre-grind non-execution from
uncertain physical grinder history while preserving the audit trail. These are historical
increments, not the current-schema specification. See [data-model.md](data-model.md),
[live-workflow.md](live-workflow.md) and [validation.md](validation.md) for authoritative
migration, maintenance and continuity semantics.

## Phase 4 — Learning / Experiment mode (infrastructure implemented; collection pending)

Implemented 2026-09-16, with the categorical extraction contrast added 2026-09-17.
Schema-v4 infrastructure freezes complete schedules and supports restartable ordinary
acquisition, deviations and early stopping. No real designed outcomes were collected in those
increments; current runtime evidence availability is the subject of #18.

[experiments.md](experiments.md) owns designs, historical gaps, coffee budgets and analysis
limits. Existing options are fixed-condition repeatability, local grind-duration response,
and categorical setting contrasts for grinder output and extraction. Select a concrete gap
through #18/#19 rather than repeating every family mechanically; #20 owns the selected pilot.

The remaining dedicated protocol tasks are:

- [Transition / retention protocol (#23)](https://github.com/dirrgang/espresso-dialin/issues/23).
- [Controlled elapsed-time drift protocol (#24)](https://github.com/dirrgang/espresso-dialin/issues/24).

These are later Phase-4 work, not a requirement to run both experiments next. Existing immediate
repeats and reference revisits do not independently identify retention or drift. Protocol
completion, physical collection and empirical identification have separate evidence criteria.
See [research-methods.md](research-methods.md) for experiment-selection discipline.

## Phase 5 — Structured system identification / richer models

Conditional research options, not committed implementation tasks. Introduce complexity only
when prospective evidence justifies a bounded comparison:

- structured grinder-output regression, including setting effects if demonstrated;
- recursive least squares if online updating is useful;
- recency weighting only with measurable drift, and robust residual handling where anomalies matter;
- learned joint use of brew duration and actual final yield for extraction;
- categorical previous-setting/change features before any justified latent retention model;
- a Gaussian-process surrogate only with adequate data and a defensible action representation.

Compare each addition with the simple baselines using chronological evaluation and ablation
tests. Grinder labels remain opaque unless a separate numeric mapping is validated. The
mathematical framing and symbols live in [model.md](model.md) and [notation.md](notation.md).
Create implementation/research issues when a specific comparison is selected.

## Phase 6 — Active experiment selection / Bayesian optimisation

Conditional on credible surrogate predictions and uncertainty. Evaluate autonomous selection
only if it can improve on transparent predefined schedules or offer useful capabilities they
lack. Possible criteria remain improvement in dial-in quality, information gain, knowledge
gradient and explicit information-versus-coffee trade-offs. Bayesian optimisation is not a
prerequisite. See [research-methods.md](research-methods.md).

## Phase 7 — Prospective closed-loop evaluation

Tracked by the deferred parent work item
[#25 — Evaluate prospective convergence and coffee use against baselines](https://github.com/dirrgang/espresso-dialin/issues/25).
Activation requires usable strategies, adequate pilot evidence and an explicit readiness
decision; richer models are optional. The parent owns completion criteria and will link
bounded protocol, operator-collection and analysis tasks when ready.

[validation.md](validation.md) owns evaluation principles. The next pilot in #20 does not
establish controller efficacy, convergence or reduced coffee use.

## Phase 8 — Decide whether to continue toward a product

Continue only if prospective evaluation demonstrates practical value. These remain options,
not delivery commitments: grinder profiles/adapters, import/export, cross-session priors or
calibration epochs, taste feedback, a PWA/API, synchronization/accounts, Bluetooth-scale or
machine integration, and pump-stop/afterflow modelling. Hardware telemetry remains a stretch
goal. Create bounded issues only when an option has a justified need and concrete scope.
