# Modelling notes

This document records the current mathematical framing. It intentionally distinguishes **established requirements** from **hypotheses to test**.

Project-wide symbols are defined in [`notation.md`](notation.md). Method-specific symbols introduced only in this document are defined where they first appear. Mathematical notation uses GitHub's LaTeX/MathJax-compatible Markdown syntax: `$...$` inline and fenced `math` blocks for display equations.

## 1. Core variables and conventions

For shot $n$, the primary observed variables are:

- $G_n$: grinder setting actually used;
- $t_{\mathrm{grind},n}$: actual grind duration;
- $D_{\mathrm{out},n}$: raw grinder output mass;
- $D_{\mathrm{puck},n}$: mass actually brewed after any manual correction;
- $t_{\mathrm{brew},n}$: recorded brew duration;
- $Y_n$: final beverage yield.

The full definitions, units and target notation are centralized in [`notation.md`](notation.md). In particular, $G_n$ is **not** assumed to be a linearly spaced numeric fineness coordinate.

Default target:

- $D_{\mathrm{puck}}^*=18.0\,\mathrm g$;
- $Y^*=36.0\,\mathrm g$;
- acceptable target brew time $30$–$35\,\mathrm s$, nominal center $32.5\,\mathrm s$.

The control outputs are initially:

- next grinder setting;
- next grind duration.

An exact pump-stop mass is **not** available in the MVP.

Two conceptual context/state placeholders appear below:

- $B_n$: known bean/session context for shot $n$;
- $\mathbf z_n^{(g)}$: additional grinder-related state/context;
- $\mathbf z_n^{(e)}$: additional extraction/brew state/context.

These placeholders do **not** imply that all possible state variables are observed or useful. Concrete models must replace them with explicit measured features and/or a defined latent state. See [`notation.md`](notation.md) for examples.

## 2. Two coupled but separable problems

### 2.1 Grinder-output model

Conceptually, learn the raw grinder output produced by grind duration, grinder setting and any justified context/state:

```math
D_{\mathrm{out},n}
=
f_D\!\left(t_{\mathrm{grind},n},G_n,B_n,\mathbf z_n^{(g)}\right)
+
\varepsilon_n^{(D)}.
```

Here $f_D(\cdot)$ is the unknown grinder-output mapping and $\varepsilon_n^{(D)}$ is residual grinder-output disturbance/noise not explained by the current model.

A trivial first baseline is proportional correction. In generic, index-free notation:

```math
t_{\mathrm{new}}
=
t_{\mathrm{old}}
\frac{D_{\mathrm{out}}^*}{D_{\mathrm{old}}}.
```

Here $D_{\mathrm{out}}^*$ is the target raw grinder output and $D_{\mathrm{old}}$ is the previously measured raw output. The currently implemented baseline is documented more precisely in [`dose-control-baseline.md`](dose-control-baseline.md).

A slightly richer model can include grinder setting because mass flow may vary with adjustment.

The preferred longer-term family is a structured/gray-box model rather than an unconstrained black box, e.g. conceptually:

```math
D_{\mathrm{out},n}
=
t_{\mathrm{grind},n}\,r(G_n,B_n,\ldots)
+
h\!\left(\mathbf z_{n-1}^{(g)},G_n\right)
+
\varepsilon_n^{(D)}.
```

Here:

- $r(\cdot)$ is a learned grinder-output-rate function, typically in g/s;
- $h(\cdot)$ is an optional history/transition correction, for example a retention-related effect;
- the ellipsis means additional variables only if a concrete model names and justifies them.

Neither $h$ nor any particular component of $\mathbf z_n^{(g)}$ should be introduced without prospective evidence.

### 2.2 Extraction / flow model

The user normally corrects the puck to approximately $18\,\mathrm g$ while dialing in. This intentionally reduces confounding and lets the extraction model focus primarily on grinder setting while still retaining actual puck dose and final yield.

A high-level vector-valued model is:

```math
\begin{pmatrix}
t_{\mathrm{brew},n}\\
Y_n
\end{pmatrix}
=
f_E\!\left(G_n,D_{\mathrm{puck},n},B_n,\mathbf z_n^{(e)}\right)
+
\boldsymbol\varepsilon_n^{(E)}.
```

Here $f_E(\cdot)$ is the unknown extraction/flow mapping and $\boldsymbol\varepsilon_n^{(E)}$ is the residual disturbance for the jointly modelled brew-duration/yield outcome.

Because final yield is not exactly $36\,\mathrm g$, $t_{\mathrm{brew},n}$ must not be treated as if every shot ended at the same yield.

## 3. Using final yield rather than discarding it

A recorded pair such as $31\,\mathrm s / 34\,\mathrm g$ contains different information from $31\,\mathrm s / 38\,\mathrm g$, although the brew duration is identical.

The quantity of interest is approximately $T_{36}$: the time required to reach a $36\,\mathrm g$ beverage yield under a defined measurement convention. In the historical data, $T_{36}$ is not directly observed whenever actual final yield differs from $36\,\mathrm g$.

### Baseline normalization

A deliberately crude baseline can estimate:

```math
T_{36}^{\mathrm{linear}}
=
t_{\mathrm{brew}}\frac{36}{Y}.
```

This assumes approximately constant average flow and is not physically exact. Historical analysis did not show consistent improvement from this normalization, so it must not be promoted to ground truth.

