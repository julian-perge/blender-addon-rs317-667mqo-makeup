# OSRS revision 149: applying an animation frame to the player model

Researched November 7, 2026 (America/New_York) by reading bytecode and local files. Nothing was run: no dumper, no client, no Blender. Every statement is tagged **[evidence]** (read in a named file, class and bytecode offset) or **[guess]** (inference not yet checked). This is research for milestone 5, not an approved plan.

Status 2026-11-07: open decisions 2 (both bodies) and 7 (timing) and the sequence opcodes of section 4 are settled by client runs; see "Clip coverage" below. The pose and action frame counters are `ap.fb` in 149.

Status 2026-11-07 for decision 3 and the rig-fit guess in section 4: the guess is wrong for these clips. Pivots are fixed while a frame is applied and every scale in walk, idle, run and 1499 is uniform, so each label moves by one rotation, uniform scale and translation. Fitted in real arithmetic, that leaves at most 2e-4 units; against the client's integer vertices the fit is at most 2.02 units off. See "Bone rig clip" below.

## Sources and naming

- Client: `<reference work folder>/gamepack-149.jar`, SHA-256 in [the appearance README](../../tests/fixtures/appearance/README.md). Offsets below are `javap -c -p` offsets inside the named method. "javap line" points into `osrs149-reference-<class>.javap` in the same folder. Classes `eg`, `eb`, `et`, `jg`, `hu`, `cd`, `if` have no dump there; they were read with `javap -p -c -cp gamepack-149.jar <class>` and the line numbers are not stable, so only offsets are cited for them.
- Names come from RuneLite source in `<RuneLite May 2018 tree>/runescape-client/src/main/java/` (May 2018, not a verified match for the July 2017 binary) **[evidence]**. `<data workspace>/decompiled-clients/` holds only the 317 and 667 clients, no OSRS 2013 or 2018 client, and `runelite-1.13.6-sources` holds only cache-library classes (`ModelDefinition`, `ModelLoader`, `ObjExporter`), so neither helps with animation naming **[evidence]**. The 2013 revision-1 client is cited only through the comments in `src/rsps_toolkit/animation/poses.py`; it was not re-read.
- Class map for 149 **[evidence from field and call shapes, names by correspondence with the 2018 source, so partly guess]**:

| 149 class | 2018 name | Role |
| --- | --- | --- |
| `dv` | `ModelData` | unlit model. `ae` = vertex labels per vertex, `au` = face labels per face, `ak`/`ap` = the grouped label arrays |
| `ej` | `Model` | lit model. `e`,`l`,`s` = vertex x,y,z; `o` = per-face alpha bytes; `q` = vertex label groups, `y` = face label groups |
| `et` | `Frames` | one frame group: `et.a` is `eg[]` indexed by file id |
| `eg` | `Frame` | one frame: `e` transform count, `l` skeleton indices, `s`/`w`/`p` = x,y,z, `v` = its `eb`, `m` = has an alpha transform |
| `eb` | `FrameMap` | `j` entry count, `n` types, `r` label lists |
| `jg` | `Sequence` | `e` = packed frame ids |
| `hu` | `PlayerComposition` | `hu.l(jg,int,jg,int,byte)` returns the posed lit model |
| `if` | `AbstractArchive` | `u` = file bytes, `s` = file id lists per group |

## 1. Where the frame is applied

**[evidence]** `dv.ak`/`dv.ap` are built by `dv.al()` (javap line 2981, offsets 0-354). It counts vertices per label from `ae` (`a` vertices) and faces per label from `au` (`v` faces) in a 256-entry histogram, allocates `ak = new int[maxLabel+1][]` and `ap` likewise, and fills each with the member indices. At offset 36 it sets `ae` to null, so the per-vertex label array is gone after grouping. `dv.ae(int,int,int,int,int)` (the lighting step, javap line 6605) copies the groups to the lit model at offsets 1815-1825: `ej.q = ak`, `ej.y = ap`. Posing therefore runs on the lit model, after lighting.

**[evidence]** The call chain for one player frame, all unchanged 149 bytecode:

