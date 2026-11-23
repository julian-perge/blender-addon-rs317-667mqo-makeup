# The spot animation (spotanim) in gamepack 149

Checked on 2026-11-22 with `javap -p -c` on the revision 149 gamepack (SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`, the same jar as [item-light.md](item-light.md)). The offsets below are bytecode offsets of the obfuscated classes. The real names come from [client-names.tsv](client-names.tsv), with the rows that this note adds. The file name of the snapshot 430 map in the data workspace says `b149`, so snapshot 430 is the cache of this client.

Obfuscated int fields are stored as `value * E` and read as `field * G`, where G is the inverse of E modulo 2^32. The table gives the getter multiplier G. The products `E * G` were computed and are 1 for every field below (Evidence).

## `ii.r(LBuffer;II)V` is the decoder

`ii.n(fe, int)` (`decode`) reads an opcode with `fe.z` (`readUnsignedByte`) and calls `ii.r` until the opcode is 0 (offsets 0 to 34). `io.j` (`getSpotAnimType`) calls `ii.n` at offset 38. No method calls `ii.k`, `ii.c`, `ii.o`, `ii.g`, `ii.p`, `ii.m` or `ii.u`: they are dead copies (Evidence: no `invoke` of them in the jar).

| Opcode | Offsets of `ii.r` | Read | Field | Getter G | Meaning |
| --- | --- | --- | --- | --- | --- |
| 1 | 0 to 8, 94 to 107 | `readUnsignedShort` | `e` | -1253440665 | model id |
| 2 | 40 to 72 | `readUnsignedShort` | `l` | 1325085135 | sequence id |
| 4 | 75 to 83, 145 to 158 | `readUnsignedShort` | `u` | -1850619791 | resize horizontal (x and z) |
| 5 | 110 to 142 | `readUnsignedShort` | `g` | 1816141671 | resize vertical (y) |
| 6 | 251 to 260, 161 to 174 | `readUnsignedShort` | `k` | 1695575337 | rotation in degrees (0, 90, 180, 270) |
| 7 | 177 to 202 | `readUnsignedByte` | `t` | -1785558529 | ambient |
| 8 | 205 to 237 | `readUnsignedByte` | `c` | 1738665771 | contrast |
| 40 | 344 to 353, 441 to 448, 240 to 248, 288 to 331 | count `readUnsignedByte`, then pairs of `readUnsignedShort` cast to short | `s` (find), `w` (replace) | - | recolours |
| 41 | 364 to 370, 334 to 341, 387 to 438 | count `readUnsignedByte`, then pairs of `readUnsignedShort` cast to short | `p` (find), `m` (replace) | - | retextures |

Any other opcode goes to offset 302 (`return`) and reads nothing (Evidence). The constructor `ii.<init>` sets `l` to -1, `u` and `g` to 128, and `k`, `t` and `c` to 0 (offsets 7 to 53, the stored constants times the getter multipliers).

For the ambient and the contrast, the encode multiplier is exactly the inverse of the getter multiplier. So the client holds the raw unsigned byte for both, with no factor (Evidence). This is not the same as the item, where the contrast is 5 times the byte and the ambient is a signed byte ([item-light.md](item-light.md)).

### The JSON of snapshot 430

`<data workspace>/exports/osrs/openrs2-430/dump/spotanims/SpotAnimDefinitions.json` has 1388 entries with the keys `id`, `modelId`, `animationId`, `resizeX`, `resizeY`, `rotaton` (sic), `ambient`, `contrast`, `recolorToFind`, `recolorToReplace`, `fullRecolor` and `clickable`. No entry has retextures. The keys match `SpotAnimDefinition.java` and `SpotAnimLoader.java` in `<data workspace>/legacy/rs2/build-667/models-and-references/runelite-src`, which read opcodes 7 and 8 with `readUnsignedByte` and store them raw (Evidence: the loader source). So the JSON values of `ambient` and `contrast` are the values that the client uses. The ambients in the JSON are 0 to 192 and the contrasts 0 to 144. That loader also knows opcodes 3, 9, 10 and 42 of later RS2 caches. The 149 client does not. In the JSON, `fullRecolor` is -1 and `clickable` is true for every entry, so these opcodes do not occur in snapshot 430 (Evidence).

## `ii.v(IB)Lej;` is `Spotanim.getModel(frame)`

The players, the NPCs, the graphics objects and the projectiles call `ii.v` (`be.n`, `ch.n`, `cy.n`, `ci.n` and their copies `k()`). No method calls `ii.x(I)Lej;`. It is a copy with the same light constants. This note uses `ii.v`.

| Offsets | What the code does |
| --- | --- |
| 0 to 18 | Get the lit model from the cache `ii.r` with the key `id` (`ii.v`). |
| 39 to 55 | On a miss: `dv.a(ii.j, e, 0)` loads the ModelData of `modelId`. When it is null, the method returns null (64). |
| 66 to 151 | For each recolour pair: `dv.c(s[i], w[i])` (`recolor`). |
| 154 to 223 | For each retexture pair: `dv.o(p[i], m[i])` (`retexture`). |
| 226 to 255 | `dv.ae(64 + ambient, 850 + contrast, -30, -50, -30)` (`ModelData.light`). The result is a Model. |
| 422 to 437 | Put the lit Model in the cache `ii.r`. |
| 95 to 103, 278 to 283 | When `sequence` is not -1 and `frame` is not -1, go to 513. Else go to 292. |
| 513 to 532 | `du.j(sequence)` (`getAnimation`), then `jg.s(litModel, frame)` (`transformSpotAnimModel`). |
| 292 to 297 | No animation: `litModel.r(true)` (`toSharedSpotAnimModel`), a copy that shares the face data. |
| 299 to 377 | When `u` or `g` is not 128: `ej.i(u, g, u)` (`scale`) on the copy. |
| 265 to 275, 397 to 510 | Rotation: 90 calls `ej.c` once (461), 180 twice (453, 87), 270 three times (495 to 507). 0 and other values: no call. Then return the copy (262). |

So the order is: load, recolour, retexture, light, cache, animate (on a copy), scale, rotate (Evidence). The client lights the ModelData before the frame transform. The animation moves the vertices of the lit Model. `ej.m` (the animate method) calls only `ej.g` and `ej.p` (`resetBounds`), so the face colours stay those of the rest pose (Evidence for the calls; Guess that `ej.g` changes only vertex positions, from the RuneLite meaning of `Model.animate`).

`ej.i(a, b, c)`, offsets 7 to 66: `x = x * a / 128`, `y = y * b / 128`, `z = z * c / 128` with Java integer division (rounds toward zero). The arrays are `ej.e`, `ej.l` and `ej.s`. The call passes `(u, g, u)`, so `resizeX` scales x and z and `resizeY` scales y (Evidence).

`ej.c()`, offsets 6 to 63: for each vertex, `t = x; x = z; z = -t` (Evidence).

## `jg.s(Lej;II)Lej;` is `transformSpotAnimModel`

| Offsets | What the code does |
| --- | --- |
| 0 to 6 | `frame = frameIDs[frame]` (`jg.e`). The index is the spotanim frame, used plainly. There is no interleave (`jg.m`) and no second sequence (Evidence). |
| 80 to 91 | `cd.m(frame >> 16)` (`getFrames`): the frame archive. |
| 72 to 77 | `frame = frame & 0xFFFF`: the file in that archive. |
| 21 to 47 | When the archive is not loaded: return `model.r(true)`, the rest pose. |
| 48 to 69, 10 to 20 | Else `copy = model.r(!frames.a(frame))`, then `copy.m(frames, frame)` (animate) and return the copy. `et.a` tells if the frame changes the alpha (Guess from RuneLite `Frames.hasAlphaTransform`). |

## How the actor draws the spotanim

The renderer calls `n(B)Lej;` (`ef.ci`, `ef.cf`, `ef.cl`, `ef.cd`, `ef.cb`, `ef.co` call `n` at offset 3). No method calls `k()Lej;`, so `be.k` and `ch.k` are dead copies (Evidence).

`be.n(B)Lej;` (Player.getModel):

| Offsets | What the code does |
| --- | --- |
| 46 to 75 | `hu.l(...)`: the player body model, kept in local 4. |
| 275 to 317 | Go on only when `graphic` (`ca.bg`, G = -1949670241) is not -1 and `spotAnimFrame` (`ca.bt`, G = 102541571) is not -1. |
| 151 to 175 | `io.j(graphic).v(spotAnimFrame)`: the spotanim model, local 5. |
| 333 to 365 | When it is not null: `spot.z(0, -spotAnimHeight, 0)` (`offsetBy`). `spotAnimHeight` is `ca.bf` (G = 750881445). |
| 936 to 952, 371 to 383 | `new ej(new ej[]{body, spot}, 2)`: one Model made from the two. |

`ch.n(B)Lej;` (NPC.getModel) does the same at 86 to 110 (`ii.v`), 353 to 365 (`ej.z(0, -bf, 0)`) and 368 to 374 and 191 to 201 (the join) (Evidence).

The game y axis points down, so `-spotAnimHeight` lifts the spotanim (Evidence for the sign in the code; the axis direction is the usual RS convention). The client does not rotate the spotanim with `ca.cs` (`orientation`) in `getModel`. The `ej.c` calls in `be.n` that read `cs` (587 to 870) act on `be.t`, a different attached model. The joined Model is drawn with the actor's orientation by the renderer, so the spotanim turns with the actor (Guess, the draw call was not read).

### Where the height and the delay come from

The player update block `dq.j` (mask 512, offsets 2385 to 2532) and the NPC update block `af.hd` (1224 to 1324) read:

* `graphic = readUnsignedShort`, and 65535 becomes -1 (`dq.j` 2506 to 2532, `af.hd` 1305 to 1324).
* An int `v`. `spotAnimHeight = v >> 16` (`dq.j` 2433 to 2444). `graphicsDelay = gameCycle + (v & 0xFFFF)` (2447 to 2465).
* `spotAnimFrame = 0` and `spotAnimFrameCycle = 0` (2468 to 2477). When `graphicsDelay > gameCycle`, `spotAnimFrame = -1` (2480 to 2503), so nothing is drawn during the delay.

`cp.p`, `cp.m` and `cp.w` hold the same code with other multipliers, and no method calls them (Evidence).

## `ap.fb(ca, int, int)` advances the frame

`client.fr` calls `ap.fb` (Evidence). That it runs once per actor for each client cycle of 20 ms is a Guess from the RuneLite meaning of `gameCycle`. The spot part, in the order the jumps run:

| Offsets | What the code does |
| --- | --- |
| 1895 to 1904 | When `graphic` is -1: skip. |
| 1922 to 1937 | When `gameCycle < graphicsDelay` (`ca.br`, G = 1767555021): skip. |
| 1136 to 1144, 1965 to 1967 | When `spotAnimFrame < 0`: set it to 0. |
| 2094 to 2116, 1988 to 2009 | `seq = io.j(graphic).l`. When it is -1: `graphic = -1` (2238). Else `du.j(seq)`. |
| 655, 2033 to 2042 | When the sequence or its `frameIDs` is null: `graphic = -1` (2228). |
| 758 to 767 | `spotAnimFrameCycle += 1` (`ca.bz`, G = 1419504763). |
| 2062 to 2076, 1860 to 1882 | When `spotAnimFrame < frameIDs.length` and `spotAnimFrameCycle > frameLengths[spotAnimFrame]` (`jg.s` the int array): |
| 2119 to 2166 | `spotAnimFrameCycle = 1`, `spotAnimFrame += 1`, then `u.fi` (`queueAnimationSound`) for the new frame. |
| 623 to 644, 2175 to 2225 | When `spotAnimFrame >= frameIDs.length` (or below 0): `graphic = -1`. |

So each frame shows for `frameLengths[i]` client cycles. After the last frame the spot effect stops: the client sets `graphic` to -1 in the same cycle. It does not loop, and it does not use `frameStep` or `maxLoops` (Evidence).

## Smoke, steam and splash spotanims in snapshot 430

There is no spotanim symbol file in `<osrs-dumps>/symbols`. `<osrs-dumps>/config/dump.spot` names the spotanims of a current cache. For every id below, the model and the sequence in `dump.spot` are the same as in the JSON of snapshot 430, so the names fit (Evidence). The frame counts and the frame lengths come from `<osrs-dumps>/config/dump.seq`, a current cache. That they are the same in snapshot 430 is a Guess.

| Id | Name | Model | Seq | Frames (sum of lengths) | resizeX, resizeY | Ambient, contrast | Recolours |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 86 | smokepuff | 3076 | 654 | 12 (47) | 128, 128 | 0, 0 | none |
| 188 | smokepuff_large | 3076 | 654 | 12 (47) | 256, 128 | 0, 0 | none |
| 931 | small_smokepuff | 9598 | 5205 | 12 (23) | 96, 96 | 60, 60 | none |
| 469 | steam_head_spotanim | 9915 | 2834 | 11 (30) | 128, 128 | 0, 0 | none |
| 484 | ratcatcher_smoke | 10057 | 2896 | 24 (124) | 128, 128 | 30, 30 | none |
| 671 | royal_steam_spotanim | 15098 | 4027 | 25 (99) | 128, 128 | 10, 0 | none |
| 797 | slug2_human_smoke | 18427 | 4836 | 35 (105) | 128, 128 | 0, 0 | none |
| 68 | watersplash | 2223 | 465 | 10 (31) | 128, 128 | 0, 0 | none |

All have `rotaton` 0. Other splashes reuse model 2223 with a recolour, for example 69 lavasplash (-22299 to 5058).

## Conclusion

A spotanim model is `ModelData(modelId)`, recoloured and retextured, lit with `(64 + ambient, 850 + contrast, -30, -50, -30)` where both values are raw unsigned bytes, then animated with `frameIDs[frame]` of its sequence, then scaled by `(resizeX, resizeY, resizeX) / 128`, then turned by `rotation / 90` calls of `(x, z) = (z, -x)`. On an actor it moves up by `spotAnimHeight` (`ej.z(0, -height, 0)`) and joins the actor model. It plays each frame for its frame length in client cycles once, then stops.

For a first test on a player, use 86 (`smokepuff`): 12 frames, no recolour, no resize and no light change, and its name and its use with teleports suggest that the client draws it on players (Guess). Use 931 (`small_smokepuff`) as a second test, because it has a resize of 96 and an ambient and a contrast of 60.
