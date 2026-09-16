# Phase 4 experiment designs and evidence boundary

This increment implements collection infrastructure, not empirical validation. No real
prospective experimental outcomes were collected or fabricated by this implementation.

## Evidence checked before selecting the first experiment

The corrected CSV and `historical.research_report(load_shots(...))` were inspected on
2026-09-16. The current CSV SHA-256 is
`5eb5e14ded1a8c957147bb7e945f6469c15d7cf546d9bb04d9404bf3c09c40bc`.
The older hash in the 2026-09-14 report is a snapshot; the checks here use the current file.
The recheck reproduces 51 rows, 50 usable grinder outputs (38 Cafe Intencion / 12 REWE),
29 adjacent compatible dose pairs, 45 primary extraction rows, and seven immediate
transition/repeat pairs: 7/8, 10/11, 16/17, 18/19, 20/21, 23/24, 47/48.
The historical CSVs and the user's notebook are excluded from this implementation diff.

| Identification question | Verified historical evidence | Remaining gap / collection decision |
| --- | --- | --- |
| Fixed-condition repeatability | Cafe Intencion has eight replicated setting/duration conditions, including four 3H/9.7 s outputs and seven 3E/9.65 s outputs. REWE has none. | Estimate current-bean/session variability at a usable operating point, rather than repeat all old settings. |
| Grind-duration response | 29 adjacent pairs, only 12 with changing durations; changes were operator-adapted. | Controlled variation with replicated conditions; proportionality, intercept and curvature remain hypotheses. |
| Setting effect on output rate | Rates differ descriptively, but settings, duration and chronology vary together. | Replicated comparable-duration categorical setting contrasts remain necessary. |
| Extraction response to setting | 45 usable extraction observations; 37 shots in nine repeated setting/puck groups, but approximate puck correction and variable yield/preparation. | Controlled replicated contrasts retaining both brew duration and actual yield; no causal setting-response calibration exists. |
| Transition / retention | Seven immediate pairs, mixed direction, with adapted durations and no complete purge/session context. | Repeated deliberate transitions plus immediate repeats; neither retention nor its absence is established. |
| Within-session drift | Bean blocks are known, physical session/day boundaries and elapsed times are not. | Reference revisits within an explicit prospective session. Historical chronology alone cannot isolate drift from adaptation or state. |

Reproduction: `load_shots(Path("data/historical_shots_corrected.csv"))` and
`research_report` in `src/espresso_dialin/historical.py`; count output-eligible rows grouped
by `(bean, setting, grind_duration_s)` for identical-condition replication. The automated
historical tests continue to validate the corrected dataset. No new regression or causal
estimate is implied by this inspection.

## First offer: fixed-condition replication

Offer **three** repeats at a user-confirmed current setting and duration. The user may select
3-6 before freezing. Do not take a setting from old historical data. This is a small pilot
for the current-bean noise gap, costs approximately 54 g at an estimated 18 g per reference
grind, and can produce ordinary drinks with puck correction. Three shots provide only a
very imprecise variability estimate; they do not establish a stable noise distribution or
separate measurement noise, grinder state, and preparation variation. If compatible designed
replicates already answer the question, do not repeat this pilot mechanically.

Hold exact setting, duration, bean/session, and preparation/hopper/purge practice as constant
as practical. No purge is required. Record any interruption or extra grinding. Extraction
repeatability is secondary and interpretable only with sufficiently comparable puck dose,
preparation, and measured brew-time/yield pairs. The current builder targets grinder response;
it does not certify that all extraction controls were followed.

## Optional next design: local duration response

At one exact setting, choose a reference duration and a positive offset smaller than that
duration. The full deterministic order is:

```text
reference, low, high, reference, high, low, reference
```

Low/high are reference duration minus/plus the chosen offset **in seconds**, never arithmetic
on grinder labels. Reference, low and high each have mean sequence position four. This balances
a linear order trend while giving three reference observations and two of each varied duration.
No grinder-setting transitions or random seed are needed. Reference revisits retain an explicit
link to their earlier matching condition. The raw revisits can reveal temporal variation;
they do not by themselves prove ageing/drift or identify a retention mechanism.

Seven attempts cost approximately 126 g at an estimated 18 g reference output. The budget
assumes proportional output only for planning, excludes purge/additional correction coffee,
and is not a model prediction. Choose a practical duration separation before outcomes; the
0.5 s UI default is editable, not an empirically validated optimal perturbation. Very small
separation relative to noise will be uninformative. Even this balanced pilot can leave intercept
and local curvature uncertain; no significance, power, or precision guarantee is made.

## Stopping, deviations and analysis

The stopping rule is fixed: finish the predefined number of **attempts**, counting abandoned
and invalidated attempts, or stop early with a saved reason. No automatic replacements,
outcome-dependent extensions, or post-hoc changes to condition membership. A new study requires
a new frozen plan. `FINISHED` means all attempts are terminal, not that all requested valid
replicates exist or that a hypothesis is resolved. `STOPPED` leaves unused steps visibly unstarted.

Each step freezes an ordinary manual plan and all currently available baseline shadows before
grinding. Actual setting/duration, grinder output, correction and brewing remain the ordinary
shot evidence. Exact input mismatches are derived as deviations; the optional grinding note
records reasons, interruptions, or other unstructured deviations even if brewing is abandoned.
No floating-point tolerance or retrospective reclassification hides input differences.
Missing grinding has no numerical deviation assessment; inspect shot status/resolution too.

Switching modes or interleaving ordinary shots is allowed and remains visible through session
shot sequence and intent. Analysis must inspect the full session chronology for interruptions;
experiment step numbers are not a claim of physically uninterrupted execution. Eligible
experimental grinder observations may inform subsequent Assisted dose baselines under the
unchanged physical-continuity rules. Designed shots must be separated from Assisted shots when
evaluating normal-use efficacy, coffee-to-target, or selection-policy performance.

Programmatic extraction (read-only after repository initialization/migration):

```python
from pathlib import Path
from espresso_dialin.repository import Repository

repo = Repository(Path("data/live.sqlite3"))
experiment = repo.experiments(session_id)[0]  # use an explicitly selected real session ID
progress = repo.experiment_progress(experiment.id)
for observation in progress.observations:
    step = observation.step  # planned inputs, condition, replicate, role, reference sequence
    shot = observation.shot  # None if never started; otherwise all raw phases/resolution/times
    deviations = observation.deviations
```

`progress.experiment` retains question, stopping rule, controls, creation time and coffee estimate;
`repo.session(experiment.session_id)` supplies immutable bean/setup/target context. The optional
shot carries actual values, outcome, immutable resolution (including non-execution confirmation),
phase timestamps and deviation note. `repo.plans(session_id, shot.sequence)` supplies frozen
selected and shadow predictions. No invalidated or unstarted observations are filtered away.

## Deliberately deferred

Dedicated transition/immediate-repeat schedules and categorical setting contrasts need a
bounded protocol for previous physical setting, setup shots, intervening grinds, purge context,
and replication of the transition itself. They do **not** need a numeric setting metric, but
implementing that protocol is beyond this first increment. Explicit per-step settings and
reference links avoid locking persistence to one schedule shape. There is no generic workflow
engine, custom-design UI or unused transition taxonomy.

Dedicated drift studies with controlled elapsed intervals and other settings interposed are
also deferred. Duration-design reference revisits are available now, but acquisition timestamps
are not exact physical event times. No recency weighting, retention model, regression/RLS,
Gaussian process, acquisition function, or Bayesian optimisation is introduced.
