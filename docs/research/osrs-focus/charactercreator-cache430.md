# Cache 430 character appearance evidence

Investigated 2026-11-07 for milestone 1 of `docs/research/osrs-player-customization.md`. Evidence only. No product implementation, cache modification, Blender execution, build or commit. This records static decoding and assembly rules and measured local outputs; it does not establish a rendered player reference.

## Sources and citation notation

The following prefixes are absolute local paths. Citations such as `C/KitDefinition.java:93-127` mean those source-file lines, inclusive. Binary citations give the class, full method signature where needed, and bytecode offsets, not reconstructed Java line numbers. These two forms deliberately distinguish readable later source from revision-149 evidence.

| Prefix | Absolute path |
| --- | --- |
| `W` | `<data workspace>` |
| `C` | `<RuneLite May 2018 tree>/runescape-client/src/main/java` |
| `D` | `<path to osrs-cache-dumper>` |
| `M` | `D/src/main/java/osrsdump/Main.java` |
| `E` | `W/exports/osrs/openrs2-430/dump` |
| `J` | `<reference work folder>/gamepack-149.jar` |

The research used the local-repository and Matt Pocock research skills. A background researcher inspected client behavior; the primary researcher inspected provenance, dumper source and actual exports. No research source was written outside this file. Read-only inline inspection of exported kit bytes is an evidence measurement, not a new supported decoder.

## 1. Snapshot identity and best client match

**OpenRS2 snapshot 430 contains OSRS revision 149**, live English, with catalog timestamp `2017-07-13T00:00:00Z`. The number 430 is a snapshot ID, not the client revision or a JS5 group number. The catalog supplies major revision 149 and a null minor revision; no more specific minor revision is established. Primary local catalog evidence: `<data workspace>/caches/osrs/openrs2-430/metadata.json:2-13`. Its recorded sources are Hlwys and K4rn4ge, with 17 valid indexes and 49,264 valid groups (`metadata.json:14-26`). A catalog date is not proof of the exact gamepack used by a player on that date.

`W/caches/osrs/openrs2-430/provenance.json:2-30` records retrieval on `2026-11-06T18:16:35.005635+00:00`, the OpenRS2 snapshot URL and file SHA-256 values. This investigation rehashed all 19 files under its `cache/` entries: **19 matched, zero mismatches**. Representative identities:

| File | SHA-256 |
| --- | --- |
| `cache/main_file_cache.dat2` | `3c48913fa884d2d33f03af71cf4be05e6915263f939c545e1fefa6953bc7fedd` |
| `cache/main_file_cache.idx2` | `80591ded9b9da0bbf52fd9a6f08ee5f4835aeb31ac76d3162bc17727cd311969` |
| `cache/main_file_cache.idx255` | `591be06738b8de75a4bffc63f16747a8521ab4fb1a8997181a67b4075bec1bf6` |

### Match assessment

