# Fork a candidate or keep this repo: research

Researched 2026-11-05 against Blender 5.2.3 LTS (`/Applications/Blender.app`, bundled Python 3.13.13, NumPy 2.3.4) and local clones of the three candidates. Each claim is marked as one of:

- **Measured**: a command or test run here, or a file and line read here.
- **Inference**: reasoned from measured facts, not run on its own.
- **Guess**: no direct evidence.

File and line references to a candidate are relative to its clone: `<clone of tamateea/RuneBlend>`, `<clone of stone-temple-pilot/ob2blender>` or `<clone of ScreteMonge/Blender-Addons>`. Experiments ran headless with `--factory-startup` on scratch copies, and all three clones stayed clean (`git status` prints nothing). Not one line here is legal advice.

## Answer

Keep this repo. A fork would discard the parts of the candidates that exist, because every one of them is weaker than the code that would replace it, and it would force GPL-3.0 on the whole project for about 3,100 lines of panel code in one file.

Lift nothing as code. Reimplement a few ideas from ob2blender, starting with the one that exposes a real defect here: deleting one vertex before export silently moved 40 of the 58 texture triangles of model 5452, with no warning (see "A defect this research found").

There is no licence blocker for that plan, since ideas are not copied code. Two licence gaps exist regardless of the candidates; see "Licences".

## Candidates at a glance

Measured, from the source and `gh` on 2026-11-05.

| | RuneBlend | ob2blender | Blender-Addons (ScreteMonge) |
| --- | --- | --- | --- |
| Reads | `.dat`: old format, new format, two later variants, RS3 (`runescape_mesh.py:67` to `78`) | old format only, `.ob2` by file filter (`runescape_mesh.py:53` to `61`, `__init__.py:49`) | JSON from the Creator's Kit (`CK_to_Blender_addon.py:27`, `35`) |
| Writes | nothing | old format (`export_model.py:61`) | JSON for the Creator's Kit (`Blender_to_CK_addon.py:54`) |
| Skins | vertex groups with weight `label / 100` (`import_model.py:77`), no face skins | integer attributes `VSKIN`, `TSKIN` (`import_model.py:99`, `119`) | none |
| Priorities | attribute `pri`, import only (`import_model.py:120`) | attribute `PRI`, model-wide and per face (`import_model.py:103` to `112`) | face maps, only before Blender 4.0 (`CK_to_Blender_addon.py:105`, `Blender_to_CK_addon.py:159`) |
| Textures | fixed folder, linked alpha (`materials.py:115`, `141`) | fixed folder, colour only with no alpha link (`import_model.py:199`, `203`), `PMN` face attribute | none |
| Face alpha | a material per alpha, which replaces the texture (`import_model.py:89` to `96`) | attribute `ALPHA`, invisible in the viewport (`import_model.py:122` to `128`) | Principled Alpha with `BLEND` (`CK_to_Blender_addon.py:166` to `169`) |
| Animation | skeletal format only, unfinished (`import_animation.py`, `import_skeleton.py`; readme lines 19 and 27) | none | baked vertex keyframes on import only (`CK_to_Blender_addon.py:185` to `193`) |
| Targets | Blender 3.4.1 (`__init__.py:7`) | Blender 4.5.2 (`__init__.py:13`) | Blender 3.0 (`CK_to_Blender_addon.py:7`) |
| Tests | none | none | none |
| Commits | 17, from 2023-08-31 to 2023-09-08, one author | 33, from 2025-09-18 to 2026-09-26; last code 2026-07-09, one author | 25, from 2024-05-28 to 2026-07-02; last code 2024-06-13 |
| Issues and PRs | no issues; PR 2 (Blender 4.0 fix) open and unanswered since 2023-12-10 | none ever | issue 2 closed, PR 1 merged |
| Forks | 4; Psycrow101's is 1 commit ahead | 4; none is ahead | 1 |
| Licence | GPL-3.0 | GPL-3.0 | none |

