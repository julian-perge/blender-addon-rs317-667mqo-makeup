# CharacterCreator Milestone 3: Native Appearance Panel

**Goal:** A View3D sidebar panel that builds, previews, updates and saves a static OSRS player from an appearance preset, using the verified `formats/` assembler. No rig, animation or export-to-game work.

**Scope:** Milestone 3 of [the player customization research](../../../../docs/research/osrs-player-customization.md#suggested-later-milestones-and-open-decisions). Builds on plans [03](03-charactercreator-m1.md) and [04](04-charactercreator-m2.md). Pure assembly stays in `formats/`; the panel only wires inputs and creates objects.

## Constraints

- No assembly logic in `blender/`. The panel calls `assemble_body`, `light` and the preset loader, and fails with a visible error when a resource is missing. No silent default outfit.
- The source preset is the truth. Replacing preview geometry never loses it, and a failed update leaves the previous preview intact.
- Revision 149 only. The panel refuses presets for another `client_revision`.
- Operators are explicit: create, update, save preset. Nothing runs from a property update callback.
- Tests follow `docs/agents/testing.md` and `docs/agents/blender.md` (throwaway profile, `scripts/test-blender.sh`).

## Tasks

- [x] **Task 1: Resource source.** Add a cache profile that resolves, from the user's dump folder, the kit catalog, item catalog, palette, and model bytes by id. Presets reference the dump folder from preferences (decision 1). Pure Python resolver in `formats/` or `blender/preferences.py`, tested without Blender with the fixture folder. Missing files raise a named error listing the path. Done: `formats/cache_profile.py` (`CacheProfile`, `MissingResourceError`) with the palette shipped in `src/rsps_toolkit/data/`. The snapshot 430 dump has no `kits/KitDefinitions.json` yet: run the dumper's `kits` target before using the panel on it. Task 8 must check that `data/` is included in the built extension.
- [x] **Task 2: Appearance data in Blender.** A property group holding the preset (body type, twelve slots, five colour choices) as the editable state, converted to and from `AppearancePreset`. Tests in Blender: round-trip and refusal of invalid values. Done: `blender/appearance_props.py` (`Scene.rs_appearance`), tests in `tests/blender/test_appearance_props.py`.
- [x] **Task 3: Create preview operator.** Assemble, light (optional), and create one mesh object with per-face colours using the existing mesh and material helpers (`blender/mesh.py`, `materials.py`). Store the preset as JSON in a custom property on the object. Blender test: object exists, face and vertex counts equal the reference case, colours match. Done: `blender/appearance_preview.py` (`rsps.create_appearance_preview`, `rs_lit` corner colours, preset in the `rs_appearance_preset` custom property), preference `cache_dump_folder`. Degenerate faces are not drawn.
- [x] **Task 4: Update operator and rollback.** Replace the geometry of the existing preview object from its stored preset. Build the new mesh first and swap only on success. Tests: failure (missing model) leaves the old mesh and preset unchanged; one Undo restores the previous mesh; repeated edits do not leak meshes or materials. Done: `rsps.update_appearance_preview` takes the current `Scene.rs_appearance`, assembles and lights first, then swaps the mesh and stored preset; a failure changes nothing. Tests cover failure, one Undo, and no leaked meshes or materials.
- [x] **Task 5: Panel controls.** Body type, kit dropdowns per body part (categories filtered by body type, non-selectable kits hidden), five colour choices, worn item fields by id (search is task 6), create and update buttons, and a visible error line. Kit labels are ids plus model-derived thumbnails are out of scope. Done: `blender/appearance_panel.py` (sidebar tab RSPS ADDON, Player Appearance), kit dropdowns as get/set enums over the equipment slots, `last_error` shown in the panel. Layout checked by eye by the user in Blender.
- [x] **Task 6: Worn item search.** Search items by name over the item catalog, filtered to items with a worn model for the chosen body type. Open decision 3. Done: `search_items` in `formats/appearance.py`, search box, slot dropdown, Wear and Take Off operators in `blender/appearance_items.py`. The slot is the user's choice because no item in snapshot 430 has a wear position.
- [x] **Task 7: Save and load preset.** Operators to save the object's preset to JSON and create a preview from a preset file. Refuse unknown schema versions and other revisions with a clear message. Done: `blender/appearance_files.py` (Save Preset saves the panel's current appearance; Load Preset fills the panel, then Create or Update shows it). Bad files change nothing.
- [x] **Task 8: Packaging and docs.** Validate and build the extension; installed-extension smoke test; update research doc, `HANDOFF.md`; Standards and Spec reviews; commit.

## Decisions (agreed with the user)

1. Runtime resources come from the dump folder named in add-on preferences. Presets store ids only.
2. The preview uses client-lit vertex colours (`formats/lighting.py`).
3. Worn items have name search in this milestone (Task 6).
4. The preview is one merged mesh, as the client assembles it.

## Known display limits (seen in Blender, not fixed)

- A faint speckle where the torso meets the belt and legs. Guess, not checked: faces from different kits overlap and Blender's depth test cannot order them, while the client orders them by render priority. The preview does not use priorities. Revisit only if it matters for a render.
- Worn capes show clipping and a hidden emblem; same suspected cause (render priority, not checked). Decided with the user: record, do not fix.
- No item has a slot or a covers-arms rule in the cache. Slots come from osrsbox-db (`data/item_slots.json`, 2021 data, commit in the file); covering is manual through a `Hidden (covered)` choice on the Head, Jaw and Arms dropdowns.

## Decisions made while building (agreed with the user)

- Update applies the panel's current appearance to the active preview object (not the object's stored preset), and Save Preset saves the panel's appearance. Update callbacks only search the catalog (read only) and clamp colour choices; nothing assembles from a callback.
- Kit names come from the cache's style enums; hands and feet use the wiki names (Basic/Plain, Basic/Elven) in kit id order, which is unverified.
- Dropdowns end with an `Other (see raw slots)` entry for a slot that holds an item, nothing, or the other body type's kit.

## Review focus

1. Kit ids, item ids and equipment values are three different namespaces in every UI field and operator argument.
2. A failed update must not change the object, its mesh or its stored preset.
3. No bpy import in `formats/`; no assembly code in `blender/`.

## Where Codex can run in parallel

Task 1's resolver and Task 2's property group are independent. Codex returns after Nov 12. Until then Tasks 1 and 2 run in this session.

## Unverified after the milestone

Moved from HANDOFF.md on 2026-11-09: the hands and feet kit names (from the wiki, by kit id order) and the pairing of kit names by ordinal are unverified.
