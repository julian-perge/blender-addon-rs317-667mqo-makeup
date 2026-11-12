# Tasks

Spec: `spec/import-by-item.md`. Plan: `tasks/plan.md`. Each task ends with `prek run --all-files`, a commit review, and one commit on `feat/import-by-item`. Tick a task and write its result under it. Build each with `test-driven-development`: one behavior at the operator seam per red/green cycle.

## Phase 1: The import

- [x] **T1 Import an item's worn model by item id** (M)
  - Description: New operator `import_scene.rs_item` in `blender/import_item.py`, with `body` (Male default, Female) and `item` (list of items with a worn model for the body). `execute` loads each model file of the worn model, makes one object per file named by model id at its stored position (no offset, no joining), writes the source record and the source hash (from one read of the model bytes through a new `CacheProfile.model_bytes`, which `load_model` now uses too), and selects the objects with the last one active. Faces show their stored colours (recolours come in T2). The class is registered in `blender/__init__.py`. No menu entry yet.
  - Accept:
    - [x] Item 2653 male gives objects 3379, 164 and 3381. Female gives 3383, 344 and 3381. Vertex positions equal the decoded model files' (no offset).
    - [x] The stored game values of each object equal the decoded model file's (`object_to_model(obj)` equals `decode(file, profile="osrs-149")`), and exporting an object writes a model whose face colours equal the file's.
    - [x] The objects are selected, earlier selections are cleared, and the last model of the worn model is active.
    - [x] Each mesh has the same source record as a plain import of the same model, and `stored_hash` equals the SHA-256 of the model's bytes in the cache.
    - [x] The item list for Male is the fixture items with a first male model other than -1, sorted by name then id, labelled `<name> (<id>)`. The list for Female follows the female models. The list function is in `formats/appearance.py` and has a unit test.
  - Verify:
    - [ ] `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_import_item.py` passes, and each case failed before its code.
    - [ ] `uv run pytest` passes (the list function).
    - [ ] `prek run --all-files` passes.
    - [x] Commit review with fixed point `HEAD`, spec `spec/import-by-item.md`, standards `CODING_STANDARDS.md` (spec and standards sub-agents; findings fixed).
  - Result (2026-11-11): `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh` gives 789 passed, 3 skipped (9 cases in `test_import_item.py`, each red on the missing module before the code). `uv run pytest` gives 1334 passed, 24 skipped. `prek run --all-files` passes.
    - Choices to report: (1) The operator imports every model id of the body's worn model that is not -1, as the spec says. `item_model` skips a third model when the second is -1; the importer does not. (2) `object_to_model(obj)` equals the decoded file except `profile`: a model in the old encoding has no source fields, so a mesh does not keep `osrs-149`. A plain RS Model import with the OSRS149 format gives the same (checked by hand), so the test expects `profile=None` for such models. (3) The import passes the same texture lookup as the plain import. (4) The operator reports `Imported <n> models of <name> (<id>)`; T3 or T5 may change the wording.
    - Not yet handled, by task: no Cache folder or an empty list (T3, T4), refusals and cleanup (T4), recolours (T2), menu entry and dialog (T3).
  - Deps: none.
  - Files: `src/rsps_toolkit/blender/import_item.py` (new), `src/rsps_toolkit/blender/__init__.py`, `src/rsps_toolkit/formats/appearance.py`, `src/rsps_toolkit/formats/cache_profile.py`, `tests/blender/test_import_item.py` (new), `tests/unit/test_appearance.py`, `tests/unit/test_cache_profile.py`.

