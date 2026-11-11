# Reusable Character: Duplicate a Player and Save It for Other Files

**Goal:** A finished player can be copied in the same file, sharing nothing but the file's one lit material (decision 12), and saved into its own .blend that another file appends as a working player. This finishes the open half of milestone 4 in `docs/research/osrs-player-customization.md` ("Export/reopen a self-contained rest-character collection ... and instantiate it twice with private rig/action/material data").

## Findings (2026-11-09)

- Shift+D on all of a player's objects (Blender's default Duplicate Data: actions, armatures and meshes copied, materials shared) puts the copies into the same player collection. The player then holds two rigs and two bodies, and every bake and Update refuses it ("should hold one armature object, it holds 2"). A worn weapon that a held clip had hidden was not copied, probably because hidden objects cannot be selected (a guess, not checked). The fade materials stay shared with the original. Evidence: run in the live session on Player.005, then removed.
- Update already rebuilds a player from its stored settings and bakes its recorded clips again (`recorded_clips`, `bake_recorded`). `carry_animation` hands the user's own actions to the rebuilt rig as the same datablocks, which is right for Update and wrong for a copy.
- The fingerprint reads material slot names (`_mesh_parts`). The lit material is shared by name (`appearance_preview.MATERIAL_NAME`), so a player appended into a file that already has that material may get it renamed with a numeric suffix and count as edited. Tested later: it did (see Result).
- Textured faces load their images from the dump folder by path (`face_materials._show_texture`), so a saved file must carry them for another machine.
- The bakes set the scene to 50 fps (`appearance_clip`, lines 100 and 196). A player appended into a scene at another frame rate plays its clips at the wrong speed.
- `bpy.data.libraries.write` writes chosen datablocks and their dependencies to a new .blend (research note, "A reusable Blender asset is more than a posed mesh").

## Decisions (agreed with the user)

1. Duplicate Player rebuilds from the recipe: a new player built from the stored settings, its game clips baked again at the same frames, and the user's own animation copied. Nothing is shared with the original (corrected by decision 12: the copy shares the file's one lit material). Mesh edits are not copied, so an edited player is refused with a note.
2. The copy stands beside the players, to the right of every player in the file, unturned, as Create places a new player.
3. Save Player writes the player with everything it needs into its own .blend. Another file gets it with File > Append, as a normal editable player. Tests open the written file again to prove it is complete. No Asset Browser entry in this phase.
4. When the active player has clips and the scene is not at 50 fps, the panel says so and offers a button that sets 50 fps. Nothing changes the frame rate without the user's click.
5. (2026-11-10) The edit check reads a numbered copy of a material as the material it is named after while their nodes, links and input values match, so an edited New Material copy is an edit and an appended player is not. Fade materials keep ignoring the number.
6. (2026-11-10) Duplicate names the copy after the original with Blender's next number: Hero becomes Hero.001.
7. (2026-11-10) Save writes the objects outside the player that it uses, such as the rig's parent or a constraint's target, and names them in its message.
8. (2026-11-10) After Duplicate the panel acts as a click on the copy does: it moves to the copy unless it holds changes not yet applied, which stay with the player they were made for.
9. (2026-11-10) A numbered material with no material of its base name reads as numbered, so it counts as an edit, and Update keeps such a player rather than replace an edit on a guess.
10. (2026-11-10) When a clip fails to bake again onto the copy, Duplicate removes the copy and shows the error, so the user fixes the cause and tries again.
11. (2026-11-10) Duplicate and Update bake the clips again without changing the scene's frame range.
12. (2026-11-10) Copies keep sharing the file's one lit material, so an edit to it shows on every player. This corrects decision 1's "Nothing is shared".
13. (2026-11-10) The user accepted the agent refinements below as decisions.

Agent refinements (accepted by the user on 2026-11-10, decision 13):
- The copy's objects are named after its own collection, and the copy is made active, as Create does.
- The panel's error for a player holding two rigs or two bodies also says that Shift+D does this and that Duplicate Player makes a working copy.
- Save Player has a panel button beside Duplicate Player, and Save refuses a player in Edit Mode. Its default file name goes through `bpy.path.clean_name`, so Hero.001 becomes Hero_001.blend, and it creates a missing folder.
- Duplicate of a rig built before joint bones warns that the user's label-bone keys were not copied, in the words Update uses.
- The material check leaves out node location, label, size and colour, and rounds values to 3 decimals, as the rest of the edit check does.

## Tasks

