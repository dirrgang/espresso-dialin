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

## Quality checks

Run before committing substantive code changes:

```sh
ruff check .
ruff format --check .
mypy src
pytest --cov=espresso_dialin --cov-report=term-missing
```

To apply formatting and safe Ruff fixes locally:

```sh
ruff check --fix .
ruff format .
```

Pre-commit runs the lightweight file and Ruff checks automatically. GitHub Actions runs linting, formatting, type checking, and tests on pull requests and pushes to `main`.

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
