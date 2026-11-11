# Deobfuscating the revision-149 client: is it worth it?

Researched 2026-11-07 against `gamepack-149.jar` (SHA-256 `19c492cc...cbdd`), the May 2018 RuneLite tree `<RuneLite May 2018 tree>` (client revision 170, [appearance evidence](../../.scratch/osrs-focus/evidence/charactercreator-cache430.md) section 1) and `cache-1.13.6-sources.jar`. Each claim is **Evidence** (read or measured, source named) or **Guess**. Nothing was installed. Scripts and outputs (`all149.txt` is `javap -p -c` of all 296 classes) are in `<scratch folder 2026-11-07-deobfuscation-value>/`.

## 1. How recent work used 2018 names

Evidence: the 2018 `@ObfuscatedName` values are revision-170 names (`ModelData` is `do`); other mapping files cover revisions 114 and 130 only (`deobfuscator/src/test/resources/`). Every 149 pairing was made by hand.

Verified by running unchanged 149 classes (Evidence):

- `dv(byte[])` and `dv.ae` lighting on all 33,196 models (`Osrs149Reference.java`; see [the OSRS cache workflow](../osrs-cache-workflow.md#evidence)).
- `hu.a`, `hu.l`, `cu.j`, `iz.k` and the `hv` palette in 16 appearance cases; all 151 client-decoded kits equal the dumper catalog ([appearance README](../../tests/fixtures/appearance/README.md)).
- `hu.l` with the walk clip, including frame, frame map and `cd.m` loading (`PoseReference.java`).

Read in 149 bytecode, not run (Evidence): own-face mapping of non-kind-0 records, render type 2 hiding, the alpha-254 overflow, worn-item opcodes and assembly, female kit categories, the slot 3 and 5 override in `hu.l`, `ej.g` arithmetic, draw order `ej.ae` ([render-priority](render-priority.md)), merge priorities.

Taken from the 2018 source only (Evidence that 149 was not checked):

- The player's sequence comes from the server appearance block; "the 149 reader was not located" ([osrs-149-animation](osrs-149-animation.md) section 4).
- Sequence opcodes 2 to 13 (loop offset, interleave, held items, priorities). `PoseReference` sets only `jg.e` on an `Unsafe`-allocated `jg`, so the 149 sequence decoder never ran.
- Texture sampling (`Graphics3D.rasterTextureAffineLine` in `face_materials.py`, `mesh.py`, `texture_uvs.py`) and the own-corner triangle rule (`ModelData.java:1032` in `formats/model.py`).
- The structure of `formats/lighting.py` (its output is checked against 149) and equipment slot names (`KitType`).
- The class map in osrs-149-animation.md, labelled "partly guess".

Two slips (Evidence), both fixed since: the notes said kind 1 to 3 records are unchecked in 149, but [reference-source-findings](../../.scratch/osrs-focus/evidence/reference-source-findings.md) reads them in `dv.ae`/`ej.au`. The appearance README cites kit decoding at `it.c(fe,int)`, which has no call sites; the live decoder is `it.r(fe,int,int)`. Both use the same multiplier, so no result changes.

## 2. 149 against 2018, measured

| 149 / 2018 | Instance field types | Called instance methods / 2018 methods | Decoder |
| --- | --- | --- | --- |
| `dv` / ModelData | 42 = 42 | 19 / 19 | new and old format: same reader-call counts |
| `ej` / Model | 34 = 34 | 24 / 24 | |
| `hu` / PlayerComposition | 6 = 6 | 9 / 9 | |
| `jg` / Sequence | 14 = 14 | 8 / 8 | opcodes 1 to 13, same reads |
| `et`, `eg`, `eb` / Frames, Frame, FrameMap | 1, 7, 4 equal | 1 / 1 | same reads, scale default 128 |
| `iz` / ItemComposition | 47 = 47 | 16 / 16 | 38 opcodes plus 30-34, 35-39, 100-109, same reads |
| `it` / KitDefinition | 8 = 8 | 6 / 6 | 1, 2, 3, 40, 41, 60-69 |
| `ep` / Graphics3D | static only | 24 / 24 (static) | |

Evidence. Field types are the multiset of declared types, game classes collapsed. "Called" counts methods (name and descriptor) invoked somewhere in the jar. `dv.ae` and `ModelData.light` use the same literals. Static member counts differ and were left out (Guess: the obfuscator moves them).

Not visible this way (Evidence): constant tables. The one known real difference, palette row 4 (11 entries in 149, 12 in 170), is a static array literal. The jar also carries uncalled decoys (`iz.am/aq/aw/aa`, `jg.o/x/h`, `it.c`, `dv.cu/cy/cn`).

Guess, well supported: for these ten classes the 2018 source is the 149 code apart from names, guards, multipliers and constant tables.

## 3. Cache side

Evidence: the 1.13.6 loaders handle every opcode the live 149 decoders test, for items, kits, sequences, NPCs (`ip.r`) and objects (`im.r`; no opcode 60, so `LegacyObjectLoader` matters for 2013 only). The hazard is revision flags: `SequenceLoader` defaults `rev226` and `rev220FrameSounds` to true, which misreads 149 opcode 13; `LegacyAnimationData.java:180` turns both off. Nothing in the cache needs deobfuscating. The gap is client-run coverage: 5 of 21,392 items and no sequences went through the 149 decoders.

## 4. Cost and tools

Measured here (Evidence):

- Vineflower 1.12.0 (in the Gradle cache) decompiled the ten classes in 5 s, fully structured, including `ej.g` and `jg.r`. Guards and multipliers stay inline.
- CFR 0.152 (Homebrew) took 214 s for the jar and left 1,518 methods unstructured, among them `ej.ae`, `ej.g`, `dv.ae`, `dv.j`, `hu.l` and `jg.r`.
- Installed: JDKs 21, 25, 26 and 27, Maven 3.10, Ghidra 12.2. Absent: JDK 8, Procyon, Fernflower.
- Neither output recompiles: classes `if` and `do` are Java keywords.

RuneLite deobfuscator (Evidence for the setup): `Deob.java` strips guards, dead code and multipliers but names everything `classN`/`methodN`/`fieldN`. Real names need `UpdateMappings` against an annotated revision-170 jar, so `runescape-client` must be compiled and `vanilla:170` found. `repo.runelite.net` answers 401 for `vanilla` 170 and 149 and 200 for `fernflower:20171017`; Maven 3.10's default `maven-default-http-blocker` blocks the POM's `http://` repositories; `runetech/osrs-gamepacks` serves `osrs-170.jar`. Guess: one to several days, with a mapper never tried across 21 revisions.

What can go wrong (Guess unless marked): ModArith infers multipliers and can be wrong; a rewritten jar is not the unchanged client, so it cannot replace the harness oracle; 170 names hide 149-only constants (the palette, Evidence).

## 5. Which future steps benefit

| Step | What it needs | Deobfuscation helps? |
| --- | --- | --- |
| More clips, female body | a client run per clip | No: `PoseReference` does it |
| Loop offset, other sequence opcodes | `jg` field per opcode, the tick loop | Partly: Vineflower `jg.r` gives the fields; the tick loop is unread |
| Held-item substitution | `hu.l` slot override, read | No: run the harness with a real `jg` |
| Alpha transforms | `ej.g` type 5, read | No |
| Textured faces, retextures | `client_lit` of the 180 static fixtures | No (Guess: retextures need an NPC or object case) |
| Render priority, draw order | `ej.ae`, read | Little |
| Object and NPC models | `im`/`ip` assembly | Yes: the largest unread code |
| Player sequence choice | the 149 appearance reader | Yes, for finding it |

## 6. Recommendation

Do not run the RuneLite deobfuscator or mapper now. The 2018 source is good enough for names and structure in these classes; constants and executed behaviour must still come from 149. Cheap middle path:

1. Decompile only the classes a step reads with the cached Vineflower, into a scratch folder outside the repo (Jagex code, never committed). Keep citing `javap` offsets.
2. Keep one 149-to-2018 name table for the ten classes, anchored by decoder opcodes and constructor order, with a script rechecking the fingerprints above.
3. Spend the time saved on client-run coverage: the live `iz.r` over all items and `jg.n` over all 7,636 sequences, compared with the dumper output.

Failure cases: the table is wrong wherever constants differ; Vineflower can misrender a method, so confirm in `javap`; object and NPC work may justify the full pipeline later.
