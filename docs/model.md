# Modelling notes

This document records the current mathematical framing. It intentionally distinguishes **established requirements** from **hypotheses to test**.

## 1. Variables

For shot `n`, observable inputs and outputs are initially:

- `G_n`: grinder setting;
- `t_grind_n`: grind duration;
- `D_out_n`: grinder output mass;
- `D_puck_n`: mass actually brewed;
- `t_brew_n`: recorded brew duration;
- `Y_n`: final beverage yield.

Default target:

- `D_puck* = 18.0 g`;
- `Y* = 36.0 g`;
- acceptable target brew time `30–35 s`, nominal center `32.5 s`.

The control outputs are initially:

- next grinder setting;
- next grind duration.

An exact pump-stop mass is **not** available in the MVP.

## 2. Two coupled but separable problems

### 2.1 Grinder-output model

Learn the grinder output produced by grind duration and setting:

```text
D_out = f(t_grind, G, grinder_state, bean/session, ...) + error
```

A trivial first baseline is proportional correction:

```text
t_new = t_old * target_dose / measured_output
```

A slightly richer model can include grinder setting because mass flow may vary with adjustment.

### 2.2 Extraction / flow model

The user normally corrects the puck to approximately 18 g while dialing in. This intentionally reduces confounding and lets the extraction model focus primarily on grinder setting:

```text
flow / time-to-target = g(G_effective, D_puck, bean/session, ...) + error
```

Because the final yield is not exactly 36 g, `t_brew` must not be treated as if every shot ended at the same yield.

## 3. Using final yield rather than discarding it

A recorded pair such as:

```text
31 s, 34 g
```

contains different information from:

```text
31 s, 38 g
```

although the brew duration is identical.

The quantity of interest is approximately:

```text
T_36 = time required for a 36 g final yield
```

but `T_36` is not directly observed whenever the actual final yield differs from 36 g.

### Baseline normalization

A deliberately crude baseline can estimate:

```text
T_36_approx = t_brew * 36 / Y
```

This assumes approximately constant average flow and is not physically exact. It is useful only as a baseline to test against richer models.

### Preferred direction

Use `(t_brew, Y)` jointly and learn the relationship empirically. Do not hard-code linear yield/time scaling unless tests show it is adequate.

## 4. Dose correction

Dose correction is a first-class part of the workflow.

Example:

```text
grind setting: 5E
grind duration: 9.65 s
grinder output: 17.4 g
corrected to target: yes
puck dose: approximately 18.0 g
```

This one observation provides useful information to two different models:

```text
(5E, 9.65 s) -> 17.4 g        # grinder-output model
5E, ~18.0 g -> brew behavior  # extraction model
```

The correction should therefore never overwrite the original grinder-output mass.

For an approximate `TO_TARGET` correction, the brewed dose should carry uncertainty rather than false precision, e.g. conceptually:

```text
D_puck ~ Normal(18.0 g, sigma_dose)
```

The exact uncertainty is to be chosen empirically/configurably; it should not be invented as measurement precision.

## 5. Robustness to bad shots

Puck preparation introduces unobserved disturbance variables: tamping, distribution, channeling, etc.

A single abnormal result such as `15 s -> 36 g` should not cause an aggressive grinder correction.

The model should therefore use robust estimation rather than ordinary least squares alone. Candidate approaches:

- Huber loss;
- Student-t residual model;
- other robust M-estimators;
- uncertainty inflation for highly surprising observations.

Desired behavior:

- an anomalous shot is down-weighted, not automatically deleted;
- the user may optionally flag an obviously failed shot;
- manual flags should not be required for normal operation.

A useful UI message may be: “Unusual shot; this observation has reduced influence on the next recommendation.”

## 6. Retention / dead-space hypothesis

Purging simplifies the mathematics but wastes coffee. A research goal is to determine whether previous grinder state can be modelled well enough that purging is optional.

A simple latent-state model could be:

```text
G_effective_n = lambda * G_effective_(n-1) + (1 - lambda) * G_n
```

or an equivalent parameterization based on the previous setting/change.

A simpler regression test before introducing a latent model is:

```text
T_n = beta0 + beta1 * G_n + beta2 * (G_n - G_(n-1)) + error
```

If the previous-setting term has little predictive value out of sample, drop the retention model.

Important caveats:

- retention is unlikely to be a single exact constant mass;
- exchange retention, static effects and delayed release may depend on beans and grind setting;
- do not build a detailed physical grinder simulation unless data justify it.

## 7. Grinder abstraction

The statistical model should not be coupled to one manufacturer's labels.

Internally distinguish the **user-facing adjustment system** from a latent fineness coordinate / ordered action space.

Supported conceptual grinder types:

### 7.1 Stepped numeric

Example `1..36`, with configurable direction (`1` finer or coarser).

The model initially assumes ordering, not necessarily equal physical spacing between numbered steps.

### 7.2 Macro + micro

Example: Baratza Sette 270-style adjustment with a coarse and a fine control.

Represent the setting structurally, e.g.:

```text
GrindSetting(macro=5, micro="F")
```

Do not flatten to a supposedly linear number unless calibration justifies that mapping. Adjacent macro ranges may overlap. Exact Sette ordering/overlap should be verified experimentally or against reliable documentation before hard-coding behavior.

The grinder adapter can translate an internal desired change into a realizable action such as a micro adjustment or macro change plus micro repositioning.

### 7.3 Numeric stepless

A continuous dial with readable numeric position, e.g. `4.35 -> 4.18`.

### 7.4 Relative / uncalibrated stepless

Fallback when no absolute position can be read. The user reports reproducible relative changes (“one unit finer”). This is inherently noisier and should be represented with greater uncertainty.

## 8. Model progression

Do not start with maximum complexity.

Suggested progression:

1. **Heuristic baseline**
   - too fast -> finer;
   - too slow -> coarser;
   - dose too low -> longer grind;
   - dose too high -> shorter grind.

2. **Simple regression**
   - dose from grind duration/setting;
   - target-time estimate from grind setting plus observed yield/time.

3. **Robust regression**
   - reduce sensitivity to channeling and other outliers.

4. **Retention-aware model**
   - only if chronological data show useful previous-state signal.

5. **Bayesian / Gaussian-process / preference model**
   - only if uncertainty handling or later taste optimization demonstrably benefits.

## 9. Taste optimization (later)

The initial target is objective dial-in, not sensory optimization.

A later system could accept a low-friction binary preference such as:

```text
liked / disliked
```

or pairwise preference:

```text
shot A better than shot B
```

This can support classification / preference learning without forcing detailed tasting scores. It is a stretch goal, not an MVP requirement.

## 10. Guiding principle

The project should optimize **information and coffee efficiency**, not mathematical sophistication.

The useful question is not “can we fit a complicated model?” but:

> Can the next recommendation reach the target with fewer shots / fewer grams of coffee than a competent simple dial-in heuristic?
