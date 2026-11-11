# Preserve Source choices the inputs do not decide

Status: resolved

Two agent choices in [plan 02](../plans/02-toolkit.md), Task 4, need the owner's decision:

- Preserve Source writes `{object name}.dat`.
- A failed import removes the objects and meshes it created.

The rest of that list is settled: the approved design (Q14) makes Preserve Source the recommended action, and plan 02 keeps auto-detected priorities out of it and stores the source file's hash.

## Decisions

The user chose on 2026-11-10, in a design interview, to keep both choices:

1. Preserve Source writes `{object name}.dat`, the name every export preset gives its main file, so an object imported from `306.dat` exports as `306.dat` and renaming the object renames the file.
2. When a model file cannot be built in Blender, RS Model import removes the objects and meshes it made for that file, imports the remaining files and reports the skipped one.

## Comments

- 2026-11-10, design interview with the user: resolved, both choices kept. The code that makes each choice now cites this issue.
