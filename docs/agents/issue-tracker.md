# Issue tracker: Local Markdown

Issues and specs live as Markdown files in `.scratch/`.

## Conventions

- Use one directory per feature: `.scratch/<feature-slug>/`.
- Store the spec at `.scratch/<feature-slug>/spec.md`.
- Store each implementation ticket in its own file at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never one combined tickets file.
- Record triage state in a `Status:` line near the top, using [Triage labels](triage-labels.md). Close a finished ticket with `Status: resolved`, as the closed issues in `.scratch/osrs-focus/issues/` are.
- Append comments and conversation history under `## Comments`.

## The earlier layout

`.scratch/osrs-focus/` and `.scratch/game-animation/` predate these conventions. Their `plan.md`, `plans/<NN>-<slug>.md` and `progress.md` are history, and new features get their own directory. Those files still mention `HANDOFF.md`, which was split into ADRs, issues, research notes and plan files on 2026-11-09; read it with `git show 0c598c4:HANDOFF.md`.

Plans with open tasks finish in their own files: on 2026-11-10 that is the last three tasks of plan 02 in `.scratch/osrs-focus/plans/`, open since 2026-11-07. Where [Workflow](workflow.md) says spec and ticket, such a plan stands in for both: read its current task, take its seams from the plan, tick its task checkboxes, and give the commit review the plan as the spec. Its results and progress go into the plan file, not into `progress.md`.

## Skill operations

When a skill says "publish to the issue tracker", create the spec or ticket file at the paths above, creating the directory if needed.

When a skill says "fetch the relevant ticket", read the referenced local file. The user normally passes its path or issue number.

## Wayfinding operations

For `/wayfinder`:

- Map: `.scratch/<effort>/map.md`, holding Notes, Decisions-so-far and Fog.
- Child ticket: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with its question in the body.
- Type: record `research`, `prototype`, `grilling` or `task` on a `Type:` line.
- Blocking: list dependencies on a `Blocked by: NN, NN` line. A ticket is unblocked when every listed ticket is resolved.
- Frontier: choose the first open, unblocked and unclaimed ticket by number.
- Claim: set `Status: claimed` and save before working.
- Resolve: append the answer under `## Answer`, set `Status: resolved`, and add a summary and link to the map's Decisions-so-far.

Wayfinding uses `claimed` and `resolved` for its workflow, and `resolved` closes any finished ticket; triage uses the five roles in the label guide.
