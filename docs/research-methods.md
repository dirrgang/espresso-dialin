# Research methods and mathematical foundations

This document records the methodological families that are most relevant to the espresso-dialin problem and explains why they may be useful. It is intentionally educational: the project should not only produce recommendations, but make the modelling assumptions and mathematics understandable and testable.

Mathematical notation in this repository uses GitHub's LaTeX/MathJax-compatible Markdown syntax: `$...$` inline and fenced `math` blocks for display equations.

Nothing in this document selects a final model. Simple baselines remain the null hypothesis that richer methods must beat prospectively.

## 1. Problem framing: system identification before optimisation

The project contains two coupled but separable systems.

For the grinder:

```math
D_{\mathrm{out},n}
=
f\!\left(G_n, t_{\mathrm{grind},n}, x^{\mathrm{grinder}}_n, B_n, \ldots\right)
+ \varepsilon^{(D)}_n
```

For extraction:

```math
\left(t_{\mathrm{brew},n}, Y_n\right)
=
g\!\left(G_n, D_{\mathrm{puck},n}, x^{\mathrm{brew}}_n, B_n, \ldots\right)
+ \varepsilon^{(E)}_n
```

where $G_n$ is grinder setting, $B_n$ denotes bean/session context, the $x_n$ terms represent possible latent process state, and the $\varepsilon_n$ terms collect residual disturbance/noise.

The first statistical task is **system identification**: infer useful approximations of the unknown functions $f$ and $g$ from observed inputs and outputs.

The second task is **control / optimisation**: given the current model and uncertainty, choose the next controllable input that best serves the current objective.

This distinction matters. A model may predict the process well without providing a good control policy, and historical observations can validate prediction more easily than counterfactual control actions.

A standard reference is Lennart Ljung, *System Identification — Theory for the User* (2nd ed., 1999):
https://www.control.isy.liu.se/books/sysid/

## 2. Current grinder baseline as a one-parameter process model

The current dose-control baselines assume locally:

```math
D_{\mathrm{out}} \approx r\,t_{\mathrm{grind}}
```

where $r$ is the grinder output rate in g/s.

The last-shot proportional controller estimates

```math
\hat r_n
=
\frac{D_{\mathrm{out},n-1}}{t_{\mathrm{grind},n-1}}
```

and recommends

```math
t_{\mathrm{next}}
=
\frac{D_{\mathrm{target}}}{\hat r_n}
=
t_{\mathrm{previous}}
\frac{D_{\mathrm{target}}}{D_{\mathrm{previous}}}.
```

The median-rate controller instead uses compatible earlier observations:

```math
\hat r_n
=
\text{median}_{i\lt n}
\left(
\frac{D_{\mathrm{out},i}}{t_{\mathrm{grind},i}}
\right),
```

then again sets

```math
t_{\mathrm{next}}=\frac{D_{\mathrm{target}}}{\hat r_n}.
```

These are deliberately small models. They are valuable because every richer model must demonstrate practical improvement over them; they are not assumed to be the final description of the grinder.

## 3. Least squares, recursive least squares, and adaptive control

A natural next family is a model that is linear in unknown parameters:

```math
y_n = \boldsymbol\phi_n^{\mathsf T}\boldsymbol\theta + \varepsilon_n.
```

For a grinder model, $y_n$ could be grinder output and $\boldsymbol\phi_n$ could contain features such as grind duration, duration-by-setting effects, or deliberately chosen basis functions.

For a batch of observations, ordinary least squares estimates $\boldsymbol\theta$ by minimising

```math
J(\boldsymbol\theta)
=
\sum_{i=1}^{N}
\left(y_i-\boldsymbol\phi_i^{\mathsf T}\boldsymbol\theta\right)^2.
```

Writing the observations as design matrix $X$ and output vector $\mathbf y$, the usual closed-form solution, when the inverse exists, is

```math
\hat{\boldsymbol\theta}
=
\left(X^{\mathsf T}X\right)^{-1}X^{\mathsf T}\mathbf y.
```

### Recursive least squares (RLS)

RLS updates the parameter estimate after each new observation instead of refitting from scratch. One common exponentially-forgetting form is

```math
\mathbf K_n
=
\frac{
\mathbf P_{n-1}\boldsymbol\phi_n
}{
\lambda + \boldsymbol\phi_n^{\mathsf T}\mathbf P_{n-1}\boldsymbol\phi_n
},
```

```math
\hat{\boldsymbol\theta}_n
=
\hat{\boldsymbol\theta}_{n-1}
+
\mathbf K_n
\left(
 y_n-\boldsymbol\phi_n^{\mathsf T}\hat{\boldsymbol\theta}_{n-1}
\right),
```

and

```math
\mathbf P_n
=
\frac{1}{\lambda}
\left[
\mathbf P_{n-1}
-
\mathbf K_n\boldsymbol\phi_n^{\mathsf T}\mathbf P_{n-1}
\right].
```