## RuneBlend on Blender 5.2

Does not run unmodified. Measured:

- `materials.py:38` asks for the Principled input `Specular`, which 5.2 does not have. The first import of each material kind raises `KeyError` and leaves a material named `palette`, `palette_alpha_<n>` or `text_<n>` with no links; later imports find that name and reuse it (`materials.py:14` to `20`). In a run over 100 models, 3 raised and 97 "succeeded" this way. That the 97 got broken materials is inference from the code order.
- With that one input renamed to `Specular IOR Level` in a scratch copy, 7,420 of the 7,456 revision 317 models import. The other 36 raise `IndexError`. Exactly 36 models start with byte 1, and `runescape_mesh.py:70` sends such a file to `decode_rs3`, so this is the cause by matching count and code path (evidence); the two lists of 36 were not compared file by file.
- `Action.fcurves` does not exist on 5.2, and `import_animation.py:92` calls `action.fcurves.new`. Animation import therefore fails on 5.2 (inference; not run, as there is no skeletal fixture here).
- `import_model.py:55` keeps faces that repeat a vertex in the mesh: 7,188 of them across the models imported. [ADR 0005](../adr/0005-faces-that-repeat-a-vertex-stay-out-of-the-mesh.md) records that such faces freeze Edit Mode. Edit Mode was not entered in this run.

Code health: a port of client decoders with no tests or export; `__init__.py:29` assigns `StringProperty` without an annotation; `import_animation.py:193` uses `i is 0`; `import_animation.py:130` to `131` records alpha transforms and drops them. No commit since 2023-09-08 (measured).

## ob2blender on Blender 5.2

Registers on 5.2, then fails or loses data on real models. The harness called the add-on's own `read_mesh`, `create_blender_mesh` and `export_to_ob2` on all 7,456 revision 317 models and compared the result, decoded by `rsps_toolkit.formats`, with the original. Its panels were not drawn, since the run is headless.

| Result (measured) | Unmodified | `int8` changed to `int32` in a scratch copy |
| --- | --- | --- |
| Models imported and exported | 6,479 | 7,451 |
| Failed on import, `OverflowError` | 972 | 0 |
| Failed on export, `IndexError` | 5 | 5 |
| Decoded equal to the original | 3,869 | 4,342 (58.2%) |
| Equal once lost faces and corner rotation are ignored | 5,090 | 5,748 (77.1%) |
| Models that lost faces | 967 | 1,148 |
| Faces lost | 6,181 | 7,378 |
| Faces with a changed colour or texture | 97,022 | 126,040 of 1,060,006 (1,536 models) |
| Faces with reversed winding | 756 | 1,131 (240 models) |

The same run with this repo's `scripts/round-trip-dump.py`, on the same day and dump: 7,456 of 7,456 equal, none failed (measured). Vertices, alpha, priorities, face skins, vertex skins and flat shading all survived the patched ob2blender run, as did each textured face's texture triangle.

Causes:

- **The `OverflowError`** comes from `import_model.py:96` and `98`: `np.int8` arrays are assigned labels above 127, which NumPy 2 refuses (evidence: the traceback). On Blender 4.5, whose NumPy this research did not check, such a value wrapping around and `& 0xFF` at export restoring it is a guess, so the right column is an estimate of its behaviour on its target version.
- **The lost faces** are deliberate: `import_model.py:43` drops every face that repeats a vertex, and 1,148 is the same model count this repo keeps aside.
- **The colour changes** come from `export_model.py:375` to `379`, which rebuilds the face colour from the material's RGB (evidence: applying its formula to all 65,536 values changes 9,842, of which 8,064 have saturation 0 and so lose their hue; on this dump's untextured faces it predicts 126,790 of 1,036,423, against the 126,040 measured).
- **The reversed winding** comes from `export_model.py:305` to `326`, which chooses a strip opcode by set membership and ignores corner order (evidence from reading the code; not isolated by a separate test). In-game, a reversed face is hidden from the side it should show.
- **The 5 export failures** are models with no vertices (inference: `export_model.py:230` reads `vertices[0]`, and exactly 5 models have none).

