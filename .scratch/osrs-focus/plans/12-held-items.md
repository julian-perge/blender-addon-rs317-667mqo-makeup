# Held Items: Clips That Change What the Hands Hold

**Goal:** A baked clip shows what the client shows in the player's hands: the tool or item the clip names (an axe for woodcutting, a spade for digging), or empty hands where the clip hides the worn weapon and shield. Weapon stance sets (the stand, walk and run clips a wielded weapon swaps in) are a later phase: the server sends them and they are not in the cache.

## Findings (2026-11-07)

- Sequence opcodes 6 and 7 (`jg.k`, `jg.t`, already decoded as `left_hand_item` and `right_hand_item`) hold an equipment code: 0 for an empty hand, or item id + 512 (1865 in the steel axe chop 1365 is item 1353, the steel axe; 1464 in the long dig 831 is item 952, the spade). No value lies between 1 and 511. Script: `<scratch folder 2026-11-07-pushdown>/held.py`.
- Of the 2,267 player clips, 1,237 set a held item: 558 only empty the hands, 679 put an item in a hand.
- `hu.l(jg action, int, jg pose, int, byte)` in gamepack-149 (offsets 93 to 398 and 573 to 583, read with `javap -c -p`): when the action sequence's `k` or `t` is 0 or more, it copies the 12 worn slots, puts `k` in slot 5 (shield) and `t` in slot 3 (weapon), and builds the model from the copy. It reads held items from its first argument only. `be.k` passes `ca.bs` (the action sequence) first and `ca.bc` (the pose sequence) second, so a clip played as a pose never changes the hands.
- `merge` shares a vertex between parts at the same position, and the vertex keeps the label of the first part that supplied it. A held item that touches the body therefore moves partly with body labels.

## Decisions (agreed with the user)

1. Scope: held items first; stances later.
2. Separate objects: the worn Weapon and Shield become their own objects in the player's collection, moved by the same rig. Each item a clip holds becomes an object too. Each object is shown only on the frames where the client shows it, in every viewport mode.
3. Follow the client: held items apply only when Play As is Action. When the picked clip names held items and Play As is Pose, the panel says so.
4. Both bake methods show held items: Bones moves the item objects with the rig, Shape Keys gives each item object its own shape keys.
5. Posing (2026-11-09, the user's choice of a deepening after this plan): `appearance_pose.pose_player(collection, clip, action=, dump_folder=)` gives both bakes the posed model, its frames and schedule, the equipment the client shows, and `ensure_parts()`, so neither bake branches on held items.
6. Clip modules (2026-11-09, the user's choice of a split): `appearance_clip` keeps the two bakes, Update Player's support and the operators; `appearance_shape_keys` writes the shape keys, `appearance_bone_action` fits the bones and writes the action, and `appearance_clip_cache` finds cache clips. Update support stayed in `appearance_clip` because it reads the clip records and mirrors the track layout the bakes write, so a module of its own had two reasons to change.

Agent refinements:
- Each object's faces come from the client's full merged model (with the substitution for a held variant), lit as one model and split by slot, so colours and labels equal the client's.
- In a gap after a clip, the held item stays with the clip's held last pose until the next clip, as the pose does (the user's hold choice).

## Tasks

- [x] **Task 1: Client reference.** Record the client's posed merged model, as an action sequence, for three clips: one that only empties the hands, one that holds an item in one hand, one with both hands set (candidates 717 cast weaken, 1365 steel axe chop, 909 mapping), with a worn weapon and shield. Fixtures and README in `tests/fixtures/animation149/`.
- [x] **Task 2: Held equipment.** A pure function gives the 12 slots the client builds from for a worn equipment list and a sequence. Assembly reports each slot's face range in the merged model. Unit tests against Task 1.
- [x] **Task 3: Split player.** Create and Update build the body mesh plus Weapon and Shield objects from one lit merged model, bound to the rig. Every place that assumed one mesh (fingerprint, edited checks, remove, fades, shape-key bake) handles the objects. Blender tests: the faces, colours and labels together equal today's single mesh.
- [x] **Task 4: Held objects and visibility.** A bake played as Action builds each held variant's slot objects (adding label bones the rig lacks), and keys every hand object's visibility on the strip's frames. Bones and Shape Keys. Bounds against Task 1.
- [x] **Task 5: Panel and Update.** The Pose hint; Update bakes again with held items. Docs, a live check with the user, commit.

## Result (2026-11-09)

The user asked the agent to drive the live check in Blender. A male player wearing a Rune scimitar and Rune kiteshield was created from the panel; the Outliner listed the body, `Player Weapon` and `Player Shield`.

- With the steel axe chop (1365) picked and Play As set to Pose, the held-items hint showed. With Play As set to Action, Bones at frame 20 added the strip; frames 1 to 19 show the scimitar and kiteshield, and from frame 20 they hide and `Player Steel axe` chops.
- Mapping (909) at frame 4580 and cast weaken (717) after it: `Player Charcoal` and `Player Papyrus` show from 4580, and both hands are empty from 4664.
- Every vertex of the body and held objects stayed within 2.28 game units of the client's posed model on the frames compared (1365: 1.78, 909: 2.28, 717: 1.61).
- The small grey spikes beside the hands are the rig's joint bones, which show where the mesh does not cover them.
- Fixed during the check: the panel's hints were cut short in a default-width sidebar, since they wrapped at a fixed 44 characters. They now wrap to the sidebar's width, measured in the interface font.
