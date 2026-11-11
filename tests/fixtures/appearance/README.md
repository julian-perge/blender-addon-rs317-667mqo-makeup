# Appearance fixtures

Inputs for the identity-kit and worn-item assembly tests, all from OpenRS2 snapshot 430 (revision 149).

- `230.dat`, `249.dat`, `292.dat`, `151.dat`, `176.dat`, `254.dat`, `181.dat`: the body models of the seven default male kits, copied unchanged from the dumper's `raw-models` output.
- `403.dat`, `456.dat`, `332.dat`, `353.dat`, `419.dat`, `358.dat`: the body models of female kits 45, 56, 61, 67, 70 and 79 respectively, copied unchanged from `<data workspace>/exports/osrs/openrs2-430/dump/dump_index/models/`. None was already in this fixture directory.
- Worn models `219`, `239`, `395`, `413` (1149), `3379`, `164`, `3381`, `3383`, `344` (2653), `3820`, `156`, `3821`, `337` (3140), and `5024`, `5025` (4087), each as `<id>.dat`, copied unchanged from `<data workspace>/exports/osrs/openrs2-430/dump/dump_index/models/`. Model 3381 is shared by both body types.
- `items/1149.dat`, `items/2653.dat`, `items/3140.dat`, `items/4087.dat`: unchanged raw definitions from the same snapshot under `dump/dump_index/items/`. The request listed four distinct IDs; these are the four raw item inputs. No exported item catalog supplies expected fields.
- Item 35 (Excalibur, one worn model `501`, female offset 6) is the only sample with a non-zero offset: raw definition `items/35.dat`, model `501.dat`, both copied unchanged from the same dump. No item in snapshot 430 has both a worn model and retextures, so the retexture path has no client reference and is covered only by unit tests on our own code.
- `kits/<id>.dat`: all 151 raw kit definitions, the files of cache index 2 group 3. `enums/<id>.dat`: the 18 style enums that `STYLE_ENUMS` in `formats/kit_names.py` names, from index 2 group 8. Both were copied unchanged from the cache by `scripts/extract-config-fixtures.py`. `test_js5.py` checks that the kit files match the `raw_kits_sha256` hashes in `reference.json`.
- `KitDefinitions.json`: the dumper `kits` target output (dumper commit `3d19603`), 151 kits.
- `KitStyleEnums.json`: the 18 rows of the `STYLE_ENUMS` enums, copied unchanged from the dumper's `enums/Enums.json` for the same snapshot. That file is RuneLite's `EnumDefinition` output and holds 410 enums.
- `revision149-palette.json`: the colour tables read from client class `hv`, copied from `.scratch/osrs-focus/evidence/` (extracted by `extract_palette.py`).
- `reference.json`: execution of the unchanged revision-149 client, recorded by `../AppearanceReference.java` and `../record_appearance.py`. For both `[0,0,0,0,0]` and `[1,2,3,4,5]`, male cases produce 264 vertices and 476 faces, and female cases produce 260 vertices and 477 faces. The existing male pre-lighting fields match `assemble_body` exactly. Female fields are captured independently for the milestone 2 comparison. These colour sets are placeholders, not chosen defaults.

## Recording and replay

Run from the repository root on macOS with uv, a JDK (recorded with Homebrew OpenJDK 21.0.13) and Apple's C compiler. `JAVA_HOME` selects the JDK; otherwise the runner uses `/usr/libexec/java_home`. No third-party Java or Python dependencies are required. Outputs must be new files.

```bash
uv run tests/fixtures/record_appearance.py \
  --client <reference work folder>/gamepack-149.jar \
  --kits <data workspace>/exports/osrs/openrs2-430/dump/dump_index/configs/identkit \
  --output /private/tmp/appearance149-reference.json
cmp tests/fixtures/appearance/reference.json /private/tmp/appearance149-reference.json
uv run pytest tests/unit
```

