# Work log

Short dated milestones and handoffs, newest first. GitHub Issues own current task status;
these entries are snapshots, not a second backlog. Follow [workflow.md](workflow.md).
For each meaningful entry record the outcome, evidence/verification, remaining work and next
action. Identify the branch/commit when relevant; link PRs and decisions once available.

## 2026-10-22 — Establish work tracking and record the project handoff

**Outcome:** Added the [workflow guide](workflow.md), implementation and research issue
templates, a PR template, agent handoff rules and links from README/roadmap.
[D-001](decision-log.md#d-001--2026-10-22--work-tracking-and-agent-handoffs) records the accepted
workflow. Created the four linked work packages below. The workflow changes are prepared
on `chore/agent-workflow`, based on `origin/main` at `df83d24`, independently of the October
extraction baseline. Published for review in
[PR #21](https://github.com/dirrgang/espresso-dialin/pull/21); integration remains pending.

**Initial inspected state:** The original checkout was `feat/extraction-setting-experiment` at `369c4c0`
(2026-10-07). Local main is `df83d24`, the September 17 merge of
[PR #16](https://github.com/dirrgang/espresso-dialin/pull/16). The GitHub main decision log
inspected on October 22 also ends with the September extraction experiment. The feature
branch additionally implements schema-v5 directional extraction feedback; it is not yet
integrated into the inspected main. Acquisition, simple dose baselines and three Learning
experiment families are implemented. Their software completion does not establish lower
coffee consumption or validated extraction control. The runtime database was not inspected;
actual prospective evidence availability remains unknown. The existing local change in
`pyproject.toml` predates this workflow task and is outside its scope.

**Initial verification:** `mise run check` passed on Python 3.14.7 against the working tree based on
`369c4c0`, including this workflow change and the pre-existing `pyproject.toml` edit: Ruff,
strict mypy, 214 tests, 97.26% branch-inclusive coverage and all repository hooks. The initial
sandbox attempt could not write the uv cache; the subsequent run with cache access passed.
Checked 46 local links across nine Markdown files, both issue-template YAML headers and the
D-001 cross-reference. Explicit file-scoped hooks also cover the newly added files, which
are not included in `prek run --all-files` until tracked.

The October 7 baseline commit's historical full-gate limitation is therefore resolved for
this inspected working tree; isolated baseline review, PR/CI evidence and integration remain
the separate scope of #17.

**Follow-up links:**

- [#17 — Review and integrate the extraction-direction baseline](https://github.com/dirrgang/espresso-dialin/issues/17).
- [#18 — Inventory prospective sessions and experiment evidence](https://github.com/dirrgang/espresso-dialin/issues/18).
- [#19 — Predefine the next pilot and evaluation criteria](https://github.com/dirrgang/espresso-dialin/issues/19),
  dependent on the inventory and, if needed, baseline integration.
- [#20 — Collect and assess the pilot](https://github.com/dirrgang/espresso-dialin/issues/20),
  dependent on the predefined protocol; physical collection belongs to the operator.

**PR verification:** `mise run check` passed on Python 3.14.7 on the isolated main-based
workflow branch: Ruff, strict mypy, 195 tests, 97.02% branch-inclusive coverage and repository
hooks. The suite emitted eight unclosed-SQLite `ResourceWarning`s in the existing maintenance
test; no application/test code was changed. Local links and issue-template headers were
rechecked on this branch (43 local links and both template headers). Newly added files are
explicitly included in the final hook run.

**Next action:** Review/integrate the baseline through #17; inventory available real evidence
through #18 independently. Use the inventory to choose the next specific identification
question before spending coffee or adding model complexity.
