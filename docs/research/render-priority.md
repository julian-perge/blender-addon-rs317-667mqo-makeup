# Render priority: how revision 149 orders faces, and what a Blender Solid-mode preview can do

Researched 2026-11-07 against the unchanged revision-149 gamepack and Blender 5.2 (`/Applications/Blender.app`). Each claim is marked as one of:

- **Evidence**: read in the revision-149 bytecode, a named decompile, or a repo file, or measured by running Blender here.
- **Guess**: reasoned from evidence, or not tested.

Only the 149 jar is the authority. The 2018 client is used for names and is checked against the 149 bytecode for each fact below.

## Sources

| Source | Location | Used for |
| --- | --- | --- |
| Revision-149 gamepack | `<reference work folder>/gamepack-149.jar` | the authority |
| 149 disassembly of `dv`, `ej`, `iz` | `<reference work folder>/osrs149-reference-{dv,ej,iz}.javap` (line numbers below are lines in these files) | face data, draw order, merging |
| 149 disassembly of `hu` | `javap -c -p -cp gamepack-149.jar hu` (offsets below are bytecode offsets) | player assembly |
| 2018 client, named | `<RuneLite May 2018 tree>/runescape-client/src/main/java/Model.java` | names for the same algorithm |

Class roles in 149 (evidence, from the code below): `dv` is the editable model (decoded from the `.dat`, merged, recoloured, lit), `ej` is the lit model that is drawn, `hu` is the player appearance, `iz` is the item definition. `dv.ae(64, 768, -50, -10, -50)` builds an `ej` (`osrs149-reference-dv.javap:6605`, called from `hu.l` at offset 292 and from `hu.au`/`hu.ak`). The 2018 equivalents are `Model` (both roles) and `PlayerComposition`.

## Where the priority lives

- Evidence: `dv.p` is the per-face priority array and `dv.t` is the single model-wide priority. `dv.ae` copies them into the `ej` as `ej.c` and `ej.h` (`osrs149-reference-dv.javap:6807` copies `p` to `ej.c`, `:7519` copies `t` to `ej.h`).
- Evidence: the draw routine `ej.ae(boolean, boolean, boolean, int)` (`osrs149-reference-ej.javap:1927` to `2938`) reads only `ej.c`, never `ej.h`. When `c` is null the faces are drawn by depth alone (offsets 1042 to 1049 branch to the plain far-to-near loop at 1058 to 1171). So a model with one priority for all faces draws as if it had no priorities. The single value matters only when the model is merged with others (see the merge section).
- Evidence: the 2018 client does the same. `Model.method2741` (`Model.java:1098`) tests `this.field1648 == null` (the per-face array) at line 1203 and never reads `field1619` (the single value) while drawing.

## Draw order inside one model

All of this is `ej.ae` in 149. Offsets are bytecode offsets inside the method. The 2018 lines are `Model.java:1098` to `1340`.