1. `hu.l(jg actionSeq, int actionFrame, jg poseSeq, int poseFrame, byte guard)` builds or fetches the lit `ej` (`dv.ae` at offset 292, merge `dv.<init>([Ldv;I)` at 828, recolour `dv.c` at 858). At offsets 1088-1154 it picks one of three calls: both sequences non-null: `jg.w(ej,int,jg,int,byte)` (interleave); only the action sequence: `jg.e(ej,int,short)`; otherwise `jg.e` with the pose sequence and pose frame. The `byte` argument must be 127 (offsets 1109-1116).
2. `jg.e(ej, frameIndex, short)`: `id = jg.e[frameIndex]`, loads the frames with `cd.m(id >> 16, byte)` (a `Frames` cache keyed by group), takes `id & 65535` as the file id, clones the model (`ej.j(boolean)`) unless the frame has an alpha transform, then calls `ej.m(et, int)` (offsets 56-74). If `cd.m` returns null the model is returned unposed (offsets 41-52).
3. `ej.m(et, int)` (javap line 8065) and its twin `ej.ba(et, int)` (javap line 1208; both are the same code behind different obfuscation control flow): returns if `ej.q == null` or the file id is -1; zeroes the three pivot statics `ej.bb`, `ej.bn`, `ej.bs` (offsets 11-15, 28-32, 45-49 in `m`); for each transform `i` of the frame calls `ej.g(frame.v.n[index], frame.v.r[index], frame.s[i], frame.w[i], frame.p[i])` (offsets 73-111); then calls `ej.p()` (bounds reset, offset 120) **[the purpose of `p` is guess]**.
4. `ej.g(int type, int[] labels, int x, int y, int z)` (javap line 3123) is the transform method. This is the answer to "the method that applies a frame's transforms to label groups". It is the 2018 `Model.animate` (`Model.java:745`) **[evidence by identical structure; the source is the same algorithm]**.

**[evidence]** Two-clip blending uses `ej.u(et,int,et,int,int[])` (javap line 2938): the first frame applies for skeleton indices not in the sorted int list, the second for those in it; `jg.w` is the caller. Offsets 61-70 zero the pivot, and the code walks the list with a cursor. The detailed pairing rule was read only roughly **[guess]**. Milestone 5 does not need it.

Transform types handled by `ej.g` **[evidence]**:

| Type | Meaning | Offsets in `ej.g` |
| --- | --- | --- |
| 0 | set pivot | 317-321 dispatch, 15-26 reset, 38-61 label loop with guard `label < q.length`, 846-935 and 1077 accumulate and count, 190-231 average and add (x,y,z), 814-818 and 231-238 empty case |
| 1 | translate | 1063-1068 dispatch, 150-204 and 324-366 add (x,y,z) |
| 2 | rotate about pivot | 377-382 dispatch, 399-541 angles, 553-758 rotation, 467-521 subtract pivot, 772-811 add pivot |
| 3 | scale about pivot | 828-833 dispatch, 836-929 loop, 1219/913/89 subtract pivot, 935-997 scale, 173/1034 add pivot |
| 5 | face alpha | 1083-1095 dispatch (needs `ej.y` and `ej.o` non-null, offsets 1088-1092 and 762-766), 1161-1243 and 1185-1210 add, 905-910 and 64-72 and 1246-1260 clamp |
| other | ignored | 189 returns |

There is no type 4 in 149 or in the 2018 source **[evidence]**.

## 2. Transform semantics and arithmetic, compared with `poses.py`

**[evidence]** All values are Java `int` (32-bit wrap) and the tables are shared with the rasteriser: `ej.bw = ep.y` (sine) and `ej.bg = ep.ai` (cosine) from `ej.<clinit>` offsets 13-16 and 233-236. `ep.<clinit>` (javap line 13496) fills 2048 entries as `(int)(65536.0 * Math.sin(i * 0.0030679615))` and the cosine analogue (offsets 8-91 and 109-191; constant `0.0030679615d` at offsets 40 and 183). `poses.py` lines for `_SINE` and `_COSINE` use the same expression and the same decimal constant.

Semantics, each compared with `_evaluate` in `src/rsps_toolkit/animation/poses.py` **[evidence for 149 side, evidence from reading the Python for the other side]**:

