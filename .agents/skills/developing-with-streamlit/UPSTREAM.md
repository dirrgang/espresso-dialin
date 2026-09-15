# Upstream provenance

- Source: https://github.com/streamlit/agent-skills
- Revision: `c69a265613f17cdd69d42e6f67b704214178fae5`
- Source directory: `developing-with-streamlit/`
- Vendored on: 2026-09-15
- License: Apache-2.0; upstream license text is preserved in `LICENSE`.
  This license applies to the vendored skill, not to the espresso-dialin project.

## Local changes

`SKILL.md` is unchanged from upstream. `scripts/discover.py` has Ruff formatting
and modern Python type annotations to satisfy this repository's Python 3.12+
quality gates; discovery behavior is unchanged. `UPSTREAM.md` is local metadata.
The full reference documentation is loaded from the installed Streamlit package
and is not vendored here.

## Updating

Review an explicit upstream commit, then replace `SKILL.md`, `scripts/discover.py`,
and `LICENSE` with the files from that revision. Preserve the upstream license
and any notices, reapply the documented style changes, and update this record.
Run the repository quality gates and the discovery command in `DEVELOPMENT.md`.
Review and commit the resulting diff. Do not replace this folder with symlinks
into `.venv` or a personal skills directory.
