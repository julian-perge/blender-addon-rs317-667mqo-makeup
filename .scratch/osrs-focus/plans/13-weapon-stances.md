# Weapon Stances: The Stand, Walk and Run Clips a Worn Weapon Gives

**Goal:** With a weapon worn, the panel offers the stand, walk and run clips the game plays for that weapon (a two-handed sword on the shoulder, a staff used as a walking stick), so the user bakes them without searching for clip names.

## Findings (2026-11-09)

Research: `docs/research/weapon-stance-sets.md`. Recounted by the agent from the downloaded files with `check.py` (scratchpad), which gave the same numbers.

- The server sends seven clips in the appearance block: stand, turn, walk, walk back, walk left, walk right, run. The revision 149 client has no defaults, and no cache holds a weapon to clip table (evidence: research note, sections 1 and 3).
- The unarmed set is 808, 823, 819, 820, 821, 822, 824.
- Alter (`item_bas.json`, `bas_mappings.json`, commit `9ddbbbe`, BSD 2-Clause) lists 712 of the 911 snapshot 430 items that take the weapon slot: 357 with a set other than the unarmed one, 355 with the unarmed set. Its 129 stance clip ids are all player clips of snapshot 430 (`data/animation_names.json`).
- The Weapon Animation Replacer plugin (`data.json`, commit `504f6bd`, BSD 2-Clause) lists 361 of the 911. On the 347 both list, 340 are equal. It lists 14 weapons Alter lacks, 6 of them with a set other than the unarmed one (Boxing gloves 7671, Toxic blowpipe (empty) 12924, Heavy casket 19941, Large spade 20164, Clueless scroll 20249, Hand fan 21354).
- The 7 disagreements: Dharok's greataxe 4718 and Meat tenderiser 7449 run with 11466 in the plugin, which snapshot 430 lacks (Alter: 824). Mouse toy 6541 (plugin: whip set), Butterfly net 10010 (plugin: stand 809, unarmed walk), Keris 10581 (plugin: staff set), Dragon cane 12373 and Royal sceptre 12439 (plugin: unarmed). Which side is right for the last five is not known.
- Not verified: that each weapon had the same set in July 2017. Both tables are newer (2024 and 2026).
- Alter's sets also hold four attack clips and a block clip. All 97 of those ids are player clips of snapshot 430. The four attack fields are named accurate, aggressive, controlled and defensive, but the names do not match the weapons' styles. The OSRS Wiki's Weapons/Categories page gives the whip Flick (accurate), Lash (controlled) and Deflect (defensive), yet Alter's whip set has an "aggressive" clip and no "controlled" one. The page gives the 2h sword Chop, Slash, Smash (crush, aggressive) and Block, yet Alter's 2h sword set puts its crush clip 406 in "controlled". Reading the four fields as the style buttons of the game's combat options in order fits both; that reading is an inference.
- The plugin keys attack clips by attack type (stab, slash, crush, special), not by style button, and has one block clip (`Swap.java`, `AnimationType`, commit `504f6bd`). So the plugin gives a weapon only Alter lacks its block clip, and no style button clips.
- The downloaded files are in `<scratch folder 2026-11-09-weapon-stance-sources>/` (`alter/`, `plugin/`), each with its `LICENSE`.

## Decisions (agreed with the user)

1. Sources: Alter is the table, and the plugin fills gaps and shows where the two disagree. The user approved the downloads.
2. Panel: a row of Stand, Walk and Run buttons under Bake clip. A click sets the clip to the worn weapon's clip and Play As to Pose. The clip search stays as it is, so turn and sidestep clips are reached by name.
3. A worn weapon in no table gets the unarmed clips, and the panel says that no stance set is known for it.
4. An Attack row under Stance: one button per style button of the game's combat options, and Block. A click sets the clip and Play As to Action. A button whose clip the weapon lacks is greyed out.
5. Where the tables disagree, Alter's set is used. The data file lists every disagreement, so they can be corrected by hand later.

Agent refinements:
- The buttons read the worn weapon of the active player, from its stored settings, since the bake goes to the active player. With no active player they are greyed out, as the bake buttons are.
- The attack buttons are labelled 1, 2, 3, 4 and Block, since Alter's field names do not say which style each holds.
- The generator stops when a set it writes gives a clip that is not a player clip of snapshot 430, from either source. The plugin's values listed as disagreements are kept as they are, so they can name such a clip (11466).
- The data file keeps both BSD notices, the source commits and the SHA-256 of each source file.
- The data file stores all seven stance clips per set, although the buttons use three, so a later change needs no new download.