- [x] **T2 Faces show the item's recolours** (M)
  - Description: `model_to_object` takes an optional per-face shown colour. `face_materials.face_material` shows it and keeps the stored values. The import builds the shown colours from a copy of the model run through the item's recolours in list order (`formats.appearance.recolour`), and passes them at the Brightness setting. The plain import is unchanged.
  - Accept:
    - [x] In item 2653 male, faces with stored colour 61, 41 or 24 show the colours that `face_colour_to_rgb` gives for 36133, 37270 and 937 at the Brightness setting. Their material still holds stored colour 61, 41 or 24. The test comment cites issue 07 decisions 2 and 8 and `ItemDefinitions.json`.
    - [x] A face in the same objects with no matching recolour shows its stored colour.
    - [x] A recolour that finds a colour an earlier one produced is applied (a test builds the item definition or checks the order against `item_model`). The comment cites the spec's Colours decision.
    - [x] A plain import and an item import of the same model never share a material. Two faces with one stored colour and different shown colours get different materials, and a plain import's materials are as before (existing import and mesh tests pass unchanged).
    - [x] Export of a recoloured object writes the model file's colours (criterion 5), and the Brightness setting changes the shown colour only.
  - Verify:
    - [ ] The T2 cases failed before the code, and a mutation check (shown colour ignored; stored value written from the shown colour) fails them.
    - [ ] `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_import_item.py tests/blender/test_mesh.py tests/blender/test_import.py tests/blender/test_export.py` passes.
    - [ ] `prek run --all-files` passes.
    - [x] Commit review as in T1 (spec and standards sub-agents; findings fixed).
  - Result (2026-11-11): `scripts/test-blender.sh` gives 799 passed, 3 skipped (19 cases in `test_import_item.py`), `uv run pytest` gives 1334 passed, 24 skipped, `prek run --all-files` passes. The four T2 cases for shown colours, order and materials failed before the code. Mutation checks: showing the stored colour fails 4 cases, and writing the shown colour as the stored value fails 6.
    - Choices to report: (1) `model_to_object` raises `ValueError` when `shown_colours` does not have one entry per face; the spec does not say. (2) The material key adds the shown colour only when it differs from the stored one, so a plain import keeps its materials. (3) Material names stay `RS_Colour_<stored>_<alpha>`, so two shown variants get Blender's `.001` suffix. (4) No fixture item has a textured face with a recolour, so a textured face is tested with a model built in the test.
  - Deps: T1.
  - Files: `src/rsps_toolkit/blender/mesh.py`, `src/rsps_toolkit/blender/face_materials.py`, `src/rsps_toolkit/blender/import_item.py`, `tests/blender/test_import_item.py`.

### Checkpoint: after T2
- [ ] Full Blender suite and unit suite pass
- [ ] Success criteria 3 to 6 hold in tests
- [ ] Review with the user before T3

## Phase 2: The user interface

- [x] **T3 The dialog and the File > Import entry** (S)
  - Description: `import_scene.rs_item_body` opens a dialog with the Male/Female choice. OK opens the search popup of `import_scene.rs_item` for that body, and picking an item runs the import. A menu entry `RS Item (from cache)` that opens the dialog is appended to File > Import and removed on unregister. The item list reads the operator's body, so it follows the body chosen in the dialog. (Changed on 2026-11-11 by the user: the plain item dropdown of the first version could not be searched.)
  - Accept:
    - [x] `menu_entry` adds `import_scene.rs_item_body` with the text `RS Item (from cache)`. `register` appends it and `unregister` removes it (the add-on registers and unregisters twice without error, as `test_register.py` does).
    - [x] With no Cache folder, the item list offers one entry that says `Set the Cache folder in the add-on preferences.` and OK is refused with the same message.
    - [x] The Female body changes the list (tested by calling the items callback with a stand-in operator, as `popup` does in `test_appearance_items.py`).
    - [x] OK in the dialog opens the item search for the chosen body, and the item operator opens a search popup when invoked (tested with stand-ins).
    - [x] By eye, in Blender 5.3 against snapshot 430: File > Import lists the entry, the dialog opens with Male chosen, OK opens the search popup with its text field, and the 3503 male items are listed (the list builds in about 10 ms). I could not type into the popup through the automation, so searching by name and by id is not checked by eye here; the popup is the one Player Appearance uses.
  - Verify:
    - [x] `scripts/test-blender.sh` gives 806 passed, 3 skipped. `prek run --all-files` passes.
    - Not yet handled, left to T4: a set cache that lists no item for the body (empty popup), a stale `none` entry with a valid cache, and `MissingResourceError` raised by the item list.
    - [ ] The user types a name and an id into the popup in Blender and confirms the search.
    - [x] Commit review as in T1 (spec and standards sub-agents; findings fixed).
  - Deps: T1.
  - Files: `src/rsps_toolkit/blender/import_item.py`, `src/rsps_toolkit/blender/__init__.py`, `tests/blender/test_import_item.py`, `tests/blender/test_register.py`, `spec/import-by-item.md`, `tasks/plan.md`.

