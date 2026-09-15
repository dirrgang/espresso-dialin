# AGENTS.md

## Purpose

This repository is a proof-of-concept research project for adaptive espresso dial-in. The primary goal is to determine whether manually entered shot data can produce better next-shot recommendations with less wasted coffee than simple dial-in heuristics.

## Before making substantive changes

Read at least:

- `README.md`
- `docs/model.md`
- `docs/notation.md` for project-wide mathematical symbols
- `docs/data-model.md`
- `docs/validation.md`
- `docs/decision-log.md`
- `docs/research-methods.md` for statistical/mathematical work

Treat the decision log as authoritative for current project decisions. Treat modelling ideas explicitly labelled as hypotheses as unproven until validated.

## Working model: research/explanation versus implementation

The project deliberately uses two complementary workflows.

### Interactive research / explanation

Repository-aware interactive ChatGPT sessions are the preferred place for:

- learning and explaining the mathematics behind candidate methods;
- literature review and comparison with established methods;
- exploring modelling assumptions and alternative formulations;
- reviewing empirical results and deciding what evidence would distinguish hypotheses;
- preparing or reviewing implementation prompts;
- explaining already-implemented code or statistical results in depth.

Educational depth is valuable here. Derivations, terminology, assumptions, failure modes, and alternatives should be made explicit when useful.

### Coding-agent implementation

Codex/coding-agent tasks should normally be bounded implementation tasks with explicit acceptance criteria. Optimize them for:

- correctness;
- minimal justified scope;
- tests and reproducibility;
- clean domain boundaries;
- empirical validation;
- maintainable code.

Do **not** distort production code into a tutorial. Comments and docstrings should explain non-obvious behavior, invariants, units, assumptions, and public interfaces, not reproduce a statistics lesson. A coding task need not spend context producing a long educational explanation unless that explanation is itself a requested durable artifact.

When an implementation introduces or falsifies a material modelling assumption, update the durable repository documentation (`docs/model.md`, `docs/research-methods.md`, `docs/decision-log.md`, validation notes, etc.) rather than relying on the coding agent's final chat response.

This split is a default workflow, not a hard tool restriction: use the tool best suited to the task. The important distinction is that **educational explanation and production implementation are separate objectives**, connected through durable repository documentation.

## Engineering principles

- Keep the proof of concept small.
- Optimize for learning whether the model works, not for product polish.
- Prefer simple models until extra complexity demonstrates out-of-sample value.
- Keep optimizer/domain logic independent from Streamlit and SQLite.
- Preserve raw measurements; derive transformed values separately.
- Store recommendations and experiment intent before their outcomes are known.
- Preserve chronology and bean/session boundaries.
- Never silently fill missing/uncertain historical data.
- Do not force purging; retention handling is an experiment, not an assumption.
- Do not require real-time hardware integration for the MVP.
- Robustness to bad/channeling-like shots is a core requirement.
- Actual final yield must be retained and used; do not pretend every shot ended at exactly 36 g.
- Manual correction of puck dose to the target is a supported controlled intervention and must not overwrite grinder output.
- Distinguish normal-use recommendations from deliberately designed Learning/Experiment-mode observations.
- Do not infer causal effects from operator-adapted observational data when a designed experiment is required to separate effects from noise/confounding.

## Initial implementation direction

Preferred PoC stack:

- Python 3.14
- Streamlit
- SQLite
- NumPy / SciPy
- pytest
- Jupyter notebooks for model exploration/backtesting

A future production frontend/backend architecture is explicitly premature until the modelling concept has been validated.

## Repository conventions

