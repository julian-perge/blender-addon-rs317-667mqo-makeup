# 667 new-format models

Status: needs-info

Parked by the owner, recorded 2026-11-04: 667 waits until the old format is done ([ADR 0003](../../../docs/adr/0003-old-school-caches-come-first.md)).

RuneLite's new-format decoder is written for Old School's variant: it crashes on every 667 model with footer flag bits 1 and 8 set (about 9,700 models) and on about 30% of models with complex textures, and a crash-free decode does not prove the values right. Tests therefore use only the vertices and faces of the four `tests/fixtures/models/rs667/` fixtures, never their texture fields. [The fork comparison](../../../docs/research/fork-or-own-copy.md) ran RuneBlend's decoder on sampled 667 models, a lead for why RuneLite crashes.

To pick it up:

- Read the rest of `dv.java` (listed under "Still to read" in `docs/research/model-formats.md`) and what the flag bit 2 and bit 4 sections hold.
- Find out why RuneLite crashes on those models.
- Test a new-format decoder against the client, starting from 667 models 5 and 396 (known RuneLite crashes). `decode` reads `FF FF` files only with the explicit `osrs-149` profile and refuses them otherwise.
- The 667 importer (`blender/importer_667.py`) still builds meshes with faces that repeat a vertex, so Edit Mode can freeze on 667 models ([ADR 0005](../../../docs/adr/0005-faces-that-repeat-a-vertex-stay-out-of-the-mesh.md)).
- `find_texture` does not search the 667 textures, which `texture_dump.zip` keeps as `667Tex/texture_<id>.png`.

## Comments

- 2026-11-10, triage with the user: needs-info. Parked. It unparks when the old format is done (ADR 0003).
