# Workflow

Read this to pick the Matt Pocock skill for a task, and before planning, implementing, committing or reporting.

Read the feature's approved spec and the ticket being worked before changing code, and keep evidence files in the feature's `.scratch/<feature-slug>/` directory. A plan from the earlier layout stands in for both, as [Issue tracker](issue-tracker.md) describes.

## Skills by task

- Design interviews: `mattpocock-skills:grilling` and `mattpocock-skills:domain-modeling`.
- Specs and tickets: `/to-spec` writes the feature's spec and `/to-tickets` splits it into tickets, as [Issue tracker](issue-tracker.md) lays them out. Both run only when the user types them, so ask the user to run them when a new feature needs its spec or tickets.
- Module interfaces: `mattpocock-skills:codebase-design`.
- Primary-source investigation: `mattpocock-skills:research`.
- Implementation: `mattpocock-skills:tdd`, one behavior at an approved public seam per red/green cycle. The seams an approved spec names supply that agreement.
- Failures: `mattpocock-skills:diagnosing-bugs` before proposing a correction.
- Instructions and agent documents: `mattpocock-skills:writing-for-agents`.
- Review: `mattpocock-skills:code-review`, both Standards and Spec axes.

Complete the specified checks before reporting success. After each verified ticket, tick its checkboxes, record the result under its `## Comments`, and close it as [Issue tracker](issue-tracker.md) says. Implementation stays with the primary agent unless the user chooses delegation.

## Commit review

Before each commit, run `mattpocock-skills:code-review` with fixed point `HEAD`, giving it the feature's `spec.md` and the tickets worked as the spec. Tell reviewers the work is uncommitted so they review `git diff HEAD`, applying [CODING_STANDARDS.md](../../CODING_STANDARDS.md). Identify owned files so unrelated work is excluded. Request approval for the concrete reviewed commit; standing approval applies only within the scope the user gave it.

## Reports and output decisions

Report every guess, accepted gap and inferred rule. Before committing, put every choice marked "needs the user's decision" (see [CODING_STANDARDS.md](../../CODING_STANDARDS.md)) to the user. Merging and installing the extension need their own authorization.