- **Pivot (type 0).** 149: sum `e,l,s` of the current (already modified) vertices of every listed label, count them, then `pivot = delta + sum / count` with Java `idiv` (truncation toward zero); with count 0, `pivot = delta`. Identical to poses (`_div`, the `affected` list, the `else` branch). The pivot statics start at 0 for each frame (`ej.m` offsets 11-49) and persist across transforms within the frame, as the poses `pivot = (0, 0, 0)` does. Identical.
- **Translate (type 1).** Adds `x,y,z` to every member vertex. Identical.
- **Rotate (type 2).** Angle `a = (v & 255) * 8` for each of x,y,z (`ej.g` offsets 385-391, 454-461, 530-538); the unit is 1/2048 turn, so the argument is in 1/256 turns and a full turn is 256. Subtract the pivot, then rotate in the order **z, then x, then y**, each skipped when its angle is 0, then add the pivot back:
  - z: `x' = (y*sin + x*cos) >> 16`, `y' = (y*cos - x*sin) >> 16` (offsets 574-600, 1000-1030);
  - x: `y' = (y*cos - z*sin) >> 16`, `z' = (y*sin + z*cos) >> 16` (offsets 1098-1124, 658-697);
  - y: `x' = (z*sin + x*cos) >> 16`, `z' = (z*cos - x*sin) >> 16` (offsets 425-451, 728-758).

  `poses.py` does the same three steps in the same order with the same formulas and `_int32` around each product sum. Identical. Intermediate results are truncated by `>> 16` (arithmetic shift, floor), which Python's `>>` matches.
- **Scale (type 3).** Subtract pivot, `v = v * s / 128` with `idiv` per axis, add pivot (offsets 935-997). Identical to poses (`_div(_int32(x * dx), 128)`).
- **Alpha (type 5).** For each label in `ej.y`: `a = (o[face] & 255) + x * 8`, clamped to 0..255, stored back as a byte (offsets 1185-1210, 905-910, 1246-1260). Only the x delta is used. Identical to poses (`min(255, max(0, alpha + dx*8))`). The face alpha bytes in the client are the transparency convention of the model class, so the same sign convention as the Python alpha **[guess for the convention; the arithmetic is evidence]**.
- **Guards.** The client skips labels whose index is `>= q.length` (type 0, 1, 2, 3 loops) and for alpha labels `>= y.length` (offset 255-262 area, 1161). Python's `dict.get` default matches **[evidence for client, evidence from reading the Python]**.

**Verdict [evidence]:** the integer transform arithmetic in 149 is identical to the existing revision-1 evaluator; no rewrite is needed. Two real differences are about data, not arithmetic: the frame decoder and the surrounding player pipeline (sections 3 and 4).

One frame-level rule matters if frames are decoded in Python **[evidence]**: `eg.<init>(byte[], eb)` inserts an implicit type-0 transform with all-zero deltas before a non-pivot transform when no pivot (type 0) entry was kept since the last emitted transform (offsets 143-213, mirrors `Frame.java` in the 2018 source). A scale transform's missing axis defaults to 128, others to 0 (offset 528: `sipush 128`). The Java `LegacyAnimationData` writer apparently already does this for revision 1 **[guess; not re-read]**.

## 3. Where frame and skeleton data live in cache 430

**[evidence]** From the client:
- `jg.u(if,if,if)` stores the sequence archive in `jg.a` and the frames archive in `jg.j` (offsets 1-5 of `<clinit>`-adjacent code, `putstatic jg.a`/`jg.j`). `eb` frame maps come from the archive `ah.n` (read by `cd.m`).
- `cd.m(frameGroup)`: `if.g(group)` lists the file ids of the group (`if.s[group]`); each file's first two bytes are the frame map id; the map is loaded with `if.p(mapId, 0, ...)`, so the map is file 0 of group `mapId` in the skeleton archive (`et.<init>` offsets 21-48, 105-175, 206-248). Frames are then built with `new eg(bytes, map)` into `et.a[fileId]`.
- `eb.<init>(int, byte[])`: u8 entry count `j`, `j` u8 types, `j` u8 label counts, then the u8 labels per entry. This matches `FrameMap.java` in the 2018 source.
- Sequence frame ids are packed `group << 16 | file` (`jg.e` offsets 4-6 and 83-92).

