# Appearance Panel: One Step-by-Step Box

**Goal:** Pick a player's look top to bottom in one box: each body kit, the item worn over it and the colour it uses sit together, instead of separate Body kits, Colours, Worn items and Raw slots boxes. Colour choices become named dropdowns with swatches.

## Decisions (agreed with the user, 2026-11-07)

1. One box, in this order: Female checkbox (kept as is); Skin; Head kit, Head item; Jaw kit; Hair colour; Torso kit, Torso item; Arms kit; Torso colour; Hands kit, Hands item; Legs kit, Legs item; Legs colour; Feet kit, Feet item; Shoe colour; then Cape, Neck, Weapon and Shield items. No item is worn in the arms slot (slot 6), so it has no item line.
2. All five colour dropdowns always show; a colour is one choice per player that several parts share (the client has five).
3. Names, by the client's palette index for revision 149:
   - Hair (25): the first 25 names of the wiki's Hairstyles page, Dark brown to Light purple. Its last five (Navy blue to Aqua) came on 18 April 2023 and are not in 149.
   - Torso (29): the wiki's clothing colours in table order, Khaki to Light Purple.
   - Legs (29): the client's own order, which starts with Emerald, then Khaki to Cyan, then Black to Light Purple as the torso list. Names follow the colour, the order follows the client.
   - Shoes (6): Brown, Khaki, Ashen, Dark, Terracotta, Grey.
   - Skin (11): the eight normal tones are named Tone 1 to Tone 8 from lightest to darkest (the client's own order is not sorted), then Green, Black and White.
4. Every dropdown entry has a swatch icon in the client's colour at the add-on's Brightness setting, and its tooltip gives the hex.
5. Item lines show the worn item's name. Search opens Blender's type-to-filter popup of every item with a worn model for that slot and body type; picking one wears it. Take Off puts back the body type's default kit (an empty slot for non-body slots).
6. While an item fills a kit's slot (torso, legs, hands, feet), that kit's dropdown is greyed and reads "Covered by item". The "Hidden (covered)" and "Other" choices stay.
7. The old Slot dropdown, Search field, results list and Take Off button go. Raw slots become a subpanel that starts closed.
8. Presets are unchanged: colours stay stored as the client's choice numbers.

## Tasks

- [x] **Task 1: Colour names (pure).** Done (`a36d8c7`). `formats/appearance_colours.py`: per colour slot, the choices in display order with name and client index. Unit tests: counts equal the palette rows; legs and torso names agree with the nearest torso colour; skin tones sort light to dark by lightness; Green, Black and White by colour.
- [x] **Task 2: Swatches and colour dropdowns (Blender).** Done: `blender/appearance_swatches.py`, `colour_items` and the `colour_*` properties. A preview collection of swatch icons, rebuilt when Brightness changes. Five enum properties whose get and set read and write `colours`. Tests: setting a dropdown writes the client index; icons exist for every entry.
- [x] **Task 3: Item lines.** Done: `rsps.pick_item`, `rsps.clear_slot(slot)`, `items_for_slot` (replaces `search_items`). `rsps.pick_item` (per-slot search popup) and a per-slot `rsps.clear_slot`; remove `item_slot`, `item_query`, the search results and `rsps.wear_item`. A pure `items_for_slot` lists every item for a slot and body type. Tests replace `test_appearance_items.py`'s search tests.
- [x] **Task 4: Panel layout.** Done: `_draw_steps` and the `VIEW3D_PT_rsps_appearance_raw` subpanel. The single box in the agreed order, covered kits greyed, the raw slots subpanel closed by default. Checked in the live Blender through the MCP.
- [x] **Task 5: Docs.** HANDOFF section, commit.

## Live check (2026-11-07)

Moved from HANDOFF.md on 2026-11-09.

Checked by the agent in the live Blender: the layout, swatches, item names, the greyed torso under a platebody, and the hands search popup filtering "dragon" to Dragon gloves and Dragonstone bracelet. Clicking panel buttons through background computer-use did not open the popup (the popup was opened from Python), so a real click on the search button and on a colour dropdown is not checked.

Open: issue 16 (`git show 2a78edd:.scratch/osrs-focus/issues/16-colour-swatches-redraw-late.md`).
