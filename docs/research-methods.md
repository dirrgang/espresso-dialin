# Research methods and mathematical foundations

This document records the methodological families that are most relevant to the espresso-dialin problem and explains why they may be useful. It is intentionally educational: the project should not only produce recommendations, but make the modelling assumptions and mathematics understandable and testable.

Nothing in this document selects a final model. Simple baselines remain the null hypothesis that richer methods must beat prospectively.

## 1. Problem framing: system identification before optimisation

The project contains two coupled but separable systems.

For the grinder:

```text
D_out,n = f(G_n, t_grind,n, grinder_state_n, bean/session_n, ...) + error
```

For extraction:

```text
(t_brew,n, Y_n) = g(G_n, D_puck,n, puck/grinder_state_n, bean/session_n, ...) + error
```

The first statistical task is **system identification**: infer useful approximations of the unknown functions `f` and `g` from observed inputs and outputs.

The second task is **control / optimisation**: given the current model and uncertainty, choose the next controllable input that best serves the current objective.

This distinction matters. A model may predict the process well without providing a good control policy, and historical observations can validate prediction more easily than counterfactual control actions.

A standard reference is Lennart Ljung, *System Identification — Theory for the User* (2nd ed., 1999):
https://www.control.isy.liu.se/books/sysid/

## 2. Current grinder baseline as a one-parameter process model

The current dose-control baselines assume locally:

```text
D_out ~= r * t_grind
```

where `r` is the grinder output rate in g/s.

The last-shot proportional controller estimates

```text
r_hat = D_previous / t_previous

t_next = D_target / r_hat
```

The median-rate controller instead uses

```text
r_hat = median(D_i / t_i)
```

over compatible past observations.

These are deliberately small models. They are valuable because every richer model must demonstrate practical improvement over them; they are not assumed to be the final description of the grinder.

## 3. Least squares, recursive least squares, and adaptive control

A natural next family is a linear-in-parameters model:

```text
y_n = phi_n^T theta + epsilon_n
```

For a grinder model, `y_n` could be grinder output and `phi_n` could contain features such as grind duration, duration-by-setting effects, or deliberately chosen basis functions.

For a batch of observations, ordinary least squares estimates `theta` by minimising

```text
sum_i (y_i - phi_i^T theta)^2
```

and, when the usual matrix inverse exists,

```text
theta_hat = (X^T X)^(-1) X^T y
```

### Recursive least squares (RLS)

RLS updates the parameter estimate after each new observation instead of refitting from scratch. One common exponentially-forgetting form is:

```text
K_n = P_(n-1) phi_n / (lambda + phi_n^T P_(n-1) phi_n)

theta_n = theta_(n-1) + K_n (y_n - phi_n^T theta_(n-1))

P_n = (1/lambda) [P_(n-1) - K_n phi_n^T P_(n-1)]
```

where:

- `theta_n` is the updated parameter estimate;
- `P_n` represents parameter uncertainty / information;
- `K_n` is the update gain;
- `0 < lambda <= 1` is a forgetting factor.

`lambda = 1` weights the full history equally. `lambda < 1` gradually discounts old observations, which may be useful if bean age, grinder state, temperature, or other slow drift changes the process.

This is a classical route from system identification to **adaptive control**: estimate the process online, then recompute the control action from the current estimate.

References:

- K. J. Åström and B. Wittenmark, *On Self Tuning Regulators* (1972): https://lup.lub.lu.se/record/8601060
- B. Bernhardsson and K. J. Åström, *Adaptive Control* lecture notes, including RLS and self-tuning regulators: https://www.control.lth.se/fileadmin/control/Education/DoctorateProgram/ControlSystemsSynthesis/2016/AdaptiveControl.pdf

Important practical warning: adaptive control can perform well in ideal simulations yet fail when nonlinearities, unmodelled dynamics, disturbances, or poor excitation are ignored. Those are directly relevant to coffee grinding and extraction.