**[evidence]** RuneLite `IndexType` (from `cache-1.13.6-sources.jar`): index 0 = ANIMATIONS (frames), 1 = SKELETONS (frame maps), 2 = CONFIGS. The 430 cache has `main_file_cache.idx0` of 11,514 bytes and `idx1` of 10,218 bytes (`ls -l`), which at 6 bytes per entry is 1,919 and 1,703 groups **[guess for the exact counts: assumes no gaps]**.

**What the local dump already holds [evidence from `ls`]** at `<data workspace>/exports/osrs/openrs2-430/dump/`:
- `dump_index/configs/sequence/`: 7,636 raw per-sequence files `0.dat` to `7635.dat` (config group 12 of index 2). They are undecoded; for example `808.dat` is 88 bytes, starts `01 00 0c` then twelve durations of `00 15` (12 frames of 21 ticks) **[the field meaning is guess; 808 being the male stand pose is guess from general RuneScape knowledge, not checked]**.
- `dump_index/configs/identkit/` (151 raw kits), `items/`, `models/` (33,196 raw models), `maps/`, `sprites/`, `music/`, and typed JSON folders `items`, `kits`, `npcs`, `objects`, `spotanims`, `structs`, `enums`, `varbits`, plus `textures`, `item_icons`, `models_obj`, `sounds`.
- **Not present:** raw or decoded frame groups (index 0), raw or decoded frame maps (index 1), decoded sequences. There is no `frames`, `skeletons` or `sequences` folder, no animation bundle, and `README.md` there states the animation reader is verified for revision 1 only and the 2013 animation request must not be reused for 430.
- The raw source is intact at `<data workspace>/caches/osrs/openrs2-430/cache/` (`main_file_cache.dat2`, `idx0`, `idx1`, `idx2`), so the data exists on disk but was never exported **[evidence]**.

`src/rsps_toolkit/animation/bundle.py` defines `Sequence`, `Frame`, `FrameMap` dataclasses already shaped like the client's (`Frame(map_id, indices, x, y, z)`, `FrameMap(types, labels)`) **[evidence]**, but its loader accepts `source.cache_revision == 1` only (`osrs-player-customization.md`).

## 4. The player case

**[evidence]** Which sequence the player plays is not decided from item or kit data in the pinned 2018 source. `Player.java` (lines 223-250 region) reads seven animation ids from the server's appearance block: standing (`idlePoseAnimation`), then six more (turn, walk, back-walk, left, right, run) and sets `poseAnimation` from them in the movement code (`class68.java:216,280,324`, `FaceNormal.java:103-122`). `Player.getModel` (`Player.java:364-365`) passes `Actor.animation` (action sequence, used when `actionAnimationDisable == 0`) and `poseAnimation` (pose sequence) to `PlayerComposition.getModel(seq, frame, seq, frame)`, which is `hu.l` in 149. So the player sequence id is **server data**, not cache data; a toolkit must let the user choose one **[evidence for 2018, guess that 149 reads the same block: the 149 reader was not located]**. A player weapon can substitute the held items for a sequence (`Sequence.leftHandItem`/`rightHandItem`, applied at `PlayerComposition.getModel` lines 243-259), so a clip can change the merged model's contents **[evidence for 2018; `jg` fields `g`,`t` look like those items, guess]**.

**Labels versus the frame map [evidence for our side, gap for the match].** The M4 merged model carries labels: vertex labels in `tests/fixtures/appearance/reference.json` span 0 to 49 in the cases sampled (case 0: 33 distinct labels among 264 vertices; case 8: 37 among 829), and face labels 0 to 27, and this comes from the unchanged client's own merge (`dv.v(dv,int)`, javap line 2107, offsets 160-181: the first vertex position's label wins on a coordinate match and a source without labels leaves 0). Whether every label listed in a player frame map falls inside this set cannot be checked until a frame map is decoded; no frame map is available locally **[gap]**. Labels a model does not have are skipped silently by the client (guards above), so a mismatch would show as unmoved vertices, not an error **[evidence]**.

**Rig fit [guess].** `appearance_rig.derive_rig` gives one bone per label headed at the centroid with weight 1.0 on one bone. A game pose does not map onto bones cleanly because (a) the pivot is recomputed from the already-moved vertices of other labels (type 0 is stateful and order dependent), (b) rotation is applied with integer truncation and a fixed z,x,y order about a pivot that need not be a bone head, (c) scale is per axis about a pivot, and (d) alpha changes are per face label. Exact reproduction therefore means evaluating the pure function per vertex and either baking shape keys or using it as a reference for fitted bone transforms **[guess]**. Qodat's rigid fit and Creator's Kit's baked morph targets are the two precedents (see [blender-animations.md](blender-animations.md)).