Other measured points from the source:

- Export triangulates and changes the user's mesh in place (`export_model.py:49` to `52`), swaps axes in place and back (`103` to `113`), and ignores modifiers and the world matrix (`54`).
- Imported colours use `colorsys` with no band offsets, brightness curve or sRGB conversion (`import_model.py:165` to `169`). Before colour management they differ from the client's palette at 0.8 by 14.8 of 255 per channel, averaged over the 400 commonest colours (measured). This is the same kind of error as the old add-on's colour conversion, which the refactor fixed ([model-formats.md](model-formats.md)).
- There are no presets, drop models or brightness setting. `__init__.py` is one file of 3,120 lines, and the Python files hold 83 lines with `print(` or `except Exception`, some of them commented out.
- `readme.md:84` to `86` lists mirrored models, janky RGB15 conversion and lost textures as known issues.
- Development is active but solo, and no outside report has reached the tracker.

## Blender-Addons on Blender 5.2

Runs on a small synthetic JSON model (one triangle, two frames): both import paths and the export finish, and the import creates an action (measured). It is not a `.dat` tool: it exchanges JSON with the RuneLite Creator's Kit plugin and never touches a cache file. On Blender 4.0 and later, priorities are dropped both ways (`CK_to_Blender_addon.py:105`, `Blender_to_CK_addon.py:159`), and the export wrote priority 0 and the last animated frame's positions (measured). `CK_to_Blender_addon.py:195` calls `me.validate()`, which [ADR 0005](../adr/0005-faces-that-repeat-a-vertex-stay-out-of-the-mesh.md) rules out because it deletes faces that repeat a vertex.

## What this repo has

Measured on the working tree on 2026-11-05: `uv run pytest` 223 passed; `scripts/test-blender.sh` 175 passed; the dump round trip above, with 1,148 models having set-aside faces entering Edit Mode without a freeze. Expected values come from RuneLite and the clients as `CODING_STANDARDS.md` requires. No candidate has a test, a reference file or a round-trip check.

## Would a fork beat continuing

No.

**Porting this repo into a fork.** Every model path of a fork gets replaced: `formats/`, `mesh.py`, `rs_layers.py`, `face_materials.py` and `export_model.py` supersede its decoder, importer and exporter, because the candidate's versions cause the losses above. What would remain of ob2blender is its panel code, and that is written against its attributes (`VSKIN`, `PRI`, `TSKIN`, `ALPHA`, and `PMN` as a float vector per face), not this repo's `RSPRI`, `RSTSKIN`, `VSKIN1:` to `VSKIN3:` and texture triangle table, which saved .blend files read and which `CLAUDE.md` says to keep stable. A rewrite of each operator would follow. RuneBlend has no export to keep, and its materials and animation need rewriting for 5.2. Blender-Addons has a different purpose.

**Taking features into this repo.** The items below are each a small operator on `texture_triangles.py` or `rs_layers.py`. An estimate of 50 to 200 lines plus tests per item is a guess.

**What a fork would cost.** The whole project becomes GPL-3.0 on publication, and the fork's history and name point at a project with a different data model. **What it would gain.** ob2blender's audience on the Lost City forum and 10 stars against 2; its tracker shows no outside reports, so the audience's size is unmeasured. Support for Lost City's `.ob2` needs no fork: `runescape_mesh.py:61` reads the same 18-byte footer as this repo's old format, so an `.ob2` file looks like a plain old-format model (inference; no `.ob2` file was decoded). This repo's importer filters on `*.dat` (`blender/import_model.py:25`). Whether Lost City is in scope is the user's call.

## Licences

Measured, from the files.

