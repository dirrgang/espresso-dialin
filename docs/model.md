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

The preferred longer-term family is a structured / gray-box model rather than an unconstrained black box, e.g. conceptually:

```text
D_out,n = t_grind,n * r(G_n, bean/session_n, ...) + h(previous_state_n, G_n) + error_n
```

where `r(...)` is a learned output-rate function and `h(...)` is an optional transition/retention term only if prospective data justify it.

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

This assumes approximately constant average flow and is not physically exact. Historical analysis did not show consistent improvement from this normalization, so it must not be promoted to ground truth.

### Preferred direction

Use `(t_brew, Y)` jointly and learn the relationship empirically. Do not hard-code linear yield/time scaling unless new evidence shows it is adequate.

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

The model should therefore use robust estimation rather than ordinary least squares alone where richer regression is introduced. Candidate approaches:

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

If a hidden temporal state eventually proves useful, the natural mathematical framework is a state-space model rather than ad-hoc history features indefinitely.

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

Do not start with maximum complexity. Add model capacity only when the data and validation question justify it.

Suggested progression:

1. **Heuristic / deterministic baselines**
   - too fast -> finer;
   - too slow -> coarser;
   - dose too low -> longer grind;
   - dose too high -> shorter grind;
   - proportional and median-rate dose controllers.

2. **Structured regression / system identification**
   - dose from grind duration and setting;
   - estimate parameters with ordinary or recursive least squares where the model is linear in parameters;
   - use forgetting/recency weighting only when drift is demonstrated or intentionally modelled.

3. **Robust regression / probabilistic residuals**
   - reduce sensitivity to channeling and other outliers;
   - quantify predictive uncertainty where it can be calibrated.

4. **State-space / retention-aware model**
   - only if prospective chronological data show useful previous-state signal.

5. **Gaussian-process or other probabilistic surrogate**
   - when the action-space representation is defensible and small-data uncertainty has clear value.

6. **Bayesian optimisation / active experimental design**
   - only when the surrogate is trustworthy enough for the algorithm to choose informative or promising next experiments.

Every richer model must be compared against the simpler model immediately below it using chronology-safe/prospective validation.

## 9. Design of Experiments and Learning Mode

Normal dial-in data are observational and operator-adapted: settings are changed because previous results were bad. This confounds process effects with the user's intervention policy.

A planned **Learning / Experiment mode** should deliberately prescribe informative shots. Examples:

- replicate the same setting/duration to estimate process noise;
- vary duration while holding grind setting constant;
- compare neighboring grind settings while keeping corrected puck dose approximately fixed;
- test the first shot after a setting change versus an immediate repeat;
- revisit a reference setting later to identify drift.

A simple second-order response-surface model illustrates what a structured DoE may estimate:

```text
y = beta_0
  + sum_i beta_i x_i
  + sum_i beta_ii x_i^2
  + sum_(i<j) beta_ij x_i x_j
  + error
```

The first Learning Mode should use transparent replicated/DoE-style experiments before using Bayesian acquisition functions. The app must record the experiment intent before the shot so that designed experiments can be distinguished from normal-use observations.

See [`research-methods.md`](research-methods.md) for the mathematical background and literature.

## 10. Normal mode versus information-seeking control

Two different objectives should remain explicit.

### Normal / assisted mode

Primary objective: maximize the probability of a good next drink while minimizing wasted coffee.

### Learning / experiment mode

Primary objective: maximize useful information about the process under practical constraints such as coffee budget, safe/realistic settings, and acceptable shot quality.

This is the classical exploration/exploitation distinction. A later Bayesian-optimisation policy can formalize it, but the distinction should exist in the data model before such a policy is implemented.

## 11. Taste optimization (later)

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

## 12. Guiding principle

The project should optimize **information and coffee efficiency**, not mathematical sophistication.

The useful question is not “can we fit a complicated model?” but:

> Can the next recommendation reach the target with fewer shots / fewer grams of coffee than a competent simple dial-in heuristic, or can a deliberate experiment buy enough information to improve future recommendations?

Prefer **gray-box modelling** where useful process structure is known, and let data learn the parts we do not know. A flexible model should not be rewarded for rediscovering obvious structure at the cost of sample efficiency.