**Lighting stays at rest [evidence].** The client animates the already-lit `ej` and does not relight, so the per-face shade arrays (`ej.g`, `ej.k`, `ej.t`) are those of the rest pose. The existing preview mesh built from `lighting.light` is therefore already the right shading for a posed model.

## 5. Recording a client-computed posed vertex set

**[evidence]** The existing harness (`tests/fixtures/AppearanceReference.java`, `record_appearance.py`) calls `hu.l(null, 0, null, 0, (byte)127)` with null sequences and snapshots the returned `ej` through reflection (`snapshot`) plus a JVMTI entry hook on `dv.ae` and on `dv.<init>([Ldv;I)V`. It builds empty archives by `Unsafe.allocateInstance` of class `ig` and fills only `if.u` (file bytes). It writes statics through reflection (`jg` is not touched today).

Feasibility **[guess unless marked]**: high, with no new JVMTI work.

1. `hu.l` with a non-null `jg` runs the same code path the game uses (offsets 1088-1154), so the posed `ej.e/l/s` after the call are the client's answer. The JVMTI hook is not needed for posed vertices; reflection on the returned object suffices, as it already does for `client_lit`.
2. The new inputs are: a `jg` instance (allocate with Unsafe and set only the int array `e` to `{group << 16 | file}`; `jg.e` reads nothing else, offsets 0-6 **[evidence]**), the static archive `jg.j` as an `if` with `u` (file bytes per group) and **`s` (file id list per group), which the current harness does not set** because kits and items do not call `if.g` **[evidence: `if.g` returns `s[group]`, `if.p` indexes `u[group][file]`]**, and the static skeleton archive `ah.n` with `u` holding file 0 of each map group. The `jg.v` frames cache is a `gc` static initialised by the class **[guess]**.
3. `ej.m` clones through `ej.j(boolean)` only when needed, so call `hu.l` twice (null sequence for rest, real sequence for posed) and read both vertex sets **[guess]**.
4. A fixture needs the raw bytes of one frame group, its frame map and the sequence file as decompressed js5 file bytes (the same form the harness already takes for models and kits). Today the dump holds none of the frame data (section 3), so the recording needs a small one-off export of one group from idx0, one from idx1 and a sequence from the existing dump. That export is outside this research; the dumper was not run.
5. Cost: the harness verifies input hashes and the gamepack SHA-256; any new input must join that list **[evidence from README]**. `hu.l` needs complete kits and models for the preset, as the current cases already supply **[evidence]**.

Also usable without any client run: the recorded pre-lighting model plus a hand-picked frame could test only our own code, not the client, so a client-computed vertex set is the only independent oracle **[guess]**.

## Proposed milestone 5

Principle: pure code in `formats/` or `animation/` first, each task test-first against the recorded client output; Blender code last.

Tasks, in order:

1. **Export one clip's inputs for the client.** Decide the clip (see open decisions), export its frame groups, the frame maps they reference and its sequence file as raw bytes into `tests/fixtures/animation149/`, with source hashes. (Dumper or one-off script; hooks and `uv` rules apply.)
2. **Decode frame map, frame and sequence (pure, TDD).** `formats/frames.py`: `decode_frame_map`, `decode_frame(bytes, map)` including the implicit pivot insertion and default 128 for scale, `decode_sequence`. Tests use the fixtures and cross-check counts with the 2018 source rules above.
3. **Extend the harness.** Set `if.s`, `jg.j`, `ah.n`, a `jg` instance; record rest and posed `ej.e/l/s` (and `ej.o` for alpha) per frame for the chosen clip, for male and female. Same recorder runner and hash list as the appearance reference.
4. **Reuse or lift `_evaluate`.** Move the pure transform from `animation/poses.py` into a function that takes plain vertex, label and frame data (no bundle or asset), keep the revision-1 test green, and add a test that equals the client's posed vertices for every frame of the clip. Expect no arithmetic change (section 2); any mismatch is then a data or ordering bug.
5. **Label coverage check (pure).** For a player model and a frame map, report labels used by the frame map that the model lacks and the reverse; assert it for the chosen clip.
6. **Timing (pure).** Frame index at a given client tick from the sequence durations and loop rules, tested against the recorded clip; decide whether the first milestone is non-looping.
7. **Blender bake.** Apply the pose function to the M4 collection's vertices as shape keys or a fitted action, using `blender/animation.py` patterns; no relighting. Add a `.blend`-level test only through the existing Blender execution path.
8. **Panel.** A sequence field (pose id) and a "play clip" operator that refuses an edited player (`is_edited`), mirroring M4's guards.