- Source code lives under `src/espresso_dialin/`.
- Tests live under `tests/` and should mirror behavior rather than implementation details.
- Exploratory notebooks live under `notebooks/`; reusable logic must move into `src/`.
- Small research datasets with explicit provenance may live under `data/`; runtime databases and generated state must not be committed.
- `data/historical_shots_staging.csv` is the auditable initial transcription and should remain unchanged except for an explicit decision to correct the transcription record itself.
- `data/historical_shots_corrected.csv` is the authoritative historical source for current modelling, backtests, and gap analysis; it may contain documented user-supplied corrections that are not inferable from the source image alone.
- Do not use staging-based numeric findings as current benchmarks after the corrected dataset became authoritative; rerun/regenerate them first.
- Python dependencies and Python-tool configuration belong in `pyproject.toml`; repository runtime/tool bootstrap belongs in `mise.toml`; commit-hook configuration belongs in `prek.toml`; resolved Python dependencies belong in `uv.lock`.
- Keep public/core interfaces typed. `mypy` is configured in strict mode for `src/`.
- Use Ruff for both linting and formatting; do not introduce a second formatter/linter without a demonstrated need.
- In GitHub Markdown, use literal `$...$` for inline mathematics and fenced `math` blocks (triple backticks followed by `math`) for display equations. Never substitute lookalike delimiters such as `§`, and do not put `$`/`$$` delimiters inside a `math` fence. GitHub's display-math pipeline can misparse a literal `<` or `>` inside TeX (for example `\sum_{i<j}`), so prefer TeX relation commands such as `\lt`, `\gt`, `\le`, `\ge`, or equivalent explicit index bounds. Avoid `\operatorname{...}` in repository math because it has rendered unreliably in GitHub; use established commands or `\mathrm{...}` for names such as `median`, `MAD`, and `MedAE`. A literal `*` inside inline math can also be consumed by Markdown emphasis parsing, so write superscript stars as `^{\ast}` rather than bare `^*`; do not “simplify” an escaped or `\ast` form back to a literal asterisk. Use ordinary code fences only for code, commands, schemas, or literal text.
- Mathematical documentation may assume knowledge roughly equivalent to an Informatik/Computer-Science bachelor's degree. Do not explain standard algebra, calculus, linear-algebra notation, basic probability/statistics notation, or commonplace operators merely for completeness. Explain project-specific semantics, non-obvious modelling assumptions, and specialist methods where they matter.
- Every **project-specific mathematical symbol** must either be defined in `docs/notation.md` or defined explicitly at first use in the document that introduces it. Conventional method-local notation is acceptable without tutorial-level explanation, but any symbol whose concrete role in the local model is not obvious should be identified briefly. Do not make readers infer state vectors, context variables, targets, residuals, feature encodings, or index meanings from convention alone.
- Do not reuse a mathematical symbol for materially different concepts across project documentation without explicitly declaring the scope/local meaning.
- Do not perform arithmetic on opaque grinder-setting labels. Expressions such as `G_n - G_(n-1)` require a separately defined and validated numerical mapping such as `z(G)`; otherwise use categorical or structured current-setting/transition features.
- Do not silently rewrite `data/historical_shots_staging.csv`. Corrections to the transcription should be explicit and reviewable in Git history and normally belong in `data/historical_shots_corrected.csv`.
- Do not add a license until the repository owner has explicitly chosen one.

## Quality gates

Before considering a code change complete, run:

```sh
mise run check
```

This is the repository-level entry point for the same core gates enforced in CI:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
uv run --locked pytest --cov=espresso_dialin --cov-report=term-missing
```

For normal development, bootstrap the environment and install the commit hook once per clone:

```sh
mise run setup
```

`prek` executes `prek.toml`; generic file checks use native built-in hooks and Ruff runs in an isolated hook environment. Do not weaken a quality gate merely to make a change pass; either fix the issue or document why the rule is inappropriate and adjust the configuration deliberately.

## Initial real setup

- Grinder: Baratza Sette 270
- Espresso machine: Sage/Breville Dual Boiler (BES920/SES920)
- Default target: 18.0 g puck dose -> 36.0 g final yield in 30–35 s
- Current bean at the start of prospective/live collection: REWE Bio Espresso ganze Bohnen, 1000 g

Do not hard-code grinder semantics beyond what has been verified. In particular, macro/micro overlap and exact ordering/calibration should be treated as a grinder-adapter concern and tested/verified rather than assumed.

## Validation discipline

When adding or comparing models:

1. establish a simple baseline;
2. use chronological/rolling validation;
3. avoid data leakage;
4. report prediction error and, where possible, uncertainty calibration;
5. evaluate coffee/shots-to-target, not fit quality alone;
6. use ablation tests to establish whether added features actually help;
7. use deliberately designed/replicated experiments when observational logging cannot identify an effect;
8. keep Normal/Assisted mode and Learning/Experiment mode objectives distinct.

If a complex model does not materially beat a simpler model, keep the simpler model.

## Scope control

Do not introduce the following without a specific validated need:

- accounts/authentication;
- cloud sync;
- PostgreSQL;
- public API;
- Bluetooth scale support;
- machine telemetry;
- pump-stop detection;
- neural networks;
- elaborate grinder calibration databases;
- taste/preference ML.

These are later extensions, not prerequisites for validating the core idea.
