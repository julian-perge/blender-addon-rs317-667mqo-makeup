# RSPS Toolkit

An extension for Blender 5.2 or later that imports, edits and exports RuneScape client models.

## Every task

- Use **uv** and **Python 3.13**.
- Run `prek run --all-files` to verify a change. It runs ruff, pyrefly, unit tests and file hygiene, and runs again at commit time.
- Read [Workflow](docs/agents/workflow.md) before planning, implementing, committing or reporting outside an `/agent-skills` stage.
- Use placeholders such as `<path to cache>` instead of local paths and personal details in commits, issues and comments, because the repo is public.
- Leave AI attribution out of commits, issues and comments.

## Build commands

Build only when requested.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B --command extension validate src/rsps_toolkit
mkdir -p dist
$B --command extension build --source-dir src/rsps_toolkit --output-dir dist
```

## Read the doc that matches the task

- [Architecture and compatibility](docs/agents/architecture.md) and [Coding standards](CODING_STANDARDS.md): before changing code.
- [GLOSSARY.md](GLOSSARY.md), with the decision records in [docs/adr/](docs/adr/) that touch the area: before exploring an area or naming a model concept.
- [Model format references](docs/research/model-formats.md): before deciding how a model field behaves.
- [Tests and reference data](docs/agents/testing.md): before writing or running tests, or working with fixtures.
- [Blender execution and packaging](docs/agents/blender.md): before running Blender or packaging, or working with the manifest or how tests reach Blender.
- [Scripted use](docs/scripted-use.md): before a script of another repo builds a region, a player, a clip or an item, or before changing `blender/scripting.py`.
- [Hand-made motion runbook](docs/hand-made-motion.md): before keying a motion on the joints of a player through the Blender MCP.
- [Named client source](scripts/named-client/README.md): before you read `gamepack-149.jar` with `javap`. Run `uv run scripts/lookup-client.py <name>` first. For each placeholder that a session names, add a row with a link to its evidence in [client-names.tsv](docs/research/client-names.tsv). The source folder comes from `scripts/named-client/build.sh`.

## Workflow

- Tasks are tracked in GitHub Issues for julian-perge/blender-addon-rs317-667mqo-makeup, with the `gh` CLI ([Issue tracker](docs/agents/issue-tracker.md)). `/agent-skills:plan` creates one sub-issue per task. `tasks/` is git-ignored scratch, except `tasks/old/`.
- Specs are files at `spec/<issue>-<slug>.md`, not `SPEC.md`. Specs from before this workflow are in `spec/old/`.
- ADRs go in `docs/adr/`. Read `GLOSSARY.md` and `docs/adr/` (those that exist) before design work.
- Start each `/agent-skills` stage with `agent-skills brief <stage> <n>`. It prints every rule of `docs/agents/workflow.md` that the stage needs, so do not read that file in a stage. Before other work in this repo, read all of `docs/agents/workflow.md`.