| Repo | File | Says |
| --- | --- | --- |
| RuneBlend | `license.txt` (added in `5a39675`) | GPL version 3 text. No `.py` file has a header, and nothing says "or later". |
| ob2blender | `LICENSE` (initial commit `666bacd`) | GPL version 3 text. `runescape_mesh.py:1` says "all credit goes to Tamatea", `readme.md:15` names RuneBlend as its base. Nothing says "or later". |
| Blender-Addons | none | No licence file; a search for licence, copyright and GPL finds nothing in any file. |
| This repo, working tree | `LICENSE`, `pyproject.toml:5`, `blender_manifest.toml:12` | All three say MIT and agree. `LICENSE` names Rooseelvis 2025 and Julian Perge 2026. |
| Upstream | `README.md:250` | "License: MIT", followed by "RSPS-free, share with cred." It has no `LICENSE` file. |

What follows:

- **GitHub's "no licence" for this repo has a plain reason.** `LICENSE` was added in `6b8a07b` on `refactor/blender-extension`, and that branch is not pushed: `origin` has only `main`, whose tree holds no licence file (measured). The MIT text itself came from this fork; the upstream author's only statement is the README line. So the MIT grant rests on one README sentence (inference).
- **The built extension omits the notice.** `dist/rsps_toolkit-7.7.0.zip` holds 27 files and no licence file, since `LICENSE` sits outside `src/rsps_toolkit/` (measured). MIT asks that the notice go with copies, so this needs fixing before the zip is shared, by putting a copy inside the package.
- **The Blender Extensions Platform would refuse MIT.** The 5.2 manual's licence page says "For add-ons, the required license is GNU General Public License v3.0 or later". blender.org's licence page says published scripts must be "shared under a GPL compliant license". MIT is GPL-compatible (general knowledge, unverified here), so this repo as MIT breaks only the platform's listing rule. Whether a listing is wanted is the user's call.
- **GPL code lifted into this repo.** Copying any candidate's GPL code means distributing the combined add-on under GPL-3.0, with source; the existing MIT notices stay and the code stays usable under GPL, but the project as shipped stops being MIT. Private use with nothing published triggers no duty. Since neither GPL candidate says "or later", GPL-3.0-only is the safe reading, and without their authors' consent that code could not be listed on the platform either (inference).
- **Blender-Addons has no licence, so no permission to copy.** Default copyright applies, and PR 1 adds a second contributor. Learn from it only.
- **Facts and ideas are free in all cases.** The file format, client behaviour, and a technique such as a vertex ID layer can be reimplemented from the idea, without keeping the code open while writing.
- **Textures and models.** RuneBlend ships 120 PNGs including `palette.png`, ob2blender 60, and this repo tracks `texture_dump.zip` and 40 files under `tests/fixtures/models/`. None of those licences covers Jagex's art, and the manual requires CC0 for assets in add-ons. This repo's build leaves textures out.
- **A provenance question inside this repo.** `blender/importer_667.py`, from upstream, shares 10 of its 431 stripped lines with RuneBlend's `runescape_mesh.py`, and the distinctive name `texture_coordinate_indices_offset` (line 363; RuneBlend line 616). Its other names differ (`triangle_` against `face_`), and the section order comes from the format. Copying from RuneBlend is not shown; a shared ancestor in deobfuscated client code is a guess. Rewriting that importer, as the parked 667 work does, removes the question.

## A defect this research found

Checking whether ob2blender's stable vertex IDs fill a real gap turned up this. Measured on model 5452: delete one vertex that no texture triangle uses (vertex 14) with `bmesh.ops.delete`, then call `model_files`. Export succeeds, the model keeps 58 texture triangles, only 18 of them still sit on their original positions, compared index by index, and `unfitted_faces` reports 0, so nothing warns. Deleting renumbers later vertices, and only the weighter's mirror goes through `texture_triangles.delete_vertices` to renumber them (`texture_triangles.py:169`). The set-aside faces already handle this case by recording positions (`mesh.py:80` to `93`); texture triangles do not. `CODING_STANDARDS.md` ("Stored data survives the user's edits") calls this a finding. The test used a script rather than Edit Mode, which is the same operation on the mesh (inference). The export warning of [ADR 0009](../adr/0009-export-warns-about-moved-texture-triangles.md) came out of it.