## Open decisions for the user

1. **Which clip first.** The idle stand, walk, or a weapon attack? A chosen clip fixes which frame maps and which labels must match.
2. **Male only or both body types.** Both are in the appearance reference; frames are shared but labels differ per merge.
3. **Bake or rig.** Shape keys per frame (exact, large) versus fitted bone keys (editable, not exact, per the Qodat precedent) versus both with the bake as reference. The M4 label-bone rig cannot reproduce stateful pivots exactly **[guess]**.
4. **Alpha (type 5).** The client changes face alpha during a clip. Include it in the first milestone or defer.
5. **Where the raw frame data comes from.** Extend the dumper, or a standalone script that reads idx0/idx1 once and writes fixtures.
6. **Weapon-driven substitution.** Whether the sequence's held-item overrides (`leftHandItem`/`rightHandItem`) are in scope, since they change the merged model.
7. **Timing fidelity.** Whether to model the 20 ms client tick loop exactly or just step through frames in order for the first milestone.
8. **Fixture scope.** One clip, one body type, two colour sets as in M2, or a wider sample.

## Clip coverage (2026-11-07)

This section and the next record client and Blender runs made after the research above, so the header's tags do not apply to them: each statement comes from those runs unless it says guess, inference or unverified.

Verified by running the unchanged revision-149 client:
- Poses: `evaluate_frame` equals the client's posed vertices on every frame of walk 819, idle 808 and run 824 for the male and female default bodies, and of sequence 1499 (loop offset 4) for the male body. Fixtures: `tests/fixtures/animation149/<walk|idle|run|loop>/`, see its README. None of these clips changes face alpha. 808, 819 and 824 hold only opcode 1, so no held items.
- Sequence opcodes: `animation/frames.decode_sequence` reads opcodes 1 to 13 into `SequenceDefinition` (loop offset, interleave, stretches, priorities, held items, loop limit, reply mode, chat frames, frame sounds), cited to `jg.r` javap offsets. It equals the client's `du.j` decoding on the 16 committed sample files and, in a one-off run, on all 7,636 sequences of the dump. Any other opcode is refused: the client skips it without reading its operands.
- Timing: `frame_schedule` follows `ap.fb` (javap offsets in `frames.py`) and equal the client's per-tick counters for 8 recorded cases. A pose sequence starts frame 0 with its counter at 0, so frame 0 shows one tick longer than its duration and the walk cycle is 49 ticks, not 48; it ignores the loop offset. An action sequence plays once (no opcode 2), or steps back by its loop offset until it has looped `max_loops` times; sequence 1499 stops after tick 2127.
- Blender: Bake Clip keys each frame on the ticks the client shows it, with a Play As choice (Pose, the default, or Action). Tests: the walk and idle bakes equal the client's timing and the idle bake equals the client's vertices for both bodies; the 1499 action bake equals the client's timing until it stops.

Not verified or not done:
- Play As defaults to Pose. That is an agent choice that needs the user's decision (issue 21 (`git show 2a78edd:.scratch/osrs-focus/issues/21-play-as-defaults-to-pose.md`)): the clip folder cannot say whether the server plays a sequence as the pose or the action.
- The start state (frame 0, counter 0) is that of a new actor. In the 149 bytecode the only places that zero the pose counters are the cycle wrap in `ap.fb`, so switching from walk to idle in game keeps the frame index; the bake always starts at frame 0. Where the client resets the action counters when an action starts was not located in 149.
- How often `ap.fb` runs (once per actor per 20 ms client cycle) is from the 2018 source, not checked in 149. The bake still uses one Blender frame per tick at 50 fps.
- Not recorded: female body for 1499, held-item substitution, interleaving two sequences (`jg.w`), face alpha (type 5), `stretches` and the precedence and priority fields' effects. Held items and face alpha were recorded later, in plans 12 and 10.

