# RSPS Toolkit

A Blender 5.2 extension that imports, edits and exports RuneScape client models.

## Every task

- Use **uv** and **Python 3.13**.
- Run `prek run --all-files` to verify a change. It runs ruff, pyrefly, unit tests and file hygiene, and runs again at commit time.
- Use the Matt Pocock skill that [Workflow](docs/agents/workflow.md) names for the kind of work, and read the rest of that file before planning, implementing, committing or reporting.
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

## Agent skills

### Issue tracker

Track issues and specs as local Markdown under `.scratch/`. See [Issue tracker](docs/agents/issue-tracker.md).

### Triage labels

Use the five default triage roles as local issue statuses. See [Triage labels](docs/agents/triage-labels.md).

### Domain docs

Single-context: root `GLOSSARY.md` and `docs/adr/`. See [Domain docs](docs/agents/domain.md).
