# Spec: Import worn models by item

Status: ready-for-agent

Written on 2026-11-11 from [.scratch/import-by-item/spec.md](../.scratch/import-by-item/spec.md), which follows the decisions 1 to 11 in [issue 07](../.scratch/osrs-focus/issues/07-imported-worn-items-show-stored-colours.md) (the user chose them on 2026-11-10). The scratch spec was written before [ADR 0017](../docs/adr/0017-read-caches-directly-without-317-and-667-code.md). This spec reads the cache, not a dump.

## Objective

A modeller who imports an Old School worn model with File > Import > RS Model sees the model file's stored colours, such as grey and tan on a rune armour set. The game shows the item's recolours. A model file alone cannot say which item it belongs to: 468 worn models are used by more than one item, and for 274 of them those items recolour the model differently (issue 07).

A new entry, File > Import > RS Item (from cache), imports the worn model of one item with that item's recolours shown. Each face keeps the model file's own colour as its stored game value, so export writes the model as the game stores it ([ADR 0006](../docs/adr/0006-export-writes-the-game-values-stored-at-import.md)). File > Import > RS Model does not change.

User: a modeller who edits Old School worn items in Blender.

### User stories

1. Import a worn item by searching its name or its item id.
2. Choose Male or Female before the import. Male is the default.
3. The search lists only items with a worn model for the chosen body.
4. Each model file of the worn model is its own object, named by its model id, at its stored position. The body's offset is not applied, and the pieces are not joined.
5. Faces show the item's recolours at the add-on's Brightness setting.
6. Export writes the model file's own colours. A round trip with no edits writes the original colours.
7. Faces that the modeller adds or paints export with the game values they are given, as for any import.
8. The importer panel says that the active object shows an item's recolours, names the item and body, and says that export writes the model's own colours.
9. A refusal gives a message that names the cause and adds nothing to the file.
10. The imported objects are selected and the last one is active, as after File > Import > RS Model.

## Decisions

From issue 07 (user, 2026-11-10), changed only where ADR 0017 requires it:

- **Entry.** A new import operator, listed under File > Import as `RS Item (from cache)` (user, 2026-11-11). It reads the Cache folder preference through `appearance_props.profile()`, the shared `CacheProfile` that Player Appearance uses. Item definitions come from `CacheProfile.items` (`WornItem`: male and female model ids, offsets, recolours, retextures). Model files come from `CacheProfile.load_model`, which decodes with the Old School revision 149 profile.
- **Body and item choice.** File > Import opens a dialog with a Male/Female choice (Male by default) and an item field (user, 2026-11-11). The item field is a dropdown that can be searched by name or id. Its entries are the items whose worn model for the chosen body has a first model id other than -1, sorted by name then id, labelled `<name> (<id>)` as in the worn item search of Player Appearance. OK runs the import.
- **Objects.** Each model id of the body's worn model (the first, then the second and third when they are not -1) becomes its own object named by the model id, at its stored position.
- **Colours.** Each face keeps the model file's colour, texture and alpha as its stored game values. A face whose stored colour an item recolour finds shows the recolour's replacement colour, at the Brightness setting. Recolours apply in the item definition's order, the same way that `formats/appearance.py` `recolour` applies them for worn items and kits. A later recolour can find the colour that an earlier one put in. No new colour conversion is added.
- **Materials.** Materials are made per object, keyed by the stored game values, as `mesh.model_to_object` does now. A material holds the stored values from the file and shows the recoloured colour. A plain import and an item import of the same model never share a material.
- **Stored data.** Each object stores the item id, the item name and the body. The panel note text comes from a function that takes an object and returns the note, or None for an object that is not an item import.
- **Refusals.** These are refused with a message that names the cause:
  - the Cache folder is not set, or the cache lacks the item config group (`MissingResourceError`);
  - the item lists retextures (the message names the item; no worn item in snapshot 430 has retextures, so how they show cannot be checked);
  - the item has no worn model for the chosen body;
  - a model file of the worn model is not in the cache (the message names the model id).

  A refused or failed import removes every object and mesh it made.