### Checkpoint: after T3
- [ ] The user has seen the entry and dialog, or has said to continue without
- [x] The dropdown search risk is closed: the user chose the search popup on 2026-11-11

## Phase 3: Safety and the panel

- [x] **T4 Refusals that add nothing** (M)
  - Description: Refuse with a message that names the cause, and leave no object, mesh or material behind. Refusals: no Cache folder or no item group (`MissingResourceError`), an item that lists retextures (names the item), an item with no worn model for the body, a model file not in the cache (names the model id). Checks that need no object run first. Anything made before a late failure is removed. `tests/js5_builder.py` gets a small item-definition encoder for the two refusals that no fixture item shows.
  - Accept:
    - [x] Each of the four refusals returns `CANCELLED`, reports the cause (the retexture message names the item, the missing model message names the model id), and leaves the counts of objects, meshes and materials as they were.
    - [x] A failure after the first object is made (the second model file is missing) leaves nothing, including the first object, its mesh and its materials.
    - [x] A test-built item with a retexture and a test-built item with a male model only (Female chosen) are built in the test, and the comments say so (spec: user choice of 2026-11-11). Expected messages come from the spec's Refusals decision.
    - [x] Before the test for "no worn model for the body" is written, check what Blender does with an enum value that is not in the list. If it rejects the value before `execute`, the test calls the function `execute` uses, and the task result says so.
  - Verify:
    - [x] Each refusal test failed before the code. A mutation check (cleanup removed) fails the late-failure test.
    - [x] `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_import_item.py` passes, and `uv run pytest` passes (the encoder is used by unit tests only if added there).
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1 (spec and standards sub-agents; findings fixed).
  - Result (2026-11-11): `scripts/test-blender.sh` gives 813 passed, 3 skipped, `uv run pytest` gives 1335 passed, 24 skipped, `prek run --all-files` passes. Every refusal test failed before the code. Mutation check: with the cleanup never running, the late-failure test fails (before the reviews moved the model reads ahead of the first object, the missing-model test failed too).
    - Blender rejects an item the list does not offer before `execute` runs (`TypeError: enum "9002" not found`), so the "no worn model for the body" test calls `_worn_models`, the function `execute` uses. The same holds for a stale `none` entry, which is tested by calling `execute` with a stand-in.
    - Choices to report: (1) The retexture message is `<name> (<id>) lists retextures, which this import does not show.` and the no-worn-model message is `<name> (<id>) has no worn model for the <body> body.`; the spec names the content, not the text. (2) A set cache that lists no item for the body, or a stale `none`, reports `Pick an item that has a worn model for the <body> body.`; the spec does not cover it. (3) A cache without the item group shows its error as the one popup entry, as `appearance_items` does, and picking it is refused with that error. (4) Any other failure while building (such as a model that cannot be decoded) also removes what was made and then raises, so it shows as a Python error. (5) Materials are removed on a failure, as the plan says. (6) `tests/js5_builder.py` has `item_definition`, with a unit test that decodes what it writes. (7) Every model file is read and decoded before the first object is made, so a missing file makes nothing; the late-failure cleanup is tested with a failing `model_to_object`. (8) An item id the cache does not hold is refused with `Item <id> is not in the cache.` (9) Not handled: an image that a textured face loads stays in the file after a failure (no fixture model has textures, so it is untested).
  - Deps: T1, T3 (the no-cache message is shared with the dialog).
  - Files: `src/rsps_toolkit/blender/import_item.py`, `tests/js5_builder.py`, `tests/blender/test_import_item.py`, `tests/unit/test_item_definition.py`.

