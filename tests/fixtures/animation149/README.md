# Revision 149 clip inputs and client recordings

Raw (decompressed) data from OpenRS2 snapshot 430 and what the unchanged revision-149 client (`gamepack-149.jar`,
SHA-256 `19c492cc...cbdd`) does with it. Paths below use `CACHE=<path to cache>` (the `cache/` folder of snapshot 430)
and `JAR=<reference work folder>/gamepack-149.jar`.

## Clip folders

| Folder | Sequence | Frames | Recorded bodies |
| --- | --- | --- | --- |
| `walk` | 819 | 8 of 6 ticks, group 207 files 357 to 364 | male, female |
| `idle` | 808 | 12 of 21 ticks, group 207 | male, female |
| `run` | 824 | 8 of 4 or 5 ticks, group 207 | male, female |
| `loop` | 1499 | 26 frames of group 274, loop offset 4 | male |
| `alpha-1697` | 1697 `HUMAN_DODGE_RF_B` | 22 frames, face alpha transforms that change no face | male, female |
| `alpha-1994` | 1994 `IC_PIT_FALL` | 8 frames; the last four fade every face | male, female |
| `alpha-3182` | 3182 `SPIT_END_ANIM_PLAYER` | 19 frames, face alpha transforms that change no face | male, female |
| `alpha-3364` | 3364 | 20 frames; frame 10 fades the player's labels 18 to 21 and 23 to 26 to 255 and the other labels to 32 | male, female |

The first three `alpha-` sequences were picked with `random.Random(149).sample` from the 217 player clips (frame map 0)
that have a face alpha transform. `alpha-3364` was found by scanning all 217: it is the only one whose alpha transforms
give the player's face labels (0 to 2, 4 and 9 to 27) more than one curve. The other 216 move no player label, or move
all of them with one curve. Its labels form two groups, and the groups differ on frame 10 (counting from 0) only. The
recordings of all four include the face alphas `o`, copied at the face count, because the
client reuses the alpha buffer of animated models for the next frame; it keeps them as signed bytes.

Every frame uses frame map 0. Sequences 819, 808 and 824 hold only their frame list (opcode 1): no held items. That
they are the player's walk, stand and run is the task's labelling, not checked against the client (the server picks
the player's sequences).

Each folder holds `sequence.dat` (file `<id>` of cache index 2 group 12), `frames/<group>_<file>.dat`, `maps/<id>.dat`
and `manifest.json` (SHA-256 of every file and of the source `main_file_cache.dat2`), made by:

```bash
uv run tests/fixtures/animation149/export_clip.py --cache $CACHE --sequence 819 \
  --output tests/fixtures/animation149/walk
```

`pose-<body>.json` is the client's rest and posed vertices for the client's own default equipment of that body
(`client_default_equipment` in `../appearance/reference.json`) and colours `[0,0,0,0,0]`, one entry per frame. The
harness `../PoseReference.java` runs the unchanged `hu.l` with a `jg` holding the packed frame ids and static frame
archives filled from the folder, then reads the lit model by reflection: `v` vertex count, `w` face count, `e`/`l`/`s`
x, y and z, `o` face alphas. Recording refuses an existing output file:

```bash
uv run tests/fixtures/record_pose.py --client $JAR --kits tests/fixtures/appearance/kits \
  --clip tests/fixtures/animation149/walk --body female
```

## Held items

| Folder | Sequence | Held items (opcode 6 shield hand, opcode 7 weapon hand) |
| --- | --- | --- |
| `held-717` | 717 `HUMAN_CASTWEAKEN` | 0 and 0: both hands empty |
| `held-1365` | 1365 `MISC_HUMAN_WOODCUTTING_STEEL_AXE` | 1865 (item 1353, Steel axe) and 0 |
| `held-909` | 909 `HUMAN_MAPPING` | 1485 (item 973, Charcoal) and 1482 (item 970, Papyrus) |

Each folder is a clip folder as above, plus `items/<id>.dat` (raw item files, the same bytes as files of cache index 2
group 10) for the worn Rune scimitar (1333) and Rune kiteshield (1201) and the held items, and `models/<id>.dat` with
each item's male worn model (the same bytes as file 0 of its group in cache index 7). `ItemDefinitions.json` is
RuneLite's decoding of the folder's items. `pose-male.json` is recorded with `--held`: the harness decodes
`sequence.dat` with the client's loader `du.j`, so `hu.l` substitutes the held items, and the equipment is the male
default with the scimitar and kiteshield worn. `rest` is the model with no sequence (630 faces); the frames have 476,
516 and 522 faces.

```bash
uv run tests/fixtures/record_pose.py --client $JAR --kits tests/fixtures/appearance/kits \
  --clip tests/fixtures/animation149/held-1365 --body male --held --weapon 1333 --shield 1201
```

## Sequence decoding and timing

`sequences/<id>.dat` are unchanged copies of file `<id>` of cache index 2 group 12: the clip sequences, and for each opcode 2 to
13 at least one sequence that uses it. `sequences.json` is recorded by `../record_sequences.py` with the harness
`../SequenceReference.java`. It decodes each file with the client's own loader `du.j` (which runs `jg.n`, `jg.r` and
`jg.v`) and stores the fields multiplied by the client's own getter multipliers. Each timing case steps the client's
per-tick actor update `ap.fb` on a constructor-free player whose pose sequence (`ca.bc`) or action sequence (`ca.bs`) is
the given id, and stores the frame index before the first tick and after each tick, -1 once an action has stopped:

```bash
uv run tests/fixtures/record_sequences.py --client $JAR --sequences tests/fixtures/animation149/sequences \
  --output tests/fixtures/animation149/sequences.json --timing 819:pose:110 808:pose:300 824:pose:80 \
  1499:pose:250 819:action:60 1499:action:2200 1501:action:200 622:action:600
```

The harness keeps the actor in `ap.fb`'s first movement branch (`ca.be` far past `client.bw`), inside the 128 to 13184
square, with no turning and no spot animation, so only the frame counters change. How often the game calls `ap.fb`
(once per actor per client cycle) is not checked in 149.