- [x] **Task 1: Duplicate Player.** Operator and panel button. Builds from the stored preset with `beside_players`, bakes `recorded_clips` again at their start frames, copies the user's actions and strips as new datablocks, and refuses an edited player or one in Edit Mode before any change. Blender tests: the copy has its own collection, rig, meshes, clip actions and fade materials; its strips start where the original's do; a user strip is copied, not shared; changing the copy's keys leaves the original's alone; an edited player is refused and nothing is added; the original is unchanged and unedited.
- [x] **Task 2: Save Player.** Operator with a file browser, defaulting to the player's name. Writes the collection and its dependencies with `bpy.data.libraries.write`, with images the file needs packed into it, leaving the open file unchanged. Blender tests: append the written collection into a file that already holds a player; the appended player is a player, unedited, plays its clips, its fade drivers read its own rig, and its textured faces show their images.
- [x] **Task 3: Frame rate.** The panel note and a Set 50 fps operator. Blender tests: the note shows for a player with clips at 24 fps and not at 50 fps; the operator sets 50 fps with `fps_base` 1.0.
- [x] **Task 4: Docs and live check.** This plan's notes and the research note's milestone 4 status. Live: duplicate a player with bone strips and a held clip, save it, append it into a new file. Commit. Done on 2026-11-10 (see Result).

## Questions for the user (asked 2026-11-09, answered 2026-11-10)

The two-axis review raised these. The user asked to be asked again later. Each lists the agent's recommendation first. On 2026-11-10 the user chose the recommended option for all four, recorded as decisions 5 to 8.

1. **Materials in the edit check.** The fingerprint ignores the number Blender adds to a taken material name (`_base_name`), so a player appended into a file with players stays editable. Blender's New Material button also makes "RS Appearance Preview.001", with the same custom properties (tested in Blender 5.2 on 2026-11-09), so an edited copy counts as no edit and Update replaces it. Options: compare a numbered copy with the material it is named after, by nodes, links and input values, and keep ignoring the number for fade materials (recommended); keep ignoring numbers and document the gap; read full names, so appended players count as edited.
2. **Copy name.** Duplicate names the copy after the original with Blender's next number (Hero becomes Hero.001), while Create names players Player.NNN. The agent refinement below says "named like a new player", which the code does not do. Options: after the original (recommended); like Create.
3. **Objects outside the player on Save.** A rig parented to an object outside the player, or with a constraint targeting one, makes Save write that object. Append then adds it to the scene as a loose object, and the rig stays parented (tested in Blender 5.2 on 2026-11-09). Options: write them and name them in the Save message (recommended); write them silently and document it; refuse and name them.
4. **Panel after Duplicate.** Duplicate always ties the panel to the copy. If the panel holds changes not yet applied, Update then applies them to the copy and refuses the player they were made for. Options: follow the copy as a click would, by the user's rule for selecting a player (recommended); always tie to the copy.

## Review findings (no decision needed, applied 2026-11-10)

- Re-bakes in Duplicate and Update set 50 fps and reset the frame range when the copy's clip track is empty, which breaks decision 4 and can cut another player's longer clip off the range. They should leave the scene's rate and range alone.
- A rig built before joint bones: Duplicate copies its label-bone keys onto joint bones. It should skip them and warn, as Update does (plan 11, Task 4).
- `plays_at_another_rate` compares (fps, fps_base) with (50, 1.0), so a scene at 100 fps with base 2.0 is flagged and the panel says it plays 50. Compare the rate itself, put 50 in one constant, and say in its docstring that an unreadable player is not flagged.
- Three places say the copies share nothing, but both use the file's one lit material: `duplicate_player`'s docstring, the operator's description and the HANDOFF notes below.
- Docstrings and comments: `_same_slot` (say it returns None when no slot matches), `carry_animation` and `STRIP_SETTINGS` (still name Update only), and the comment above the unused-action removal in `bake_clip_to_rig` ("a duplicated player").
- Unmarked claims: the HANDOFF notes' "almost all of it the bone keys", the Findings' "since hidden objects cannot be selected", and Findings line 3's "Not tested yet", which the Result answers.
- Tests: copied keys changed on one player leave the other's alone, using actions with real slots; duplicating a player with a shape-key clip; Set 50 fps starting from a base other than 1.0; the append test should read the clip track by `CLIP_TRACK`, not through `_clip_track`; drop the extra `appearance_preview` import in `test_appearance_files.py`.
- Rename `_copied` to `_shift_d_hint`. Give the append-nesting defect from the live check its own issue file.
- Provenance: the HANDOFF notes below file the copy's naming under the user's choices; it is an agent refinement until question 2 is answered. The Shift+D hint, the Save Player panel button and Save refusing Edit Mode are agent refinements too.
- Not applied: dropping the `appearance_preview` import in `test_appearance_files.py`, because the Save tests build their player with `appearance_preview.assemble_parts`.

## Second review (2026-11-10)

The two-axis review of the applied answers and findings raised these.

- Applied without a decision: strips that shared an action on the original share one copy of it on the duplicate; the material check reads arrays with `foreach_get` and compares node settings that name other data, such as an Image node's image; three docstrings; tests for Duplicate's and Save's Edit Mode refusals, a numbered fade material, appending twice, appending into a file without players, 60 fps on a base of 1.2, and a clip that cannot be baked again.
- Put to the user: decisions 9 to 13.
- Noted and left as they are: the rule that leaves an old rig's label-bone keys behind sits in `_replace`, `duplicate_player` and the Duplicate operator; some repetition in the tests; issue 26 (Asset Browser) was not asked for in this phase and stays parked.