### Preferred direction

Use $(t_{\mathrm{brew}},Y)$ jointly and learn the relationship empirically. Do not hard-code linear yield/time scaling unless new evidence shows it is adequate.

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

```math
(G=5E,\;t_{\mathrm{grind}}=9.65\,\mathrm s)
\longrightarrow
D_{\mathrm{out}}=17.4\,\mathrm g,
```

and, after correction,

```math
(G=5E,\;D_{\mathrm{puck}}\approx18.0\,\mathrm g)
\longrightarrow
\text{brew behaviour}.
```

The correction should therefore never overwrite the original grinder-output mass.

For an approximate `TO_TARGET` correction, the brewed dose should carry uncertainty rather than false precision, e.g. conceptually:

```math
D_{\mathrm{puck},n}
\sim
\mathcal N\!\left(D_{\mathrm{puck}}^*,\sigma_{\mathrm{dose}}^2\right).
```

Here $\sigma_{\mathrm{dose}}$ would be the standard deviation representing uncertainty in the approximately corrected puck dose. Its value is not currently known and must be estimated or configured explicitly rather than invented as measurement precision.

## 5. Robustness to bad shots

Puck preparation introduces unobserved disturbance variables: tamping, distribution, channeling, etc.

A single abnormal result such as $15\,\mathrm s\rightarrow36\,\mathrm g$ should not cause an aggressive grinder correction.

The model should therefore use robust estimation rather than ordinary least squares alone where richer regression is introduced. Candidate approaches:

- Huber loss;
- Student-$t$ residual model;
- other robust M-estimators;
- uncertainty inflation for highly surprising observations.

Desired behavior:

- an anomalous shot is down-weighted, not automatically deleted;
- the user may optionally flag an obviously failed shot;
- manual flags should not be required for normal operation.

A useful UI message may be: “Unusual shot; this observation has reduced influence on the next recommendation.”

## 6. Retention / dead-space hypothesis

Purging simplifies the mathematics but wastes coffee. A research goal is to determine whether previous grinder state can be modelled well enough that purging is optional.

### Possible latent effective-fineness model

A simple latent-state idea could be expressed only **after** a defensible numerical fineness representation $z(G)$ has been established:

```math
z_n^{\mathrm{effective}}
=
\lambda z_{n-1}^{\mathrm{effective}}
+
(1-\lambda)z(G_n),
```

where:

- $z(G_n)$ maps the user-facing grinder setting to a validated numerical/latent fineness coordinate;
- $z_n^{\mathrm{effective}}$ is a hypothetical effective fineness after transition/retention effects;
- $0\leq\lambda\leq1$ controls persistence of the previous state.

This is a **hypothesis**, not a currently valid Sette representation. In particular, arithmetic such as $G_n-G_{n-1}$ is not meaningful while grinder settings remain opaque/categorical labels.

### Simpler transition-feature test first

Before introducing a latent state, test whether explicit current-setting and transition features add predictive value:

```math
t_{\mathrm{brew},n}
=
\beta_0
+
\boldsymbol\beta_G^{\mathsf T}\boldsymbol\phi(G_n)
+
\boldsymbol\beta_{\Delta}^{\mathsf T}\boldsymbol\psi(G_{n-1},G_n)
+
\varepsilon_n.
```

Here:

- $\boldsymbol\phi(G_n)$ encodes the current setting without assuming equal physical step spacing;
- $\boldsymbol\psi(G_{n-1},G_n)$ encodes the setting transition, for example changed/not-changed or structured macro/micro features;
- $\boldsymbol\beta_G$ and $\boldsymbol\beta_{\Delta}$ are learned coefficient vectors;
- $\varepsilon_n$ is residual brew-time disturbance for this illustrative regression.

If transition features have little prospective/out-of-sample value, do not add a retention model merely because one is physically plausible.

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

A simple second-order response-surface model illustrates what a structured DoE may estimate. Let $q_1,\ldots,q_p$ be $p$ quantitative experimental factors and let $y$ be the measured response:

```math
y
=
\beta_0
+
\sum_{i=1}^{p}\beta_i q_i
+
\sum_{i=1}^{p}\beta_{ii}q_i^2
+
\sum_{i=1}^{p-1}\sum_{j=i+1}^{p}\beta_{ij}q_i q_j
+
\varepsilon.
```

Here $\beta_0$ is the intercept, $\beta_i$ are main-effect coefficients, $\beta_{ii}$ are quadratic coefficients, $\beta_{ij}$ are pairwise interaction coefficients, and $\varepsilon$ is residual experimental variation.

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

A later system could accept a low-friction binary preference such as `liked / disliked` or a pairwise preference such as `shot A better than shot B`.

This can support classification / preference learning without forcing detailed tasting scores. It is a stretch goal, not an MVP requirement.

## 12. Guiding principle

The project should optimize **information and coffee efficiency**, not mathematical sophistication.

The useful question is not “can we fit a complicated model?” but:

> Can the next recommendation reach the target with fewer shots / fewer grams of coffee than a competent simple dial-in heuristic, or can a deliberate experiment buy enough information to improve future recommendations?

Prefer **gray-box modelling** where useful process structure is known, and let data learn the parts we do not know. A flexible model should not be rewarded for rediscovering obvious structure at the cost of sample efficiency.