1. **Skip and cull.** Evidence: a face whose `t[i]` (the face colour slot) is `-2` is skipped (offsets 104 to 116). A face whose screen-space triangle is not counter-clockwise is culled and never bucketed (cross product test, `ifle` at offset 233). 2018: lines 1117 and 1157. The whole routine returns at once when the model diameter `ap` is 1600 or more (offsets 0 to 10, `return` at 1644); 2018: line 1099.
2. **Depth bucket.** Evidence: the bucket of a face is `(z[a] + z[b] + z[c]) / 3 + radius`, where `z` is the vertex depth after the view rotation (`ab` in 149) and `radius` is `ej.ar` (offsets 254 to 283 and 1187 to 1214). The face index is appended to `ao[bucket]` and the bucket count `ay[bucket]` is incremented (offsets 1263 to 1282). 2018: line 1159, `field1653`, `this.radius`. The integer division means a bucket is one depth unit wide. Faces in one bucket keep ascending face index.
3. **No priorities.** Evidence: when `c` is null, buckets are walked from `diameter - 1` down to 0 (far to near) and each face is drawn in bucket order (offsets 1058 to 1171, draw call `ej.au(int)`). Painter style, one bucket at a time. 2018: lines 1203 to 1214.
4. **With priorities.** Evidence: the buckets are walked far to near once, and each face is appended to a second list by priority: `af[priority][ac[priority]++] = face` (offsets 1251 to 1344). Priorities 0 to 9 also add the face's bucket number to a running sum `ba[priority]`. Priority 10 stores its bucket numbers in `bp[]` and priority 11 in `bi[]`, in the order they were appended. The count arrays are zeroed for 12 entries first (offsets 1123 to 1149). 2018: lines 1216 to 1240.
5. **Draw order of priorities 0 to 9.** Evidence: priorities are drawn in ascending number, 0 first, so a higher priority overpaints a lower one. Inside one priority, faces stay in far-to-near bucket order (step 4 appended them that way). So the order is a painter sort within a priority and a fixed order between priorities 0 to 9, whatever the depth.
6. **Priorities 10 and 11.** Evidence: these two are not drawn at a fixed place. Three average depths are computed from the priority groups: `avg12 = (ba[1] + ba[2]) / (ac[1] + ac[2])` (offsets 1370 to 1401), `avg34 = (ba[3] + ba[4]) / (ac[3] + ac[4])` (1409 to 1432) and `avg68 = (ba[6] + ba[8]) / (ac[6] + ac[8])` (1496 to 1523). Each average is 0 when its groups are empty. While the loop is about to draw priority 0, 3 or 5, any pending 10/11 face whose bucket number is greater (farther) than `avg12`, `avg34` or `avg68` respectively is drawn first. After priority 9, all remaining 10/11 faces are drawn. 2018: lines 1243 to 1340, with the same indices (1 and 2, 3 and 4, 6 and 8) and the same trigger values 0, 3 and 5.
7. **10 before 11.** Evidence: the 10 list is consumed first; when it runs out the loop switches to the 11 list (offsets 1586 to 1594 and 1672 to 1702, `af[11]`). A 10 and an 11 face are therefore never ordered by depth against each other, only against the surrounding groups. 2018: lines 1263 to 1265 and the repeated `var30 != field1661[11]` switch.
8. **Result.** Evidence: the order is a global sort only in the sense that every face goes through one far-to-near pass to fill the lists. The final order is priority first (with 10 and 11 floating by view depth), then depth bucket, then face index. There is no z-buffer in this path; a later face overwrites an earlier one regardless of true 3D depth.

Consequence for the existing glossary (evidence): `GLOSSARY.md` says the client "does not depth-sort faces within a model". That is wrong for the unprioritised path and for the order inside a priority; the client depth-buckets every face. The sentence is true in the sense that depth does not change the order between two different priorities 0 to 9.

## Merged player models

- Evidence: the player model is built in `hu`. `hu.s(byte)` (and `hu.ap()`) allocate a 12-entry `dv[]` (`bipush 12; anewarray dv`, `hu.s` offset 221) and fill it from body kits (`it.s(short)`) and worn items (`iz.o(boolean, byte)` and `iz.k(boolean, byte)`). They merge it with `new dv(dv[], count)` (`hu.s` offset 177, `hu.l` offset 828), recolour with `dv.c(short, short)`, and `hu.l` lights the result once with `dv.ae` (offset 292 or the equivalents in `hu.au`/`hu.ak`). So the drawn body is one model with one `ej.c` array.
- Evidence: `dv(dv[], int)` (`osrs149-reference-dv.javap:19006` to `19736`) keeps per-face priorities from each source. It starts `t = -1` (offset 42), takes `t` from the first source and compares it to each later source's `t` (offsets 209 to 222 and 372 to 380). It allocates the merged `p` array when any source has its own `p`, or when two sources have different single values (flag in local 4, offsets 496 to 503). It then copies each face's priority: the source's `p[j]` when it has one (offsets 832 to 854), and otherwise the source's single `t`. 2018: `Model(Model[], int)` at `Model.java:218` to `312`, flag `var3`, copy at lines 308 to 313.
- Evidence: if every source has no `p` and the same `t`, the merged model has no `p` and falls into the unprioritised path above (steps 3). A cape or belt model with no per-face priorities and a different `t` from the torso still gets a merged `p` array, filled with each source's `t`.
- Evidence: the repo's own merge keeps priorities too: `src/rsps_toolkit/formats/appearance.py:161` to `210` appends `m.render_priorities[i]` for every face. The preview builds one mesh with one shared material (`src/rsps_toolkit/blender/appearance_preview.py:36` to `70`), so the Blender mesh has the same data the client sorts on.
- Guess: which equipment slot index is the cape (the 12-slot array has the cape in a fixed slot). The ordering above does not depend on the slot, because slot only decides the face index inside the merged model, and face index only breaks ties inside one priority and one depth bucket.

