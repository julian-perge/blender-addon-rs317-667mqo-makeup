# Reading the live RuneLite cache instead of a dump

Researched 2026-11-11 against the RuneLite client's disk cache (`<path to RuneLite cache>`, the `jagexcache/oldschool/LIVE` folder, last written by RuneLite 1.13.6 on 2026-11-10), snapshot 430 (build 149), OpenRS2 cache 2757 (build 242), RuneLite `runelite/runelite` at `bb0fa42` (cache module, BSD 2-Clause) and OpenRS2 `openrs2/openrs2` at `50175bc` (ISC). Each claim is **Evidence** (read or measured, source named) or **Guess**. The cache was only opened for reading. Scripts and outputs (`survey.py`, `decode.py`, `walk.py`, `DecodeModels.java`) are in a scratch folder, `<scratch>/2026-11-11-runelite-cache-research/`.

## Summary

- Reading a js5 disk cache is not the hard part. The repo's own `Js5Store` (`formats/js5.py`) read all 120,356 groups of the live cache, and every group matched its reference table CRC (Evidence, `survey.py`).
- The hard part is the revision. The live cache is build 242 content, and the data the extension needs has changed format since build 149 (Evidence, section 3):
  - all 62,769 models end in `fffd` or `fffe`, and `formats.decode` refuses every one;
  - 6,887 of 15,167 sequences use opcodes the 149 decoder refuses, among them the walk clip 819;
  - all 2,787 frame maps have bytes after the 149 layout, and the player's frame map 0 was restructured;
  - the 18 kit style enums that `kit_names.py` reads are empty or changed.
- Recommendation: do not point the extension at the live cache now. Replace the dumper's JSON with direct reads of the snapshot 430 js5 cache, which the extension already reads for clips. Treat live support as a separate revision project (section 6).

## 1. What the extension reads from the dump now

Evidence, from the source. The dump is the dumper's output for snapshot 430. The `cache_dump_folder` preference names it (`blender/preferences.py:22-26`), and `formats/cache_profile.py` reads it:

| Dump file | Read by | Used for |
| --- | --- | --- |
| `kits/KitDefinitions.json` | `cache_profile.py:55-63`, `appearance.load_kits` (`appearance.py:63-77`) | body part, models, chathead models, recolours, retextures |
| `enums/Enums.json` | `cache_profile.py:65-74`, `kit_names.load_kit_names` (`kit_names.py:36-52`) | kit display names from the 18 style enums in `STYLE_ENUMS` (`kit_names.py:17-27`) |
| `items/ItemDefinitions.json` | `cache_profile.py:74-78`, `appearance.load_items` (`appearance.py:80-95`) | names, six worn models, offsets, recolours |
| `dump_index/models/<id>.dat` | `CacheProfile.load_model` (`cache_profile.py:83-87`) | worn and kit models, decoded with the `osrs-149` profile |

Callers: `appearance_props.profile` (the panel), `appearance_preview` (Create and Update), `appearance_held.variant` (held-item bakes) and `appearance_collection` (replace and duplicate), all through `shared_profile` (`cache_profile.py:119-123`).

Other inputs (Evidence):

- Clips are read from the js5 cache itself, not the dump. The `cache_folder` preference (`preferences.py:28-33`) names snapshot 430's `cache/` folder, and `animation/clip.py:13-15` and `CacheClip` (`clip.py:58-82`) read sequences from index 2 group 12, frames from index 0 and frame maps from index 1.
- The animation bundle (`animations/manifest.json` with models, textures, sequences, frame maps and frames, `animation/bundle.py:320-362`) is a separate dumper output, loaded by File > Import animation.
- Texture PNGs come from the `texture_folder` preference (`preferences.py:17-21`), such as the dumper's texture dump.
- Generated tables ship in `src/rsps_toolkit/data/`: `animation_names.json` and `player_joints.json` (from snapshot 430 through `Js5Store`, `scripts/generate-*.py`), `item_wear.json` (from cache 2757), `weapon_clips.json` and the revision 149 palette.

## 2. Where each one lives in the cache

Evidence, measured on the live cache with `survey.py` and named after RuneLite's `IndexType.java:30-51` and `ConfigType.java:32-51`. The master index `main_file_cache.idx255` has 23 entries (indexes 0 to 22). Index 16 has an empty entry. There is no entry for index 24 (`GAMEVALS`), although the client folder holds 1-byte `idx23` and `idx24` files.

