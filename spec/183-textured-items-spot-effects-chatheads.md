Source: [issue 183](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/183) (a headless script builds textured items, spot effects and chatheads that play their clips).

# Spec: Textured items, spot effects and chatheads, V1

Status: approved

Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and [CODING_STANDARDS.md](../CODING_STANDARDS.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The decisions are in [ADR 0036](../docs/adr/0036-textured-faces-and-face-alpha-show-as-the-client-draws-them.md), [ADR 0037](../docs/adr/0037-a-spot-effect-is-an-npc-collection-that-plays-its-sequence-once.md) and [ADR 0038](../docs/adr/0038-a-chathead-is-an-npc-collection-lit-with-the-widget-light.md). The client evidence is in [docs/research/textured-light.md](../docs/research/textured-light.md), [docs/research/spot-effects.md](../docs/research/spot-effects.md) and [docs/research/chatheads.md](../docs/research/chatheads.md). Every obfuscated name that this spec uses has a row in [docs/research/client-names.tsv](../docs/research/client-names.tsv).

The owner's package prompt holds the design, so the Design stage was skipped. The owner approved the stages to run one after the other in one session.

## Scope check

The issue names three capabilities. They share the lit mesh of `appearance_preview.build_mesh` and the NPC collection, so one spec covers them, in this build order:

| Module | Responsibility | Depends on |
| --- | --- | --- |
| textured-faces | Light and draw textured faces and face alpha on players, items, NPCs | none |
| spot-effects | Decode a spot effect, build it at an anchor, play its sequence once | textured-faces |
| chatheads | Build a player chathead and an NPC chathead, play chat clips with their chat frames | textured-faces |

## Assumptions

Each item is a guess until the owner confirms it. The decision comment of the build lists them again.

1. A player keeps the render types that its flat shading gives (`lighting.light_hsl` before this spec). The join of parts loses a stored render type 2 or 3, as `lighting._stored_render_types` says. An item, a spot effect and a chathead model of one part use the stored render types of the model.
2. Face alpha at rest shows on players, items, NPCs, spot effects and chatheads: a plain face covers (256 - alpha) / 256 of its pixels, as the region scenery does. Before this spec a player face drew opaque at rest.
3. A face that the client never draws (third lit value -2) is left out of the mesh. A clip that changes its alpha does not show it.
4. A textured face in a fade group shows the grey light value without its texture while the clip fades it.
5. A texture image is shared by texture id and brightness in one file, and a texture material by texture id and brightness. A texture that a caller does not supply shows magenta times the light value, as in the region scenery.
6. The texture animation of the client (such as the moving lava of the Fire cape) is not shown.
7. A spot effect plays its sequence once, from `start`, with the frame schedule of a Pose (frame 0 shows one tick longer), and its mesh is hidden from the frame after its last tick. A spot effect with no sequence shows its rest model from `start` and is never hidden.
8. A spot effect on a joint takes the place and the turn of the joint. The client puts it at the actor's place and lifts it by a height, and turns it with the actor (Guess in [spot-effects.md](../docs/research/spot-effects.md)).
9. A chathead is rigged for the frame map of chatneu1 (588), the frame map 82 of the human chat clips, unless the script names another sequence.
10. A chat clip loops in the client widget with no extra tick for frame 0 after the first cycle. The bake repeats it as a Pose, so frame 0 gets one extra tick in each cycle.
11. The chat clip names come from `seq.sym` of the osrs-dumps repo, a current cache. They are names for the same ids, not checked for 2017.

## Objective

A script of another repo shows players and props with textured items, game effects such as smoke and steam, and talking heads in close-up. Each is built from the cache in headless Blender through `rsps_toolkit.blender.scripting`, and it is lit as the revision 149 client lights it.

The user is the owner's scripts and the agent sessions that write them. Success is in "Success criteria".

## Commands

```bash
prek run --all-files
BLENDER=<path to blender> scripts/test-blender.sh tests/blender/test_scripting.py
RSPS_SNAPSHOT_430_CACHE=<path to cache> uv run pytest tests/unit
<path to blender> --background --factory-startup --python-exit-code 1 --python <script.py>
```

## Project structure

```
src/rsps_toolkit/formats/lighting.py          light_hsl goes. Callers use light with the render types of their model.
src/rsps_toolkit/formats/spot_effect.py       New: the spot effect decoder, its model and its light.
src/rsps_toolkit/formats/chathead.py          New: the head model of a player and of an NPC, and the widget light.
src/rsps_toolkit/formats/npc_definition.py    Opcode 60 is kept as chathead_models.
src/rsps_toolkit/formats/item_definition.py   Opcodes 90 to 93 are kept as the head models of the item.
src/rsps_toolkit/formats/appearance.py        WornItem gets the head models.
src/rsps_toolkit/animation/clip.py            pose_vertices applies the chat frames when asked.
src/rsps_toolkit/blender/appearance_preview.py build_mesh draws textured faces, face alpha and leaves hidden faces out.
src/rsps_toolkit/blender/appearance_fades.py  A polygon that leaves a fade group goes back to its own material.
src/rsps_toolkit/blender/npc_collection.py    _build takes the textures, and the record of a spot effect or chathead.
src/rsps_toolkit/blender/appearance_clip.py   bake_npc_clip gets repeat_until, and a chathead is posed with chat frames.
src/rsps_toolkit/blender/scripting.py         create_spot_effect, create_player_chathead, create_npc_chathead, chat_clip.
src/rsps_toolkit/data/animation_names.json    Gets "chat_clips".
scripts/generate-animation-names.py           Writes "chat_clips" from seq.sym.
docs/scripted-use.md                          One example call for each new function.
tests/unit/, tests/blender/                   Tests.
```

## What to build

### 1. Textured faces on a player (task #103)

- `lighting.light_hsl` is removed. Its callers call `lighting.light` with the render types that the old function used for a joined model: 1 for a flat face and 0 for any other (Assumption 1). `light` already follows `dv.ae` of gamepack 149 for textured faces and for alpha 254 and 255 ([textured-light.md](../docs/research/textured-light.md), section 1).
- The `Shading` of a textured face holds light values from 2 to 126. `build_mesh` writes such a corner to `rs_lit` as the grey `value / 128`, as `region_scenery._write_lit` does. A face whose third lit value is -1 shows its first value at each corner, whether it is flat or of render type 3.
- A face whose third lit value is -2 is not in the mesh (`ej.ae` skips it, textured-light.md section 2).
- `build_mesh` gets `textures: Mapping[int, TexturePixels] | None`. A textured face gets a material that emits the texture image times `rs_lit`, read one texel per pixel, with the texel alpha as its cover, and back faces culled. The face alpha does not count for a textured face (`ep.k` does not read `ep.v`). The mesh gets the UV layer of model import (`texture_uvs`) for its textured faces.
- `appearance_preview.texture_pixels(folder, model, brightness)` reads the textures of the textured faces of a model before any Blender data exists, and refuses a texture that the cache lacks.
- `build_mesh` stores the material slot of each polygon in the face attribute `rs_lit_slot`. `appearance_fades.apply_fades` and `clear_fades` put a polygon that leaves a fade group back on that slot, and on slot 0 for a mesh without the attribute.
- Create Player, Update Player, Duplicate Player, the held items of a bake, Create NPC, Make rig and `scripting.create_player` pass the textures.
- A male player who wears the Fire cape (6570) builds, and its 24 faces of texture 40 show texture 40.

### 2. Textured faces and face alpha on a lit item

- `scripting.import_item` lights the inventory model with `light` and the render types of the model, and passes its textures.
- A plain face with alpha `a` from 1 to 255 gets a material that emits `rs_lit` and covers `(256 - a) / 256` of its pixels (`ep.g` and `ep.m`, textured-light.md section 2). Materials are shared by alpha. Face alpha 0 keeps the one shared material of players.
- Vial of water (227, model 2789) builds. Its two faces of alpha 254 are drawn with a cover of 2 / 256.

### 3. The spot effect decoder

`formats/spot_effect.py`:

- `SpotEffect`: `id`, `model`, `sequence` (-1 for none), `resize_width` and `resize_height` (128 is a scale of 1), `rotation` (degrees), `ambient`, `contrast`, `recolours`, `retextures`. The opcodes are those of `ii.r` ([spot-effects.md](../docs/research/spot-effects.md), section 1): 1, 2, 4, 5, 6, 7 and 8 (unsigned bytes, no factor), 40 and 41. Any other opcode is refused.
- `read_spot_effect(store, spot_effect_id)` reads config group 13 of index 2 and refuses an id that the cache lacks.
- `spot_effect_model(effect, load_model)`: the model, recoloured, then retextured (`ii.v` offsets 39 to 217).
- `spot_effect_lighting(effect)`: `(64 + ambient, 850 + contrast, -30, -50, -30)` (`ii.v` offsets 226 to 255).
- `spot_effect_scale(effect)`: `(width, height, width) / 128` in game x, y and z, applied after the animation (`ii.v` offsets 351 to 374).

### 4. A spot effect in a scene

`scripting.create_spot_effect(folder, spot_effect_id, *, brightness, start=0, location=(0, 0, 0), height=0, joint=None, offset=(0, 0, 0), name=None) -> SpotEffect`:

- It builds an NPC collection of the lit model (`npc_collection`), rigged for the frame map of the first frame of the sequence, with the scale of the spot effect on the rig object and the turn of opcode 6 around the up axis. `ej.c` turns (x, z) to (z, -x), so the rig turns by minus the rotation.
- With no `joint`, the rig is at `location` and `height` game units higher, as the client lifts it by its height (`be.n` offsets 352 to 365). With `joint=(rig, name)`, it is on that joint with `attach_to_joint` and `offset`, and a `location` or `height` is refused.
- It bakes the sequence as a Pose from `start` for one cycle, and keys the mesh hidden on the frame after the last tick (`ap.fb` sets the graphic to -1 when the frame passes the end). It keys the mesh shown on `start` and hidden before it.
- It returns `collection`, `rig`, `mesh`, `start` and `end` (the first frame that does not show it, or None).
- It refuses a spot effect that the cache lacks, a model with no vertex skins when the effect has a sequence, and a sequence with no frames, before any Blender data exists.
- The smoke puff 86 (model 3076, sequence 654) on a player is the test case.

### 5. Chathead models

- `NpcDefinition.chathead_models` keeps opcode 60: a u8 count, then one u16 model id each (`ip.r`, [chatheads.md](../docs/research/chatheads.md), section 2).
- `WornItem` gets `male_head_models` and `female_head_models`, each two ids with -1 for none, from item opcodes 90 and 92 (male) and 91 and 93 (female) (chatheads.md, section 3).
- `formats/chathead.py`:
  - `player_head_model(equipment, kits, items, load_model, colours, palette, female)`: for each of the 12 slots in order, a kit gives its chathead models joined, recoloured and retextured (`it.s`), and an item gives its first head model, joined with its second when that is not -1, recoloured and retextured (`iz.o`). Nothing is moved. The parts are joined and the five colour choices recolour the result as the body does (`hu.s`). A slot whose head model is none gives nothing. No part at all is refused.
  - `npc_head_model(npc, load_model)`: the chathead models joined, then the recolours and the retextures of the NPC, with no scale (`ip.e`). An NPC with no chathead models is refused.
  - `WIDGET_LIGHTING = (64, 768, -50, -10, -50)` (`hy.u`, chatheads.md section 1). The NPC's own ambient and contrast do not count.

### 6. Chat clips

- `pose_vertices(..., chat=True)` applies the frame of each step and then its chat frame to the same vertices (`jg.p`). A step past the end of the chat frames, or with the file id 65535, gets the frame only.
- An NPC collection whose record says `chathead` is posed with chat frames by `bake_npc_clip`.
- `bake_npc_clip` gets `repeat_until`, with the rules of `bake_clip_to_rig`.
- `data/animation_names.json` gets `"chat_clips"`: each sequence of snapshot 430 that `seq.sym` names with a name that starts with `chat`, by id, with that name. The generator gets `--chat-names <seq.sym>`, and its `"clips"` stay as they are.
- `clip.load_chat_clip_names()` reads them.

### 7. Chatheads in a scene

- `scripting.create_player_chathead(folder, look, *, brightness, location=(0, 0, 0), name="Chathead", rig_sequence=588) -> Chathead` and `scripting.create_npc_chathead(folder, npc_id, *, brightness, location=(0, 0, 0), name=None, rig_sequence=588) -> Chathead`. `Chathead` has `collection`, `rig` and `mesh`. The NPC name defaults to the NPC's name and "chathead".
- The chathead is an NPC collection lit with `WIDGET_LIGHTING`, rigged for the frame map of `rig_sequence`.
- `scripting.bake_clip` takes a `Chathead`, a `SpotEffect` or any NPC collection too, and bakes it with `bake_npc_clip`.
- `scripting.chat_clip(name) -> int` gives the id of a chat clip by its name, such as `chathap1` (567). It refuses an unknown name.
- The male default look in chathap1 (567) and Man (NPC 3078, chathead model 53) in chatneu1 (588) are the test cases.

### 8. Docs

`docs/scripted-use.md` gets one example call for each new function and drops "Spot effects, chatheads" from "Not here". The note that a textured model is refused goes.

## Testing strategy

- Unit tests (`tests/unit/`) for the decoders, the head models, the light values, the chat frame posing and the chat clip names. Expected values come from RuneLite's JSON of snapshot 430 (spot effects, NPC chathead models, item head models), from the client lines of the evidence notes (light values, render types, the order of the frame and the chat frame), and from `seq.sym` (names). Real-cache tests need `RSPS_SNAPSHOT_430_CACHE` and skip without it.
- Blender tests (`tests/blender/`) for the meshes, materials, fades, the spot effect visibility keys and the chathead bake, through `scripting`. Run only the changed files during the build.
- Each feature gets a test that fails before its change.
- A scratch script outside the repo renders the stills of the success criteria.

## Boundaries

- Always: the verify command through `agent-skills run --` before each commit; one commit for each task, with the subject ending in `(#<task>)`; placeholders for local paths in the repo, the issues and the commits.
- Ask first: none in this run. The owner gave every judgment call to the session, which posts each with `agent-skills decide`.
- Never: push, open a pull request, close an issue or change a label; write outside the repo except scratch files; change the kit API of package 5 (`create_player`, `import_item`, `attach_to_joint`, `bake_clip`, `key_travel`, `import_region`, `import_regions`).

## Success criteria

1. The verify command of AGENTS.md passes through `agent-skills run --`, with the unit tests and the Blender tests.
2. Each feature has a test that failed before its change.
3. A male player who wears the Fire cape builds, and its textured faces show texture 40 lit with the light values of `dv.ae`.
4. `scripting.import_item(CACHE, 227, ...)` builds Vial of water with its face alpha.
5. `scripting.create_spot_effect(CACHE, 86, ...)` builds the smoke puff on a player, plays sequence 654 once and hides it after.
6. `scripting.create_player_chathead` and `scripting.create_npc_chathead(CACHE, 3078, ...)` build, and chathap1 and chatneu1 bake on them with their chat frames.
7. The stills of the issue exist: 270x480, no lamps, brightness 0.6.

## Out of scope (deferred)

- Texture animation of the client.
- Spot effects on scenery, on the ground of a tile, and projectiles.
- The dialogue box, chat text and the widget camera (zoom and turn of the head).
- The glTF export of textured faces and face alpha of players.
- NPC impostors for chatheads (`ip.l` in `ip.e`).
- Stored render types 2 and 3 of the parts of a joined model.

## Open questions

None. The guesses are the Assumptions above.