## What to reimplement

Every item is an idea from ob2blender or RuneBlend and is GPL there: reimplement, do not copy. Each gap was checked by searching `src/` and the project's handoff notes at the time.

| # | Source | Short quote | Gap here | Licence |
| --- | --- | --- | --- | --- |
| 1 | ob2blender `__init__.py:392` to `434` (`_ensure_pmn_stable_ids`, `_remap_mesh_pmn_indices_from_stable_ids`) | `v[stable_layer] = int(v.index)` | The defect above. A vertex integer layer follows vertices through edits, so triangles can be renumbered from it. | Idea only. A simpler alternative here: record positions and warn or refuse, as set-aside faces do. |
| 2 | ob2blender `__init__.py:2093` to `2105` (`generate_new`) | `new_vert = bm.verts.new(snapped)` | `texture_triangles.fit` (`:94`) snaps P, M and N to the nearest vertex, so a UV edit moves when it is fitted. New vertices at the solved positions give an exact fit. | Idea only. It adds vertices to exported models, so ask the user first. |
| 3 | ob2blender `__init__.py:2271` (`OB2_OT_select_labeled`) | `"Select items whose label matches the given label"` | Painters and weighter apply values; nothing selects by priority, face skin or vertex skin. | Idea only. |
| 4 | ob2blender `__init__.py:1430`, `1285`, `1719` | `"Select all faces whose PMN exactly matches..."` | Nothing selects a texture triangle's faces or vertices, or swaps P, M, N on faces. | Idea only. |
| 5 | ob2blender `__init__.py:1519` | `"Assign first/second/third selected vertices to P/M/N"` | Partial: Apply takes three vertices ([ADR 0008](../adr/0008-texture-triangles-are-what-export-writes.md)), but by nearest projected corner, not click order. | Idea only. |
| 6 | ob2blender `__init__.py:1572` | `"Pair adjacent selected triangles as quads..."` | Apply gives one triangle per selection, so a textured wall of many quads needs one Apply per quad. Lowest priority of these. | Idea only. |
| 7 | RuneBlend `runescape_mesh.py:535` to `538`, `1178` to `1182` | `has_extended_vertex_groups = (face_type_flag & 0x10) == 16` | Parked 667 work: `model-formats.md` lists flag bits 2 and 4 as unconfirmed and does not mention 0x10 or 0x20. RuneBlend's RS3 path names 2 "particles" and 4 "billboards"; that those meanings carry to 667's format is a guess. | Learn only, then confirm against `dv.java`. |

On item 7, measured: RuneBlend's decoder ran on 6,002 sampled 667 models without an exception on 5,745 (95.7%), including 899 of 912 with flag bits 1 and 8 set, where issue 23 (`git show 2a78edd:.scratch/osrs-focus/issues/23-667-new-format-models.md`) says RuneLite always crashes, and including models 5 and 396. That is no proof of correct values: `runescape_mesh.py:587` tests `face_type_flag == 1`, so with bits 1 and 8 both set it skips no face type section. So its survival on those models and misread data can go together (inference). It is a lead for why RuneLite crashes, nothing more.

## Examined, and not worth taking

