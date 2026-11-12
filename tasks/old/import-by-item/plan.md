Spec: spec/old/import-by-item.md

# Implementation Plan: Import worn models by item

Branch: `feat/import-by-item`. One commit per task. Tasks are in `tasks/old/import-by-item/todo.md`. Issue: issue 07 (`git show 2a78edd:.scratch/osrs-focus/issues/07-imported-worn-items-show-stored-colours.md`).

## Overview

A new operator, File > Import > `RS Item (from cache)`, imports the worn model of one item for the Male or Female body. Each model file of the worn model becomes its own object, named by its model id, at its stored position. Faces that an item recolour finds show the replacement colour at the Brightness setting. The stored game values stay the model file's own, so export writes the model as the game stores it ([ADR 0006](../../../docs/adr/0006-export-writes-the-game-values-stored-at-import.md)). The importer panel tells the user what an item import shows. File > Import > RS Model does not change.

## What the code reading found

- The operator reads the cache through `appearance_props.profile()` ([appearance_props.py:63](../src/rsps_toolkit/blender/appearance_props.py:63)). `CacheProfile.items` gives `WornItem` (models, offsets, recolours, retextures). `CacheProfile.load_model` decodes with the revision 149 profile and raises `MissingResourceError` for a missing model, with the model id in the message ([cache_profile.py:116](../src/rsps_toolkit/formats/cache_profile.py:116)). `CacheProfile.items` raises it too when the cache lacks the item group.
- `model_to_object` ([mesh.py:13](../src/rsps_toolkit/blender/mesh.py:13)) makes one material per distinct `(colour, texture, alpha)` and stores the values on the material (`face_materials.face_material`). Export reads the values back from the material, never from the shown colour (`material_values`). So the only change needed is a way to pass a different colour to show. Textured faces have no face colour and stay as they are.
- Recolour order: `formats/appearance.py` `recolour` replaces every face colour equal to `find`, and `item_model` applies the item's recolours in list order, so a later recolour finds colours that an earlier one put in. The shown colour list is the model's face colours copied, then run through the same function in the same order. No new colour conversion.
- Material identity changes. The key must include the shown colour, or two faces with one stored colour and different shown colours would share a material. For a plain import the shown colour equals the stored one, so the key is unchanged and the plain import keeps its materials (spec: "RS Model does not change").
- Source record: `model_to_object` already calls `model_source.write_source` and `mark_imported`. The importer adds `record_source_hash` of the model's bytes in the cache. `CacheProfile.load_model` reads the bytes and returns only the decoded `Model`, so the bytes are lost. T1 splits it: a new `CacheProfile.model_bytes(model_id)` reads the raw container once, and `load_model` becomes `decode(self.model_bytes(id), profile="osrs-149")`. The importer calls `model_bytes`, hashes them and decodes the same bytes, so each model file is read once. Behaviour and error messages of `load_model` stay the same.
- The existing plain-import cleanup removes new objects and meshes. It does not remove materials. The item import must leave "nothing" in the file (user story 9), so its cleanup also removes the materials it made.
- `RSPS_OT_pick_item` ([appearance_items.py:54](../src/rsps_toolkit/blender/appearance_items.py:54)) and its `_slot_items` are the prior art for the item list, the `<name> (<id>)` label and the kept-list workaround for Blender's enum strings. `items_for_slot` also needs a slot, which an import has not got, so the new list is a separate small function (repetition over a shared abstraction).
- Fixtures: items 1149, 2653 and 3140 have recolours. All their male and female model files are in `tests/fixtures/appearance/`. Item 2653: male 3379, 164, 3381, female 3383, 344, 3381, recolours 61 to -29403, 41 to -28266, 24 to 937 (`ItemDefinitions.json`). The decoder reads colours as unsigned 16 bit, so -29403 is 36133. No fixture item has retextures or lacks a female model, so T4 builds those item definitions in the test.
- Naming: the third model of 2653 is 3381 for both bodies. Importing the same item twice makes `3381.001` (Blender adds the suffix). Export names the file from the object name, so the user renames it back. This is how a repeated plain import behaves too. Not handled.