## Result (2026-11-10)

- Each answer and finding has a Blender test: an edited numbered copy of the lit material counts as an edit and an unchanged one does not; Save names the rig's parent and a constraint's target, which the written file holds; the panel stays on the original while it holds changes not yet applied; Duplicate and Update bake again without changing the scene's rate or range, for shape-key and bone clips; Duplicate of a rig without joint bones warns and leaves its keys behind; the rate check reads `fps / fps_base`, so 100 fps on base 2 plays 50; keys changed on a copy's slotted action leave the original's alone; a shape-key clip is baked again onto the copy with its own keys.
- Live (2026-11-10, driven by the agent through the Blender MCP at the user's request, with the add-on loaded from `src`): a male player with the Rune scimitar and Rune kiteshield, a held woodcutting strip (sequence 1365) at frame 1 and a walk (819) at 4566, both baked as bone strips from the snapshot 430 cache. In a scene at 24 fps with range 1 to 9000, Duplicate made Player.001 with its own Steel axe object and its strips at the same frames. The scene stayed at 24 fps and 1 to 9000, the panel moved to the copy, and neither player counted as edited. Save wrote a 21.6 MB file holding the copy's five objects and the lit material, with no outside objects to name. In a new file (File > New), File > Append brought it in as a player: unedited, no notice, both strips at their frames, and the lit material under its own name. The 24 fps warning showed, and Set 50 fps cleared it. At frame 120 the copy holds the Steel axe and the scimitar is hidden.
- Seen in the live check, not caused by this plan: at frame 120 of the held woodcutting clip a dark triangle lies on the ground behind the feet. A player built fresh in the same file and baked with the same clip shows it too. Not investigated.

## Result (2026-11-09)

- Task 2 needed no image packing: players use one shared material that emits the lit corner colours and no images (`appearance_preview._material`). The append test's textured-faces check was dropped for that reason.
- The fingerprint now reads material names without Blender's numeric suffix, because Append renamed the shared lit material and the appended player counted as edited (evidence: the append test fails without it). Decision 5 (2026-11-10) narrows this: a numbered copy reads as its original only while their nodes, links and input values match.
- Duplicate names the copy's objects after its own collection; the first version named them after the original.
- Live check: see the HANDOFF notes below. A saved player with a 4,555-frame clip made a 21 MB file. Append puts the collection into the active collection, so a player's collection that is active in the Outliner receives the appended player as a child, and Update then refuses the outer player.

## Notes moved from HANDOFF.md (2026-11-09)

- Shift+D on all of a player's objects puts the copies into the same player collection, so it holds two rigs and two bodies and every bake and Update refuses it. A weapon a held clip had hidden was not copied, and the fade materials stayed shared (evidence: tried in the live session). The error for a player holding two of an object now says Shift+D does this and points to Duplicate Player (an agent refinement).
- Duplicate Player (the user's choices): builds a second player from the stored settings beside the players, unturned, bakes the original's recorded clips again at their start frames, and gives it copies of the user's own actions and strips (`carry_animation(copy_actions=True)`). The copy is named after the original with Blender's next number (the user's choice on 2026-11-10), and its objects after its own collection (an agent refinement). It shares only the file's one lit material, which every player uses: its fade materials are its own and their drivers read its rig. An edited player is refused before any change, because a rebuild cannot carry mesh edits.
- Save Player (the user's choice): writes the player and every datablock it uses to its own .blend with `bpy.data.libraries.write`, the collection with a fake user. Another file adds it with File > Append, choosing the collection. Players use no images: their one shared material emits the lit corner colours (`appearance_preview._material`), so nothing needs packing. Its panel button and its refusal in Edit Mode are agent refinements.
- The fingerprint reads material names without the numeric suffix Blender adds when a name is taken. Appending a saved player into a file that already holds players renames the shared lit material, which made the appended player count as edited (evidence: the append test fails without the change). Since 2026-11-10 (decision 5) a numbered copy reads so only while its nodes, links and input values match the material it is named after.
- The panel warns when the active player has clips and the scene does not play 50 fps, with a Set 50 fps button (the user's choice; nothing changes the frame rate without a click).
- Live (2026-11-09): Player.005 (a held woodcutting strip at frame 1 and a walk at 4566, moved, turned and scaled) duplicated as Player.006 with both strips at the same frames, a new Steel axe object, unedited, the panel tied to it. Saved, it made a 21 MB file. Most of that is probably the bone keys of the 4,555-frame woodcutting strip (0.58 million keyframe points), a guess that was not measured. Appended back, it arrived as Player.007, unedited, with both strips. At 24 fps the panel showed the warning, and Set 50 fps fixed it.
- Found in the live check: Append links the collection into the active collection. With a player's collection active in the Outliner, the appended player lands inside it, and Update then refuses the outer player, because it holds a child collection. Making the Scene Collection active before appending avoids it. Issue 27 tracks it.
- Not done (the user's choice for this phase): an Asset Browser entry.