- **Animation import (RuneBlend).** The gap here is real: nothing in `src/` reads animation frames, though animation was not among the project's goals at the time either. RuneBlend does not fill it. Its reader handles the later skeletal format, with bones and curves (`import_animation.py:9` to `18`), and `base.py:6` to `8` says: "most of it is utilized for runescape legacy animation system which we are not supporting in blender yet". Old-format models carry labels and no skeleton (`GLOSSARY.md`), so frames for 317 would come from the clients (`Frames.java`, `Frame.java`, `model-formats.md`). It uses `action.fcurves`, which 5.2 lacks, and its readme calls skeletons mostly not okay.
- **Baked vertex keyframes (Blender-Addons, `CK_to_Blender_addon.py:185` to `193`).** It works on 5.2, but it needs frames someone else computed in the Creator's Kit, and there is no licence. If animation preview is ever wanted, keying `co` per vertex is a well-known technique that needs no lifting.
- **Palette texture (RuneBlend `import_model.py:154`, `materials.py:12`).** One material with a 128 by 512 palette and UVs instead of a material per colour. It breaks here because the UV layer previews texture triangles and export reads game values from materials. It also fixes one brightness.
- **Alpha.** Materials here already use the client's `(256 - alpha) / 256` (`face_materials.py:105`). RuneBlend uses `1 - alpha / 255` and loses the texture on textured faces with alpha; ob2blender shows no alpha at all.
- **Colour conversion and RGB15 tools (ob2blender `__init__.py:2703` to `2722`).** They are the lossy formula measured above. [ADR 0006](../adr/0006-export-writes-the-game-values-stored-at-import.md) names the nearest palette colour as the fix if recolouring is needed.
- **UV and triangle maths (ob2blender `pmn_uv.py`).** This repo already has `formats/texture_uvs.py`, tested against RuneLite.
- **Dropping faces that repeat a vertex (ob2blender `import_model.py:43`).** The set-aside faces here keep them.
- **Priority and stacked faces.** No candidate has any logic for stacked, coplanar or overlapping faces. A search for those words finds only `ob2blender/readme.md:37` on double-sided faces.

## The open decision: stacked textured faces under DITHERED

The candidates' choices bear on this only a little; rendering this repo's own models bears on it more.

### What the candidates chose

- **Both GPL candidates cull every material**: `RuneBlend/materials.py:40`, `85`, `132`, `ob2blender/import_model.py:207`, `247`, and ob2blender also sets the view's culling (`:86` to `87`). `RuneBlend/readme.md:26` says "Back face culling is applied by default". ob2blender's readme says to tick culling to see double-sided faces (`readme.md:37`). The client agrees on the path read: `ZKARKDQW.java:4455` draws a face only when it faces the camera. Other draw paths were not read.
- **None of them chose a render method for this.** They set `blend_method = 'CLIP'`, which 5.2 maps to `DITHERED` (measured: `CLIP`, `HASHED` and `OPAQUE` all give `DITHERED`, `BLEND` gives `BLENDED`).
- **RuneBlend links texture alpha and defaults to Material Preview** (`materials.py:141`, `import_model.py:109`), so it has the settings that give black (inference; not rendered through RuneBlend).
- **ob2blender does not link alpha and defaults to Solid view** (`import_model.py:199`, `85`), which is why nothing black is on show for its users (guess). Unlinking alpha here does stop the black on 5452, but the top texture's transparent texels turn opaque and hide the leaves, so the canopy goes dark: the wrong picture. It is no fix.

### What the renders show

EEVEE renders, no Material Preview, one angle at 256 pixels, of all 105 models whose textured faces share corners with another face, plus 60 random others. "Black" is the share of visible pixels below 3% brightness; the measure counts real colour 0 faces too, so the difference between settings is what matters. Settings: DITHERED (current), DITHERED plus culling, BLENDED plus culling.

| Stack kind | Models | More black under DITHERED than BLENDED + culling (over 0.5 points) | Culling alone clears it |
| --- | --- | --- | --- |
| Two different textures | 9 | 4 (1650, 1693, 5452, 5457: 42 to 50%) | none |
| Same texture, 2 or more faces | 67 | 11 (2010, 2012, 2059, 2109, 2020, 1866, 2016, 4293 and smaller) | 2059, 2109 |
| Texture on a coloured face | 29 | 0 | not needed |
| Not stacked (sample) | 60 | 0 | not needed |

