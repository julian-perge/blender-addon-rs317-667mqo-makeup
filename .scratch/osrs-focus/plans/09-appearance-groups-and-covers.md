# Appearance Panel: Groups and Covers Toggles

**Goal:** Follow-up to plan 08 after the user's check. Group each body part's kit, colour and item with a line between groups, and let worn items hide the kits they cover, as the game server does for full-body items and full helms.

## Findings (2026-11-07)

- 3rd age vambraces (10336) assemble exactly as the unchanged revision-149 client does for both bodies (vertices, faces, colours, priorities, alphas, labels), recorded with a scratch copy of the harness in `<scratch folder 2026-11-07-vambraces>/`. The client's own icon shows the same pointed brown cuff. Not a defect.
- Torso items such as Khazard armour (75), Dharok's platebody (4720) and the Zamorak platebody (2653) bring their own arms. Their arm faces lie on the arms kit's faces and both have priority 10, which sorts by view depth, so the two z-fight. The server sends an empty arms slot for these items; the 149 cache has no wear positions to say which (every `wearPos` is -1, also in OpenRS2 cache 241).
- Over all 306 male torso items, the item model has vertices on either none of the eight arm labels of the default arms kit (37 items: aprons, chainbodies) or on six to eight of them (269 items: platebodies, robes, Khazard). Female: 37 and 269. With the arms slot empty, Khazard and Dharok's look complete for both bodies.

## Decisions (agreed with the user)

1. Layout, one box, a line between groups:
   - Female, with Skin right-aligned on the same row.
   - Head kit with Hair colour on its right; Item line; Jaw kit.
   - Torso kit with Torso colour on its right; Item line; Arms kit.
   - Hands kit; Item line.
   - Legs kit with Legs colour on its right; Item line.
   - Feet kit with Shoe colour on its right; Item line.
   - Cape, Neck, Weapon and Shield item lines.
2. Covers toggles under an item line while an item is worn: "Covers arms" under the Torso item, "Covers hair" and "Covers jaw" under the Head item ("Covers jaw" only for a body type that has jaw kits; the female body has none, so her empty jaw slot never counts as covered). Ticking empties the kit slot; unticking puts back the kit that was there before (kept per scene, not in presets), or the body type's default kit when there is none.
3. Picking a torso item sets "Covers arms" by the data: ticked when the item's worn model has a vertex on an arm label of the body type's default arms kit, off otherwise. Head toggles start off.
4. Take Off un-covers what the item covered.
5. "Hidden (covered)" leaves the Head, Jaw and Arms dropdowns. A covered kit's row is greyed and reads "Covered by item".

## Tasks

- [x] **Task 1: Arms rule (pure).** `brings_own_arms` in `formats/appearance.py`, tested on fixture items.
- [x] **Task 2: Covers properties.** Toggles with get and set over `equipment`, the remembered kits, auto-tick on pick, un-cover on Take Off, no Hidden choice. Blender tests.
- [x] **Task 3: Grouped layout**, checked in the live Blender.
- [x] **Task 4: Docs**, commit.

## Superseded (2026-11-07)

The arms rule and the wiki platebody table were replaced by wear positions from OpenRS2 cache 2757 (`data/item_wear.json`); see HANDOFF.md, "Wear data from cache 2757".