Regenerate (see `tests/fixtures/animation149/README.md` for the variables):

```bash
uv run tests/fixtures/animation149/export_clip.py --cache $CACHE --sequence $DUMP/sequence/808.dat --output tests/fixtures/animation149/idle
uv run tests/fixtures/record_pose.py --client $JAR --kits $DUMP/identkit --clip tests/fixtures/animation149/idle --body male
uv run tests/fixtures/record_sequences.py --client $JAR --sequences tests/fixtures/animation149/sequences --output tests/fixtures/animation149/sequences.json --timing 819:pose:110 808:pose:300 824:pose:80 1499:pose:250 819:action:60 1499:action:2200 1501:action:200 622:action:600
uv run tests/fixtures/record_sequences.py --client $JAR --sequences $DUMP/sequence --output /tmp/all-sequences.json
```

Repeat the first two for walk 819, run 824 and loop 1499, and for `--body female`. Recording refuses existing output files, so move the old file away first. The all-dump comparison was a scratch script (`<scratch folder 2026-11-07-clip-coverage>/compare_all.py`) that decodes each dump file with `decode_sequence` and compares it with the client JSON.

## Bone rig clip (2026-11-07)

Done: Bake Clip has a Method choice (Shape Keys, the default and the exact reference, or Bones), and the panel shows Bake Shape Keys and Bake Bones. `animation/label_fit.py` fits, per frame and label, the least-squares rotation, uniform scale and translation from the label's rest vertices to `pose_vertices` (Horn's quaternion method, pure Python). `appearance_clip.bake_clip_to_rig` turns each fit into the label bone's location, quaternion and scale in its rest frame and writes one constant curve per channel into a layered action (slot, layer, keyframe strip, channelbag), keyed on the same `frame_schedule` ticks as the shape-key bake, rest on frame 0 and after the end.

Why a similarity and not an affine fit: a pose bone has no shear, and in these clips every pivot is fixed while a frame is applied and every scale is uniform (1499 scales all three axes alike, 0 to 112 of 128), so each label moves by one similarity. Evidence: fitted against a real-arithmetic evaluation of the same frames, the residual is at most 2e-4 units (the sine table's 1/65536 steps), and a 12-parameter affine fit against the client is no better (max 1.1 to 1.9). The milestone 5 guess that stateful pivots prevent this was wrong (scratch scripts in `<scratch folder 2026-11-07-bone-rig-clip>/`).

Measured distance from the fitted vertices to the client's recorded vertices, in game units (max, mean): walk male 1.77, 0.38; walk female 1.45, 0.39; idle male 1.46, 0.29; idle female 1.20, 0.29; run male 2.01, 0.54; run female 1.85, 0.49; loop 1499 male 1.56, 0.33. The error is the client's integer truncation after each rotation and scale step, which no smooth transform follows; it is largest on the labels with the longest transform chains (1, 19, 22, 27, 28), a reading of the per-label maxima, not traced. Between 108 and 1,662 vertex positions per clip, counted over all its frames, are exact. Blender's 32-bit armature result is within 6.2e-5 units of the 64-bit fit.

Rules: one clip method per player. The bone bake refuses a mesh with shape keys (Update Player rebuilds without them), and the shape-key bake refuses a rig with any action (unlinking it is not an edit). Both refuse edited players and Edit Mode. The bone bake replaces its own action (marked `rs_bone_clip`), refuses an action it did not make, builds the new action fully before assigning it and removes it on failure. It sets every pose bone to quaternion rotation.

Not done or open: the fitted clip on a body the client did not record, and other frame maps, are untested; a non-uniform scale would leave a larger error, and none of the recorded clips has one. Removing the previous action only when nothing else uses it is an agent choice (issue 20 (`git show 2a78edd:.scratch/osrs-focus/issues/20-rig-and-clip-agent-choices.md`)).

Checked by eye on 2026-11-07 in the user's Blender, beside a shape-key bake of the same walk: the two walk alike, and the evaluated meshes differ by at most 1.6 game units (mean 0.42 to 0.49) over frames 1 to 49, within the fit error above.