| Data | Index / group | Live cache | Snapshot 430 |
| --- | --- | ---: | ---: |
| Kits (`IDENTKIT`) | 2 / 3 | 307 files | 151 |
| Enums | 2 / 8 | 5,970 files | 1,725 |
| Items | 2 / 10 | 34,766 files | 21,392 |
| Sequences | 2 / 12 | 15,167 files | 7,636 |
| Frames (`ANIMATIONS`) | 0, one group per frame set | 11,314 groups, 219,880 files | 1,919 groups |
| Frame maps (`SKELETONS`) | 1, one file per group | 2,787 | 1,703 |
| Models | 7, one file per group | 62,769 | 33,196 |
| Textures | 9 / 0 | 216 files in one group | 59 |
| Sprites (texture images) | 8 | 8,822 groups | |
| Skeletal animations (`ANIMAYAS`) | 22 | 1,059 groups | none |
| Maps | 5 | 2,950 groups | |

Config index 2 has 41 groups. Snapshot 430 counts are from [revision-170-cache.md](revision-170-cache.md) section 3.

Format facts (Evidence):

- Every reference table uses protocol 7 (smart group ids) with flag 4 (lengths). Group versions are Unix times. The config groups the extension needs carry 1793635793 to 1793635796, that is 2026-11-02.
- Sectors are 520 bytes with an 8-byte header, or 10 bytes for group ids above 65535 (RuneLite `DataFile.java:97-145`, OpenRS2 `DiskStore.kt:165-176` and `470-477`). `js5.py:36-55` does the same.
- Containers in the live cache are kinds 0, 1 and 2 only: none, headerless bzip2 and gzip (RuneLite `CompressionType.java:29-31`). No group uses kind 3, LZMA, which OpenRS2 also reads (`Js5CompressionType.kt:10-14`).
- Every stored group ends with a 4-byte trailer after the container, not the 2-byte version that older caches use. RuneLite reads either (`Container.java:158-166`). `js5.unpack` ignores the trailer, so it is not affected. The reference table CRC covers the container without the trailer: all 120,356 groups match.
- The reference table layout in `js5.reference_table` (names, CRC, uncompressed CRC, digests, lengths, versions) matches OpenRS2 `Js5Index.kt:278-352`.

Decoded from the live cache (Evidence, `decode.py`):

- Kits: all 307 decode with RuneLite's `KitLoader` opcodes. They use only opcodes 1, 3, 5 and 70: models and chathead models are now 4-byte ids (`KitLoader.java:63-71` and `101-104`). Snapshot 430 used 1, 2, 3, 40 and 60. Of the 151 old kits, 101 keep the same body part, models and chathead models.
- Enums: all 5,970 decode with `EnumLoader.java:62-135` (opcodes 1 to 6 in use).
- Items: all 34,766 pass the repo's strict item decoder (`scripts/generate-item-wear.py`). Item 1149 is "Dragon med helm", male model 219, female model 395, slot 0. Worn models up to 62,566 come from the 4-byte opcodes 45 to 50.
- Models: all 62,769 decode with RuneLite's `ModelLoader` from cache library 1.13.6, with no exception (`DecodeModels.java`). Model 0 has 176 vertices and 327 faces. Model 219 has 64 vertices and 88 faces. 452 models carry skeletal groups. `ModelLoader` does not check that it read the whole file, so "no exception" is a weaker check than the repo's decoders make.
- Walk clip 819: its 8 frames decode with the repo's `decode_frame` once the frame map trailer is cut off. The frame bodies after the 2-byte map id equal the 430 frames byte for byte. The frames moved from group 207 to group 10985.

The live cache is the same data as OpenRS2 cache 2757 (build 242, 2026-11-03): the reference tables of indexes 0, 1, 2, 7, 8, 9 and 22 are byte-identical (Evidence). The client's build is not in the cache or in RuneLite's log, so build 242 is inferred from that match (Guess, well supported).

## 3. Compression, encryption and new formats