- **Source record.** Each object gets the same source record as a plain import of the same model (`model_source.write_source` through `model_to_object`, and `record_source_hash` of the model's bytes in the cache), so the Preserve Source export works on it.

## Tech stack

Python 3.13, uv, Blender 5.2 and later, pytest, ruff, pyrefly, prek. No new dependencies. `formats/` stays pure (no `bpy`).

## Commands

See [AGENTS.md](../AGENTS.md). The ones this work uses:

```bash
prek run --all-files
uv run pytest
BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh
```

## Project structure

```
src/rsps_toolkit/blender/import_model.py   the new operator and its menu entry go here, or in a new import_item.py (Plan decision)
src/rsps_toolkit/blender/mesh.py           model_to_object gains a way to show a face colour other than the stored one
src/rsps_toolkit/blender/ui.py             the panel note for the active object
src/rsps_toolkit/formats/appearance.py     existing WornItem, items_for_slot and recolour; a body-only item list may go here
src/rsps_toolkit/__init__.py               registers the new class and menu entry
tests/blender/test_import_item.py          new: seam 1 and seam 2
tests/js5_builder.py                       may gain a small item-definition encoder for the refusal tests
```

## Code style

Follow [CODING_STANDARDS.md](../CODING_STANDARDS.md), [docs/agents/architecture.md](../docs/agents/architecture.md) and the existing operators (`RS_OT_import_model`, `RSPS_OT_pick_item`). Messages name the missing thing and the setting to fix, for example `Set the Cache folder in the add-on preferences.` Use the glossary's terms: worn model, recolour, face colour, model, item.

## Testing strategy

Tests drive the feature where a modeller does, through the operator, and check what ends up in the file and what export writes.

- **Seam 1: the import operator**, run headless with the item and body set, against the `cache` fixture in `tests/blender/conftest.py` (the appearance fixtures as a cache). Items 1149, 2653 and 3140 have recolours, and all their male and female model files are in the fixtures. The tests check:
  - one object per model file of the worn model, named by model id (for example 2653 male gives 3379, 164 and 3381);
  - faces whose stored colour a recolour finds show the replacement at the Brightness setting, and other faces show their stored colour;
  - the stored game values equal the decoded model file's own;
  - exporting an imported object writes the model file's own colours;
  - the Female choice imports the female worn model;
  - selection and the active object;
  - refusals that add nothing: an item with a retexture, an item with no female worn model, a model file missing from the cache, and no Cache folder. The first two use item definitions built in the test (user, 2026-11-11), because no fixture item has them.
- **Seam 2: the panel note function.** For an item import, the note names the item and body and says that export writes the model's own colours. A plain import gets no note.
- Expected values come from the fixture item definitions and model files (cache data with RuneLite JSON references in `tests/fixtures/appearance/`) and from issue 07's decisions. Test comments cite issue 07's decision numbers.
- Prior art: `tests/blender/test_import.py` (several files, selection, skipped files), `tests/blender/test_export.py` (export an imported object and decode the written file), `tests/blender/test_appearance_items.py` (recoloured worn models from the same fixtures).

## Boundaries

Always:
- Run `prek run --all-files` before each commit, one commit per task, on branch `feat/import-by-item`.
- Keep File > Import > RS Model unchanged.
- Trace each expected value to the fixtures or to issue 07.

Ask first:
- Adding a dependency.
- Changing what the plain import shows or stores.
- Changing `formats/appearance.py` behaviour that Player Appearance uses.

Never:
- Write recoloured colours into exported model files.
- Edit expected values to make a test pass.
- Put local paths or personal details in commits.

## Success criteria

1. File > Import lists `RS Item (from cache)`. It opens a dialog with a Male/Female choice (Male by default) and a searchable item field.
2. The item field lists only items with a worn model for the chosen body, and matches names and ids.
3. Importing item 2653 for the male body gives objects 3379, 164 and 3381 at their stored positions. They are selected, and 3381 is active.
4. Faces with colour 61, 41 or 24 in those objects show the item's replacements for them (-29403, -28266 and 937 in `ItemDefinitions.json`, as signed 16-bit values) at the Brightness setting. Their stored face colour stays 61, 41 or 24.
5. Exporting one of those objects writes a model whose face colours equal the model file's.
6. Importing 2653 for the female body gives objects 3383, 344 and 3381.
7. Each refusal in Decisions leaves the file's objects and meshes unchanged and reports the cause.
8. The importer panel shows the note for an item import and no note for a plain import. The user checks the entry, the dialog and the note in Blender.
9. `prek run --all-files` and the Blender suite pass.

## Out of scope

- Changing File > Import > RS Model.
- Joining an item's model files into one object, or applying the female offset.
- Showing retextures.
- Inventory models, head models and drop models.
- Writing recoloured colours into exported files.
- Picking an item for an object imported as a plain model file.
- 317 and 667 items (ADR 0017 removed that code).

## Open questions

None. The user answered three on 2026-11-11: the menu label, the dialog for the body and item, and test-built item definitions for the refusal tests.

## Notes

- The design interview said imported materials are shared by game values. That was wrong: each import makes its own materials per object. Decision 8 of issue 07 (a recoloured face gets its own material) holds with the existing material building, as long as the shown colour comes from the recolour and the stored values from the file.
- The shown colours are checked through the cache's item definitions, not against a client render of a worn item alone. Player Appearance's worn item colours use the same recolour arithmetic and are checked against the revision 149 client (`tests/fixtures/appearance/reference.json`).
- `record_source_hash` is written by the plain import and read by nothing in `src/` today. The item import writes it too, so both imports leave the same record.
