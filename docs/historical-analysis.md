# First historical exploration — 2026-09-11

The historical data justify a small dose-control baseline and careful grouped descriptions. They do **not** justify adopting linear yield normalization as the extraction target, fitting a physical grind scale, or adding retention state.

## Reproduction and provenance

Source: the current handwritten transcription in `data/historical_shots_staging.csv`, unchanged by this analysis. SHA256: `882392feecf6e23e2747f6de70d656e15e73caf208d14327a11a4ec3d361ce49`.

Install `.[dev,analysis]`, then run all cells in `notebooks/01_historical_exploration.ipynb`, or:

```sh
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_historical_exploration.ipynb
```

The notebook records the input hash and interpreter, displays all analysis tables and exclusions, and plots every eligible observation. Reusable calculations are in `src/espresso_dialin/historical.py`. Notebook outputs are cleared for version control, consistent with the notebook conventions; the numerical findings are recorded here. No new dependency was needed.

Validation on Python 3.14.2: `ruff check .`, `ruff format --check .`, `mypy src`, and `pytest --cov=espresso_dialin --cov-report=term-missing` all passed (43 tests, 100% statement/branch coverage). All eight notebook code cells executed successfully, producing three figures; the local pre-commit hook was installed. In a restricted Windows environment, Jupyter/IPython/Matplotlib cache paths were directed under the ignored `.venv/` directory. This run does not establish results on other interpreters.

## Audit and usable samples