## 4. State-space models and latent grinder state

Some relevant variables may not be directly observable. Retained grounds are one candidate example.

A generic state-space model is:

```text
x_n = A x_(n-1) + B u_n + w_n

y_n = C x_n     + D u_n + v_n
```

where:

- `x_n` is a latent internal state;
- `u_n` is the controlled input;
- `y_n` is the observed output;
- `w_n` and `v_n` represent process and measurement noise.

A Kalman filter is the classical solution for linear-Gaussian state-space models; extended/unscented or particle methods handle progressively more nonlinear cases.

For this project, a latent retention state is only justified if simpler previous-setting/change features first show prospective value. The state-space framing is therefore a conceptual tool, not an implementation commitment.

## 5. Design of Experiments (DoE)

Passive logging answers: “what happened during normal use?”

**Design of Experiments** asks a stronger question: “which deliberately chosen experiments let us distinguish process effects from noise most efficiently?”

This matters because normal dial-in behaviour is confounded: the user changes settings precisely because the previous result was unsatisfactory. Repeated, deliberately structured shots are much more informative about causal process behaviour.

### Replication

Repeated shots at identical controlled settings estimate process variability. Without replication, an observed difference between two settings cannot be cleanly separated from random shot-to-shot variation.

### Factorial / response-surface designs

For quantitative factors `x_1, x_2, ...`, a second-order response surface can be written as:

```text
y = beta_0
  + sum_i beta_i x_i
  + sum_i beta_ii x_i^2
  + sum_(i<j) beta_ij x_i x_j
  + error
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

Primary objective: gain information about the grinder / extraction process efficiently, subject to practical constraints on coffee use and acceptable operating ranges.

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

```text
f(x) ~ GP(m(x), k(x, x'))
```

After observations, GP regression produces both a posterior mean and posterior uncertainty:

```text
f(x) | data -> mean mu(x), variance sigma^2(x)
```

This is attractive for espresso because shots are expensive, datasets are likely to remain small, and uncertainty is operationally useful.

Reference: Rasmussen & Williams, *Gaussian Processes for Machine Learning* (MIT Press, open-access edition):
https://gaussianprocess.org/gpml/

### Bayesian optimisation (BO)

Bayesian optimisation builds a probabilistic surrogate for an expensive objective and uses an **acquisition function** to choose the next experiment. The acquisition function trades off:

- exploitation: try inputs already predicted to be good;
- exploration: try inputs whose outcome would be informative because uncertainty is high.

Conceptually:

```text
x_next = argmax_x acquisition(mu(x), sigma(x), objective, constraints)
```

Common acquisition functions include Expected Improvement, Knowledge Gradient, and entropy/information-based methods.

Reference: Peter Frazier, *A Tutorial on Bayesian Optimization*:
https://arxiv.org/abs/1807.02811

BO is a strong long-term candidate for Learning Mode because each espresso shot has real cost. It is **not** an immediate default: useful BO requires a meaningful representation of the action space, a defensible surrogate model, and enough data to calibrate uncertainty.

## 8. Gray-box modelling is the preferred direction

The project should prefer combining known process structure with learned parameters/residuals rather than asking a completely unconstrained black box to rediscover obvious physics.

For the grinder, a useful family may look like:

```text
D_out,n = t_n * r(G_n, bean_n, ...) + h(previous_state_n, G_n) + epsilon_n
```

Here:

- proportionality to grind duration is used as structural knowledge where it remains adequate;
- `r(...)` is learned and may vary with grind setting or bean/session;
- `h(...)` is an optional transition/retention term only if data support it;
- `epsilon_n` models residual process noise.

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

```text
Does this improve prospective prediction, calibration, shots-to-target,
or coffee-to-target enough to justify the additional complexity?
```

The intended end state is not “use the most advanced statistics available”. It is a scientifically defensible, sample-efficient controller whose behaviour can be explained and whose additional complexity is validated against simpler baselines.