`--input` optionally selects the fixture directory. The recorder verifies the gamepack SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`. It records hashes of all 151 raw kits, all 28 model DATs and four raw item DATs, both input JSON files and both recorder sources. Runtime-decoded kit fields must match the entire typed catalog, and runtime `hv` tables must match the palette JSON, before output is written. This checks the raw kit source and the typed inputs independently of production Python.

## Execution boundary

The harness loads the original JAR in an isolated class loader, as the static-model reference does. It supplies decompressed bytes in the client's archive `if.u` file storage, using constructor-free `ig` instances. Kit config group 3, item config group 10 and model file 0 are supplied; missing selected resources fail. It invokes `it.w(if,if)` to bind the kit and model archives and initialize the kit count, then `it.m(int)` for catalog validation. It calls `hu.a(int[],int[],boolean,int,int)` with null equipment, each body type, five zero colour choices, NPC transform -1 and guard -2032808093. The resulting `hu.a` equipment arrays are recorded as `client_default_equipment`; they are not reconstructed from the catalog. The null-equipment guard is required at bytecode offsets 171-185 and throughout the kit scan. The observed male array `[0,0,0,0,274,0,282,292,256,289,298,266]` and female array `[0,0,0,0,312,0,317,326,301,323,335,0]` both match the independently supplied candidates. The runner reports any mismatch without changing either supplied array.

Assembly then calls the same initializer with explicit `equipment` for male cases and `female_equipment` for female cases, followed by both colour sets. Each case records its `female` boolean. The male cases remain first and retain their original captured data. The model archive is sized from the highest supplied model ID, currently 5025 (5026 entries). The palette bindings reproduce `client.aa(int)` without starting the game: `hv.a -> hu.l`, `hv.n -> hu.w`, `hv.j -> gw.s`, `hv.r -> cd.p`.

The actual `hu.l(jg,int,jg,int,byte)` runs with null sequences and byte guard 127. Its own readiness checks, `ij.j(int,byte)` kit lookup, `it.e(byte)` body assembly, `dv(byte[])` model decoding, `dv(dv[],int)` merging and `dv.c(short,short)` recolouring execute unchanged. All 151 kits are decoded before assembly; the client's kit cache remains unchanged and may evict entries normally.

A small JVMTI agent, embedded as C source in the runner and compiled in a temporary directory, observes method entry to `dv.ae(int,int,int,int,int)`. It checks the actual arguments `(64,850,-30,-50,-30)` and serializes the receiver immediately, before the first lighting instruction. It neither replaces methods nor transforms class bytes. The agent uses no debugger socket. After the method returns, the Java harness serializes the lit `ej` returned by `hu.l`. No game startup, disk-cache opening, server connection, Python assembly or Python decoding supplies expected geometry. Compilation products and intermediate captures are temporary.

## Field contract and bytecode evidence

`cases[].before_lighting` is the normalized model compared by the unit test. `client_raw` preserves every declared non-static field captured at lighting entry, and `client_lit` preserves every declared non-static field on the returned `ej`. `lit` provides counts, hidden-face count and the three per-face shade arrays (`ej.g`, `ej.k`, `ej.t`). All twelve cases light successfully with zero hidden faces. The toolkit's `assemble_body` returns an unlit model, so `test_appearance.py` compares the pre-lighting fields, and `test_lighting.py` compares `formats/lighting.light` with the three shade arrays in `lit` for every case. No rendered screenshot is claimed.

These mappings refer to `javap -c -p` on the pinned JAR, not later named source:

| Output | Revision-149 fields / evidence |
| --- | --- |
| Vertex count, face count | `dv.a`, `dv.v`; merge constructor resets them at offsets 1060-1065 and 729-733, then increments as vertices/faces are inserted. |
| Vertices | `dv.j`, `dv.n`, `dv.r` (X, Y, Z); `dv.v(dv,int)` reads them at offsets 43-77 and 32-38 and inserts at 86-159. |
| Faces | `dv.e`, `dv.l`, `dv.s`; merge constructor remaps each corner through `dv.v(dv,int)` at offsets 1089-1134 and 645-667. |
| Colours | `dv.g`, unsigned shorts; `dv.c(short,short)` replaces matching entries at offsets 10-30. |
| Alphas, priorities | `dv.m`, `dv.p`, unsigned bytes; absent alpha expands to zero, absent per-face priority expands from `dv.t`. Merge copies these at offsets 913-929 and 830-854. |
| Face skins, vertex skins | `dv.au`, `dv.ae`; merge copies face labels at offsets 946-970; vertex insertion copies the first position's label at `dv.v(dv,int)` offsets 160-181. |
| Flat shading | `dv.w == 1`; the raw render bytes remain in `client_raw`. |
| Textures | This closure has zero texture records (`dv.c == 0`), null texture IDs (`dv.k`) and null mappings (`dv.u`); normalization emits null per-face references and an empty triangle list. |
| Lit geometry and shades | `dv.ae` assigns `ej.v/w` counts at offsets 883-889 and 1730-1736; `ej.g/k/t` are the three shade arrays. |

For the male cases, the merge constructor allocates coordinate and vertex-skin arrays to the sum of input vertex counts (294), but uses only the first `dv.a` entries (264). Normalized arrays are trimmed to that active count; `client_raw` retains the unused capacity. This is not a vertex-count disagreement.

`hu.l` calls the merge at offsets 820-831, primary recolouring at 330-355, secondary recolouring at 836-858 and lighting at 279-292. Each colour slot executes its primary and secondary passes before advancing to the next slot. Kit decoding stores the category multiplied by -1924753457 (`it.r(fe,int,int)`; the offsets 287-296 were read in the uncalled `it.c(fe,int)`, which has the same multiplier); catalog validation accounts for Java's 32-bit wraparound. Palette provenance and snapshot/client pairing limits remain those in the [appearance evidence](../../../.scratch/osrs-focus/evidence/charactercreator-cache430.md) and [static-reference README](../models/osrs149/README.md). Revision identity is established; exact historical snapshot/gamepack pairing remains unverified.

## Worn-item captures

The four original kit cases remain first, with every existing field unchanged and a full `equipment` array appended. They have no `outfit` field. Eight new cases carry `outfit` values `dragon_plate` or `dragon_chain`, each with male/female bodies and both colour sets. Slot 0 is 1661, slot 7 is 4599, and slot 4 is 3165 for `dragon_plate` or 3652 for `dragon_chain`. All other slots retain the body type's default kits. The plate label follows the requested case name; item 2653 is a Zamorak platebody. No hair or arm slots are cleared, so these are explicit test outfits, not game-accurate slot-clearing claims.

| Outfit | Body | Vertices | Faces |
| --- | --- | ---: | ---: |
| dragon_plate | male | 512 | 975 |
| dragon_plate | female | 520 | 977 |
| dragon_chain | male | 829 | 1316 |
| dragon_chain | female | 714 | 1133 |

Counts are identical for the two colour sets. All twelve cases have zero hidden faces after lighting, and all worn models are untextured.

The harness binds raw item storage to `eb.e` and model storage to `iz.l`, then invokes `cu.j(id,-1827004326)`. The unchanged client reads group 10 and runs `iz.r(fe,1882926117)` / `iz.v(fe,int,int)` itself. Its normal item lookup and worn-model paths then execute inside `hu.l`. The top-level `items` object includes every non-static decoded field in `client_raw`, normalized unsigned recolour/retexture pairs, and per-body logical `model_ids`, positive Y `offset`, `before_player_merge` counts and observed `merge_counts`. Model IDs retain -1 sentinels. Integer field multipliers and binding evidence are in section 9 of the [appearance evidence](../../../.scratch/osrs-focus/evidence/charactercreator-cache430.md).

| Item | Male worn models | Female worn models | Recolours (unsigned find -> replace) | Male counts (vertices, faces) | Female counts |
| --- | --- | --- | --- | --- | --- |
| 1149 | 219, 239 | 395, 413 | 61 -> 924 | 72, 94 | 78, 110 |
| 2653 | 3379, 164, 3381 | 3383, 344, 3381 | 61 -> 36133; 41 -> 37270; 24 -> 937 | 190, 311 | 196, 315 |
| 3140 | 3820, 156 | 3821, 337 | 61 -> 926 | 521, 652 | 404, 471 |
| 4087 | 5024 | 5025 | none | 112, 216 | 112, 216 |

Every selected offset is zero, every retexture list is empty, and no selected worn model is null. Item 2653 demonstrably takes the three-model merge path for both male and female bodies: the JVMTI observer records argument 3 at entry to `dv(dv[],int)` with immediate caller `iz.k`. Items 1149 and 3140 record argument 2; item 4087 performs no item-level merge. These observations are captured during direct calls to `iz.k(female,(byte)-54)`, before running the complete player cases. The observer disables method-entry events during its Java callbacks and does not alter client code or data.
