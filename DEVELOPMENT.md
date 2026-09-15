# Development

## Prerequisites

- Git
- [mise](https://mise.jdx.dev/)

The repository declares its Python and developer-tool versions in `mise.toml`. Python dependencies are declared in `pyproject.toml` and resolved in the committed `uv.lock`; no global Python packages are required.

For interactive shells, activating mise is recommended so repository-scoped tools such as `uv` and `prek` are directly available. Commands exposed through `mise run` work without shell activation.

## Environment setup

From the repository root, run:

```sh
mise run setup
```

This installs the tool versions declared in `mise.toml`, synchronizes the project environment from `uv.lock`, and installs the `prek` Git hook.

If this clone still has a legacy hook from the previous `pre-commit` setup, `prek install` deliberately enters migration mode instead of deleting it. After confirming that the legacy hook is obsolete, replace it once with:

```sh
mise exec -- prek install --force
```

Do not add `--force` to the normal setup task: repository bootstrap should not silently overwrite arbitrary user-managed Git hooks.

The project currently keeps development and analysis tooling as `dev` and `analysis` extras. `mise run setup` installs both. The analysis extra contains notebook/plotting tools and is not required by CI.

## Common commands

```sh
mise run check      # lint, formatting check, mypy, tests + coverage
mise run fix        # apply safe Ruff fixes and formatting
mise run test       # tests + coverage
mise run typecheck  # mypy
mise run app        # local Streamlit application
```

The tasks use `uv run --locked` so normal development commands fail rather than silently rewriting a stale lockfile.

## VS Code

The repository includes shared workspace recommendations under `.vscode/` for Python, Pylance, Ruff, mypy, and Jupyter. The workspace points Python tooling at `.venv`; Ruff and mypy use the repository environment rather than independent bundled tool versions.

Pylance remains available for navigation, completion, and language-server features, but its type checker is disabled because strict mypy is the repository's authoritative type-checking gate.

Editor integration is convenience only. The repository tasks and CI remain authoritative and can be run without VS Code.

## Streamlit agent skill

The repository includes a discovery skill at
[`.agents/skills/developing-with-streamlit/`](.agents/skills/developing-with-streamlit/SKILL.md).
Codex discovers it from the repository; no personal skill installation is needed.
The files are ordinary version-controlled files, not symlinks into a local environment.

After setting up the project environment, verify discovery from the repository root:

```sh
uv run --locked --extra dev python .agents/skills/developing-with-streamlit/scripts/discover.py --project-dir .
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

`prek` runs the lightweight file and Ruff checks automatically on commit using the repository's existing `.pre-commit-config.yaml`. GitHub Actions independently runs the locked Ruff, mypy, and pytest quality gates on pull requests and pushes to `main` for supported Python versions.

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

Keep runtime dependencies small. Add a dependency only when it materially reduces implementation or modelling complexity. Runtime dependencies belong in `project.dependencies`; development and analysis-only dependencies must remain separate from runtime requirements.

The current `dev` and `analysis` extras predate the uv/mise migration. A future cleanup may move local-only tooling to standardized PEP 735 dependency groups; that migration should be done together with regeneration and verification of `uv.lock`, not as an unrelated metadata-only edit.

The project intentionally does not have a public release or license yet. Those decisions should be made explicitly if the PoC becomes a maintained/public project.
