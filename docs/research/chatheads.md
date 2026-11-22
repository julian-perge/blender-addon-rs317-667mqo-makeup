# The chathead in gamepack 149

Checked on 2026-11-22 with `javap -p -c` on the revision 149 gamepack (SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`, the same jar as [item-light.md](item-light.md)). The offsets below are bytecode offsets of the obfuscated classes. The real names come from [client-names.tsv](client-names.tsv), with the rows that this note adds. A name that the mapper did not give is a descriptive name chosen for this note.

Each obfuscated int field is read with a multiplier. The values below are the decoded values: the read multiplier times the write multiplier is 1 modulo 2^32 for every pair that this note uses (checked for `hy.bh`, `hy.bw`, `hy.ea`, `hy.eu`, `jg.p`, `client.gb` and `iz.as`, `iz.ab`, `iz.av`, `iz.at`).

## Which copies the client calls

`hy` has five methods with the signature `(jg, int, boolean, hu)`: `u`, `ac`, `af`, `bp` and `bi`. Only `hy.u` has callers: `et.if` (`gameDraw`) at offsets 8504 and 8588, and the copy `client.qw`. `ac`, `af`, `bp` and `bi` have no call site, and `ac` passes changed constants to `dv.ae`. Evidence. This note uses `hy.u` only.

The same holds for the other classes: `hu.ap` (a copy of `hu.s`), `jg.aj`, `jg.ax`, `jg.ad`, `jg.az` (copies of `jg.p`), `client.te` and `client.ty` (copies of `je.ic`) have no call site. Evidence. The live chain is `client.gg` (called by `client.aj`, `methodDraw`) -> `eq.in` -> `et.if` -> `hy.u`, and `client.gg` offset 1024 -> `je.ic`. Evidence.

## Widget model types

The server packet handler `client.ga` sets the type of a widget model:

| Offsets | What the code does |
| --- | --- |
| 1249 to 1305 | `modelType = 2`, `modelId = npc id` from the packet, when one of them changes. This is the NPC head. |
| 15276 to 15302 | `modelType = 3`, `modelId = localPlayer.composition.w()`. This is the player head. |

`hu.w()` (offsets 0 to 103) returns `305419896 + npc id` when `transformedNpcId` is not -1, otherwise `(j[0] << 25) + (j[4] << 20) + (a[0] << 15) + (a[8] << 10) + (a[11] << 5) + a[1]`. It is only a cache key: `hy.u` never reads the model id for type 3 except in the key. Evidence.

The other types: 1 is a model id, 4 is an item (`cu.j(id).w(10)`), and 5 is the full model of the local player, which `et.if` (offsets 8406 to 8465) builds with `hu.l` and never passes to `hy.u`. Evidence. `h.e` (called from `cu.aq` and `cu.aw`) writes the types 2 (offset 584) and 3 (offset 640) too. Evidence. That `h.e` is the script opcode handler for these types is a Guess.

## `hy.u` is `Widget.getModel`

The boolean argument selects the field pair: false reads `modelType` (`hy.bs`) and `modelId` (`hy.bh`) at offsets 35 to 45 and 332 to 340, true reads `hy.bo` and `hy.bk` (the second pair) at offsets 48 to 58 and 366 to 374. Evidence.

| Offsets | What the code does |
| --- | --- |
| 518 to 531 | Type 0: return null. |
| 256 to 108 | Type 1 with id -1: return null. |
| 132 to 152 | Look up `(type << 16) + id` in `hy.g` (`Widget_cachedModels`). A hit skips to the sequence step. |
| 192 to 203, 345 to 358 | Type 1: `dv.a(an.w, id, 0)`, then `light(64, 768, -50, -10, -50)`. |
| 286 to 300, 486 to 499 | Type 2: `hf.a(id).e()` (`NPCComposition.getHeadModelData`), then `light(64, 768, -50, -10, -50)`. |
| 379 to 451 | Type 3: null composition gives null. Otherwise `hu.s()` (`PlayerComposition.getHeadModelData`), then `light(64, 768, -50, -10, -50)`. |
| 462 to 483, 206 to 239 | Type 4: `cu.j(id).w(10)`, then `light(64 + ambient, 768 + contrast, -50, -10, -50)` with `iz.bp` and `iz.bi`. |
| 82 to 96 | Put the lit model in `hy.g` under `(type << 16) + id`. |
| 7 to 8, 559 to 573 | When the sequence is not null: return `seq.p(model, frame)`. The animated model is not cached. |

A missing model data sets the static flag `hy.c` and returns null (offsets 28 to 32, 432 to 437, 511 to 515). Evidence.

So both heads are lit with `(64, 768, -50, -10, -50)`. The NPC's own `ambient` and `contrast` (`ip.ai`, `ip.ae`) are not used: only `ip.v` (the world model) reads them, at offsets 418 to 449, with `(64 + ambient, 850 + contrast, -30, -50, -30)`. The player body (`hu.l` offsets 279 to 292) uses `(64, 850, -30, -50, -30)`. Evidence.

## `jg.p` applies the sequence to a widget model

`jg.p(ej, int)` is the only reader of the field `jg.l` outside the decoder and its uncalled copies, and `hy.u` is its only caller. Evidence.

| Offsets | What the code does |
| --- | --- |
| 0 to 22 | `id = frameIDs[frame]` (`jg.e`), `frames = cd.m(id >> 16)` (`getFrames`), `id &= 0xFFFF`. |
| 114 to 119, 284 to 289 | `frames` is null (not loaded): return `model.j(true)` with no transform. |
| 41 to 104 | When `jg.l` is not null and `frame < jg.l.length`: `chat = jg.l[frame]`, `chatFrames = cd.m(chat >> 16)`, `chat &= 0xFFFF`. |
| 134 to 196 | No chat frame (null array, frame past its end, group not loaded, or file id 65535): `copy = model.j(!frames.a(id))`, `copy.m(frames, id)`, return. |
| 257 to 281, 209 to 254 | With a chat frame: `copy = model.j(!frames.a(id) & !chatFrames.a(chat))`, then `copy.m(frames, id)`, then `copy.m(chatFrames, chat)`, return. |

`ej.m(et, int)` is the transform of a model by one frame (`Model.animate`). `et.a(int)` decides only the boolean that `ej.j` (`toSharedModel`) gets. The mapper name `hasAlphaTransform` for `et.a` is a Guess from RuneLite.

So a chathead frame is the frame of `frameIDs` and then the frame of `chat_frames` at the same index, both on the same model. Evidence. The same frame index picks both, and the frame lengths come from `frameLengths` only.

## `jg.r` opcode 12 is the chat frame list

Offsets 557 to 584: `count = readUnsignedByte()`, `jg.l = new int[count]`. Offsets 608 to 374 and 358 to 371: `l[i] = readUnsignedShort()` for each entry. Offsets 655 to 691: `l[i] += readUnsignedShort() << 16` for each entry. So the file ids come first and the group ids second, as in opcode 1. Evidence. The toolkit decoder (`frames.py` line 181 to 184) reads the same layout.

Opcode 1 for comparison (offsets 242 to 167): a u16 count, `count` u16 frame lengths (`jg.s`), `count` u16 file ids, then `count` u16 group ids (`jg.e`). Evidence.

## `ip.e` builds the NPC head

| Offsets | What the code does |
| --- | --- |
| 0 to 12, 386 to 394, 151 to 94 | When `configs` (`ip.ap`) is not null: `ip.l()` (`transform`, by varbit or varp). Null gives null, otherwise return the transformed NPC's `e()`. |
| 58 to 81 | `ip.w` is null: return null. |
| 339 to 348, 117 to 161 | When any model of `ip.w` is not loaded in `gw.j` (`if.v`, `tryLoadRecord`): return null. |
| 185 to 194, 222 to 336 | Load each id of `ip.w` with `dv.a(gw.j, id, 0)`. |
| 252 to 293 | One model is used as it is. More are joined with `new dv(dv[], n)`. |
| 28 to 114, 197 to 214, 351 | `dv.c(colors[i], modifiedColors[i])` for each pair of opcode 40 (`ip.o`, `ip.x`). |
| 357 to 419 | `dv.o(textureToReplace[i], textureToReplaceWith[i])` for each pair of opcode 41 (`ip.f`, `ip.h`). |
| 422 | Return. |

There is no `dv.h` (resize) in `ip.e`. The world model `ip.v` reads `widthScale` and `heightScale` (`ip.b`, `ip.q`) at offsets 656 to 734. Evidence.

## `ip.r` opcode 60 is the head model list

Offsets 633 to 704: `count = readUnsignedByte()`, `ip.w = new int[count]`, then `w[i] = readUnsignedShort()` for each entry. Evidence. So the field that the mapper calls `additionalModels` (`ip.w`) holds the chathead models. The toolkit skips `2 * count` bytes there, which is the right length. A decoder that keeps them reads one u8 count and then `count` u16 model ids, and builds the head as above: the same recolours and retextures as the body, no resize.

## `hu.s` builds the player head

| Offsets | What the code does |
| --- | --- |
| 0 to 42 | When `transformedNpcId` (`hu.r`) is not -1: return `hf.a(r).e()`, the NPC head. |
| 43 to 167, 281 to 293, 483 to 491, 368 to 389 | For each of the 12 slots `v = equipmentIds[i]` (`hu.a`): for 256 <= v < 512 check `ij.j(v - 256).l()` (kit head ready), for v >= 512 check `cu.j(v - 512).c(isFemale)` (item head ready). |
| 78 to 82, 230 | Something not ready: return null. |
| 221 to 227, 416 to 440 | `parts = new dv[12]`, `n = 0`. |
| 525 to 534, 301 to 365 | For each slot: v < 256 is skipped. A kit gives `ij.j(v - 256).s()`, kept when not null. |
| 390 to 430 | An item gives `cu.j(v - 512).o(isFemale)`, kept when not null. |
| 170 to 180 | `new dv(parts, n)`. |
| 443 to 466, 232 to 254 | For each of the 5 colour slots: when `j[i] < gw.s[i].length`, `dv.c(hu.l[i], gw.s[i][j[i]]`). |
| 494 to 508, 193 to 215, 537 | Then, when `j[i] < cd.p[i].length`, `dv.c(hu.w[i], cd.p[i][j[i]]`). |
| 543 | Return. No light, no resize. |

`client.aa` (offsets 150 to 180) and its copies set `gw.s = hv.j`, `hu.l = hv.a`, `cd.p = hv.r` and `hu.w = hv.n`. These are the four tables of `revision149-palette.json` (`primary_choices`, `primary_sources`, `secondary_choices`, `secondary_sources`). `hu.l` (the body, offsets 332 to 352 and 838 to 858) runs the same two passes with the same tables. Evidence. So the head takes the same palette recolours as the body, in the same order: per colour slot the primary pass, then the secondary pass, and a choice past the end of a row changes nothing.

The head reads `equipmentIds` as they are. It has no sequence, so the held-item swap of the body (`hu.l` offsets 228 to 276, `jg.t` into slot 3 and `jg.k` into slot 5) does not happen. Evidence. `hu.s` drops no slot by itself: a slot is empty only when the equipment value is below 256, as for the body. Evidence. The hiding of hair or jaw under a helmet is in the appearance data, not in `hu`. Guess: this agrees with the covers toggles of `appearance.py`, which empty the slot value.

## `it.s` builds the kit head

| Offsets | What the code does |
| --- | --- |
| 0 to 5, 253 to 255, 151 to 154 | `parts = new dv[5]`, `n = 0`. |
| 17 to 73, 208 to 228 | For i in 0 to 4: when `m[i] != -1`, `parts[n++] = dv.a(it.j, m[i], 0)`. |
| 76 to 85 | `new dv(parts, n)`, always, also for 0 or 1 part. |
| 87 to 126, 231 to 250 | `dv.c(recolorToFind[i], recolorToReplace[i])` (`it.l`, `it.s`, opcode 40). |
| 157 to 207, 129 to 148 | `dv.o(retextureToFind[i], retextureToReplace[i])` (`it.w`, `it.p`, opcode 41). |
| 14 | Return. No resize. |

`it.l()` (head ready) checks the same five ids with `if.v`. `it.<init>` (offsets 23 to 46) sets `m = {-1, -1, -1, -1, -1}`. `it.r` (offsets 362 to 371, 265 to 268, 320 to 335) reads opcodes 60 to 69 as `m[opcode - 60] = readUnsignedShort()`. Evidence. Opcodes 65 to 69 would index past the 5 entries. Guess: no cache kit uses them, as `kit_definition.py` says. The mapper's `it.m` (`models`) is the chathead list, which the toolkit stores as `chathead_models`.

A kit with no head model still gives an empty `dv` (not null), so it adds no faces. Evidence (offsets 76 to 85).

## `iz.o` builds the item head

| Offsets | What the code does |
| --- | --- |
| 0 to 8, 284 to 292 | `a = maleHeadModel` (`iz.as`), `b = maleHeadModel2` (`iz.av`). |
| 33 to 70 | Female: `a = femaleHeadModel` (`iz.ab`), `b = femaleHeadModel2` (`iz.at`). |
| 111 to 129 | `a == -1`: return null, so the slot adds nothing. |
| 81 to 108, 145 to 140 | Load `a` from `iz.l`. When `b != -1`, load it too and join both with `new dv(dv[], 2)`. |
| 12 to 16, 164 to 213 | `dv.c(colourToReplace[i], colourToReplaceWith[i])` (`iz.o` field, `iz.x`). |
| 240 to 272 | `dv.o(textureToReplace[i], textToReplaceWith[i])` (`iz.f`, `iz.h`). |
| 275 | Return. |

There is no resize and no offset. The worn model `iz.k` moves its model by the body type offset with `dv.g(III)` at offsets 305 and 424 (`iz.aa`, `iz.ax`), and `iz.o` has no such call. Evidence.

`iz.v` (the decoder) stores the four fields, each as `readUnsignedShort()`:

| Opcode | Offsets | Field |
| --- | --- | --- |
| 90 | 504 to 514, 1082 to 1092 | `iz.as`, male head |
| 91 | 820 to 829, 1119 to 1129 | `iz.ab`, female head |
| 92 | 1135 to 1145, 1337 to 1348 | `iz.av`, male head 2 |
| 93 | 1175 to 1199 | `iz.at`, female head 2 |

Evidence. The toolkit's `item_definition.py` line 61 reads and drops these four.

## `je.ic` advances the widget animation

`client.gg` offset 1024 calls `je.ic(hy.e[root], -1)`. `je.ic` walks the widgets of a parent and calls itself for children. Evidence. For each widget of type 6 (`hy.h`, offset 352):

| Offsets | What the code does |
| --- | --- |
| 749 to 761, 398 to 407 | Both `sequenceId` (`hy.bw`) and `sequenceId2` (`hy.bg`) are -1: no animation. |
| 424 to 433, 81, 339 to 349, 736 to 746 | `active = ds.ii(widget)`. The sequence is `bg` when active, else `bw`. -1 means no animation. |
| 495 to 504 | `seq = du.j(id)` (`getAnimation`). |
| 379 to 392 | `modelFrameCycle` (`hy.eu`) `+= client.gb`. |
| 531 to 553 | While `modelFrameCycle > frameLengths[modelFrame]` (`jg.s`): |
| 120 to 144 | `modelFrameCycle -= frameLengths[modelFrame]`, |
| 579 to 588 | `modelFrame` (`hy.ea`) `+= 1`, |
| 150 to 164 | when `modelFrame < frameIDs.length`, redraw (`ay.ir`) and test again, |
| 597 to 623, 100 to 117, 570 to 576 | else `modelFrame -= frameStep` (`jg.p`). When the result is below 0 or not below `frameIDs.length`, `modelFrame = 0`. |

`jg.<init>` sets `frameStep` to -1 (offset 5, decoded), so with no opcode 2 the frame goes past the end and restarts at 0. So a widget animation always loops. `je.ic` reads no other sequence field: `maxLoops`, `replyMode`, `stretches` and the interleave list have no effect here. Evidence.

`et.if` (offsets 8251 to 8259, 8219 to 8233, 2434 to 2443, 8556 to 8588) picks the same sequence with the same `ds.ii` test and passes `hy.ea` as the frame to `hy.u`. Evidence.

`client.gb` counts client cycles: `client.fr` adds 1 to it (offsets 3071 to 3078), and `client.gg` sets it to 0 (offsets 1869 to 1870). Evidence. `client.fr` is called once per client cycle of 20 ms. Guess, from RuneLite, not proven here. So the frame lengths are in 20 ms client cycles, as for other sequences.

When a script or packet sets a new sequence, it sets `modelFrame = 0` and `modelFrameCycle = 0` (`fn.v` offsets 1112 to 1131). Evidence. On the first pass `modelFrameCycle` must pass the length, so frame 0 shows for its length plus one cycle, and each later frame for its length. Evidence (the test at 531 to 553 is `>`, not `>=`).

When `bu` is not 0 (offsets 689 to 697, 640 to 653, 463 to 479, 764 to 832), the widget also turns: `rotationX += (bu >> 16) * gb` and `rotationZ += (short) bu * gb`, each `& 2047`. Evidence. This is the model spin, not the sequence.

## Chat sequence names

From `<osrs-dumps>/symbols/seq.sym`, the names that start with `chat` in the main block are 554 to 617: quiz 554-557, skull 558-561, bored 562-565, hap 567-570, shock 571-574, con 575-578, goblin 580-583, ent 584-587, neu 588-591, shifty 592-595, scared 596-599, drunk 600-603, laugh 605-608, sad 610-613, ang 614-617. The ids 566, 579, 604 and 609 in that block are not chat sequences. Other `chat` names: chateasterbunny4 451, chat_baffled 1182, chat_baffled_idle 1187, chatchant1 1637, chathand1-4 4119-4122, and many from 7175 up (13949 to 13989 are the newer `chat_*` and `*_idle` set).

`animation_names.json` keeps no id from 554 to 617. Its `source` says it holds only sequences whose frames all use frame map 0 (the player body). Guess: the chat sequences use a head frame map, so the generator leaves them out.

## Conclusion

A chathead is a widget model of type 2 (NPC) or 3 (player). Its model data is `ip.e` or `hu.s`: the head models (NPC opcode 60, kit opcodes 60 to 64, item opcodes 90 to 93) joined, with the definition's recolours and retextures, and for the player the same palette passes as the body. There is no resize and no item offset. The model is lit with `(64, 768, -50, -10, -50)`. The animation applies `frameIDs[f]` and then `chat_frames[f]` to the same model. The frame advances by the `frameLengths` of the sequence in client cycles and always loops (back by `frameStep`, or to 0).