| Local artifact | Established identity | Suitability and confidence |
| --- | --- | --- |
| `J` | Revision-149 gamepack, SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`, rehashed in this investigation. | **Best revision match; high confidence in revision identity.** Its actual initialization and JS5 handshake write 149. Its classes `it`, `hu`, `iz` and `hv` supply revision-149 kit, appearance, item and palette evidence. Exact binary pairing with snapshot 430 is **unverified**. |
| `<RuneLite May 2018 tree>` | RuneLite `1.3.9-SNAPSHOT`; embedded client **revision 170**, not 149. `pom.xml:31,46`; `C/Client.java:2636,2705-2708,2990` initialize/send 170. | **Best available full named Java source for readable comparisons; high confidence that it is a later client.** Selected appearance control flow is corroborated against `J`; whole-client parity is unverified, and its palette differs. No Git metadata pins this source dump to an upstream commit. |
| `W/references/osrs/runelite-1.13.6-sources` and compatibility symlink `W/runelite-1.13.6-sources` | Extracted RuneLite cache-library source, not a revision-149 game client. The inspected directory contains `ModelLoader`, `ModelDefinition` and `ObjExporter`. The complete cache source JAR is in `~/.m2/repository/net/runelite/cache/1.13.6/`. | **High confidence as dumper implementation evidence; no matching-client claim.** The dumper pins cache library 1.13.6 at `D/pom.xml:15`. A library release number does not establish an OSRS revision. |

Gamepack provenance and internal handshake offsets are already recorded in [reference-source-findings.md](reference-source-findings.md#artifact-identity-and-provenance-limits). The pinned archive is `runetech/osrs-gamepacks` commit `2e92962075cfbc0df227cc783c37633d5e92f297`, blob `28a34a60c68a2518eb959b79f59be1d3fe813524`. Existing `osrs149-reference-client.javap` beside `J` records initialization passing `765,503,149` and the five-byte JS5 request containing opcode 15 followed by integer 149. Archive provenance does not establish certificate authenticity: signature verification and an exact snapshot/client association remain unverified.

**There is no verified exact-match full named revision-149 source among the inspected locations.** Use `J` as the authoritative revision reference and `C` as readable, explicitly later corroboration. Do not call `runelite-master` the July-2017 client.

Named-source identities, rechecked here:

| File under `C` | SHA-256 |
| --- | --- |
| `KitDefinition.java` | `23e39523bcfcb5df61dde5fa069a7d62d39e8cbeb6f163695268ffafe43db937` |
| `PlayerComposition.java` | `80854a13e9d5a323e4cd05a2bf1a34bdc9c36593ec1fabdaab62152e46a0cbd9` |
| `ItemComposition.java` | `c042a2c14a9d6d8500968561a4c78da26963ae3bcef0ddcd88c19c611b158007` |
| `class228.java` | `a9e73e824b4e5d4c3e1f3df631c9631e2ac5d9619ea55763bf640bcfa41f87a7` |

## 2. Identity kits

The readable source loads kit ID `id` from config group 3, file `id`, then decodes it: `<RuneLite May 2018 tree>/runescape-client/src/main/java/WorldMapManager.java:483-495`. The dumper library also names config group 3 `IDENTKIT` (`cache-1.13.6-sources.jar!/net/runelite/cache/ConfigType.java:28-38`).

`C/KitDefinition.java:64-84,93-127` gives this opcode stream; all multi-byte values below are big-endian:

| Opcode | Payload and meaning |
| --- | --- |
| 0 | End of definition. |
| 1 | Unsigned byte body-part category. Default is -1. |
| 2 | Unsigned byte count, then that many unsigned-short body model IDs. This is a list, not one mandatory model. |
| 3 | No payload; set `nonSelectable = true`, default false. |
| 40 | Unsigned byte count, then ordered unsigned-short source/destination face-colour pairs, stored as Java shorts. |
| 41 | Same layout for texture replacements. |
| 60 through 69 branch | Unsigned-short chathead model ID at index `opcode - 60`. The backing array has only five entries initialized to -1; the branch alone does not establish valid support for opcodes 65-69. |

Revision-149 corroboration: `J!it.class`, `r(fe,int,int)` reads category at offsets `305-314`, model count/list at `30-81`, selectable flag at `94-99`, recolours at `112-155,180-193,382-395`, retextures at `197-210,220-259,288-301`, and the 60-range branch at `265-268,320-334,362-365`.

Body assembly loads every listed body model, uses the sole model directly or merges multiple models, applies kit recolours in order, then retextures in order. Missing body-model list returns null. Readiness checks every listed model. Head models have separate readiness/assembly methods and are not the body list. Sources: `<RuneLite May 2018 tree>/runescape-client/src/main/java/KitDefinition.java:139-191`, `:200-257`. Revision-149 `it.e(byte)` loads at offsets `139-154`, merges at `125-135` or selects a single model at `243-246`, recolours at `104-119`, then retextures at `250-265`.

### Measured snapshot-430 kit contents

Inspected all `E/dump_index/configs/identkit/{0..150}.dat`: **151 files**, contiguous IDs, each consumed exactly through its opcode-0 terminator, with zero trailing bytes or unknown opcodes under the layout above. Observed opcode occurrence counts: `0:151`, `1:151`, `2:151`, `3:6`, `40:2`, `60:62`. No opcode 41 or 61-69 occurred. This measures this snapshot; it does not remove those branches from the client contract.

All referenced body and head model files exist in `E/dump_index/models/`. Presence does not establish successful client decoding or rendered correctness. Example raw record `identkit/0.dat` is `01 00 3c 00 3f 02 01 00 e6 00`: category 0, chathead model 63, one body model 230, terminator.

## 3. PlayerComposition slots and assembly

`C/PlayerComposition.java:46,55-74` maps seven body-part categories into a twelve-entry equipment array. For default selection it scans kit IDs in ascending order, rejects `nonSelectable`, matches category `part + (female ? 7 : 0)`, and stores `kitId + 256`. It does not choose by kit name. Changing kits uses the same filter; the female branch skips category 1 (`:82-108`).

Revision-149 evidence is `J!hu.class`: static initializer offsets `0-39` contain exactly `[8,11,4,6,9,7,10]`; `a(int[],int[],boolean,int,int)` allocates 12 entries at `156-160`, iterates seven categories at `164-168`, scans ascending IDs at `8-9,43-51,229-232`, rejects non-selectable kits at `92-97`, checks the body-type/category offset at `108-134,20-23`, and stores `256 + kitId` at `200-213`.

Applying those confirmed rules to the observed snapshot-430 kits gives this deterministic male default candidate:

| Body-part category | Equipment slot | First selectable male kit ID | Body model ID | Encoded entry |
| --- | --- | --- | --- | --- |
| 0 | 8 | 0 | 230 | 256 |
| 1 | 11 | 10 | 249 | 266 |
| 2 | 4 | 18 | 292 | 274 |
| 3 | 6 | 26 | 151 | 282 |
| 4 | 9 | 33 | 176 | 289 |
| 5 | 7 | 36 | 254 | 292 |
| 6 | 10 | 42 | 181 | 298 |

The complete equipment array is `[0,0,0,0,274,0,282,292,256,289,298,266]`. Kit IDs and encoded entries are different namespaces, including where an encoded entry equals another model's ID. All seven body DAT files are present and none ends in `ffff`. These are source-selected defaults, not proof of a particular server's new-player outfit or a user-approved artistic appearance. No default colour indices are inferred: the initialization method receives its five colours as an argument.

**Guess, terminology only:** customary names for categories 0-6 are hair, jaw/beard, torso, arms, hands, legs and feet. The numeric mapping above is observed; these human labels were not established by the traced revision-149 methods. The evidence does not require those labels to assemble the candidate.

For the remaining equipment-slot vocabulary, the local later API explicitly names cape 1, amulet 2, weapon 3, torso 4, shield 5, legs 7, head 8, hands 9, boots 10 and jaw 11 (`<RuneLite May 2018 tree>/runelite-api/src/main/java/net/runelite/api/kit/KitType.java:29-38`). That enum does not name slots 0 and 6. These names are revision-170 API evidence, not a recovered revision-149 server equipment specification.

The assembly loop walks slots 0 through 11:

- Values below 256 contribute no body model through these branches; zero is the default empty entry.
- Values from 256 through 511 resolve kit `value - 256`.
- Values at least 512 resolve item `value - 512`, using the body-type-specific worn model path.
- Gather non-null parts, merge them, perform both global body-colour passes, then light with `(64,850,-30,-50,-30)`.

Sources: `<RuneLite May 2018 tree>/runescape-client/src/main/java/PlayerComposition.java:266-322`. Actual revision-149 `hu.l(jg,int,jg,int,byte)` checks kit/item thresholds at offsets `364-369,694-707`, calls kit assembly at `915-931` and item assembly at `762-782`, merges at `820-831`, applies the two recolour paths at `330-355,836-858`, and lights at `279-292`.

The named-source merge constructor retains face colours, alpha, priorities, face skins and texture references and remaps face indices (`C/ModelData.java:156-304`). Its vertex insertion reuses the first vertex with equal XYZ and only copies a vertex skin when inserting a new vertex (`:1059-1083`). This detailed merge behavior has not been independently replayed for a snapshot-430 character in this investigation; concatenating OBJ parts does not establish parity with it.

Appearance packet decoding in the later source reads twelve high-byte/low-byte encoded entries, with high byte zero meaning an empty slot. Slot 0 value 65535 switches to an NPC transform ID. Five colour bytes follow; out-of-range primary-palette indices are reset to zero, and the body-type flag is interpreted as `value == 1`. Sources: `C/Player.java:180-221,277`. These exact packet details were not traced in the revision-149 player class here.

Equipment visibility is represented by the supplied equipment array, not a universal hide-hair/hide-arms heuristic in this assembly loop. A slot containing a worn item replaces the kit that would otherwise occupy that slot; other kit slots remain unless the appearance has changed them. The source loop does not establish how a server chooses slots to clear for a helmet or platebody. Likewise, the later source's sequence overrides replace slots 5 and 3 before assembly (`C/PlayerComposition.java:243-258`); animation substitution is outside this plain static candidate.

The later client checks resource readiness, reuses its last cached model when possible, or returns null (`C/PlayerComposition.java:266-284`). It does not silently choose a different default outfit. That fallback has not been executed for the candidate here.

## 4. Body colours: revision-specific client tables

These are five **palette indices**, not arbitrary RGB values and not an identity-kit payload. Ordered kit/item replacements happen before global appearance recolours. Each colour index can trigger two replacements on the assembled model. Readable algorithm: `<RuneLite May 2018 tree>/runescape-client/src/main/java/PlayerComposition.java:312-322`. The later table bindings are `C/Client.java:1505-1508`; literal tables are `C/class228.java:15-18`.

Actual revision-149 tables reside in `J!hv.class`, not in those later literals. Its initializer has primary sources `hv.a` at offsets `0-33`, primary choices `hv.j` at `474-1172`, secondary sources `hv.n` at `441-468`, and secondary choices `hv.r` at `39-437`. `client.aa(int)` binds `hv.j -> gw.s` at `150-153`, `hv.a -> hu.l` at `159-162`, `hv.r -> cd.p` at `168-171`, and `hv.n -> hu.w` at `177-180`. `hu.l(...)` uses those tables in the two passes cited above.

| Colour index | Primary source | Primary row length | Secondary source | Secondary row length |
| --- | --- | --- | --- | --- |
| 0 | 6798 | 25 | -10304 | 25 |
| 1 | 8741 | 29 | 9104 | 29 |
| 2 | 25238 | 29 | -1 | 0 |
| 3 | 4626 | 6 | -1 | 0 |
| 4 | 4550 | 11 | -1 | 0 |

Sources and destinations are 16-bit face-colour values stored as signed Java shorts. Preserve their bit patterns; for example -10304 represents unsigned 55232. Empty secondary rows cause no replacement. Each pass checks its own row length. There is no RGB conversion in this appearance-recolour operation.

**Confirmed incompatibility:** revision 149's primary row 4 is exactly `[4550,4537,5681,5673,5790,6806,8076,4574,17050,0,127]` (`hv.<clinit>`, allocation offsets `1097-1101`, entries `1103-1170`). Revision 170 adds `-31821`, making that row length 12 (`C/class228.java:16`). The other primary rows and the secondary rows match the inspected later literals. Do not copy the revision-170 table wholesale into a revision-149 profile.

The in-client colour-cycling method additionally excludes choices at least 8 for colour index 4, despite the longer underlying row. This is confirmed in revision-149 `hu.n(int,boolean,int)` at offsets `39-41,76-78,150-168`; readable later equivalent is `C/PlayerComposition.java:116-148`. Distinguish selectable UI choices from the complete table. Friendly colour names and the five category names are not supplied by these numeric tables.

## 5. Worn item decoding and assembly

The inventory model is a separate representation from body-worn models. Default worn model IDs are -1 and offsets are zero (`C/ItemComposition.java:305-316`). Decode stops at opcode zero (`:351-359`). Relevant opcode citations: `<RuneLite May 2018 tree>/runescape-client/src/main/java/ItemComposition.java:395-404`, `:415-431,437-448`.

| Opcode | Payload |
| --- | --- |
| 1 | Unsigned-short inventory model ID. Not the worn model. |
| 23 | Unsigned-short first male worn model, then **unsigned-byte** male offset. |
| 24 | Unsigned-short second male worn model. |
| 25 | Unsigned-short first female worn model, then **unsigned-byte** female offset. |
| 26 | Unsigned-short second female worn model. |
| 78 / 79 | Unsigned-short third male / female worn model. |
| 40 / 41 | Unsigned-byte count plus ordered unsigned-short pairs for recolours / retextures. |
| 90 / 92 | First / second male chathead model. |
| 91 / 93 | First / second female chathead model. |

The cache-library loader used by the dumper independently reads these worn fields (`cache-1.13.6-sources.jar!/net/runelite/cache/definitions/loaders/ItemLoader.java:128-145` for first/second models and offsets). Its field names `maleModel0` and `femaleModel0` correspond to the named client's `maleModel` and `femaleModel`.

Revision-149 decoding has existing file:line evidence, not just the later source: `J`'s sibling `<reference work folder>/osrs149-reference-iz.javap:7248` contains the active zero-terminated `r(fe,int)` loop dispatching to `v(fe,int,int)` at `:9670`. The latter writes the male primary/secondary/third fields at `:10186,:9895,:10167`, female primary/secondary/third at `:9985,:9929,:10178`, and male/female offsets at `:9775,:9911`. Those offset writes use the byte reader, while model IDs use the unsigned-short reader, matching the readable opcode layout above.

Assembly selects male or female fields, returns null when the primary model is -1, loads the first model, and merges two or three components when present. **The third component is reached inside the second-component branch**, so three independent optional model IDs would misdescribe the control flow. Translate the assembled worn model by `(0, maleOffset, 0)` or `(0, femaleOffset, 0)` in client model units, then apply item recolours, then retextures. Only afterward does PlayerComposition merge all parts and apply body colours. No inventory camera settings or inventory resize operation is applied by this worn-model method. Sources: `<RuneLite May 2018 tree>/runescape-client/src/main/java/ItemComposition.java:745-792`; the translation adds to XYZ at `C/ModelData.java:1346-1353`. Readiness checks first/second/third model availability separately (`ItemComposition.java:709-735`).

Revision-149 `J!iz.class`, `k(boolean,byte)` corroborates assembly: male fields `aw/aq/ad`, female `ag/aj/az`; primary absence `107-113`; first load `114-122`; second branch `124-127,144-153`; third load `171-180`; three-model merge `182-213` or two-model merge `224-250`; male offset field `aa` passed to `dv.g(0,offset,0)` at `293-305`, female field `ax` at `412-424`; recolour loop `311-327`, retexture loop `12-28`. Bytecode layout is not execution order: jumps reach recolouring before retexturing.

Measured item examples, directly from the existing JSON:

| Item | Inventory model | Male worn models; offset | Female worn models; offset |
| --- | --- | --- | --- |
| 1127, Rune platebody | 2605 | `[306,164,-1]`; 0 | `[468,344,-1]`; 0 |
| 4151, Abyssal whip | 5412 | `[5409,-1,-1]`; 0 | `[5409,-1,-1]`; 6 |

Primary output citations: `E/items/ItemDefinitions.json:79598` and `:291450`, respectively. These illustrate multiple components and body-type offsets; neither item is selected for the plain-outfit candidate. The platebody JSON also retains ordered colour replacements, including negative signed-short destinations.

## 6. What the dumper and existing dump contain

The inspected dumper HEAD is `a89a0f0322a67368ccffc857c5dab4e2c442cb54` (2026-11-06). Its existing unrelated working-tree changes were left alone. The original full snapshot-430 dump report identifies an earlier producer `2e331e1`; current source behavior and that recorded run are separate evidence. Sources: `<data workspace>/exports/osrs/openrs2-430/verification/summary.json:2-6`, `D/pom.xml:15`, `M:75-78,374-419`.

| Output / target | Actual snapshot-430 contents and limits |
| --- | --- |
| `raw-configs` | `E/dump_index/configs/identkit/<id>.dat`: 151 raw kit definitions. Names come from config group IDs; group 3 is `identkit`. No typed kit JSON catalog, selectable-kit index, palette catalog or appearance recipe. `M:615-641`. |
| `items` | `E/items/ItemDefinitions.json`: 21,392 typed definitions serialized from `ItemLoader` results. Includes ID/name; inventory model/camera fields; all six male/female worn model fields; both offsets; four head model fields; ordered `colorFind/colorReplace`, `textureFind/textureReplace` arrays where present; action arrays; resize/lighting fields; note/bought/placeholder links; params and other library fields. Optional null arrays are omitted. `M:374-375,442-505`. |
| `raw-items` and `raw-configs` | 21,392 individual item DATs in each of `dump_index/items/` and `dump_index/configs/item/`. All 21,392 corresponding pairs were byte-compared here: zero differences. `M:399,529-541,615-641`. |
| `raw-models` | 33,196 `dump_index/models/<id>.dat` files, retaining original model data for a later decoder and closure check. `M:400,568-612`. |
| `models-obj` | 33,196 OBJ files plus 33,196 MTL files. Each is an individual model preview, not a resolved player. No kit/item assembly or appearance recolouring. Vertex/face skins, render priorities and original texture records are not emitted as structured source data. Source: `M:860-891`; `D/src/main/java/osrsdump/ObjModelWriter.java:26-74,94-113`. |
| `textures` / `item-icons` | 59 texture PNGs and 21,391 inventory icons in the existing main dump. Icons are inventory renders, not worn-player previews. The original run missed item 8283; its recorded failure is not a claim that the current dumper still has that defect. `verification/summary.json:36-45,63-71`; `M:978-989`. |

Every exported item has `wearPos1 == wearPos2 == wearPos3 == -1` in this snapshot: **zero definitions with a non-default wear position**. The modern loader exposes those fields, but their presence in JSON does not supply historical equipment-slot or hidden-body-part metadata. An inventory action named Wear/Wield also does not specify which appearance slots must be cleared.

## 7. Gaps for a male plain-outfit prototype

The available evidence identifies a concrete seven-kit, no-worn-item candidate and its model closure. It does not finish milestone 1's independent assembly/visual validation.

1. **Typed appearance input is missing.** The dumper has raw kit bytes and typed items, but no typed kit catalog, revision-149 palette output or complete appearance/resource recipe. The seven male kits above are measured defaults, not an already exported player bundle.
2. **Colours remain a selection.** Five colour indices must be chosen and recorded. The source initializer receives them; it does not establish one canonical default. Revision-149 palette lengths and the colour-4 UI restriction are now evidenced. No colour choice or friendly name is invented here.
3. **Independent assembled reference is missing.** Run the selected kits, colours and models through the revision-149 constructor/kit/player paths and compare final geometry, ordered recolours, retained source data and lighting/visibility. Existing revision-149 static-model fixtures cover individual models, not this complete appearance. No character render, screenshot or Blender comparison was produced here.
4. **Raw presence is established, model decoding for this character is not replayed.** All seven candidate body DATs exist and lack the new-format marker. No claim that every kit, every worn model or every snapshot-430 model works in Blender follows from that. The existing format audit's 5,398 new-format decoder failures concerns broader model support, not a measured failure of these seven candidate files.
5. **Worn outfit selection adds another evidence requirement.** If plain outfit means actual worn items rather than the body kits, item IDs and the full twelve-slot appearance must be supplied or independently established. The current item JSON cannot recover all equip/visibility rules. The no-item candidate avoids making a guessed equipment-clearing rule but does not prove worn-equipment support.
6. **Model/material preservation remains to be checked end to end.** OBJ is insufficient as the canonical character source: preserve raw models, colours, alpha, priorities, texture references and skin labels through assembly. No rig or animation mapping is established. The opt-in animation reader still rejects `cache_revision != 1` (`D/src/main/java/osrsdump/LegacyAnimationData.java:109-110`), so it cannot be cited as a revision-149 appearance-bundle producer.
7. **Exact pairing and full protocol parity remain unverified.** Internal revision 149 is proven; the exact gamepack used with snapshot 430, authenticity verification, packet decode parity and server outfit selection are not. Selected binary/source control-flow agreement is not whole-client equivalence. The observed palette difference demonstrates why that boundary matters.

## Reproduction boundary

Read-only commands for the binary observations, printing to stdout without creating decompiled files:

```bash
javap -classpath <reference work folder>/gamepack-149.jar -c -p hu
javap -classpath <reference work folder>/gamepack-149.jar -c -p it
javap -classpath <reference work folder>/gamepack-149.jar -c -p iz
javap -classpath <reference work folder>/gamepack-149.jar -c -p hv
```

The existing `osrs149-reference-client.javap` and `osrs149-reference-iz.javap` beside `J` also support client initialization and item tracing. The artifact contains duplicate methods with altered constants; the exact active signatures above matter. CFR stdout was used for navigation and readable comparison; claims with bytecode offsets were checked against `javap`, not accepted from malformed decompilation. No client was executed in this investigation. Only the terminology line explicitly marked **Guess** is speculative; numbered gaps are unverified work, not assumed outcomes.

## 8. Revision-149 worn item confirmation

Investigated 2026-11-07 for milestone 2, Task 1. Fresh `javap -c -p` output from `J` confirms the rules below. The jar's SHA-256 remains `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`; the fresh `iz` output is byte-identical to the existing sibling `osrs149-reference-iz.javap`. All numeric citations below are **method-local bytecode offsets**, not dump line numbers. These are static observations, with cache-dependent derivations identified separately. No client or reference harness was executed.

### Decoder and field mapping

The active `iz.r(fe,int)` reads an opcode through `fe.z(byte)` at `0-5`, exits on zero at `12-31,46`, and calls `iz.v(fe,int,int)` at `34-40` with sentinel `-1736448167`. This selects the live paths through the decoder's sentinel guards. The following offsets refer to that exact `v` signature.

| Opcode | Revision-149 payload and destination | Bytecode offsets |
| --- | --- | --- |
| 1 | Unsigned-short inventory model ID, `t`; separate from worn models. | Dispatch `0-9`; read/write `707-719`. |
| 23 | Unsigned-short first male worn model, `aw`, then unsigned-byte male offset, `aa`. | Dispatch `410-416`; model `1064-1078`; offset `199-209`. |
| 24 | Unsigned-short second male worn model, `aq`. | Dispatch/read/write `447-465`. |
| 25 | Unsigned-short first female worn model, `ag`, then unsigned-byte female offset, `ax`. | Dispatch `471-477`; model `643-657`; offset `489-498`. |
| 26 | Unsigned-short second female worn model, `aj`. | Dispatch `338-348`; read/write `525-537`. |
| 78 | Unsigned-short third male worn model, `ad`. | Dispatch `1003-1013`; read/write `1024-1035`. |
| 79 | Unsigned-short third female worn model, `az`. | Dispatch/read/write `1041-1058`. |
| 40 | Unsigned-byte count; ordered pairs of unsigned shorts cast to Java `short`, colour find `o[i]`, colour replace `x[i]`. | Dispatch/count/allocation `660-704`; index zero `566-569`; loop test `725-736`; find `64-78`; replace `766-780`; increment `1404-1407`. |
| 41 | Unsigned-byte count; ordered pairs of unsigned shorts cast to Java `short`, texture find `f[i]`, texture replace `h[i]`. | Dispatch `622-632`; count `1607-1614`; allocation `808-816,849-857`; index zero `419-422`; loop test `316-327`; pair and increment `897-930`. |
| 90 / 92 | Unsigned-short first / second male chathead model, `as` / `av`. | Dispatch `504-514` / `1135-1145`; read/write `1081-1092` / `1336-1348`. |
| 91 / 93 | Unsigned-short first / second female chathead model, `ab` / `at`. | Dispatch `819-829` / `1174-1184`; read/write `1118-1129` / `1188-1199`. |

Reader signedness is confirmed in the binary itself: `fe.z(byte):0-26` advances one byte and masks `baload` with `255` at `21-25`, yielding `0..255`. `fe.d(int):0-51` advances two bytes, masks both with `255` at `24-28,42-46`, shifts the earlier byte left eight at `47-49`, and adds at `50`: a big-endian unsigned short. Both worn offsets are therefore **one unsigned byte**, with no sign extension or subtraction of 256. Model reads are not cast to short or converted from 65535 to -1 in these branches. Colour and texture pairs do use `i2s`: negative Java/JSON short values preserve the original 16-bit patterns. Pairs retain input order and find/replace direction.

`iz.<init>()` sets all six worn models to logical -1, using each field's encoded integer multiplier: `aw:125-129`, `aq:303-307`, `ad:36-40`, `ag:150-154`, `aj:157-161`, `az:182-186`. Offsets start at zero, `aa:145-147`, `ax:164-166`. The decoder writes and assembly reads use inverse multipliers modulo 2^32; those obfuscation constants do not change the logical values.

### Worn-model assembly and readiness

The active worn method is `iz.k(boolean,byte)`, called with sentinel `-54` by `hu.l`. False selects male `aw/aq/ad` at `0-8,158-168,34-44`; true replaces all three with female `ag/aj/az` through `430-437,65-84,255-265`. Its control flow is:

1. If the selected primary ID is -1, return null (`107-113`), regardless of secondary/third IDs. Otherwise load the primary through `dv.a(iz.l, primary, 0)` (`114-122`).
2. If the second ID is -1, jump directly to offsets (`124-127 -> 348`). Otherwise load the second (`144-153 -> 87`). Only here test the third (`87-96`): if present, load it (`171-180`) and merge `[first, second, third]` (`182-213`); otherwise merge `[first, second]` (`224-250`). A third ID without a second is ignored by assembly.
3. After that item-level merge, false applies nonzero `aa` via `dv.g(0, aa, 0)` (`348-355 -> 268-305`); true applies nonzero `ax` via `dv.g(0, ax, 0)` (`47-54 -> 333-345 -> 412-424`). Both paths then reach recolouring at `366`.
4. Apply `dv.c(o[i], x[i])` in ascending index order (`366-400 -> 311-327 -> 406-409`), then `dv.o(f[i], h[i])` in ascending order (`478-489 -> 218-221 -> 448-461 -> 12-28 -> 472-475`). Return the result at `500-502`. The retexture block's smaller bytecode offsets do not mean it executes first.

Translation **adds the positive decoded offset to client Y**, with X and Z unchanged. `dv.g(int,int,int)` adds argument 1 to vertex array `j` at `60-70`, argument 2 to `n` at `12-22`, and argument 3 to `r` at `38-48`. The vertical-height calculation in `dv.d():97-103,10-20,187-194` uses negated `n`, corroborating the Y identification. Thus positive offset increases client Y, in the downward direction of the client's height convention; there is no negation at the worn-item call. This is a client-coordinate statement, not a Blender-axis conversion.

`dv.c(short,short):2-34` replaces matching face colours (`g`) with argument 2; `dv.o(short,short):0-48` similarly replaces face textures (`k`), returning immediately if the texture array is null. Each ordered replacement sees earlier replacements. `iz.k` calls no inventory resizing or camera-setting method: its entire normal path is selection, loading/merge, translation, recolour, retexture, return.

The explicit null return in `k` is the primary-ID sentinel case. Missing resource bytes are a separate case: `dv.a(if,int,int):0-14` returns null when archive lookup returns null. `k` does not guard the loaded primary before translating or replacing colours/textures; a null load can pass through the final return if no later operation dereferences it. Do not interpret this method as a general missing-resource error policy. The normal player path performs readiness checks first. `iz.g(boolean,int)` chooses the same body-type fields (`0-8,76-86,18-28,136-145,53-73`), returns true for primary -1 (`89-98 -> 264-265`), and otherwise checks primary (`184-195`), second if present (`109-112,154-166`), and third if present (`213-216,234-246`) **independently**. Readiness can therefore check a third model that assembly would ignore when the second is absent.

### Player-composition call and female kits

In `hu.l(jg,int,jg,int,byte)`, normal equipment comes from `hu.a` (`753-759`); sequence overrides can copy the array and replace slots 5 and 3 (`143-159,210-225,573-584,316-327`). Its readiness pass tests `value >= 512` at `484-489`, looks up `cu.j(value - 512, ...)` at `507-515`, and passes `hu.n` to `iz.g(boolean,int)` at `518-524`.

The assembly loop visits twelve slots (`909-912,162-169,814-817`), loads the current value at `687-692`, and distinguishes kits in `[256,512)` (`694-707`) from items `>=512` (`364-372`). The item branch calls `cu.j(value - 512, ...)` (`762-770`), then `iz.k(hu.n, (byte)-54)` (`773-779`). It skips null results (`782-786`) and appends non-null results (`804-813`). `hu.a(int[],int[],boolean,int,int):137-139` stores the supplied female boolean in `hu.n`, so false selects the male item fields and true the female fields above. Per-item offset/recolour/retexture finish before the player merge (`820-831`), then the five body-colour choices run (`833 -> 1016-1019 -> 982-992`, calls `330-355,836-861`), then lighting (`279-292`).

Female kit categories are **part + 7**, confirmed in `hu.a(int[],int[],boolean,int,int)`: `it.v` is read at `108-115`, the female boolean chooses 7 or 0 at `116-134`, and addition/comparison occurs at `20-23`. Null equipment creates twelve zeroes (`0-5,156-160`); initialization scans seven parts (`164-168`) and ascending kit IDs (`8-9,43-51,229-232`), rejects null/non-selectable definitions (`78-81,92-97`), and stores the first match as `256 + kitId` at `equipment[hu.m[part]]` (`200-214 -> 153 -> 14`). `hu.<clinit>():0-39` defines that slot mapping as `[8,11,4,6,9,7,10]`. Changing body type through `hu.r(boolean,byte):0-5,23-33` calls this initializer with null equipment and the existing colours. Kit cycling also uses +7 (`hu.j(int,boolean,int):204-232`) and skips part 1 for females (`0-8,183-193,74`); initialization still searches its category 8.

Applying that static initializer to all 151 raw snapshot-430 kit definitions under `E/dump_index/configs/identkit/` gives:

| Part | Female category | Slot | First selectable kit | Encoded entry |
| --- | --- | --- | --- | --- |
| 0 | 7 | 8 | 45 | 301 |
| 1 | 8 | 11 | none | 0 |
| 2 | 9 | 4 | 56 | 312 |
| 3 | 10 | 6 | 61 | 317 |
| 4 | 11 | 9 | 67 | 323 |
| 5 | 12 | 7 | 70 | 326 |
| 6 | 13 | 10 | 79 | 335 |

The resulting twelve-slot female default is **`[0,0,0,0,312,0,317,326,301,323,335,0]`**. No raw kit has category 8, so slot 11 remains zero. This is a **static derivation from measured cache bytes and confirmed bytecode**, not a hard-coded array in `hu` or a runtime fixture. Equality to an array captured by executing the revision-149 initializer is **unverified** and remains milestone 2, Task 2 work.

### Differences from section 5's revision-170 source

No behavioral difference was found for the listed worn/head opcodes, offset width/signedness, ordered find/replace arrays, body-type selection, nested second/third assembly, positive Y translation, or offset then recolour then retexture order. The revision-149 names/signatures differ: the worn method is `iz.k(boolean,byte)`, its fields are those mapped above, and recolour/retexture are `dv.c`/`dv.o`. The independent readiness checks and lack of a general load-null guard are now explicit qualifications to section 5, not demonstrated revision differences. Female defaults depend on the kit catalog; a revision-170 default array or complete female-catalog equivalence is **unverified**. Section 5's exported item examples and cache-library implementation claims were not remeasured here; exact snapshot/gamepack pairing and whole-client equivalence remain **unverified** as in sections 1 and 7.

## 9. Revision-149 item harness bindings

Investigated 2026-11-07 for milestone 2, Task 4, using fresh `javap -c -p cu iz fe hu` on the same SHA-256-pinned `gamepack-149.jar` as section 8. These are static bytecode observations; runtime outfit results belong to the appearance fixture recorder.

`cu.j(int,int)` reads item bytes from `eb.e` through `if.n(10, itemId, (byte)-2)` at method-local offsets 376-387. It constructs `iz` at 446-453, constructs `fe(byte[])` at 480-486, and invokes `iz.r(fe,1882926117)` at 489-492. `fe(byte[])` stores the supplied bytes and resets its cursor to zero at offsets 4-18. The item configuration archive can therefore be supplied through constructor-free archive storage group 10, with no game initialization. Worn model loading uses static archive `iz.l` in `iz.k(boolean,byte)` at offsets 114-122, 144-153 and 171-180. Assigning `eb.e` and `iz.l` binds the configuration and model archives independently.

`cu.j` requires its second argument to be less than -1597312825, including on the cache-hit return path at offsets 132-150. `hu.l` supplies -1887289503 for readiness lookup at 507-515 and -1827004326 for assembly lookup at 762-770. The latter is suitable for direct harness lookup. `hu.l` calls `iz.k` with byte -54 at offsets 773-779.

The following table records the read multipliers used by `iz.k`, so the harness can expose logical item values after the original decoder runs. Multiplication uses Java's signed 32-bit overflow semantics. Recolour fields `o/x` and retexture fields `f/h` are ordered short arrays and need only unsigned 16-bit normalization for JSON.

| Logical value | Encoded field | Read multiplier | `iz.k` offsets |
| --- | --- | --- | --- |
| Male model 1 | `aw` | -1032210027 | 0-8 |
| Male model 2 | `aq` | -1410308759 | 158-168 |
| Male model 3 | `ad` | -2049145749 | 34-44 |
| Female model 1 | `ag` | -342824299 | 65-73 |
| Female model 2 | `aj` | 1991139359 | 74-84 |
| Female model 3 | `az` | 85456167 | 255-265 |
| Male Y offset | `aa` | -1445417827 | 268-305 |
| Female Y offset | `ax` | -761981003 | 333-345, 412-424 |

For a read-only runtime proof of the three-model path, a JVMTI method-entry observer can select `dv.<init>(dv[],int)`, signature `([Ldv;I)V`, and inspect local slot 2 for the input count. The immediate caller is `iz.k` at bytecode offset 210 for its three-model constructor call, or offset 247 for its two-model call. Capturing the count while invoking each item's unchanged `iz.k` distinguishes the actual constructor path from a deduction based solely on decoded model IDs. A direct `iz.k` return also provides the item's vertex and face counts after its own merge, translation and colour/texture replacements, before the player-composition merge.
