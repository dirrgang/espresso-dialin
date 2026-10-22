# Development and research workflow

Use small, reviewable work packages with explicit acceptance criteria. Keep implementation
completion and empirical validation separate: working acquisition software does not establish
better predictions, convergence or coffee savings.

## Where information belongs

| Artifact | Authoritative content |
| --- | --- |
| GitHub issue | Task scope, acceptance criteria, dependencies, current task status and ongoing handoffs |
| Commit message | Change-specific purpose, outcome, verification and applicable handoff context |
| Pull request | Delivered change, review discussion, verification evidence and current delivery handoff |
| [Decision log](decision-log.md) | Durable decisions, rationale, alternatives and evidence boundaries |
| [Work log](work-log.md) | Historical archive; no routine updates or required session-start reading |
| [Next steps](next-steps.md) | Broad research phases and priorities |
| [AGENTS.md](../AGENTS.md) | Standing instructions for agents working in this repository |

Link these artifacts rather than maintaining duplicate task checklists. GitHub Issues are the
detailed work log. A Project board is optional; it should display the same issues rather than
introduce another task list. Keep commit context specific to the committed change and the
PR description specific to the delivered work; neither is a second task backlog. Do not
copy tool or chat transcripts into issues, commit messages, PRs or repository documentation.

## Roadmap, tasks and parent issues

Keep broad phases, priorities and conditional research options in [next-steps.md](next-steps.md).
Move selected, actionable work into issues with explicit outcomes and acceptance criteria;
leave a short issue link in the roadmap. Do not create an implementation commitment for every
possible future model or product feature.

A parent issue (epic) represents one coherent, finishable goal spanning several bounded tasks.
Use sub-issues when those tasks are ready to scope. A deferred parent states its activation
criteria; being tracked does not authorize immediate execution. A roadmap can contain several
such goals and is not itself an epic. Keep current status and detailed dependencies in issues,
and retain existing work-log entries as dated historical evidence rather than current plans.

## Start a work package

1. Read the repository guidance, relevant issue and its latest comments, linked PR and
   decision records. If no task is identified, use the roadmap to select work. Inspect the
   branch, base commit and existing local changes; preserve unrelated work. The archived
   work log is optional historical context, not the session entry point.
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

Keep progress and ongoing handoffs in the issue when something material changes: a dependency,
scope, finding, blocker or verification result. Update the PR description when a PR exists.
A useful handoff identifies what is done, what remains, the relevant branch/commit, verification
and its checked revision or working-tree scope, and the next concrete action. Distinguish
committed work from local changes and implemented, integrated and empirically validated states.

If GitHub cannot be accessed, preserve a temporary untracked handoff outside the archived
work log (for example in a task-specific temporary file). Report its location and what must be
synchronized to the issue/PR when access returns. Do not commit that temporary note or unrelated
work just to create a handoff; a commit's body can preserve context for the change it contains.

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

## Commit and PR messages

For substantive commits, use a concise subject describing the change and a body explaining
its purpose and outcome, relevant verification, and unresolved limitations or next action
where applicable. Reference the issue/PR when available. Commit messages are snapshots of
the committed change; later verification or status changes belong in the issue/PR rather
than a rewritten published commit. Never imply that checks covered uncommitted work or a
different revision. Small self-explanatory fixes need no ceremonial handoff block.

Keep the PR description current with the final behavior, issue/decision links, verification
and checked revision, material limitations, and remaining work or next action. Use the PR
template's handoff section; write None when no work remains within the PR's scope. If only
part of an issue is delivered, identify the remaining criteria and keep the issue open.

## Finish or hand off

- Use the PR template to explain the problem, resulting behavior, verification and material
  limitations. Link the issue; use `Closes #...` only when merging the PR satisfies that issue.
- Close an implementation issue when its delivery criteria are satisfied. Keep any separate
  empirical-validation issue open until its own evidence criteria are satisfied. An
  inconclusive experiment can be complete when its predefined reporting criteria are met.
- Update relevant domain documentation when an assumption, interface or observed result
  materially changes. Record consequential decisions in the decision log with evidence links.
- Record the final or interrupted handoff in the issue and current PR description, with
  change-specific context in substantive commit bodies. Do not append to the archived work log.

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
