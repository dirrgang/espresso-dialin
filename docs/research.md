# Related work and differentiation

## Research-methods overview

The problem is not unique to espresso. Important parts map directly onto established fields:

- **system identification** for learning input/output relationships from measured shots;
- **adaptive control** for updating process parameters online and recomputing control actions;
- **state-space estimation** for possible hidden grinder state such as retention or slow drift;
- **Design of Experiments (DoE)** for deliberately choosing informative shots rather than relying only on observational use;
- **Gaussian-process regression / Bayesian optimisation** for sample-efficient probabilistic modelling and experiment selection when each shot has real cost;
- **gray-box modelling** for combining known process structure with learned parameters instead of treating the whole problem as an unconstrained black box.

See [`research-methods.md`](research-methods.md) for the mathematical framing, equations, Learning-Mode concept, and primary references.

## EspressoPost

Repository: https://github.com/itayke/espressopost

EspressoPost is the closest known existing project and should be treated as the main conceptual baseline.

As documented in its README (checked 2026-09-10), EspressoPost:

- runs on a Waveshare ESP32-S3 Touch AMOLED device;
- stores per-shot raw brew time and a 1–5 quality rating;
- records ambient temperature, humidity, and pressure;
- uses a **per-preset Bayesian linear regression** of brew time on grind setting plus climate variables;
- recommends a grind setting and exposes confidence;
- stores preset dose, yield and target time;
- supports calibration epochs such as a new bag, grinder recalibration, or machine change;
- persists shot records locally and can push them one-way to Google Sheets;
- describes its current model as **time-only**; a later quality model and recency weighting are explicitly deferred until data justify them.

### Important overlap with this project

Both projects:

- learn from historical shots;
- use a statistical model rather than only fixed dial-in rules;
- recommend the next grind setting;
- care about confidence/uncertainty;
- separate model math from UI/platform concerns.

Therefore “Bayesian regression for espresso grind recommendations” is **not** a useful differentiator by itself.

### Potential differentiators to validate

This project instead focuses on the measurements and interventions already available in a low-instrumentation home workflow:

1. **Actual grinder output mass** is an observation, allowing grind duration itself to be optimized.
2. **Actual final beverage yield** remains an observation even when the intended 36 g target is missed; brew duration is interpreted jointly with yield.
3. **Manual dose correction to the target** is explicitly represented, preserving both grinder output and approximate puck dose.
4. **Robust outlier handling** is a core requirement because puck preparation/channeling can create extreme shots.
5. **Chronological previous-grinder state / retention** may be modelled so purging can remain optional, but only if data demonstrate value.
6. **Grinder adjustment abstraction** should support stepped, stepless, and macro/micro systems rather than a single numeric dial.
7. The project objective is explicitly **low-waste dial-in**: fewer shots / fewer grams of coffee to reach the target region.
8. A future **Learning / Experiment mode** should deliberately request informative DoE-style shots when the user wants to improve the process model, rather than always optimizing the immediate beverage.

These are hypotheses and product choices, not yet proven advantages over EspressoPost.

## Espresso-specific scientific literature

### Cameron et al. — mathematical modelling and low-waste espresso

Michael I. Cameron et al., *Systematically Improving Espresso: Insights from Mathematical Modeling and Experiment*, Matter 2(3), 2020.

DOI: https://doi.org/10.1016/j.matt.2019.12.019

Relevant findings:

- mathematical/mechanistic modelling can isolate important espresso process effects;
- grinder setting and water pressure materially affect reproducibility;
- extraction yield versus grind setting is not globally monotonic in experiment;
- very fine grinding can produce inhomogeneous flow and poor reproducibility;
- model-guided protocols can reduce wasted coffee.

Project implication: do not encode a globally monotonic “finer is always better/more extracted” assumption across the entire grinder range.

### Smrke et al. — fines and particle-size distribution

Samo Smrke, André Eiermann, Chahan Yeretzian, *The role of fines in espresso extraction dynamics*, Scientific Reports 14, 5612 (2024).

Article: https://www.nature.com/articles/s41598-024-55831-x

Relevant findings:

- espresso grounds have a characteristically bimodal particle-size distribution;
- the share of fines strongly changes puck permeability and extraction time;
- a single summary particle size does not fully describe extraction behaviour;
- the study used partial least squares regression on particle-size distributions to predict extraction time.