## Tasks

- [x] **Task 1: Data file.** `scripts/generate-weapon-stances.py --alter <folder> --plugin <folder>` writes `src/rsps_toolkit/data/weapon_stances.json`: the named sets (seven stance clips and five attack clips each, -1 where none), item id to set for every snapshot 430 weapon either source lists, the disagreements, and the sources with their notices. Same layout as `scripts/generate-item-wear.py`.
- [x] **Task 2: Reader.** `formats/weapon_stances.py`, with no bpy import: the clips of a weapon item id and whether a table lists it, and the unarmed clips. Unit tests: the twelve sample weapons of the research note, an unlisted weapon, a weapon only the plugin lists, every clip id in the file is a player clip of snapshot 430, and every listed item takes the weapon slot.
- [x] **Task 3: Panel.** The Stance and Attack rows and their operator. Blender tests: with an Abyssal whip worn, Walk sets clip 1660 and Play As to Pose, Run sets 1661, and Attack 1 sets 1658 and Play As to Action; with an unlisted weapon, Walk sets 819 and the panel shows the note; with no weapon there is no note; with no active player the rows are greyed out.
- [x] **Task 4: Docs and live check.** HANDOFF.md and the research note's status line. A live check in Blender: a whip, a two-handed sword and a staff, each baked with Stand, Walk and Run, and one unlisted weapon. Commit.

## Result (2026-11-09)

- The names changed while building: the data file is `data/weapon_clips.json`, the generator `scripts/generate-weapon-clips.py` and the reader `formats/weapon_clips.py`, since they hold attack clips as well as stances.
- The file lists 726 weapons: 712 from Alter and 14 that only the plugin lists, and 110 sets. After review it lists 64 disagreements: 7 on stance clips and 62 on the block clip. The first version compared stance clips only.
- In `appearance_clip`, the player's weapon is read by `worn_weapon` and its clips by `worn_weapon_clips`, after the glossary's "worn item".
- Live check, driven by the agent in a scene of its own: an Abyssal whip, a Rune 2h sword, a Staff of air and Leaf-bladed spear item 4159, each with Stand, Walk and Run baked as bone strips, and the whip's first attack as an Action. Item 4159 is in neither table; item 4158 of the same name is in the file with Alter's spear set. Every strip has the clip the table gives, and the spear's panel shows the note. Background clicks did not reach Blender, so the operator was run through Python in the sidebar's context with each button's arguments. The rows, the greyed buttons (3 for the whip and the unarmed set, Block for the Rune scimitar), the note and Play As were checked in screenshots; no automated test draws the panel.
- Found in the live check: a player whose rig was moved by hand counts as edited, so the bakes refuse it. That is older behaviour (evidence: `fingerprint` reads the world matrix of the body and the rig).
- Found in review and decided by the user: Alter gives no block clip for 12 weapons where the plugin gives one (all seven scimitars among them), and the 14 weapons only the plugin lists have no clips for attack buttons 1 to 4. Both stay greyed out.

## Open

- Which side is right on the five stance disagreements that are not about clip 11466, and on the block clips.
- Which set each weapon had in July 2017.
- About 13 weapons known from RSMod v1 or v2 to need another set (the eleven Crystal halberd ids 13091 to 13101, Boxing gloves 7673, Crate with zanik 8871) are in neither downloaded table and get the unarmed clips with the note.

## Live check (2026-11-09)

Moved from HANDOFF.md on 2026-11-09.

- Live check (2026-11-09, driven by the agent): four players each baked Stand, Walk and Run as bone strips. They wore an Abyssal whip (808, 1660, 1661, and attack 1658 as Action), a Rune 2h sword (2561, 2562, 2563), a Staff of air (813, 1205, 1210), and Leaf-bladed spear item 4159 (808, 819, 824, with the note shown). Item 4159 is in neither table; item 4158, also named Leaf-bladed spear, is in the file with Alter's spear set. Background clicks did not reach Blender this time, so the operator was run through Python in the sidebar's context with the buttons' arguments. The rows, the greyed buttons, the note and Play As were checked in screenshots.
