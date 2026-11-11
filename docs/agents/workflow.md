# Workflow

Read this before any `/agent-skills` command, and before planning, implementing, committing or reporting. This repo uses the file mode of `agent-skills`: specs and tasks are Markdown files in the repo, and they are committed.

The user types each stage. Run one stage per session. When it ends, name the next stage and stop.

## Stages

| Stage | Command | Result |
| --- | --- | --- |
| Idea | `/agent-skills:idea-refine` | A sharp goal. |
| Design | `/agent-skills:interview-me` | A settled design. |
| Spec | `/agent-skills:spec` | `spec/<slug>.md`. |
| Plan | `/agent-skills:plan` | `tasks/plan.md` and `tasks/todo.md`. |
| Build | `/agent-skills:build` | The next unchecked task, built and committed. |
| Bug | `/agent-skills:test` | A failing test, then the fix. |
| Review | `/agent-skills:review` | Findings against the standards and the spec. |

## Design

Read `GLOSSARY.md`, `docs/adr/` and `CODING_STANDARDS.md` (those that exist) before the first question. Use the glossary's terms. Report any conflict with an ADR.

Use the glossary's terms in specs, tasks, hypotheses and test names, and follow its guidance on synonyms to avoid. A concept that is not in the glossary is either language the project does not use, so reconsider it, or a real gap, so note it for the Design stage.

Record each settled decision as an ADR in `docs/adr/` with the `documentation-and-adrs` skill, and continue the existing numbering. Add each settled term to `GLOSSARY.md`.

## Spec

Save the spec to `spec/<slug>.md`. For commands, structure and code style, link `AGENTS.md`. Keep evidence files in `.scratch/<slug>/evidence/`.

## Plan

`tasks/plan.md` and `tasks/todo.md` hold one spec's plan at a time. Name the spec file on the first line of `tasks/plan.md`. When every task is checked, move both files to `tasks/done/<slug>/` so the next plan starts clean.

## Build

One branch per spec, `<type>/<slug>`, with one commit per task. `/agent-skills:build auto` runs every unchecked task after one approval.

Implement with `test-driven-development`: one behavior at an approved public seam per red/green cycle. The seams that the spec names give that agreement.

Run the verify command from `AGENTS.md` (`Every task`) before each commit. After a task passes its checks, tick its checkbox in `tasks/todo.md` and write the result under that task. Implementation stays with the primary agent unless the user chooses delegation. Open the pull request and stop. The user merges.

## Commit review

Before each commit, run the review with fixed point `HEAD`. Give it the spec file and the tasks worked as the spec. Tell the reviewers that the work is uncommitted, so they review `git diff HEAD` and apply [CODING_STANDARDS.md](../../CODING_STANDARDS.md). Name the files this work owns, so unrelated work is excluded. Ask for approval of the exact reviewed commit. A standing approval applies only inside the scope the user gave.

## Review

Run the review in a new session, not in the build session. The command starts no subagent, so the build session would review its own work. Check out the PR branch first (`gh pr checkout <pr>`), because the command reviews staged changes or recent commits.

Run `/agent-skills:review` on the branch. Give it the spec file as the spec. Name [CODING_STANDARDS.md](../../CODING_STANDARDS.md) as the standard. The review does not read it on its own.

Fix small findings in the review session. Start a new build session for large ones.

## Earlier layout

`.scratch/<feature>/` holds specs, tickets and plans that were written before this workflow. They are history. New work uses `spec/` and `tasks/`.

`.scratch/osrs-focus/` and `.scratch/game-animation/` still mention `HANDOFF.md`. It was split into ADRs, issues, research notes and plan files on 2026-11-09. Read it with `git show 0c598c4:HANDOFF.md`.

The last three tasks of plan 02 in `.scratch/osrs-focus/plans/` have been open since 2026-11-07. They finish in their own file. Read its current task, take its seams from the plan, and tick its task checkboxes. Give the commit review the plan as the spec. Write results and progress into the plan file, not into `progress.md`.

## Reports and output decisions

Report every guess, accepted gap and inferred rule. Before committing, put every choice marked "needs the user's decision" (see [CODING_STANDARDS.md](../../CODING_STANDARDS.md)) to the user. Merging and installing the extension need their own authorization.
