# Workflow

Read this before any `/agent-skills` command, and before planning, implementing, committing or reporting. The commands default to `SPEC.md` and `tasks/todo.md`. This repo uses the tracker mode of `planning-and-task-breakdown`: GitHub issues hold the tasks, and files under `spec/` hold the specs. [Issue tracker](issue-tracker.md) holds the `gh` commands.

The user types each stage. Run one stage per session. When it ends, print the next stage's command as the last line, with real issue, PR and file values, and stop. The user pastes that line into a new session, so it must need no edits. `/agent-skills-next` prints the same commands for the whole tracker.

## Stages

| Stage | Command | Result |
| --- | --- | --- |
| Idea | `/agent-skills:idea-refine <issue>` | A sharp goal, as a comment on the issue. |
| Design | `/agent-skills:interview-me <issue>` | A settled design, as a comment on the issue. |
| Spec | `/agent-skills:spec <issue>` | `spec/<issue>-<slug>.md`. |
| Plan | `/agent-skills:plan <issue>` | One sub-issue per task. |
| Build | `/agent-skills:build <task issue>` | One branch, one pull request. |
| Bug | `/agent-skills:test <issue>` | A failing test, then the fix, on one branch with one pull request. |
| Review | `/agent-skills:review issue #<task>, PR #<pr>, spec <spec file>, standard <standard file>` | Findings against the standards and the spec. |

An issue that is one task with acceptance criteria goes straight to Build.

## Labels

| Label | Meaning |
| --- | --- |
| `needs-triage` | Nobody has judged the issue yet. |
| `needs-info` | The issue waits for an answer from its reporter. |
| `ready-for-agent` | One task with acceptance criteria. An agent can build it unattended. |
| `ready-for-human` | The work needs the user's hands or judgment. |
| `wontfix` | The issue will not be done. |

An open issue carries exactly one of these. Change a label only when the user approves it.

## Design

Read `GLOSSARY.md`, `docs/adr/` and `CODING_STANDARDS.md` (those that exist) before the first question. Use the glossary's terms. Report any conflict with an ADR.

Use the glossary's terms in specs, issues, hypotheses and test names, and follow its guidance on synonyms to avoid. A concept that is not in the glossary is either language the project does not use, so reconsider it, or a real gap, so note it for the Design stage.

Record each settled decision as an ADR in `docs/adr/` with the `documentation-and-adrs` skill, and continue the existing numbering. Add each settled term to `GLOSSARY.md`.

## Spec

Save the spec to `spec/<issue>-<slug>.md`, where `<issue>` is the source issue. Link the source issue on the first line. For commands, structure and code style, link `AGENTS.md`. Comment the spec's path on the source issue. Keep evidence files in `docs/research/`.

## Plan

Publish each task as a sub-issue of the source issue. Add blockers as native `blocked_by` dependencies. A task body names no blocker: a body list goes stale, and the native edges stay true.

Give every item of a spec's list to one task. A review of each task alone misses an item that two tasks share.

Task body: `Parent`, `Spec` (the spec file's path), `What to build`, `Acceptance criteria`, `Verification` (the exact command). Label each task `ready-for-agent`.

`tasks/plan.md` holds the plan's decisions, risks and an ordered list of the task issue numbers. It is git-ignored scratch. A plan is complete when every issue it lists is closed, and a complete plan can be replaced without asking.

## Build

`/agent-skills:build` reads one argument, `auto`. Any other text selects single-task mode, so the task issue number you type is context. The plan is the open sub-issues of the source issue.

Pick the task with the **frontier query** in [Issue tracker](issue-tracker.md). Claim it with `gh issue edit <n> --add-assignee @me`.

One task, one branch, one pull request. Branch: `<type>/<issue>-<slug>`. Commit subject: `<type>: <summary> (#<issue>)`, with a conventional-commit type (`feat`, `fix`, `chore`, `docs`). PR title: a plain sentence. Put `Closes #<issue>` in the PR body. Bug tasks start with a failing test.

`/agent-skills:build auto` runs every task of one spec on one branch, `<type>/<source issue>-<slug>`, with one commit per task. Its pull request closes every task issue.

Implement with `test-driven-development`: one behavior at an approved public seam per red/green cycle. The seams that the spec names give that agreement.

Run the verify command from `AGENTS.md` (`Every task`) before each commit. Implementation stays with the primary agent unless the user chooses delegation. Open the pull request, print the review command and stop. The user merges.

The review command is the session's last line:

```
/agent-skills:review issue #<task>, PR #<pr>, spec <spec file>, standard CODING_STANDARDS.md
```

- **Spec file**: the `Spec` line of the task body. When the task body has none, use the `spec/` path in the parent issue's body. When neither names one, leave out the `spec` part.
- In `auto` mode, `<task>` is the source issue.

A Bug session ends with the same command.

## Commit review

Before each commit, run the review with fixed point `HEAD`. Give it the spec file and the task issue as the spec. Tell the reviewers that the work is uncommitted, so they review `git diff HEAD` and apply [CODING_STANDARDS.md](../../CODING_STANDARDS.md). Name the files this work owns, so unrelated work is excluded. Ask for approval of the exact reviewed commit. A standing approval applies only inside the scope the user gave.

## Review

Run the review in a new session, not in the build session. The command starts no subagent, so the build session would review its own work. Check out the PR branch first (`gh pr checkout <pr>`), because the command reviews staged changes or recent commits.

Run `/agent-skills:review` on the branch with the command that the Build section gives. It names the task issue, the PR, the spec and [CODING_STANDARDS.md](../../CODING_STANDARDS.md), because the review does not read the spec or the standard on its own.

Fix small findings in the review session. Start a new build session for large ones.

## Earlier layout

`spec/old/` and `tasks/old/` hold the specs and plans that were written before this workflow. They are history. Their evidence files are in `docs/research/`. Tasks were issue files in `.scratch/osrs-focus/issues/` until 2026-11-12. The open ones became GitHub issues 8 to 11. Read a closed one with `git show 2a78edd:.scratch/osrs-focus/issues/<file>`.

Comments in the code that say "issue 27" mean the old issue file of that number, not a GitHub issue.

`tasks/old/osrs-focus/` and `tasks/old/game-animation/` still mention `HANDOFF.md`. It was split into ADRs, issues, research notes and plan files on 2026-11-09. Read it with `git show 0c598c4:HANDOFF.md`.

## Reports and output decisions

Report every guess, accepted gap and inferred rule. Before committing, put every choice marked "needs the user's decision" (see [CODING_STANDARDS.md](../../CODING_STANDARDS.md)) to the user. Merging and installing the extension need their own authorization.