Tie rule inside the client (evidence): two faces in the same priority and the same bucket are drawn in ascending face index, so the later face index wins. For a merged player the face index follows the 12-slot order.

## Why Blender Solid mode z-fights (evidence and guess)

- Evidence: the client paints in an order and has no depth test between faces. Blender Solid mode (Workbench) uses a depth test, so face index order and polygon order in the mesh do not change what is visible. Reordering polygons cannot fix it.
- Evidence (measured): Blender 5.2 exposes no depth bias, polygon offset or render priority for Workbench or for materials in Python. A scan of `Material`, `Object`, `View3DShading`, `SpaceView3D` and `MaterialSlot` RNA properties for names containing sort, priority, depth, offset, front, order, transparent or blend found only `Material.blend_method`, `Material.show_transparent_back`, `Material.line_priority` (line art), `Object.show_transparent` and `Object.show_in_front`. None is a per-material depth offset.
- Guess: `Object.show_in_front` draws that object over all others, but it still depth-tests inside itself, and several such objects test against each other, so it cannot encode 12 priorities.
- Guess: z-fight happens where a higher-priority face is nearly coplanar with, or slightly inside, a lower-priority face (belt over torso). It cannot be solved by any offset where the higher-priority face lies behind the lower one in 3D, because the client draws it on top anyway.

## Options for the Solid-mode preview

| Option | What it fixes | Failure cases | Cost |
| --- | --- | --- | --- |
| A. Offset each face along its normal by `priority * epsilon`, as a non-destructive Geometry Nodes modifier on the preview object (split edges, then offset by normal times the priority attribute) | Nearly coplanar and shallow overlaps: belt on torso, trim on a body | Overlap deeper than the largest offset; a high-priority face behind a low-priority one; 10 and 11 (depend on view); faces of equal priority and bucket (face-index tie); split edges open hairline cracks and the offset thickens silhouettes | Small. One modifier, no change to stored data |
| B. Split into one object per priority and use `show_in_front` | Nothing reliable (see guess above) | Fails inside each object and across objects | Medium |
| C. Move the vertices of the preview mesh permanently | Same as A | Same as A, plus the preview mesh no longer matches the model, and a later export from it would write moved vertices | Medium, and risky |
| D. Material slots per priority with depth bias | Nothing, no such property exists in Solid mode (measured above) | Not possible | None |
| E. Per-view repaint: re-sort polygons or draw in an overlay on every redraw | Exact order, for views where the draw callback can disable the depth test | Needs a GPU draw handler in `SpaceView3D`, skips Blender's own selection and shading, and depends on guesses about the handler API in 5.2 | High |
| F. Accept and document the limit | Nothing | Torso and belt flicker; the cape flickers over the back | None |

## Recommendation

Option A, with a documented limit for what it cannot fix. This is a guess: it was not built or run. The reasoning:

- Evidence: priority is a per-face number 0 to 11, and the preview mesh already holds the merged per-face priorities, so the modifier needs only a face attribute copy (`render_priorities`) on the preview mesh.
- Evidence: it is non-destructive, so the stored model and any export are untouched. That matters because option C would put moved vertices where an export could read them.
- Guess: order the offsets by the priority number for 0 to 9, and place 10 and 11 at fixed ranks (for example 10 above 9 and 11 above 10). The real client moves them by view depth (step 6), so a static rank is wrong for views from the far side. Most of the player's 10 and 11 faces are small trim pieces, so this is an acceptable error. Check with a real preview before accepting it.
- Guess: pick the offset in model units so it exceeds the float precision of the Solid depth buffer at the preview's usual zoom but stays well under one model unit per priority step. Tune against the torso and belt pair, then the cape, and expose it as a preview setting. A value that is too small does nothing; one that is too large shows a gap.
- Guess: apply the modifier after the armature modifier so the offset follows the pose.

Failure cases to state in the UI or docs: deep overlaps (a cape that intersects the torso by more than the largest offset), a higher-priority face lying behind a lower one, 10 and 11 from the far side, equal-priority ties, and silhouette growth from the offset. If the cape still fights after tuning, option F for the cape alone is the fallback.

Open check (guess, untested): run option A on the male and female default players and the dragon plate set from `tests/fixtures/AppearanceReference.java`, and count the overlapping face pairs whose priorities differ and whose plane distance is smaller than the offset. That count says how much of the z-fight A can remove before building anything further.