Project implication: nominal grinder setting is only a proxy for the physically relevant particle distribution. Unobserved PSD variation can appear as process noise even at the same setting.

### Pannusch et al. — explicit Design of Experiments for espresso

Pannusch et al., *Influence of Flow Rate, Particle Size, and Temperature on Espresso Extraction Kinetics*, Foods 12(15), 2871 (2023).

DOI: https://doi.org/10.3390/foods12152871

Relevant feature: the study used a **central composite experimental design** to vary grind size, water flow and temperature systematically.

Project implication: deliberate replicated/structured shots are scientifically preferable to relying exclusively on observational dial-in history when trying to identify process effects.

## System-identification and control foundations

### Ljung — System Identification

Lennart Ljung, *System Identification — Theory for the User*, 2nd ed.

Book/resource page: https://www.control.isy.liu.se/books/sysid/

This is the core methodological reference for learning dynamical/input-output models from measured data.

### Åström / Wittenmark — adaptive and self-tuning control

K. J. Åström and B. Wittenmark, *On Self Tuning Regulators* (1972):
https://lup.lub.lu.se/record/8601060

Adaptive-control lecture material covering recursive least squares and self-tuning regulators:
https://www.control.lth.se/fileadmin/control/Education/DoctorateProgram/ControlSystemsSynthesis/2016/AdaptiveControl.pdf

Project implication: online parameter estimation with a forgetting factor is a classical candidate for adapting to drift; it is not necessary to invent a bespoke “ML” mechanism for that problem.

## Probabilistic modelling and experiment selection

### Gaussian processes

C. E. Rasmussen and C. K. I. Williams, *Gaussian Processes for Machine Learning*.

Open-access book: https://gaussianprocess.org/gpml/

Project relevance: GPs are attractive for small, expensive datasets because they produce a predictive mean and uncertainty, but they require a meaningful representation/kernel over grinder settings and other inputs.

### Bayesian optimisation

Peter I. Frazier, *A Tutorial on Bayesian Optimization*:
https://arxiv.org/abs/1807.02811

Project relevance: Bayesian optimisation is specifically intended for expensive/noisy black-box objectives and uses an acquisition function to balance exploitation and exploration. It is a plausible later engine for Learning Mode, not a reason to skip basic system identification or experimental design.

## Granular-material / powder-feeding analogy

The grinder-output subproblem has a useful industrial analogy in gravimetric powder feeding: a granular material is transported by a mechanical actuator and the goal is predictable mass flow despite material and equipment variation.

Andrew P. Shier et al., *Development of a predictive model for gravimetric powder feeding from an API-rich materials properties library*, International Journal of Pharmaceutics 625 (2022), 122071.

DOI: https://doi.org/10.1016/j.ijpharm.2022.122071

The study uses a semi-empirical feed-factor model and data-driven parameter prediction, and notes that real-time feedback can refine approximate feed-factor knowledge as material is dispensed.

The analogy should not be overstated: an espresso burr grinder is not a loss-in-weight powder feeder. The useful lesson is methodological — mass-flow systems with granular materials are commonly approached with a combination of process structure, statistical identification, and feedback control.

## Other tools/projects mentioned during exploration

The following were identified as relevant leads during initial exploration and should be reassessed before making strong comparison claims:

- **Beanconqueror** — extensive coffee/shot logging and hardware integrations; useful reference for data capture and interoperability.
- **HomeBarista / Dial In / Vurr / PullPilot** — examples of contemporary dial-in/logging tools that provide next-shot guidance or recommendations, but their recommendation algorithms were not established as equivalent to the dynamic low-waste model proposed here.
- **BayBE** — general Bayesian optimization / design-of-experiments tooling; potentially relevant if the project later becomes a true sequential experimental-design or preference-optimization problem.

The proof of concept should not attempt to compete on logging breadth or hardware integration. Its value must come from measurable recommendation quality and/or information efficiency under the simple manual workflow.

## Research stance

The right null hypothesis is:

> The additional model complexity does not materially improve dial-in over a simple heuristic/static baseline.

A second research principle is:

> Normal use and deliberate learning are different objectives and should be recorded as such.

If historical and prospective validation fail to show a practically meaningful advantage from richer modelling, simplify the project rather than inventing complexity to justify it.
