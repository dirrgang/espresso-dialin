# Development and research workflow

Use small, reviewable work packages with explicit acceptance criteria. Keep implementation
completion and empirical validation separate: working acquisition software does not establish
better predictions, convergence or coffee savings.

## Where information belongs

| Artifact | Authoritative content |
| --- | --- |
| GitHub issue | Task scope, acceptance criteria, dependencies and current task status |
| Pull request | Delivered change, review discussion and verification evidence |
| [Decision log](decision-log.md) | Durable decisions, rationale, alternatives and evidence boundaries |
| [Work log](work-log.md) | Dated milestones and concise handoffs with links to tasks and evidence |
| [Next steps](next-steps.md) | Broad research phases and priorities |
| [AGENTS.md](../AGENTS.md) | Standing instructions for agents working in this repository |

Link these artifacts rather than maintaining duplicate task checklists. GitHub Issues are the
detailed work log. A Project board is optional; it should display the same issues rather than
introduce another task list. Do not record every tool invocation or copy chat transcripts into
repository logs.

## Start a work package

1. Read the repository guidance and relevant decisions, then inspect the branch, base commit
   and existing local changes. Preserve unrelated work.
2. For substantive work, use an issue with a concrete outcome, scope limits, relevant source
   documents, dependencies and observable acceptance criteria. Small fixes can be described
   directly in a PR; they do not need a separate issue merely for bookkeeping.
3. Use the implementation or research/experiment issue template. Explicitly distinguish
   software delivery from evidence collection or model validation.
4. Check dependencies before starting dependent work. Record missing data or external inputs
   in the issue; absence of access is not evidence of absence.

Prefer one coherent work package per branch/PR. When a reused branch contains both merged
and new work, compare against current main before preparing the next PR. User authorization
for a task governs execution; this workflow adds no blanket approval step.

## Execute and verify

Keep progress in the issue when something material changes: a dependency, scope, finding,
blocker or verification result. A useful handoff identifies what is done, what remains,
the relevant branch/commit and the next concrete action. If GitHub cannot be accessed,
record a temporary handoff in the work log and identify what still needs synchronization.

For code changes, run `mise run check` before claiming completion. Record the checked
revision or working-tree scope and the command/result in the PR. Report passed, failed and
unavailable checks separately; individual checks do not replace a blocked full gate. For
documentation/templates, inspect links, Markdown and template structure and run the repository
checks where available. Do not add tests that merely mirror documentation.

For research, identify source versions/snapshots and preserve chronology, bean/session
boundaries, missingness and Assisted versus Learning intent. Define experimental schedules,
coffee budgets, stopping/deviation rules and evaluation criteria before outcomes. Record
actual measurements and inconclusive findings without promoting hypotheses to decisions.
See [validation.md](validation.md) and [research-methods.md](research-methods.md).

## Finish or hand off

- Use the PR template to explain the problem, resulting behavior, verification and material
  limitations. Link the issue; use `Closes #...` only when merging the PR satisfies that issue.
- Close an implementation issue when its delivery criteria are satisfied. Keep any separate
  empirical-validation issue open until its own evidence criteria are satisfied. An
  inconclusive experiment can be complete when its predefined reporting criteria are met.
- Update relevant domain documentation when an assumption, interface or observed result
  materially changes. Record consequential decisions in the decision log with evidence links.
- Add a short work-log entry for a meaningful milestone or interrupted handoff. Identify
  implemented, integrated and empirically validated states explicitly when they differ.

## Decision records

Keep the existing dated records and anchors. New decisions use a stable sequential ID such
as `D-001`, a date and a status: `proposed`, `accepted` or `superseded`. This numbering starts
with the workflow decision; older records are not retrospectively renumbered.

Each new record states context, decision, alternatives considered, consequences and evidence
or linked issues/PRs. A proposal is not authoritative until accepted. A substantive reversal
gets a new record; mark the old record superseded and link both directions while retaining
its rationale. Minor factual corrections should be explicit and reviewable. Hypotheses and
open questions remain labelled as such; acceptance of a software design is not validation
of its modelling assumptions.