Encryption (Evidence): all 2,950 map groups in index 5 decompress without an XTEA key, and OpenRS2 lists 0 keys for cache 2757 ([cache-2757-wear-positions.md](cache-2757-wear-positions.md) section 1). Nothing the extension needs (indexes 0, 1, 2, 7, 8 and 9) was ever encrypted. `js5.py:4-5` says encrypted groups are not supported, which does not matter here.

What the repo's decoders cannot read (Evidence, `decode.py` with the repo's own functions):

| Data | Live cache | Repo decoder | Source of the new layout |
| --- | --- | --- | --- |
| Models | 26,927 `fffe` and 35,842 `fffd`; no old-format and no `ffff` model | `formats.decode` refuses both markers (`formats/__init__.py:35-36`): 0 of 62,769 | `ModelLoader.java:13-27`. `fffd` is the `ffff` layout with a 26-byte footer that adds a skeletal flag and a length (`:37-62`, skeletal groups `:199-202` and `:260-273`). `fffe` is the old layout with a 23-byte footer that adds the same two fields (`:413-436`, `:525-529`, `:581-594`). The 149 footers are 23 bytes (`:777`) and 18 bytes (`:1123`) |
| Sequences | opcodes 13 to 17 and 19 in use: 1,097 skeletal clips (opcode 13), 1,739 with frame sounds (opcode 14), 5,553 with a vertical offset (opcode 16) | `decode_sequence` accepts only 1 to 13 (`frames.py:17`, `:147-148`) and refuses 6,887 of 15,167, including clip 819, which now starts with opcode 16 | `SequenceLoader.java:38-47` and `159-210`. Opcode 13 now holds a skeletal animation id, not 24-bit frame sounds. No file uses opcode 18 (debug name) |
| Frame maps | 2,616 end with two zero bytes; 171 carry skeletal data | `decode_frame_map` refuses all 2,787 for unread bytes (`frames.py:95-96`) | RuneLite's `FramemapLoader.java:39-60` reads the 149 part and ignores the rest |
| Frame map 0 (player) | 245 transforms instead of 227. Within the first 227, 60 types and 96 label sets differ | | `player_joints.json` and the joint names in `scripts/generate-player-joints.py` are tied to the 430 layout |
| Kit style enums | of the 18 in `STYLE_ENUMS`, 16 are empty and 771/772 grew from 14 to 23 entries | `load_kit_names` would leave most kits unnamed | Where current kit names live was not found (Guess: the db tables in config groups 38 and 39) |

Guess: the frame bodies of clip 819 are unchanged while frame map 0 changed, so either the walk sets only transforms whose meaning stayed, or the walk now plays differently. This was not checked.

## 4. Reference code

Evidence, file and line in the clones named above:

- Disk store: RuneLite `cache/src/main/java/net/runelite/cache/fs/jagex/DataFile.java:69-170` (read) and `IndexFile.java`. OpenRS2 `cache/src/main/kotlin/org/openrs2/cache/DiskStore.kt:155-215`.
- Containers: RuneLite `fs/Container.java:93-172`. OpenRS2 `Js5Compression.kt:112-170` (with XTEA and LZMA).
- Reference tables: RuneLite `index/IndexData.java`. OpenRS2 `Js5Index.kt:284-352` and `Js5Protocol.kt:3-12` (protocols 5, 6 and 7).
- Definitions: RuneLite `definitions/loaders/KitLoader.java`, `EnumLoader.java`, `ItemLoader.java`, `SequenceLoader.java`, `FrameLoader.java`, `FramemapLoader.java`, `ModelLoader.java`, `TextureLoader.java`, `SpriteLoader.java`.
- The May 2018 tree `runelite-master` (revision 170) has none of the `fffd`, `fffe` or rev226 code. It matches snapshot 430 better ([revision-170-cache.md](revision-170-cache.md)).

## 5. Risks

### Game updates and the shared profile

Evidence: `CacheProfile` keys each catalog on the `st_mtime_ns` of its JSON files (`cache_profile.py:46-54`). A js5 source has no per-catalog file: kits, enums, items and sequences all live in `main_file_cache.dat2` and `idx2`. The client writes `dat2` for any group it stores, so a key on `dat2` times would parse again after unrelated writes (Guess: such as sound or map downloads). The precise key is the group version or CRC in the reference table, which `survey.py` reads in a few milliseconds.

