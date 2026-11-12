# Model formats: findings from the game clients

## Reference sources

Use the source that matches the question. RuneLite is a port, so where it and a client disagree, the client wins.

| Source | Location | Use it for |
| --- | --- | --- |
| 317 client, Vineflower decompile | `<data workspace>/decompiled-clients/src317.zip` (from `runescape-b317-2005-06-13-12-56-24-openrs2#33303.jar`) | old-format rules, face colour palette, alpha and priority conventions |
| 667 client model class `dv`, CFR decompile | `<data workspace>/decompiled-clients/out-cfr/dv.java` (from `runescape-b667-2011-09-29-13-06-20-openrs2#31169.jar`) | new-format layout, flags, versions, complex textures |
| 2018 Old School client, decompiled with names | `<RuneLite May 2018 tree>/runescape-client/src/main/java/` | the client's own decoder, rasteriser, lighting, animation |
| RuneLite 1.13.6 cache library | `<data workspace>/runelite-1.13.6-sources/` (unzipped from `~/.m2/repository/net/runelite/cache/1.13.6/cache-1.13.6-sources.jar`; unzip more classes from there as needed) | the code behind the `<id>.json` reference files, which `ModelReference.java` runs |
| RuneLite 1.3.9 (May 2018) tree | `<RuneLite May 2018 tree>/cache/`, `model-viewer/` | the item icon renderer and older loaders |
| Revision 1 Old School client | <https://github.com/Shadowrs/osrs-refactor-revision-1> (obfuscated names) | Old School behaviour at launch |
| 667 models | `<data workspace>/rs667-models/models/`, extracted by `extract_js5_index.py` beside them | 667 fixtures and scans |
| Old School models, textures, icons | `<data workspace>/dump/` | Old School fixtures, scans, visual checks |

