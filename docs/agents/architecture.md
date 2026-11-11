# Architecture and compatibility

Read this before changing imports, module boundaries, Blender data access or stored mesh data.

## Extension boundary

Blender builds and loads exactly `src/rsps_toolkit/`. The manifest lives inside that folder; nothing outside it ships.

- Keep `bpy` imports out of the package's `__init__.py`. It imports the Blender layer lazily inside `register()` so plain pytest can import the package.
- Put code that touches `bpy`, `bmesh`, `gpu` or `mathutils` in `blender/`.
- Keep `formats/` and `presets.py` pure: they never import `bpy`, directly or through a sibling.

## Types and Blender data access

Pyrefly records legacy type errors in `pyrefly-baseline.json`. When rewriting a module, fix its baseline entries and run:

```bash
uv run pyrefly check --prune-baseline
```

Add new code without adding baseline entries.

The bpy stubs do not support indexing or iterating array properties such as `polygon.vertices` and `material.diffuse_color`. Read arrays with `foreach_get`; read polygon corners through `mesh.loops[polygon.loop_start + i].vertex_index`.

## Saved-file compatibility

Keep Blender layer names `RSPRI`, `RSTSKIN` and `VSKIN1:` to `VSKIN3:` stable. Saved `.blend` files and the exporter read them.

`origin` is the owner's fork and nothing goes upstream, so a refactor can rename, move and delete freely.

## Module design

The module design approved on 2026-11-04, as the modules stand on 2026-11-09. Terms follow `GLOSSARY.md`.

- `formats/` turns bytes into a `Model` and back. The approved public interface was `Model`, `decode`, `encode`, `face_colour_to_rgb`, `rgb_to_face_colour` and `texture_uvs`, and tests cross only that interface. `decode` now also reads the new `FF FF` format with the `osrs-149` profile, `formats/__init__.py` also exports the set-aside and new-format names, and `rgb_to_face_colour` is not written yet.
- `presets.py` holds the export presets, `detect_model_type` and the one body-part label table, `BODY_PARTS`, from which `MIRRORED_LABELS` is derived. It works only on body-part labels.
- `blender/mesh.py` has `model_to_object` and `object_to_model`. The Blender storage conventions live only in `blender/rs_layers.py`, and the importer, exporter, weighter and both painters go through it.
- `blender/face_materials.py` creates face colour and texture materials and owns material identity. `blender/preferences.py` holds the folder settings and the `find_texture` lookup.
- Both painters draw their overlays through `blender/painter.py`, each with its own layer and labels.
- The `DROP_PARAMS` transform maths stays in the export operator.
- Scene properties and most draw handlers are registered in `blender/__init__.py`.
- `blender/` stays one flat folder, with modules of one feature sharing a name prefix, such as `appearance_` for the player. The owner dropped the approved move of the weighter, the texture tool, the Aether materials, the render style, the panels and the material colour list into `blender/operators/` and `blender/panels/` on 2026-11-10, since a split by role cuts across that grouping and the move changes no behaviour ([issue 11](../../.scratch/osrs-focus/issues/11-operators-and-panels-never-moved.md)).