- **The first stack rule was wrong; [ADR 0011](../adr/0011-stacked-textured-faces-blend-and-cull.md) has the corrected one.** It said 42 models and 2,104 faces stacked on "another texture". Those numbers came from a rule that counted any textured face stacked on a face of another kind, by corner positions, so it mixed two-texture stacks with textures on colours. This research counted by the faces' own corners and got 38 models and 2,094 faces for that rule, and 29 of those 38 are textures on colours, which show no black here; 6282, listed as the worst, has a single texture and no black. Meanwhile same-texture stacks, outside that rule, do go black (2010 at 14%). The rule matching the measurements is: two or more textured faces on the same corners, which is 76 models by vertex index, or 82 by corner positions (measured; the two counts differ because some stacked faces use separate vertices at the same positions, a guess).
- **Why culling alone fails.** 186 of the 190 two-texture stacks face the same way (measured); only model 3449's 4 are back to back. So culling removes neither face, and 5452 stays at 44% black. This turns an earlier guess into evidence for those stacks: the guess was that culling, the fix in Blender issue 136453, fails here because that issue's stacked faces were back to back while ours face the same way. 2059 and 2109 clear with culling, so their stacks are back to back (inference).
- **BLENDED without culling** shows see-through patches: 17.5% of pixels differ from BLENDED plus culling on two-texture models, on average (measured), which agrees with the earlier finding.
- **BLENDED everywhere breaks solid objects.** On the 60 non-stacked models, 5 differ by over 5% between culled DITHERED and culled BLENDED. Viewed: table 1227, box 3869 and bookcase 4285 show inner faces drawn over outer ones, and 1806 shows its base and water layered wrongly. So option 3 (both on all textured) is out on this evidence.
- **Stacked models pay this cost too.** 1571 loses its black patches under BLENDED but gains visible wrong layering. Five models of the two-texture kind (2007, 2008, 2021, 3449, 5775) do not go black at this angle and gain nothing from a switch. So the switch is a trade on each model where black is small.
- **Culling on all textured** changes 4.5% of pixels on average on non-stacked models, and up to 49% (4441, 6907, walls and steps whose back sides vanish). This matches the client, but it stops a user seeing a wall from behind while editing. It does not fix the black.

### Recommendation

Use BLENDED plus culling only on textured materials with two or more textured faces on the same corners, and leave everything else as it is. That is option 1 with a corrected rule. Culling on all other textured materials is a separate preference with no bearing on black. It is the user's decision, and export ignores all of it.

Two things to handle if that is chosen:

- `aether_materials.py:161` and `268` set `blend_method`, and `"OPAQUE"` resets a material to DITHERED on 5.2, so using that panel brings the black back (inference from the measured mapping; not run through the panel).
- `upgrade_materials.py:48` reads `BLENDED` as a sign of a legacy alpha. Materials with game values are not upgraded, so imports are safe (from the code), but a test belongs with the change.

One untested lead: on 5452, BLENDED plus culling on texture 8 alone gives 0.0% black, and on texture 17 alone 3.1% (measured), which leaves one layer solid. Those renders were measured but not viewed, and this cannot help same-texture stacks, which share one material.

## Guesses and gaps

- The ob2blender `int32` column stands in for its behaviour on Blender 4.5, which was not run.
- RuneBlend's skeleton and animation code was read, not run; there is no skeletal fixture here.
- ob2blender's and RuneBlend's panels were not exercised, since headless runs draw no UI.
- All renders are one or two camera angles, EEVEE render rather than Material Preview, and low resolution; the black share is a threshold, not a visual judgement, except for the models named as viewed.
- BLENDED layer order was not compared with the client's priority order; 26 of the 190 two-texture stacks have differing priorities (measured).
- The porting effort per feature is a guess.
- The licence reading is a developer's, not a lawyer's.
