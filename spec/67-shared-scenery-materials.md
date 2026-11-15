# Spec: Shared scenery materials for a region import - V1

Source: [issue 67](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/67) (The scenery meshes of a region import share their materials), part of [issue 35](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/35).

Status: the owner approved this spec on 2026-11-15.

This spec follows the measurement comment on issue 67 and [the idea one-pager](../docs/ideas/67-shared-scenery-materials.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). [Spec 35](35-draynor-region-import.md) puts a change to model import under "Ask first". The owner chose the direction of this spec in the design interview on 2026-11-15, and answered four questions:

1. **Viewport.** Build the change first. A Material Preview timing of `48_50`, before and after, is part of the verification. It is not a gate before the work.
2. **Render difference.** The renders of the two imports differ in 790 of about 2 million channel values, by at most 9/255. This is accepted when its cause is found. If the cause is the draw order of blended faces, the difference stays. If a shared material looks different from the material it replaces, that is a bug to fix.
3. **Names.** A shared material keeps the name that `face_materials.face_material` gives it. Two keys with the same name get Blender's `.001` suffix. Names that show all the values belong to the region palette follow-up.
4. **Other tools.** Aether, PMN texturing and Upgrade RS Materials can edit a material that many scenery meshes now share. That is accepted for a region import. The pull request records which of these tools edit a material in place. No code changes for them.

## Objective

A region import makes one material for each distinct material key of its scenery, instead of new materials for each scenery mesh. The goal is the time to draw a frame of a region import. The material count is the way to get there.

The measurement of 2026-11-15 on `48_50` of snapshot 430 found:

| Measure | Now | Shared |
| --- | --- | --- |
| Scenery materials | 3,169 | 325 |
| EEVEE frame after the first render | 1.08, 0.95, 1.01 s | 0.40, 0.33, 0.36 s |
| `.blend` size | 4.93 MB | 2.14 MB |

The user is the owner, who looks around an imported region in Material Preview.

### Material key

The material key of a face is `(colour, texture, alpha, shown_instead, stacked)`:

- `colour`, `texture` and `alpha` are the game values that `material_values` reads back.
- `shown_instead` is the shown colour when it differs from the face colour, else `None`. This is the key that `model_to_object` uses today. The region import passes no shown colours, so for scenery it is always `None`.
- `stacked` is true when at least one face of this mesh with the other four values is a stacked face. This is the same test that decides today whether `show_stacked` changes the material of this mesh.

With `stacked` in the key, each shared material draws as it draws in its own mesh today. Without it, the first mesh that uses a material would decide for every other mesh whether it draws blended and culled.

A shared dict is valid only for one `find_texture` and one brightness. One region import uses one of each.

## Design

`model_to_object` gets one new optional keyword argument:

```python
def model_to_object(
    model: Model,
    name: str,
    find_texture: FindTexture | None = None,
    brightness: float = face_materials.DEFAULT_BRIGHTNESS,
    shown_colours: Sequence[int | None] | None = None,
    materials: dict[MaterialKey, bpy.types.Material] | None = None,
) -> bpy.types.Object:
```

- `MaterialKey` is a type alias in `mesh.py` for the tuple above.
- When `materials` is `None`, `model_to_object` makes the same materials as before: one new material for each key of this mesh, with the same names, values and draw settings.
- When `materials` is a dict, the caller owns it. For each key of this mesh, `model_to_object` uses the material in the dict, or makes a new one and puts it in the dict. A new material for a key with `stacked` true gets `show_stacked` when it is made. A material that comes from the dict is not changed.
- Each mesh still has one slot for each key that its faces use, in the order of the first face that uses it, as today.
- `model_to_object` finds the stacked faces before it makes any material, so that it knows the full key of the first face that uses each material.

`region_scenery.scenery_objects` makes one empty dict for each call and passes it to every `_mesh` call. `import_region` calls `scenery_objects` once for each import, so the dict lives for one import. No dict is kept after the import, and no material is taken from `bpy.data`.

The cleanup in `import_region` removes every material that is new since the import started. Every shared material is new in this import, so a failure needs no change. One undo removes the whole import, as today.

Model import (`import_model.py`), item import, animation and every other caller of `model_to_object` pass no dict and do not change.

## Commands

See [AGENTS.md](../AGENTS.md). Verification for this spec:

```bash
RSPS_SNAPSHOT_430_CACHE=<path to cache> BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh tests/blender/test_region_import.py tests/blender/test_mesh.py
prek run --all-files
```

## Project structure

See [AGENTS.md](../AGENTS.md) and [Architecture](../docs/agents/architecture.md). The files of this spec:

