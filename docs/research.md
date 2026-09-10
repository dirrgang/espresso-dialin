# Related work and differentiation

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

These are hypotheses and product choices, not yet proven advantages over EspressoPost.

## Other tools/projects mentioned during exploration

The following were identified as relevant leads during initial exploration and should be reassessed before making strong comparison claims:

- **Beanconqueror** — extensive coffee/shot logging and hardware integrations; useful reference for data capture and interoperability.
- **HomeBarista / Dial In / Vurr / PullPilot** — examples of contemporary dial-in/logging tools that provide next-shot guidance or recommendations, but their recommendation algorithms were not established as equivalent to the dynamic low-waste model proposed here.
- **BayBE** — general Bayesian optimization / design-of-experiments tooling; potentially relevant if the project later becomes a true sequential experimental-design or preference-optimization problem.

The proof of concept should not attempt to compete on logging breadth or hardware integration. Its value must come from measurable recommendation quality under the simple manual workflow.

## Research stance

The right null hypothesis is:

> The additional model complexity does not materially improve dial-in over a simple heuristic/static regression.

If historical and prospective validation fail to reject that hypothesis in a practically meaningful way, simplify the project rather than inventing features to justify it.