Evidence: `Js5Store` reads each reference table once and never again (`js5.py:23` and `60-64`), and `appearance_clip_cache` keeps one store per folder for the whole session (`appearance_clip_cache.py:24-29`). After an update while Blender runs, the store would split groups with stale file lists. This is harmless on a fixed snapshot and wrong on a live cache.

### File locking and writes

- Evidence: the 2018 client opens cache files with `RandomAccessFile(..., "rw")` and takes no `FileLock` (`runelite-master/runescape-client`: `FileOnDisk.java:54`, `class224.java:77`; no `tryLock` or `FileLock` in the tree). The current client was not decompiled. Guess: it still does not lock, so reads succeed while it runs.
- Guess: a read during a write can see a group whose index entry and sectors disagree. `js5.py:49-50` raises `ValueError` on a broken sector chain, and a reference table CRC check would catch the rest.
- Evidence: RuneLite's cache library opens `dat2` and every index with mode `"rw"` (`DataFile.java:46`, `IndexFile.java:54`), and OpenRS2's `DiskStore` opens with `READ, WRITE` and sometimes `CREATE` (`DiskStore.kt:133`, `518`, `568`). Neither is safe on the client's folder. Earlier research ran RuneLite's loaders on a copy for this reason (`cachecopy` in the cache 2757 scratch folder). `Js5Store` opens with `"rb"` only (`js5.py:30`, `39`).
- Reading a clone of the folder (`cp -c` on APFS) gives a consistent snapshot at no disk cost.

### Licensing

- Evidence: RuneLite is BSD 2-Clause (`LICENSE`), OpenRS2 is ISC (`README.md:73-76`). Porting their format logic with credit fits both. The repo already cites `ItemLoader` this way (`scripts/generate-item-wear.py:15-17`).
- The cache content is Jagex's. Reading the user's own cache at run time ships no game data, the same as reading a dump today. What may go into committed fixtures was not researched, and no Jagex terms were read.

### What would change in code and tests

- For a direct reader of snapshot 430, small changes (Evidence for the list): `cache_profile.py` reads kits, enums and items from `Js5Store` instead of JSON. A kit decoder and an enum decoder are needed (about 40 lines each). The item decoder moves from `scripts/generate-item-wear.py` into `src`. `load_model` reads index 7. The two preferences could become one. 22 test files mention the dump layout or the profile (`rg` over `tests/`), led by `tests/unit/test_cache_profile.py`, `test_kit_names.py`, `test_appearance.py` and `tests/blender/conftest.py`.
- For the live cache, large changes: new model decoders for `fffd` and `fffe`, a rev226 sequence decoder, frame maps with trailers, a new player joint table, a new kit name source, new animation names, and new client evidence. The 149 evidence base (the `gamepack-149` references, 430 fixtures and sweeps) does not transfer. [revision-170-cache.md](revision-170-cache.md) section 5 counted 83 files that name `osrs-149`, `gamepack-149` or 430.
- A live cache moves under the user. Pinning an OpenRS2 archive (2757 holds the same data as this live cache) gives a fixed, hashable input.

## 6. Recommendation

Do not read the live cache now. Reading the container format is not the hard part: the repo already has that reader. Every catalog the extension uses changed layout after build 149, and the extension's correctness evidence is tied to the 149 client ([ADR 0003](../adr/0003-old-school-caches-come-first.md)).

Do read a js5 cache directly instead of the dumper's JSON, starting with snapshot 430. The extension already reads that cache for clips. A minimal reader needs:

1. `Js5Store` as it is, read-only, with reference tables keyed on the index's version or CRC instead of being kept for the session.
2. Decoders for kit (`KitLoader` opcodes 1, 2, 3, 5, 40, 41, 60 to 79), enum (opcodes 1 to 8) and the item fields in `WornItem` (the strict decoder from `generate-item-wear.py`).
3. `CacheProfile` reading index 2 groups 3, 8 and 10 and index 7, with its catalogs keyed on those group versions.
4. A check that the result equals the current dump on snapshot 430: kits, item fields, kit names and model bytes.

Live or build-242 support would then add, as its own plan: `fffd` and `fffe` model decoding (the `ffff` and old decoders plus a 3- or 5-byte footer change and skeletal groups), rev226 sequence opcodes, frame map trailers, regenerated joints and names, a reader that copies the folder first, and new client references to verify against.
