# Historical exploration — corrected source, 2026-09-14

The corrected data support retaining the simple dose baselines, but do not demonstrate controller savings, reliable linear yield normalization, or retention predictive value. More observations change the numerical comparisons without resolving the observational confounding.

## Reproduction and provenance

Current source: `data/historical_shots_corrected.csv`, with user-supplied corrections and recovered values. Shots 37–39 use 3D (macro 3, micro D), as confirmed by the user on 2026-09-14 and recorded in their provenance notes. The staging CSV remains unchanged. The [2026-09-11 staging analysis](historical-analysis-staging-2026-09-11.md) is preserved as an archived snapshot, not a current benchmark.

CSV SHA256: `36bf1f7e09520e61d0beb776217bf05ab51d6ae2e5ba0d697485df91eb2b69cd`.

Install `.[dev,analysis]` and execute:

```sh
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_historical_exploration.ipynb
```

The notebook records Python and the source hash, displays exclusions, grouped statistics, sensitivity tables and chronological comparisons, and produces three figures. Reusable calculations remain in `src/espresso_dialin/historical.py`. Outputs are cleared for version control; numerical findings are retained here. Project symbols are defined in [notation.md](notation.md).

Validation on Python 3.14.3: all eight notebook code cells executed successfully and all three figures were visually checked. Ruff lint/format, strict mypy, and all 71 tests passed (99% coverage). A pre-existing formatting issue in the historical-data test was corrected without changing test behavior.

## Audit and eligibility

All 51 rows remain in chronological order: 39 Café Intención Espresso Intensivo and 12 REWE Bio Espresso ganze Bohnen, 1000 g. There are 44 `ok`, six `partial`, and one `approximate` rows. Bean blocks are not verified sessions.

| Eligible observations | Café Intención | REWE | Total |
| --- | ---: | ---: | ---: |
| Positive grind duration + output, also with known setting | 38 | 12 | 50 |
| Positive brew time + yield | 35 | 11 | 46 |
| Primary extraction, usable puck interpretation | 34 | 11 | 45 |
| Repeated extraction shots / groups | 33 / 7 | 4 / 2 | 37 / 9 |
| Adjacent compatible dose pairs | 27 | 2 | 29 |
| Past-only exact-setting extraction comparisons | 26 | 2 | 28 |
| Immediate change/repeat pairs | 6 | 1 | 7 |

Relative to staging, output eligibility increases 41 → 50, primary extraction 40 → 45, adjacent dose pairs 17 → 29, and rolling extraction comparisons 23 → 28. These are changes in sample composition, not model improvements.

All settings and grind durations are now populated. Remaining measurement blanks: grinder output 1 (14); brew duration 3 (26, 33, 37); final yield 5 (26, 33, 36, 37, 50). Blank notes (36) are not missing measurements. Shot 14 also has UNKNOWN correction and is excluded from primary extraction despite its entered 18 g. Row 28 now has TO_TARGET correction. All primary extraction observations retain approximate 18 g corrected puck interpretation; raw output is never substituted for puck dose. Accepting shot 14's dose only in sensitivity raises extraction eligibility to 46. No imputation is applied.

Shot 40's approximate grinder output remains included; excluding it changes the rate summary but no adjacent dose pair. This sensitivity does not quantify general measurement uncertainty.

## Grinder output and dose baselines

| Output rate (g/s) | n | Mean | Median | Sample SD | Range |
| --- | ---: | ---: | ---: | ---: | --- |
| Café Intención | 38 | 1.879 | 1.885 | 0.092 | 1.636–2.016 |
| REWE | 12 | 1.913 | 1.856 | 0.181 | 1.691–2.203 |

These spreads mix settings and chronology. Café Intención 3H has four identical 9.7 s grinds spanning 17.9–18.6 g (SD 0.289 g). At 3E, seven 9.65 s grinds span 16.74–19.45 g (SD 0.910 g), two 9.5 s grinds span 17.89–18.37 g (SD 0.339 g), and five 9.4 s grinds span 17.66–18.76 g (SD 0.415 g). At 3D, shots 38–39 repeat 9.5 s with 17.7–17.9 g output (SD 0.141 g). REWE has no replicated identical-setting/duration output condition. These establish descriptive variability, not isolated causal effects or pure measurement noise.

For adjacent same-setting, same-block observations, the proportional model predicts current output using previous output rate multiplied by current **actual** duration. The comparator carries forward previous output. Recommendations target 18 g but their unobserved outcomes are never scored as historical facts. Errors are prediction minus observation.

| Adjacent dose sample | n | Proportional MAE / RMSE (g) | Carry-output MAE / RMSE (g) |
| --- | ---: | ---: | ---: |
| Café Intención | 27 | 0.698 / 0.865 | 0.658 / 0.856 |
| REWE | 2 | 0.881 / 0.961 | 1.185 / 1.326 |
| Overall | 29 | 0.711 / 0.872 | 0.694 / 0.896 |

Only 12 pairs change duration; the other 17 give identical predictions for both methods. Proportional median absolute error is 0.600 g. Unlike the staging comparison, proportional MAE is now slightly worse overall than carrying output forward, while RMSE is slightly better. Neither method dominates; proportionality is not established as a physical law or controller benefit.

The existing rolling controllers use earlier exact-setting history within a bean block, including nonadjacent visits. They produce 33 matched predictions, a different sample from the adjacent analysis:

| Rolling controller | n | MAE (g) | RMSE (g) | Median absolute error (g) |
| --- | ---: | ---: | ---: | ---: |
| Last-shot proportional | 33 | 0.761 | 0.922 | 0.629 |
| Past-only median rate | 33 | 0.675 | 0.866 | 0.495 |