- `src/rsps_toolkit/blender/mesh.py`: the `materials` argument, the `MaterialKey` alias and the `stacked` part of the key.
- `src/rsps_toolkit/blender/region_scenery.py`: one dict for each `scenery_objects` call.
- `tests/blender/test_mesh.py`: model import makes the same materials as before, and a dict is shared.
- `tests/blender/test_region_import.py`: the scenery of `48_50` has one material for each key, and the cleanup tests still pass.
- `docs/research/67-shared-scenery-materials.md`: the viewport timing and the cause of the render difference.
- `scripts/measure-region-materials.py`: a mode for the viewport timing, if a script is the way to measure it.

## Code style

See [CODING_STANDARDS.md](../CODING_STANDARDS.md). Use the glossary's terms: loc, placement, scenery, stacked faces, face colour, face alpha.

## Testing strategy

The seams are `model_to_object` and `import_region` (or the RS Region import operator). Tests do not call `_mesh` or read the dict from inside `scenery_objects`.

`tests/blender/test_mesh.py`, with built models and no cache:

- Two calls of `model_to_object` with no dict on the same model make two separate sets of materials, with the same names, values and draw settings as before this change.
- Two calls with one dict on models that use the same keys make one set of materials, and both meshes point at them.
- A dict shared by a mesh with stacked faces and a mesh without them, with the same other four values, gives two materials. Only the material of the stacked mesh draws blended and culled.
- Export of a mesh that uses shared materials gives the same game values as export of the same mesh with its own materials.

`tests/blender/test_region_import.py`, with snapshot 430:

- After the import of `48_50`, no two scenery materials have the same material key, and every scenery face shows the same values and draw settings as its own material would. The count is 325, the number that the measurement found.
- The existing tests of one undo and of a failure while building the scenery or the terrain still pass, with no change to their assertions.

The viewport timing and the render difference are measured once by hand or by script, and recorded in `docs/research/67-shared-scenery-materials.md`. They are not unit tests.

## Boundaries

- **Always:**
  - Keep the output of model import the same when no dict is passed.
  - Keep the `material_values` contract: export and the painters read only the custom properties of a material.
  - Run the verification commands before each commit.
- **Ask first:**
  - Any change to the names, values or draw settings of the materials that model import makes.
  - Any change to the cleanup in `import_region`.
  - Any fix for the render difference that changes how a material draws.
- **Never:**
  - Take a material from `bpy.data` or from an earlier import.
  - Merge duplicate materials after the build.
  - Change how the terrain makes its materials.

## Success criteria

- [ ] The import of `48_50` on snapshot 430 makes one scenery material for each material key, 325 in all.
- [ ] Model import of one model makes the same materials as before: same count, names, game values and draw settings.
- [ ] A failure while building the scenery or the terrain, and one undo of a full import, still remove every material that the import made.
- [ ] A Material Preview timing of `48_50`, before and after this change, is in `docs/research/67-shared-scenery-materials.md`, with the method and the numbers.
- [ ] The cause of the render difference is found and recorded in the same file. A shared material that looks different from the material it replaces is fixed.
- [ ] The pull request says which of Aether, PMN texturing and Upgrade RS Materials edit a material in place, so that the edit now reaches every loc that shares it.
- [ ] `prek run --all-files` passes and the pyrefly baseline has no new entry.

## Out of scope (deferred)

- The region palette: a panel list of the shared materials, named by their values, where one edit recolours every loc that uses a material. It is a follow-up issue.
- Names that show the shown colour and the stacked flag: they belong to the region palette.
- Terrain materials: they are emission materials with baked light, and there are only a few.
- Reuse of materials across imports or from `bpy.data`: it breaks the cleanup and changes model import.
- Merging duplicate materials after the build: it makes 3,169 materials and then removes most of them.
- One material for each texture, with the colour on a face attribute: it breaks the `material_values` contract.
- Code changes to Aether, PMN texturing or Upgrade RS Materials for shared materials.

## Guesses and choices to confirm

- **Guess:** EEVEE already reuses one shader for materials with identical node trees. This would explain why the shader compile time does not change. It is not verified, and the spec does not depend on it.
- **Guess:** the render difference comes from the draw order of blended faces. The verification checks it.
- **Guess:** `bpy.ops.wm.redraw_timer` in a GUI Blender with a Material Preview viewport gives a usable redraw time. If it does not, the build task picks another method and records it.
- **Choice:** `scenery_objects` owns the dict, not `import_region`. `scenery_objects` is the only caller that makes scenery meshes, and it runs once for each import.
- **Choice:** the 325 count is asserted in the region test. It changes if the cache snapshot or the material key changes.
- **Open:** should the `materials` argument be recorded as an ADR? It changes the interface of model import, which spec 35 treats as an ask-first change.