## Dependency graph

```
T1 import by item id (objects, names, selection, source, export)
 ├─ T2 recolours shown (mesh.py, face_materials.py)
 ├─ T3 dialog and menu entry
 │   └─ T5 stored item data and panel note
 └─ T4 refusals and cleanup
```

T2, T3 and T4 depend only on T1. They touch `import_item.py` or `mesh.py`, so they run one after another, not in parallel. T5 needs the operator's final shape, so it comes after T3.

## Architecture decisions

- **New module `blender/import_item.py`** with the operator, its item list, its menu entry and `classes`. The spec left this open. Reason: `import_model.py` holds the file-based importer (`ImportHelper`, `files`, profiles) and shares nothing with a cache-based one. The module name follows `import_model`, `import_animation`.
- **Properties and operators:** `import_scene.rs_item` has `body` (EnumProperty `MALE` default, `FEMALE`) and `item` (EnumProperty with an items callback, like `RSPS_OT_pick_item`), and its `invoke` opens a search popup. A second operator, `import_scene.rs_item_body`, shows the body choice as a dialog, and OK opens the search popup of the first (user, 2026-11-11: the plain dropdown could not be searched). The callback lists items whose first model id for the chosen body is not -1, sorted by lower-case name then id, labelled `<name> (<id>)`.
- **Item list function** `items_with_worn_model(items, female)` is pure and goes in `formats/appearance.py` beside `items_for_slot`. It adds a function and changes none that Player Appearance uses (the spec's "ask first" does not apply). If the user prefers no edit to that file, it moves into `import_item.py`.
- **Recolours shown:** `model_to_object` gains an optional `shown_colours: Sequence[int | None] | None` (one per face, `None` means "same as stored"). `face_materials.face_material` gains an optional `shown_colour`. The material key becomes `(colour, texture, alpha, shown)`. The plain import passes nothing.
- **Stored item data** (item id, name, body) goes on the object, through new read and write functions in `rs_layers.py`, because the architecture notes keep Blender storage conventions there. It names no vertex or face, so the "stored data survives edits" standard needs no index test. A test checks that it survives a mesh edit and that a plain import has none.
- **Panel note** is `item_import_note(obj) -> str | None` in `ui.py`, and the panel draws it under `draw_presentation_notice`. The note text names the item and the body and says that export writes the model's own colours.
- **Refusals:** the operator checks everything that can be known before it makes anything (retextures, body model, then loading every model file), so a refusal usually has nothing to remove. A snapshot of objects, meshes and materials before the build, and removal of what is new on any failure, covers the rest.
- **Reports:** a refusal is `self.report({"ERROR"}, message)` and returns `CANCELLED`, as `RSPS_OT_clear_slot` does. Messages follow the style of the existing ones: name the cause and the setting to fix.

## Task list

See `tasks/old/import-by-item/todo.md`. Five tasks and a close-out, three checkpoints.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| An enum with thousands of items (snapshot 430 has 3503 male worn items) is slow, or its dropdown has no search | High | Happened in T3: the dropdown opened at once but could not be searched. The user chose the fallback on 2026-11-11: a body dialog, then `invoke_search_popup` as in Player Appearance. |
| A test passes because a face already showed the right colour | High | T2 checks a face with a recolour and a face without one in the same object, and the stored value of the recoloured face. A mutation check (recolour ignored) must fail them. |
| Blender rejects an enum value that is not in the current list before `execute` runs, so the "no worn model for this body" refusal cannot be reached headless | Med | T4 first checks what Blender does. If it rejects the value, the test reaches the check through the shared function that `execute` calls, and the task result says so. |
| Item and body stored on an object are stale after the user swaps its material or recolours it by hand | Low | The note says what the import showed, not what the object shows now. The wording is part of T5. |

## Open questions

- **Materials on refusal.** The spec says a refused import removes objects and meshes. The plan also removes the materials, so "adds nothing to the file" (story 9) is true. Say if the materials should stay.
- **Popup search.** Closed on 2026-11-11 by the user's choice of a search popup. Typing a name and an id into it still needs the user's check in Blender (T3 Verify).
