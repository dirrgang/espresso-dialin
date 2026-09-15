# Development

## Prerequisites

- Git
- [mise](https://mise.jdx.dev/)

The repository standardizes on Python 3.14 and declares its Python and developer-tool versions in `mise.toml`. Python dependencies are declared in `pyproject.toml` and resolved in the committed `uv.lock`; no global Python packages are required.

For interactive shells, activating mise is recommended so repository-scoped tools such as `uv` and `prek` are directly available. Commands exposed through `mise run` work without shell activation.

## Environment setup

From the repository root, run:

```sh
mise run setup
```

This installs the tool versions declared in `mise.toml`, synchronizes all project dependency groups from `uv.lock`, and installs the `prek` Git hook.

If an older clone still has a legacy hook runner, `prek install` may deliberately enter migration mode instead of deleting the existing hook. After confirming that the old hook is obsolete, replace it once with:

```sh
mise exec -- prek install --force
```

Do not add `--force` to the normal setup task: repository bootstrap should not silently overwrite arbitrary user-managed Git hooks.

Development-only Python tooling is declared in the standardized `dev` dependency group and is synchronized by uv by default. Notebook and plotting tools live in the separate `analysis` group. `mise run setup` installs both groups for a full local development environment; CI only needs the default `dev` group.

## Common commands

```sh
mise run sync       # synchronize the locked local environment
mise run check      # sync once, then lint, formatting, mypy, tests + coverage
mise run fix        # sync once, then apply safe Ruff fixes and formatting
mise run test       # sync once, then tests + coverage
mise run typecheck  # sync once, then strict mypy for src
mise run app        # sync once, then local Streamlit application
```

All repository tasks depend on the shared `sync` task. mise executes a shared dependency only once, then may run independent quality gates in parallel. The quality commands themselves use `uv run --no-sync`, so concurrent Ruff, mypy, and pytest processes do not race while trying to modify the same `.venv`. The shared sync uses `uv sync --locked --all-groups`, so stale lockfiles fail rather than being silently rewritten and the complete local development environment stays installed.

## VS Code

The repository includes shared workspace recommendations under `.vscode/` for mise, Python, Pylance, Ruff, mypy, and Jupyter. After `mise run setup`, select the repository `.venv` as the Python interpreter locally. On Windows this is `.venv\Scripts\python.exe`; on Linux/macOS it is `.venv/bin/python`. Ruff and mypy use the repository environment rather than independent bundled tool versions.

The recommended mise VS Code extension remains useful for inspecting tools, environment variables, and tasks, but the repository disables its automatic configuration of other extensions. The Python executable installed by mise is the base interpreter used to create the uv environment; it is not the project interpreter. If mise-vscode previously wrote `python.defaultInterpreterPath` to the base mise Python, remove that workspace entry if desired and use `Python: Select Interpreter` to select `.venv`. VS Code stores an explicitly selected workspace interpreter internally, so that explicit selection takes precedence over a later workspace-level `python.defaultInterpreterPath` default.

Pylance remains available for navigation, completion, and language-server features, but its type checker is disabled because strict mypy is the repository's authoritative type-checking gate.

Editor integration is convenience only. The repository tasks and CI remain authoritative and can be run without VS Code.

## Streamlit agent skill

The repository includes a discovery skill at
[`.agents/skills/developing-with-streamlit/`](.agents/skills/developing-with-streamlit/SKILL.md).
Codex discovers it from the repository; no personal skill installation is needed.
The files are ordinary version-controlled files, not symlinks into a local environment.

After setting up the project environment, verify discovery from the repository root:

```sh
uv run --no-sync python .agents/skills/developing-with-streamlit/scripts/discover.py --project-dir .
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
mise run check
```

To apply formatting and safe Ruff fixes locally:

```sh
mise run fix
```

`prek` runs lightweight file checks and Ruff automatically on commit from `prek.toml`. Generic file checks use `prek`'s built-in hooks, while Ruff runs in an isolated hook environment pinned independently from the project environment. Full mypy and pytest checks remain repository-level quality gates rather than commit hooks. GitHub Actions independently synchronizes the locked environment once and then runs Ruff, mypy, and pytest without additional environment mutation on Python 3.14 for pull requests and pushes to `main`, with a focused Windows app smoke test on the same Python version.

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

Keep runtime dependencies small. Add a dependency only when it materially reduces implementation or modelling complexity. Runtime dependencies belong in `project.dependencies`; local-only development and analysis tooling belongs in standardized PEP 735 `dependency-groups` and must not become published package extras.

`uv.lock` is committed and is the reproducible resolution used by local development and CI. Dependency declarations and the lockfile must be updated together.

The project intentionally does not have a public release or license yet. Those decisions should be made explicitly if the PoC becomes a maintained/public project.