The `.pack200` and `.js5` (packclass) client downloads were not needed: the plain `.jar` holds the same classes. To reproduce the 667 decompile: `cfr-decompiler <class>.class --extraclasspath client667.jar --outputdir out-cfr` (Homebrew's `cfr-decompiler`, CFR 0.152), run on single extracted classes so the case-insensitive macOS file system cannot drop classes such as `dd` and `dD`. Vineflower 1.10 to 1.12 cannot decompile the 667 decoders. In the 317 decompile, the class reading the 18-byte old-format footer is `ZKARKDQW` (`var3.z = var0.length - 18`, line 130 of `ZKARKDQW.java`).

Line numbers in the 667 sections refer to `dv.java`.

## OSRS revision 149: snapshot-430 reference gate

Use the [versioned field contract](../../tests/fixtures/models/osrs149/contract.md)
and [replay instructions](../../tests/fixtures/models/osrs149/README.md) for the
July-2017 OSRS profile. The independently archived gamepack's internal handshake
identifies revision 149; its SHA-256 is
`19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`.
Its association with the exact snapshot-430 binary is indirect. Checked on 2026-11-07: OpenRS2's `caches.json` lists archive 430 as game `oldschool`, build major 149, timestamp 2017-07-13, with 17 of 17 indexes and 49,264 of 49,264 groups valid; the jar's signed entries are dated 2017-07-06, and its client class passes the literal 149 to its applet setup (`sipush 149` beside 765 by 503, `osrs149-reference-client.javap` line 2126). OpenRS2 does not publish which gamepack belongs to snapshot 430, so the pairing rests on the equal build number, dates one week apart, and the client reproducing the cache's bodies and outfits exactly.

The selected 180 real models have records from the unchanged RuneLite loader,
a separate source-section reader, and actual revision-149 `dv(byte[])` followed
by `dv.ae(64,768,-50,-10,-50)`. Geometry, new-format colours, textures, render
bytes, alpha, priorities, labels and coordinates were compared with the client
constructor. Footer flags, texture parameters and tails come from the separately
pinned source-section reader. Untextured
coordinate slots are normalized to -1 rather than the client's unused zeroes.

The actual `dv.ae` conversion retains referenced type-zero texture records only.
Other mappings become -1; `ej.au` then uses the face's own corners. Do not apply
667 complex-projection interpretations to this profile. The source still owns
every record and its parameter bytes, including unused records and independent
textured colours. Type-two records contain 13 parameter bytes; types one/three
contain 11. Their meanings and the nonzero tail payloads remain uninterpreted.

`ej.t == -2` marks a hidden face. Stored render type 2 is hidden unless alpha
overrides it; alpha 255 forces effective type 2 and alpha 254 forces type 3.
Type 3 is flat when untextured and hidden when textured. The selected files
exercise stored type 2 and both alpha overrides; the textured type-3 branch is
verified bytecode rather than an observed snapshot-430 case. Exact method offsets
are in [source findings](../../.scratch/osrs-focus/evidence/reference-source-findings.md).

Both this client and RuneLite have the item-8283 alpha-254 neighbor-read overflow.
The [approved repair policy](../adr/0002-icon-buffer-edge-policy.md) supplies
transparent zero only outside the framebuffer. Its expected PNG comes from an
unchanged rasterizer with one guard cell; it is not an original game pixel.

## 667 client: choosing the format

The `dv(byte[])` constructor calls the new-format decoder `a(byte[], boolean)` when the last two bytes are both `-1` (`FF FF`) and the old-format decoder `a(int, byte[])` otherwise.

## 667 client: new-format footer (lines 279 to 302)

The footer starts 23 bytes before the end of the file, in this order:

| Bytes | Field |
| --- | --- |
| 2 | vertex count |
| 2 | face count |
| 1 | texture triangle count |
| 1 | flags |
| 1 | priority: 255 means one priority per face, any other value is the priority of every face |
| 1 | has face alphas |
| 1 | has face skins |
| 1 | has textures |
| 1 | has vertex skins |
| 2 each | lengths of the x, y and z vertex data, the face index data and the texture coordinate data |
| 2 | marker `FF FF` |

Flags:

- bit 1: the file has a face render type per face.
- bit 2: extra sections after the texture data (the decoder reads two counted lists of short pairs, lines 621 to 645). Their meaning is unconfirmed.
- bit 4: another extra section after those (lines 646 to 655), a counted list of two shorts, a byte and a signed byte. Its meaning is unconfirmed.
- bit 8: the byte just before the footer (23 + 1 bytes from the end) is a format version. Without bit 8 the version is 12 (field initializer `this.h = 12`).

## 667 client: texture triangles

Each texture triangle starts with a render type byte at the very start of the file (lines 306 to 324): 0 for a PMN triangle, 1 to 3 for complex textures (the decoder counts 2 separately because it carries two more bytes).

For complex textures, the scale fields that follow P, M and N are sized by the format version (lines 361 to 365 and 570 to 615):

| Version | Scale fields |
| --- | --- |
| below 14 | three 2-byte values (6 bytes) |
| 14 | 2 bytes, 3 bytes, 2 bytes (7 bytes) |
| 15 and above | three 3-byte values (9 bytes) |

Then come one byte each for rotation, direction and speed, read from three separate sections. Render type 2 also reads two more bytes from the speed section.

Across the 63,198 new-format models in the 667 cache, only versions 12, 14 and 15 occur:

| Flags bits 1 and 8 | Version | Models |
| --- | --- | --- |
| neither | 12 | 26,082 |
| bit 1 only | 12 | 7,351 |
| bit 8 only | 14 | 1,363 |
| bit 8 only | 15 | 18,672 |
| both | 14 | 645 |
| both | 15 | 9,085 |

RuneLite decodes almost every bit-8 model without crashing, so the version-dependent scale size does not by itself explain its failures. It crashes on every model with both bits set and on about 30% of models with complex textures and no version byte. The cause is still unknown; comparing RuneLite's `decodeType1` with lines 325 to 370 here is the next step.

## 317 client: old-format priority and alpha

Both are from the Vineflower decompile in `<data workspace>/decompiled-clients/src317.zip`.

- Priority: the footer's priority byte creates a per-face priority array only when it is 255. Any other value becomes one priority for the whole model: the header stores it as `-priority - 1` (`ZKARKDQW.java` around line 168) and the model reads it back with `this.N = -var3.n - 1` (line 357).
- Alpha: the face alpha array `this.L` exists only when the footer's alpha flag is set (line 360). When drawing a face, the model sets the rasterizer's alpha to 0 if that array is missing and to the face's value otherwise (line 4272). The rasterizer `OPPOFIOL` draws solid when alpha is 0 and otherwise blends `new pixel * (256 - alpha) + screen pixel * alpha` (lines 1429 to 1476). So 0 is opaque, 255 is nearly fully transparent, and a model without an alpha section is opaque.

## 317 client: face colour to RGB

The palette builder is in `OPPOFIOL.java` (lines 470 to 700, with the brightness curve at line 744). For each 16-bit face colour:

- hue = `(colour >> 10) / 64 + 1/128`, saturation = `((colour >> 7) & 7) / 8 + 1/16`, lightness = `(colour & 127) / 128`, each offset to the middle of its band.
- These go through standard HSL to RGB, with each channel truncated to `int(c * 256)`.
- Each channel then becomes `int((c / 256) ** brightness * 256)`. Brightness is the display setting, 0.9, 0.8, 0.7 or 0.6 (`client.java` lines 4072 onwards), and the client starts at 0.8 (`client.java` line 15624, after "Unpacking textures"); the client also adds a random offset of up to 0.015 each time it rebuilds the palette.
- A result of pure black becomes `0, 0, 1`.

RuneLite's `JagexColor.HSLtoRGB` follows the same steps. `rsps_toolkit.formats.face_colour_to_rgb` matches it exactly on 1,076 sampled colours at all four brightness settings (`tests/fixtures/colours.json`).

The old add-on's `rune_hsl_to_rgb` treated lightness as HSV value, left out the band offsets and the brightness curve, and returned grey for colour 0. The refactor fixed that conversion.

Face colour 0 is right to look black: the client's lighting function (`ZKARKDQW.java` line 3320 onward) multiplies the light by the colour's lightness, which gives 0, then raises it to the minimum of 2 of 127, with hue and saturation 0. On tree model 5452 that is the mouth.

## 2018 Old School client (RuneLite 1.3.9 source dump)

`<RuneLite May 2018 tree>/` is a May 2018 RuneLite source tree (1.3.9-SNAPSHOT, not a git repository). It covers Old School only: nothing in it reads the 317 cache or the 667 format. Its `runescape-client/src/main/java/` is the decompiled game client, with many names restored through `@Export`, so it is easier to read than the revision 1 source.

- `ModelData.java` is the client's own model decoder: `decodeOldFormat` at line 779, `decodeNewFormat` at line 423, and the choice between them by the `FF FF` footer marker at line 334. It can serve as a second reference for Old School models besides RuneLite's port.
- `Model.java` sorts faces into 12 buckets by render priority (line 189, loop at line 1216), which confirms that render priority runs 0 to 11.
- `Model.java` line 869: animation transform type 5 adds `delta * 8` to the alpha of every face in the listed face skins, clamped to 0 to 255. This confirms that face skins drive alpha animation. No transform that changes face colour was found.
- `ModelData.light()` at line 1538 shades face colours from ambient, contrast and a light direction when the client turns model data into a drawable model.
- `Frames.java`, `Frame.java` and `FrameMap.java` show how animation frames move vertices by vertex skin label.
- `cache/.../item/ItemSpriteFactory.java` renders item icons in software. It sets brightness 0.6 (line 119) and lights the model with ambient `item.ambient + 64`, contrast `item.contrast + 768` and light direction `-50, -10, -50` (line 216). Item icons are therefore drawn at brightness 0.6, while the Blender import defaults to the 317 client's starting value 0.8 (a preference), which matters when comparing imports against icons.
- `Graphics3D.rasterTextureAffineLine` (line 2050) sets u and v to 0 wherever the perspective divisor is 0. The divisor comes from the cross product of the texture triangle's edges, so a texture triangle whose corners lie on one line samples texel (0, 0) across the whole face. `ModelData.java` line 1032 drops a face's texture triangle when it has the face's own corners, and the face then uses its own corners as P, M and N.
- `cache/.../definitions/ModelDefinition.java` line 150, `computeTextureUVCoordinates()`, is RuneLite's conversion of texture triangles into face UVs. The 1.13.6 copy (line 155) is what the `face_texture_u` and `face_texture_v` reference values come from.
- `model-viewer/.../ModelViewer.java` line 322 draws faces of a model without an alpha section, and faces with alpha 0, at OpenGL alpha 255 (opaque). That agrees with the 317 client's convention that alpha 0 is opaque.
- `cache/.../loaders/ModelLoader.java` is an older copy of the loader the fixtures already use; its new-format footer has the same layout, so it is no better a reference for 667.

## Old School revision 149 in this add-on (cache 430)

Measured against cache 430 and the Gate 0 fixtures; see [the OSRS cache workflow](../osrs-cache-workflow.md).

- The `FF FF` footer layout is decoded by `formats/new_format.py` with the explicit `osrs-149` profile. It keeps the
  render type of every face, the independent colour of every textured face, every texture record with its kind and
  parameter bytes, the opaque tail and the footer section flags.
- Only texture records of kind 0 are taken to hold vertex numbers.
  The OSRS client at revision 170 (`runescape-client` in RuneLite, `ModelData.java` lines 1559 to 1590) copies only
  kind 0 records into the drawable model and gives faces of kinds 1 to 3 no texture triangle, so `Model.java` line
  1370 draws them with their own corners as P, M and N. The preview does the same. Revision 149 is checked too:
  `dv.ae` keeps only kind 0 records and `ej.au` copies a face's own corners when it has no retained record
  (`.scratch/osrs-focus/evidence/reference-source-findings.md` items 3 to 5), though the render-level Gate 0
  comparison still needs a client run. RuneLite's `computeTextureUVCoordinates` (line 150) leaves those faces' UVs at zero, so it is no
  reference for them. The texture tools still refuse to edit those faces.
- 17 of 5,398 `FF FF` models re-encode with a different face-index compression mode. Their decoded models are equal;
  the bytes are not.
- A shading change on a newer model is refused, because what a render type does in the client is not established
  ([ADR 0012](../adr/0012-newer-models-refuse-unestablished-edits.md)). Render types 1 and 3 are taken to be flat,
  unverified.
- Two rules write the footer of a hand-built model or of an edit that contradicts a source footer flag (unedited
  models replay their source flags). The client citations are bytecode offsets in the revision 149 jar, with
  obfuscated names. The reading is in
  [client-rules.md](../../.scratch/codec-rules-cited/evidence/client-rules.md).
- One shared priority is stored once in the footer (0 for no faces). Confirmed, except the 0. Client rev 149, class
  `dv`, method `j`, offsets 2235 to 2240 and 965 to 969: a footer priority byte of 255 means that one priority byte
  follows for every face, and any other value is the one priority of all faces. The client has no case for a model
  with no faces, so writing 0 there is our choice.
- The render-type and alpha sections are left out when all their values are 0. Confirmed. Client rev 149, class
  `dv`, method `ae`, offsets 563 to 570, 1192 to 1199, 1488 to 1491 and 1706 to 1709: a missing render type or alpha
  array reads as 0. Class `dv`, method `j`, offsets 1516 to 1522 and 1559 to 1562: each of those sections is read
  only when its footer flag is 1.
- A texture index above 254 is refused. Confirmed. Client rev 149, class `dv`, method `j`, offsets 1632 to 1665: a
  face's texture coordinate is one file byte that holds the index plus 1. Class `dv`, method `ae`, offsets 428 to 436
  and 449 to 459: file byte 0 means no texture triangle, and any other byte is used as an unsigned index, so 254 is
  the highest index. The client has no check of its own. We refuse 255 because it does not fit in the byte.
- An opaque tail whose first byte is nonzero and that holds fewer than 11 bytes is refused. The 11 is the client's
  number. Refusing a shorter tail is our own stricter rule, and the owner decided on 2026-11-11 to keep it
  ([issue 17](../../.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md)). Client rev 149, class `dv`, method `j`, offsets 2689 to 2694, 1901 to
  1903, 2709 to 2725, 2423 to 2431, 2740 to 2748 and 172 to 180: when the first tail byte is nonzero, the client reads
  11 bytes (1, 2, 2, 2 and 4) and ignores them. It checks no length, so a shorter tail makes it read the footer.
- Unverified, and marked so in the code, these reject input: texture kinds above 3, and footer flags other than 0
  or 1. Each needs a client citation or the user's decision
  ([issue 17](../../.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md)).
- The texture tools' rules for new-format models ([ADR 0012](../adr/0012-newer-models-refuse-unestablished-edits.md))
  are conservative choices; how the client treats such edits is unverified.

## 317 cache: container, archives and textures

The 317 cache zip holds `cache/main_file_cache.dat` (12.5 MB) and `main_file_cache.idx0` to `idx4`: the old 317 cache format, which RuneLite's library (and so `osrs-cache-dumper`) cannot read. A throwaway prototype (step 6, 2026-11-06; kept on branch `prototype/317-cache` of `<path to osrs-cache-dumper>`, folder `prototype-317/`) read all of it. Every point below was checked against the 317 decompile (`<data workspace>/decompiled-clients/src317.zip`, class names obfuscated):

- `IGSLDTHC.java`: each `idxN` entry is 6 bytes, a 3-byte file size and a 3-byte first sector. `main_file_cache.dat` is made of 520-byte sectors, each an 8-byte header (file ID 2 bytes, chunk number 2, next sector 3, store 1, which is the index number plus 1) and up to 512 data bytes. The client opens idx0 to idx4 with a 500,000-byte file limit.
- `XTGLDHGX.java`: idx0 holds JAG archives. An archive starts with two 3-byte sizes; if they differ the whole archive is bzip2-compressed, otherwise each file is. Then a 2-byte file count and, per file, a 4-byte name hash (`hash * 61 + char - 32` over the upper-cased name), a 3-byte size and a 3-byte packed size. The bzip2 data lacks its `BZh1` header. idx0 file 5 is `versionlist` and file 6 `textures` (`client.java` bytecode).
- `GHOWLKWN.java` line 59: idx1 (models) to idx4 files are gzip data followed by a 2-byte version, which the client checks, with a CRC32 of the bytes before it, against `model_version` and `model_crc` in `versionlist`.
- `OPPOFIOL.java`: textures are the indexed images "0" to "49" in the `textures` archive. `DSMJIEPN.java` reads one: `<name>.dat` starts with a 2-byte offset into `index.dat`, which holds the canvas width and height, a palette size and 3-byte RGB entries (entry 0 not stored), then per image an x and y offset (1 byte each), width and height (2 each) and a layout byte (0 row-major, 1 column-major). Its method `c()` places the image at its offsets on the full canvas, which is what the rasteriser uses.
- `OPPOFIOL.java` lines 400 to 510: the rasteriser draws texel `palette[index] & 0xF8F8FF`, and a texel of 0 is transparent. It first sets any palette entry other than 0 that would mask to 0 to 1, so only palette index 0 is transparent; a near-black entry such as texture 8's 0x000300 stays opaque. It draws 64-pixel textures doubled to 128, nearest neighbour.

What the prototype found: 7,537 model entries, of which 7,456 are present; each one's version and CRC match `versionlist`, and `rsps_toolkit.formats.decode` reads every one (1,051 textured). The other 81 are listed in `versionlist` but were never downloaded into this cache. All 50 textures decode; 38 are pixel-identical to `texture_dump.zip`, including palette index 0 written as transparent, and 12 differ, which looks like a different cache revision behind `texture_dump.zip` (a guess). Textures 10, 40, 42, 43 and 47 are a single blue colour in this cache. Some images are narrower than their 128-pixel canvas (texture 33 is 125 wide); the prototype, like `texture_dump.zip`, wrote the cropped image. Against the Old School dump, 43 of the 50 show the same picture (the colour offset above aside); 10, 33, 40, 42, 43, 45 and 47 (10, 40, 42, 43 and 47 a single blue in the 317 cache) are different pictures, so a texture folder from one game shows those 7 wrongly for the other. The prototype first counted 44, missing 33, which it had written cropped and so never compared; on the canvas the 317 texture 33 is red leaves where the Old School dump and `texture_dump.zip` have brown foliage.

The real extractor (2026-11-05) is `Cache317` in `osrs-cache-dumper`, branch `feature/317-cache`, with JUnit tests against the cache zip, the Old School dump and `texture_dump.zip`. Given a folder with `main_file_cache.dat`, it writes `dump_index/models/<id>.dat` and `textures/<id>.png`, the same layout as the Old School dump; its README describes both. Its 7,456 models are byte-identical to the prototype's. Textures sit on their full canvas as `c()` places them, with only palette index 0 transparent, and keep the stored palette colours and their stored size (64 or 128); the client's brightness and its doubling of 64-pixel textures are drawing steps the extractor leaves out. 48 of the 50 have exactly the Old School dump's transparent pixels; texture 33 is a different picture, and texture 8 differs in 2 pixels, (79, 81) and (81, 80), opaque mid colours in the 317 cache and transparent in the Old School dump. The Old School dumper makes a pixel transparent only when it comes out black, so the Old School cache stores something else there (evidence from the dumper's code; the Old School cache's pixels there are not read).

## Still to read

- The rest of `a(byte[], boolean)`: face index decoding (lines 486 onwards) and the vertex and face section offsets (lines 325 to 370), to check against `formats/old_format.py` and the add-on's `importer_667.py`.