- [x] **T5 Stored item data and the panel note** (M)
  - Description: Each imported object stores the item id, the item name and the body, through `rs_layers.py`. `ui.item_import_note(obj)` returns the note for an item import and None for any other object. The importer panel draws the note for the active object.
  - Accept:
    - [x] After an item import, `item_import_note` for an object names the item and the body and says that export writes the model's own colours. The note says what the import showed (Plan, Risks).
    - [x] A plain import's object, an object with no data, and None give no note.
    - [x] The stored item data is still there after the user moves vertices in Edit Mode and after duplicating the object, and the stored values and Preserve Source export are unaffected.
    - [x] The note text is plain ASCII, in short sentences, and wraps in the panel width (the panel wraps with `textwrap.wrap(width=30)`, as the presentation notice does).
    - [x] By eye: the panel shows the note for an imported item object and none for a plain model.
  - Verify:
    - [x] The cases failed before the code.
    - [x] `BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_import_item.py tests/blender/test_model_source.py` passes.
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1 (spec and standards sub-agents; findings fixed).
  - Result (2026-11-11): `scripts/test-blender.sh` gives 823 passed, 3 skipped, `uv run pytest` gives 1335 passed, 24 skipped, `prek run --all-files` passes. The ten T5 cases (six tests, one with four parameters) failed before the code (the note function did not exist); the four cases for unreadable data were added after the review. By eye in Blender 5.3: with the last item object active, the panel shows an "Imported by item" box with the note wrapped in short lines; with a plain import active, it shows no note. The note sentence "Shown colours follow the item's recolours." replaced "Its recolours were shown at import." after that check, because the old one was false for an item with no recolours.
    - The note reads: `Imported from item <name> (<id>), <male|female> body. Shown colours follow the item's recolours. Export writes the model's own colours.` It says what the import showed, not what the object shows now.
    - Choices to report: (1) The note wording is mine; the spec gives its content only. (2) The item data is one JSON custom property on the object (`rs_item_import`, in `rs_layers.py`), so a duplicate keeps it; unreadable data reads as no note. (3) The tests cover moving a vertex in Edit Mode and duplicating; the data names no vertex or face, so the other cases of the stored data standard do not apply. (4) The panel check moved the panel to the Item tab in a throwaway Blender session only, to read it without clicking.
  - Deps: T1, T3.
  - Files: `src/rsps_toolkit/blender/rs_layers.py`, `src/rsps_toolkit/blender/ui.py`, `src/rsps_toolkit/blender/import_item.py`, `tests/blender/test_import_item.py`.

### Checkpoint: after T5
- [ ] `prek run --all-files` and the full Blender suite pass (success criterion 9)
- [ ] Every user story (1 to 10) has a test, or a by-eye check named in the results (stories 1, 2 and 8 in part)
- [ ] Out of scope untouched: File > Import > RS Model, joining, female offset, retextures shown, other model kinds
- [ ] Review with the user before T6

## Phase 4: Close-out

- [ ] **T6 Close-out and pull request** (XS)
  - Description: Tick issue 07 with a dated comment that names the commits. Add the glossary term only if the glossary lacks a fit and the user agrees. Move the plan to `tasks/done/import-by-item/`. Open the pull request and stop. The user merges.
  - Accept:
    - [ ] Issue 07 shows its status and a dated comment that links `spec/import-by-item.md`.
    - [ ] `rg -n "RS Item \(from dump\)" .` finds nothing outside `.scratch/` history (the old label was "from dump").
    - [ ] `tasks/plan.md` and `tasks/todo.md` are in `tasks/done/import-by-item/`.
    - [ ] Pull request open from `feat/import-by-item`, with no local paths and no attribution lines.
  - Verify:
    - [ ] `prek run --all-files` passes.
  - Deps: T5.
  - Files: `.scratch/osrs-focus/issues/07-imported-worn-items-show-stored-colours.md`, `GLOSSARY.md` (optional), `tasks/`.

### Checkpoint: complete
- [ ] All nine success criteria in the spec met (criteria 1 and 8 by eye with the user)
- [ ] Ready for review in a new session (`/agent-skills:review`)