Here:

- $\hat{\boldsymbol\theta}_n$ is the updated parameter estimate;
- $\mathbf P_n$ represents parameter uncertainty/information in the RLS recursion;
- $\mathbf K_n$ is the update gain;
- $0\lt \lambda\leq1$ is a forgetting factor.

$\lambda=1$ weights the full history equally. $\lambda\lt 1$ gradually discounts old observations. Equivalently, the estimator approximately gives observation $i$ at time $n$ a weight proportional to

```math
\lambda^{\,n-i}.
```

That may be useful if bean age, grinder state, temperature, or another slow drift changes the process.

This is a classical route from system identification to **adaptive control**: estimate the process online, then recompute the control action from the current estimate.

References:

- K. J. Åström and B. Wittenmark, *On Self Tuning Regulators* (1972): https://lup.lub.lu.se/record/8601060
- B. Bernhardsson and K. J. Åström, *Adaptive Control* lecture notes, including RLS and self-tuning regulators: https://www.control.lth.se/fileadmin/control/Education/DoctorateProgram/ControlSystemsSynthesis/2016/AdaptiveControl.pdf

Important practical warning: adaptive control can perform well in ideal simulations yet fail when nonlinearities, unmodelled dynamics, disturbances, or poor excitation are ignored. Those are directly relevant to coffee grinding and extraction.

## 4. State-space models and latent grinder state

Some relevant variables may not be directly observable. Retained grounds are one candidate example.

A generic linear state-space model is

```math
\mathbf x_n
=
A\mathbf x_{n-1}+B\mathbf u_n+\mathbf w_n,
```

```math
\mathbf y_n
=
C\mathbf x_n+D\mathbf u_n+\mathbf v_n,
```

where:

- $\mathbf x_n$ is a latent internal state;
- $\mathbf u_n$ is the controlled input;
- $\mathbf y_n$ is the observed output;
- $\mathbf w_n$ and $\mathbf v_n$ represent process and measurement noise.

A Kalman filter is the classical solution for linear-Gaussian state-space models; extended/unscented or particle methods handle progressively more nonlinear cases.

For this project, a latent retention state is only justified if simpler previous-setting/change features first show prospective value. The state-space framing is therefore a conceptual tool, not an implementation commitment.

## 5. Design of Experiments (DoE)

Passive logging answers: “what happened during normal use?”

**Design of Experiments** asks a stronger question: “which deliberately chosen experiments let us distinguish process effects from noise most efficiently?”

This matters because normal dial-in behaviour is confounded: the user changes settings precisely because the previous result was unsatisfactory. Repeated, deliberately structured shots are much more informative about causal process behaviour.

### Replication

Repeated shots at identical controlled settings estimate process variability. If a response at fixed inputs is modelled as

```math
y_i = \mu + \varepsilon_i,
```

then replication gives empirical information about the variance of $\varepsilon_i$. Without replication, an observed difference between two settings cannot be cleanly separated from random shot-to-shot variation.

### Factorial / response-surface designs

For quantitative factors $x_1,x_2,\ldots,x_p$, a second-order response surface can be written as

```math
y = \beta_0 + \sum_{i=1}^{p}\beta_i x_i + \sum_{i=1}^{p}\beta_{ii}x_i^2 + \sum_{i=1}^{p-1}\sum_{j=i+1}^{p}\beta_{ij}x_i x_j + \varepsilon.
```

The linear terms estimate main effects, the squared terms capture curvature, and the interaction terms capture effects that depend on combinations of factors.

A **Central Composite Design (CCD)** combines factorial points, axial points, and repeated centre points so that such a quadratic surface can be estimated efficiently.

Direct espresso precedent exists: Pannusch et al. used a central composite design to study grind size, water flow rate, and temperature in espresso extraction kinetics:
https://doi.org/10.3390/foods12152871

This does not imply that a CCD is automatically the best design for our exact workflow, but it strongly supports deliberate experimental shots rather than relying only on opportunistic logging.

## 6. Planned Learning / Experiment mode

The application should eventually distinguish two objectives.

### Assisted / normal mode

Primary objective: make the next drink likely to be acceptable with minimal waste.

The controller should exploit what is currently known and avoid unnecessary experimentation.

### Learning / experiment mode

Primary objective: gain information about the grinder/extraction process efficiently, subject to practical constraints on coffee use and acceptable operating ranges.

The tool may deliberately request experiments such as:

- repeat the same setting/duration several times to estimate noise;
- change only grind duration while holding setting fixed;
- compare neighbouring grinder settings at a fixed corrected puck dose;
- repeat the first shot after a setting change and the next shot at the same setting to test transition/retention effects;
- revisit a reference setting later to distinguish drift from setting effects.

The experiment intent must be recorded **before** the outcome, just like recommendations. Data collection should preserve whether a shot was a normal-use shot or part of a designed experiment.

