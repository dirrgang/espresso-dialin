# Prospective dose-control baseline

This is the first deployable grinder-output baseline. It recommends grind duration for
a target grinder output, initially 18.0 g. It does not recommend grind settings or model
extraction.

## Controllers

Both controllers implement the typed `DoseController` interface in
`espresso_dialin.dose_control` and return the same serializable recommendation record.

### Last-shot proportional

Use the most recent earlier compatible observation:

```text
rate = previous_output / previous_duration
next_duration = target_output / rate
              = previous_duration * target_output / previous_output
```

### Past-only median rate

Use all earlier compatible observations:

```text
rate_i = output_i / duration_i
rate = median(rate_i)
next_duration = target_output / rate
```

Neither result is silently clamped. Targets and observed measurements must be finite and
positive. Missing duration or output remains explicit and makes that observation unusable
for dose control. With no usable compatible history, the controller raises
`InsufficientDoseHistoryError` rather than borrowing unrelated data.

## Compatibility and chronology

The initial `ExactDoseCompatibility` policy requires equality of every one of:

- bean identity;
- session identity, including `None` only matching `None`;
- contiguous block identity;
- exact, opaque grinder-setting label.

The controllers also require an observation sequence strictly below the target sequence.
They therefore reject future observations even if a caller supplies them. Grinder-setting
labels are categorical: no Sette macro/micro ordering, spacing, or overlap is assumed.

Compatibility is a protocol supplied to a controller, so a later validated policy can relax
these rules without changing either algorithm. The default does not pool across beans,
sessions, blocks, or settings to increase sample size.

## Prospective record and scoring

`DoseRecommendation` records the model identifier/version, context, target and recommended
duration, estimated rate, expected output, exact source observation IDs, observation count,
and latest included sequence. Its local ID is a deterministic hash of the model, target
context, and history. `created_at` accepts a timezone-aware timestamp; it is `None` for the
historical reconstruction because no real pre-shot creation time exists. Stable dict/JSON
serialization is provided for later SQLite persistence.

Both models expect the target output at their recommended duration by construction. That is
not an uncertainty claim. No uncertainty interval is emitted.

`score_recommendation` does not refit. It applies the stored rate to the duration actually
used, then reports predicted and actual output, prediction-minus-actual signed error,
absolute error, and whether actual output is within a target band. Its 0.2 g default is named
and documented as provisional; comparative trial tolerances must be fixed before results are
examined.

## Historical rolling evaluation

Run the current evaluation with:

```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; from espresso_dialin.historical import load_shots, rolling_dose_report; print(rolling_dose_report(load_shots(Path('data/historical_shots_staging.csv'))))"
```

For each eligible historical shot, each controller receives the dataset but internally uses
only compatible observations with lower sequence numbers. Its stored rate predicts output at
the **actual historical duration**. The independently reported recommended duration is a
counterfactual action and is not assigned the actual shot's outcome.

This produces 22 predictions per strategy: 21 in `unknown_pre_bio` / historical block 0 and
one in `new_bio_espresso` / block 1. This exceeds the earlier analysis's 17 adjacent pairs
because the controller may use the latest earlier exact-setting observation across intervening
settings or incomplete rows, while never crossing a bean/block boundary.

| Block | Strategy | n | MAE (g) | RMSE (g) | Median absolute error (g) |
| --- | --- | ---: | ---: | ---: | ---: |
| All | Last-shot proportional | 22 | 0.835 | 1.017 | 0.757 |
| All | Past-only median rate | 22 | 0.732 | 0.975 | 0.487 |
| Earlier label / block 0 | Last-shot proportional | 21 | 0.851 | 1.036 | 0.815 |
| Earlier label / block 0 | Past-only median rate | 21 | 0.743 | 0.992 | 0.476 |
| New bio / block 1 | Last-shot proportional | 1 | 0.497 | 0.497 | 0.497 |
| New bio / block 1 | Past-only median rate | 1 | 0.497 | 0.497 | 0.497 |

Median-rate is numerically better overall, particularly on median absolute error, but it does
not materially establish superiority. There are only 22 non-independent rolling predictions,
21 come from one incompletely identified block, both strategies are identical when only one
prior observation exists, and the second block contributes one comparison. No controller
action outcome is observed unless the historical action happened to match it.

Other limitations remain: operator-adapted observational data, missing and approximate
transcription, unknown earlier bean/session boundaries, changing bean age and grinder state,
and no randomized duration interventions. These metrics test rate/output prediction, not
closed-loop convergence, coffee saved, or shots-to-target.

## Prospective collection

For every new bean/session/block:

1. Choose one controller according to a comparison schedule fixed before the shot.
2. Create and persist its recommendation before grinding, including timestamp and all source
   observation IDs.
3. Use the exact recorded setting and recommended duration as closely as practical; record
   the actual duration rather than silently replacing it with the recommendation.
4. Weigh and retain raw grinder output, then separately record any correction to puck dose.
5. Score the frozen recommendation against actual duration/output without refitting on that
   shot.
6. Add the shot to history only after scoring, then create the next recommendation.

Record deviations and failures rather than deleting them. Compare both prediction error and
closed-loop outcomes such as corrections, shots-to-target, and coffee-to-target. Alternate or
randomize controllers across comparable new sessions where practical; do not switch based on
which method would have looked better after seeing an outcome.
