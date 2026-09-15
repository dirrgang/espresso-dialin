# Development

## Prerequisites

- Git
- Python 3.12 or newer

The repository uses a standard `pyproject.toml`; no global Python packages are required.

## Environment setup

### PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,analysis]"
pre-commit install
```

### POSIX shell

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,analysis]'
pre-commit install
```

The `analysis` extra contains notebook/plotting tools. It is optional for ordinary package development.

## Streamlit agent skill

The repository includes a discovery skill at
[`.agents/skills/developing-with-streamlit/`](.agents/skills/developing-with-streamlit/SKILL.md).
Codex discovers it from the repository; no personal skill installation is needed.
The files are ordinary version-controlled files, not symlinks into a local environment.

After activating the project environment, verify discovery from the repository root:

```sh
python .agents/skills/developing-with-streamlit/scripts/discover.py --project-dir .
```

Read the `SKILL.md` at the printed path for version-matched Streamlit guidance.
Bundled guidance requires Streamlit 1.57 or newer; this is an optional agent-tooling
requirement, not a change to the application's supported dependency range. For older
installations, use documentation matching the installed version. The discovery script
does not install or upgrade packages.

The small discovery skill is vendored; the full references remain in the Streamlit
package and follow its installed version. See
[`UPSTREAM.md`](.agents/skills/developing-with-streamlit/UPSTREAM.md) for the pinned
source, license, local changes, and update procedure. Avoid installing a second
personal copy of the same skill.

## Quality checks

Run before committing substantive code changes:

```sh
ruff check .
ruff format --check .
mypy src
python scripts/run_pyright.py
pytest --cov=espresso_dialin --cov-report=term-missing
```

To apply formatting and safe Ruff fixes locally:

```sh
ruff check --fix .
ruff format .
```

Pre-commit runs the file, Ruff, and project-wide Pyright checks automatically. Pyright covers
the packaged source, tests, root Streamlit entry point, and the historical-exploration
notebook (through nbQA) using the same type-checking engine as Pylance. GitHub Actions runs
linting, formatting, both type checkers, and tests on pull requests and pushes to `main`.

## Research and coding-agent workflow

The project deliberately separates interactive research/explanation from coding-agent execution.

Use repository-aware interactive ChatGPT work primarily for:

- understanding statistical/control methods and their mathematics;
- literature review and comparison of candidate approaches;
- inspecting repository state and reviewing empirical results;
- discussing assumptions, identifiability, confounding, and experiment design;
- designing bounded implementation tasks and reviewing their results afterward.

Use Codex/coding agents primarily for:

- implementing a clearly scoped change;
- adding/refactoring tests and typed domain code;
- executing reproducible analyses already specified by the research question;
- updating durable repository documentation when implementation changes a modelling assumption.

A useful default loop is:

```text
interactive analysis / explanation
    -> bounded Codex implementation
    -> interactive review / explanation
    -> next evidence-driven task
```

This separation is intended to improve both learning and implementation quality. Production code should not be made artificially verbose or tutorial-like merely to explain the statistics; educational derivations belong in interactive discussion or durable research documentation where they are genuinely useful. Conversely, material modelling assumptions, validation results, or decisions must not live only in an agent chat response: record them under `docs/`.

For mathematical Markdown in the repository, use GitHub's LaTeX/MathJax-compatible syntax: `$...$` inline and fenced `math` blocks for display equations. Prefer fenced `math` blocks over multiline `$$...$$` because GitHub Markdown can parse the latter incorrectly.

See `AGENTS.md` for the detailed instructions that coding agents should follow.

## Project boundaries

The current phase is a research PoC. Prefer notebooks and small Python modules that answer the modelling questions documented under `docs/` before adding product infrastructure.

In particular:

- raw historical observations are immutable research inputs except for explicit transcription corrections;
- model-derived values should be reproducible from raw data;
- reusable logic belongs under `src/espresso_dialin/` rather than only in notebooks;
- local SQLite databases and generated runtime state are ignored by Git;
- secrets belong in local environment/configuration files and must not be committed.

## Dependency policy

Keep runtime dependencies small. Add a dependency only when it materially reduces implementation or modelling complexity. Development-only tools belong in the `dev` extra; notebook/visualization tools belong in the `analysis` extra.

The project intentionally does not have a public release or license yet. Those decisions should be made explicitly if the PoC becomes a maintained/public project.