Café Intención supplies 30 predictions (MAE 0.763 vs 0.668 g); the three REWE predictions are identical for both methods (MAE 0.746 g). The median-rate improvement is descriptive historical evidence for retaining this simple comparator, not proof of generalization, significance, closed-loop convergence or coffee savings. No intervals are emitted or calibration evaluated.

## Extraction and yield normalization

The derived approximation is:

```math
T_{36}^{\mathrm{linear}}=t_{\mathrm{brew}}\frac{36}{Y}.
```

It assumes constant average flow, not measured time-to-target. Shot 9 remains 28 s at 43 g, giving 23.44 s on this derived scale. Actual yields span 33–43 g for Café Intención and 33.7–36.5 g for REWE among positive time/yield pairs.

Repeated groups match exact categorical setting, contiguous bean block, and puck interpretation/target. Pooled within-group sample variance is weighted by group size minus one.

| Bean | Repeated shots / groups | Pooled SD raw → normalized (s) | Conditional MAE raw → normalized (s) | Conditional RMSE raw → normalized (s) |
| --- | ---: | ---: | ---: | ---: |
| Café Intención | 33 / 7 | 5.891 → 6.138 | 5.692 → 5.915 | 7.917 → 8.511 |
| REWE | 4 / 2 | 12.500 → 11.544 | 15.500 → 14.201 | 17.678 → 15.922 |

The chronological comparison uses expanding medians from earlier eligible same-setting/block/puck observations (minimum one prior), with 26 Café Intención and two REWE held-out shots. Raw prediction is past median brew time. Normalized prediction is past median linear T36 multiplied by **held-out observed final yield / 36**, scored against current raw time. Thus it is conditional reconstruction using an outcome-side measurement, not a deployable next-shot normalized forecast. No future outlier screen enters prediction.

Normalization still worsens the larger bean block's pooled spread and conditional error while improving the tiny REWE sample. Reduced spread would not establish accuracy of true T36 even where observed. Preserve yield jointly with brew time, but do not promote linear normalization to ground truth. Matching settings across beans remain incomparable as replicates: Café Intención 3G has 24–25 s versus REWE's 80 s; 3I has 26–30 s versus 67 s. This cautions against pooling without establishing a causal bean effect.

## Robustness and chronology

The retrospective screen uses absolute modified z-score `0.67448975 * abs(value - median) / MAD`, with unscaled MAD, threshold 3.5, and at least five observations per extraction group. Zero MAD is unscorable. Café Intención 3E (13 observations) and 3D (five) qualify, giving 18 screened observations per time metric; no flags occur. All observations remain included. Absence of flags does not demonstrate absence of preparation problems. The 24 s repeat differences at Café Intención 3F and REWE 4E remain too sparsely replicated to diagnose an outlier; REWE 5H's 17 s singleton is not known channeling.

There are 49 known adjacent transitions and 43 extraction-eligible current shots with known previous setting (18 changed, 25 unchanged). Setting 50 is recovered, so 50 → 51 is now known; missing yield on 50 still blocks an extraction repeat comparison. The correction creates a 3E → 3D transition at 36 → 37, removing that pair from adjacent same-setting dose scoring. Missing extraction on 37 prevents a new first/repeat extraction pair. Bean boundaries reset history, and missing outcomes are not bridged.

The seven first-after-change/immediate-repeat pairs remain 7→8, 10→11, 16→17, 18→19, 20→21, 23→24, and 47→48. Repeat-minus-first linear T36 differences are −4.63, +0.26, −1.65, −5.36, +15.16, +2.61, and −6.90 s. Mixed direction and adapted setting/preparation choices prevent attribution to retention. More known transitions have not supplied additional informative immediate pairs. Retention is unresolved, not disproven; no credible held-out previous-setting ablation is established here.

## Conclusions and experiment gaps

| Question | Corrected-data conclusion | Remaining evidence needed |
| --- | --- | --- |
| Repeatability | Several replicated Café Intención output conditions already show variability; REWE lacks identical-duration/setting repeats | Replication in the current bean/session where uncertainty matters |
| Duration response | Multiple durations and 12 changing-duration adjacent pairs inform a baseline, but are operator-adapted | Controlled, replicated duration variation at fixed setting; enough separation to test intercept/nonlinearity |
| Setting affects output rate | Descriptive differences remain confounded with time and duration | Controlled comparable-duration setting contrasts with replication |
| Linear yield normalization | No consistent benefit; larger block worsens | Prospective joint brew-time/yield validation with an explicit target convention |
| Robust prediction | Substantial variation motivates caution; a MAD screen diagnoses no bad shots | Chronological/prospective comparison of robust predictors against simple baselines |
| Retention | Still only seven immediate pairs, no identified predictive benefit | Repeated planned transitions and immediate repeats, with session/purge context recorded |
| Dose controller savings | Median-rate historical prediction improves, mainly on Café Intención | Recommendations frozen before outcomes and prospective shots/coffee-to-target trials |

Known bean identity removes one earlier uncertainty. Sessions, timestamps, ageing, purge/hopper state and preparation remain unrecorded; corrected puck doses remain approximate. Overlapping rolling training histories are not independent experimental trials. No causal setting effects, physical grinder calibration, uncertainty coverage or coffee savings can be inferred.

**Next step:** use the already-implemented dose baselines in prospective acquisition, and choose Learning-Mode shots for these specific gaps. The refresh does not justify additional model complexity or a generic repetition campaign. See [next-steps.md](next-steps.md).