There are **51 rows**: 39 `unknown_pre_bio` and 12 `new_bio_espresso`; transcription statuses are 36 `ok`, 14 `partial`, and one `approximate` (shot 40's grinder output). These are two contiguous bean-label blocks, not two verified brewing sessions. Earlier unidentified beans may conceal additional boundaries.

| Analysis | Earlier bean label | New bio label | Total |
| --- | ---: | ---: | ---: |
| Positive grind duration + output (rate) | 30 | 11 | 41 |
| Rate with exact setting | 29 | 10 | 39 |
| Positive brew time + yield (derived $T_{36}$ available) | 35 | 11 | 46 |
| Primary extraction with usable puck interpretation and setting | 29 | 11 | 40 |
| Repeated extraction settings, at least two shots | 28 / 7 groups | 4 / 2 groups | 32 / 9 groups |
| Extraction with known immediate previous setting | 28 | 9 | 37 |
| First-after-change / immediate repeat pairs | 6 | 1 | 7 |
| Compatible adjacent dose prediction pairs | 16 | 1 | 17 |
| Past-only exact-setting extraction comparisons | 21 | 2 | 23 |
| MAD-screenable extraction observations per metric | 10 | 0 | 10 |

There are 40 known-setting adjacent transitions before extraction eligibility: 31 earlier and nine newer. Of the 37 extraction-eligible current shots, 17 follow changes (9/8 by bean label) and 20 follow unchanged settings (19/1). Rate groups with at least two observations contain 28 earlier shots across seven settings and two newer shots at one setting. The notebook also shows identical-setting, identical-duration output repeats.

| Field | Blank cells |
| --- | ---: |
| sequence | 0 |
| bean_label | 0 |
| grind_setting | 7 |
| grind_macro | 7 |
| grind_micro | 7 |
| grind_duration_s | 9 |
| grinder_output_g | 2 |
| dose_correction_mode | 0 |
| puck_dose_g | 0 |
| brew_duration_s | 3 |
| final_yield_g | 5 |
| transcription_status | 0 |
| source_region | 0 |
| notes | 36 |

Blank notes are not missing measurements. Numeric blanks remain missing; invalid/nonfinite numbers fail loading, and nonpositive measurements are ineligible for the relevant ratios. File order is preserved and sequence reversals/duplicates are rejected rather than sorted away.

Eligibility is question-specific. For example shot 2 is usable for extraction despite its missing grind duration; shot 26 is usable for output despite missing extraction measurements. Rows 14 and 28 have `UNKNOWN` correction and an 18 g puck entry; the primary analysis does not assume that default-looking entry establishes dose control. All 40 primary extraction shots have approximate `TO_TARGET` puck doses of 18 g. Raw grinder output is never used as their brewed dose. The notebook separately shows a sensitivity accepting those two uncertain doses (42 extraction candidates), without changing primary eligibility or source data. Dose uncertainty remains unquantified.

## Grinder output and proportional control

Rate mean / median / sample SD is **1.874 / 1.885 / 0.096 g/s** for the earlier group (30 shots), and **1.923 / 1.907 / 0.187 g/s** for the newer group (11). These SDs mix settings and chronology; they are not pure measurement-noise estimates. The respective ranges are 1.636–2.016 and 1.691–2.203 g/s.

At earlier 3H, four identical 9.7 s grinds yield 17.9–18.6 g (rate SD 0.030 g/s). Earlier 3E has ten output-rate observations, median 1.892 g/s and SD 0.075 g/s; earlier 3I has three, median 1.970 g/s and SD 0.023 g/s. This is evidence of variability and setting-associated differences, but operator adaptation, elapsed time and unidentified bean changes prevent attributing them to setting alone. The newer group mostly has one output-rate observation per setting. A global duration/output regression would obscure these confounders.

The dose baseline computes

```math
t_{\mathrm{new}}
=
t_{\mathrm{old}}
\frac{18}{D_{\mathrm{old}}}.
```

To evaluate its rate assumption on observed outcomes, the next output is predicted as

```math
\hat D_{\mathrm{next}}
=
\frac{D_{\mathrm{old}}}{t_{\mathrm{old}}}
t_{\mathrm{actual,next}}
```

for immediate same-setting neighbours within a block. No missing neighbour is skipped. Recommendations and actual durations are displayed separately.

| Bean label | Pairs | Proportional MAE / RMSE (g) | Carry last output MAE / RMSE (g) |
| --- | ---: | ---: | ---: |
| Earlier | 16 | 0.689 / 0.870 | 0.704 / 0.931 |
| New bio | 1 | 0.497 / 0.497 | 0.590 / 0.590 |

Across 17 pairs, proportional MAE is **0.678 g**, RMSE **0.853 g**, median absolute error **0.497 g**. Only seven pairs change grind duration; in the other ten, both baselines make the same prediction. This supports proportional control as a plausible simple baseline, not as a proven improvement or exact physical law. Small, selected duration changes cannot estimate a reliable intercept or nonlinear response. Excluding approximate shot 40 affects descriptive rate summaries but no compatible dose pair.

## Extraction and yield normalization

Actual yield ranges from **33–43 g** among 35 earlier time/yield pairs and **33.7–36.5 g** among 11 newer pairs. The linear normalization used in the analysis is

```math
T_{36}^{\mathrm{linear}}
=
t_{\mathrm{brew}}\frac{36}{Y}.
```

For shot 9, $t_{\mathrm{brew}}=28\,\mathrm s$ and $Y=43\,\mathrm g$, giving

```math
T_{36}^{\mathrm{linear}}
=
28\frac{36}{43}
\approx23.44\,\mathrm s.
```

That is a material change of interpretation, but it does not establish that $23.44\,\mathrm s$ was the actual time to $36\,\mathrm g$.

Comparison groups match exact setting, contiguous bean block, dose interpretation and dose target. No numerical spacing/order between macro/micro settings is assumed.

| Bean label | Repeated shots / groups | Pooled within-group SD, raw → $T_{36}$ (s) |
| --- | ---: | ---: |
| Earlier | 28 / 7 | 6.140 → 6.557 |
| New bio | 4 / 2 | 12.500 → 11.544 |

Pooling here weights within-group sample variances by $n-1$, never combines raw bean-group outcomes. Earlier normalization lowers SD in two of seven repeated groups and raises it in five. Examples: 3E improves slightly (4.274 → 4.199 s); 3I worsens (2.000 → 3.578 s). Both newer repeated groups improve, but each contains only two observations. Thus normalization is **not consistently variance-reducing**. Even a reduction would not prove target-time accuracy because the derived scale changes with yield.

The chronological comparison uses an expanding median of earlier eligible shots at the same setting/block/puck target (minimum one prior shot). For a common observed target, the normalized prediction maps the past median back to the current observed yield:

```math
\hat t_{\mathrm{brew,current}}
=
\operatorname{median}\!\left(T_{36,\mathrm{past}}\right)
\frac{Y_{\mathrm{current}}}{36}.
```

Both this and the raw-time median are scored against observed current brew time.

| Bean label | Held-out shots | Raw MAE / RMSE (s) | Normalized MAE / RMSE (s) |
| --- | ---: | ---: | ---: |
| Earlier | 21 | 5.810 / 8.190 | 6.221 / 9.081 |
| New bio | 2 | 15.500 / 17.678 | 14.201 / 15.922 |

Training is past-only and no retrospective outlier filter is applied. However, the normalized method uses the held-out **observed yield**, an outcome unavailable before brewing. These are conditional reconstruction errors, not deployable next-shot forecast errors or measured $T_{36}$ errors. There is no true $T_{36}$ ground truth, interval calibration, or proof of causal superiority. The mixed evidence weakens adopting linear normalization automatically, while leaving the requirement to retain yield intact.

Matching settings also vary sharply across bean labels: earlier 3G has times 25 and 24 s, versus one newer shot at 80 s; earlier 3I has 26–30 s, versus one newer shot at 67 s. These are warnings against cross-bean pooling, not estimates of a clean bean effect.

## Outliers and possible retention

The transparent robust screen uses the absolute modified z-score

```math
z_i^*
=
0.67448975
\frac{|x_i-\operatorname{median}(x)|}{\operatorname{MAD}(x)},
```

and flags $z_i^*>3.5$ within extraction comparison groups with at least five observations. MAD is unscaled in descriptive tables; zero MAD is reported as unscorable. Only earlier 3E qualifies (10 observations per time metric), and **no observations are flagged**. All shots remain included. Mean/SD alongside median/MAD document spread without pretending to know preparation quality.

Earlier 3F has a 24 s repeat difference (shots 6 and 15), and newer 4E differs by 24 s (43 and 51). Their separation in time and two-shot sample sizes preclude identifying an outlier. The newer 17 s shot at 5H is a singleton: it is not evidence of known channeling. The need to avoid overreaction remains sensible, but superiority of a particular robust predictive method is untested.

For the six earlier first-after-change/immediate-repeat pairs, repeat-minus-first $T_{36}$ differences are **−4.63, +0.26, −1.65, −5.36, +15.16, +2.61 s**. The sole newer pair is **−6.90 s**. Directions are mixed, and comparisons confound the previous setting, chosen new setting, operator decisions and shot preparation. Unknown setting 50 breaks adjacency to 51; a known bean boundary also resets history. There are too few repeated transitions to train and hold out a credible previous-setting ablation. **Retention predictive value remains untestable here**, rather than disproven.

## Conclusions and next step

| Hypothesis | Status from this dataset |
| --- | --- |
| Linear normalization consistently improves repeatability | Not supported; worsens the larger group's pooled spread and conditional errors |
| Proportional grind-duration control is a useful baseline | Plausible, noisy; no demonstrated controller benefit |
| Grind setting changes output rate | Descriptive association; causal/material predictive effect unresolved |
| Robust/outlier handling improves recommendations | Large variability motivates caution; predictive benefit untested |
| Previous-setting/retention features add value | Insufficient compatible transitions for credible validation |
| One extraction relationship transfers across beans | Strongly cautioned against by same-label differences; no pooling justified |

Limits include observational adaptation, small/uneven groups, unidentified sessions and earlier beans, missing/approximate transcription, unknown elapsed time/ageing/purge history, approximate corrected puck dose, unknown preparation quality, and absent true time-to-36-g measurements. Held-out comparisons overlap in their training histories and are not independent experimental trials. Coffee-to-target, shot savings, controller convergence and uncertainty calibration cannot be estimated honestly here.

**Single next implementation step:** implement a small typed proportional-dose baseline with a past-only same-block median-rate comparator and explicit recommendation records for prospective evaluation. Keep the initial extraction evidence categorical and descriptive; collect targeted repeated settings and durations before extraction regression or retention features. This analysis does not start that phase.