The first Learning Mode should be transparent and rule/DoE based. Bayesian active-learning policies should be introduced only after we have enough prospective data and a defensible action-space representation.

## 7. Gaussian processes and Bayesian optimisation

A Gaussian process (GP) treats an unknown function as a probability distribution over functions:

```math
f(x)\sim\mathcal{GP}\!\left(m(x),k(x,x')\right).
```

After observations $\mathcal D$, GP regression produces a posterior predictive distribution. At a candidate input $x$ this can be summarised by posterior mean and variance,

```math
f(x)\mid\mathcal D
\sim
\mathcal N\!\left(\mu(x),\sigma^2(x)\right),
```

under the usual Gaussian observation assumptions.

This is attractive for espresso because shots are expensive, datasets are likely to remain small, and uncertainty is operationally useful.

Reference: Rasmussen & Williams, *Gaussian Processes for Machine Learning* (MIT Press, open-access edition):
https://gaussianprocess.org/gpml/

### Bayesian optimisation (BO)

Bayesian optimisation builds a probabilistic surrogate for an expensive objective and uses an **acquisition function** to choose the next experiment. The acquisition function trades off:

- exploitation: try inputs already predicted to be good;
- exploration: try inputs whose outcome would be informative because uncertainty is high.

Conceptually,

```math
x_{\mathrm{next}}
=
\arg\max_x
\alpha\!\left(x;\mu(x),\sigma(x),\mathcal D,\text{objective},\text{constraints}\right),
```

where $\alpha$ is the acquisition function.

Common acquisition functions include Expected Improvement, Knowledge Gradient, and entropy/information-based methods.

Reference: Peter Frazier, *A Tutorial on Bayesian Optimization*:
https://arxiv.org/abs/1807.02811

BO is a strong long-term candidate for Learning Mode because each espresso shot has real cost. It is **not** an immediate default: useful BO requires a meaningful representation of the action space, a defensible surrogate model, and enough data to calibrate uncertainty.

## 8. Gray-box modelling is the preferred direction

The project should prefer combining known process structure with learned parameters/residuals rather than asking a completely unconstrained black box to rediscover obvious physics.

For the grinder, a useful family may look like

```math
D_{\mathrm{out},n}
=
t_n\,r(G_n,B_n,\ldots)
+
h(x_{n-1},G_n)
+
\varepsilon_n.
```

Here:

- proportionality to grind duration is used as structural knowledge where it remains adequate;
- $r(\cdot)$ is learned and may vary with grind setting or bean/session;
- $h(\cdot)$ is an optional transition/retention term only if data support it;
- $\varepsilon_n$ models residual process noise.

This is a **gray-box** approach: neither a fixed physical model nor an unconstrained black box.

A related industrial analogy is gravimetric powder feeding. Shier et al. modelled feed-factor profiles using a semi-empirical process model with parameters predicted from material/process properties, and explicitly note that real-time feedback can refine approximate feed-factor values as more material is dispensed:
https://doi.org/10.1016/j.ijpharm.2022.122071

The analogy is not physical equivalence, but it demonstrates that mass-flow control of granular material is a mature system-identification/process-control problem.

## 9. Espresso-specific research constraints

### Fine grinding can introduce non-monotonic behaviour

Cameron et al. combined mathematical modelling and experiment and found that extraction yield does not remain monotonically better as grinding becomes finer. Very fine grinding can create inhomogeneous flow and poor reproducibility:
https://doi.org/10.1016/j.matt.2019.12.019

Implication: do not assume a globally monotonic “finer is always more extraction” model across the full action space.

### Grinder setting is only a proxy for physical particle distribution

Smrke et al. showed that espresso particle-size distribution is bimodal and that the fraction of fines strongly affects puck permeability and extraction time. They modelled extraction time from the full particle-size distribution using partial least squares regression:
https://www.nature.com/articles/s41598-024-55831-x

Implication: a user-visible grinder setting is not a complete physical state variable. Even at a fixed nominal setting, unobserved PSD variation can appear as process noise or drift.

## 10. Practical model-selection principle

The project should use a ladder of increasing complexity and stop when extra complexity no longer earns its cost.

A reasonable evidence ladder is:

1. deterministic heuristic / proportional baseline;
2. robust descriptive statistics and past-only baselines;
3. structured regression / RLS with deliberately chosen features;
4. state-space terms only when temporal-state evidence exists;
5. Gaussian-process or other probabilistic surrogate when uncertainty estimates are useful and calibratable;
6. Bayesian optimisation / active experimental design when the surrogate and action space are trustworthy enough to choose experiments.

For every step, ask:

> Does this improve prospective prediction, calibration, shots-to-target, or coffee-to-target enough to justify the additional complexity?

The intended end state is not “use the most advanced statistics available”. It is a scientifically defensible, sample-efficient controller whose behaviour can be explained and whose additional complexity is validated against simpler baselines.
