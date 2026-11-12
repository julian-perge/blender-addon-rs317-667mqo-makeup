# A revision-170 cache: what it would add

Researched 2026-11-07 against OpenRS2 `caches.json`, the May 2018 RuneLite tree `<RuneLite May 2018 tree>`, snapshot 430 and the downloaded archive 34. Each claim is **Evidence** (read or measured, source named) or **Guess**. No client jar was downloaded or run. Scripts and outputs are in `<scratch folder 2026-11-07-rev170>/`.

## 1. Which archive matches runelite-master

Evidence: `pom.xml:46` sets `rs.version` 170. The tree has no Git metadata, and every original file is dated 2018-05-15 11:20 (Guess: the commit time of an archive export). OpenRS2 lists three build-170 caches: 34 (2018-05-10), 35 (05-17) and 36 (05-24).

Highest ids in `runelite-api` `ObjectID`, `NpcID` and `ItemID` against config groups 6, 9 and 10 of each archive, fetched with the OpenRS2 group API (Evidence):

| Source | Objects max | NPCs max | Items max |
| --- | ---: | ---: | ---: |
| runelite-master | 32536 | 8195 | 22374 |
| Archive 34 | 32536 | 8195 | 22375 |
| Archive 35 | 32544 | 8205 | 22397 |
| Archive 36 | 32738 | 8335 | 22436 |

Item 22375 in archive 34 holds only placeholder opcodes 148 and 149 (Evidence); Guess: unnamed placeholders are left out of `ItemID`. **Archive 34 chosen**, high confidence for the data. That the tree's client is the gamepack served with archive 34 is a Guess: the tree has no gamepack hash.

## 2. Download

Evidence: `<data workspace>/caches/osrs/openrs2-34/` follows the 430 layout (`cache/`, `keys/` with 1,253 files, `downloads/` fetched with HTTPie, `metadata.json`), and `provenance.json` holds SHA-256 for all 1,278 files. `main_file_cache.dat2` is `1bc205fa...1b5d`.

## 3. 430 against 34, measured

All Evidence, from `compare.py` and `codec_sweep.py`.

| Data | 430 (149) | 34 (170) | Result |
| --- | --- | --- | --- |
| Kits, config group 3 | 151 | 151 | all 151 raw files identical; opcodes {1, 2, 3, 40, 60} in both |
| 18 kit style enums (`KitStyleEnums.json`) | | | all identical |
| Sequence 819 | | | identical bytes (`da995aec...`), equal to the `animation149/walk` fixture |
| Its 8 frames and frame map 0 | | | identical bytes, equal to the fixtures |
| Sequences | 7,636 | 7,985 | 7,612 identical, 24 changed, 349 added; opcode set 1 to 13 in both |
| Frame groups / frame maps | 1,919 / 1,703 | 2,091 / 1,796 | 13 and 4 changed, 172 and 93 added |
| Models (index 7) | 33,196 | 35,129 | 33,010 identical, 178 changed, 8 removed (29032-29038, 29040), 1,941 added (all ids above 33195) |
| Model formats (old / `ffff`) | 27,798 / 5,398 | 27,707 / 7,422 | 93 changed models moved old to `ffff`; no `fffd`/`fffe` footer in either |
| Sample items 1149, 2653, 3140, 4087, 35 | | | raw definitions identical |
| Items | 21,392 | 22,376 | 812 changed, 984 added; identical opcode set |
| Textures (index 9) | 59 | 59 | all identical |
| Enums | 1,725 | 1,912 | 92 changed, none of them kit enums |

Appearance fixture models: 27 of 29 identical. Both changed ones belong to item 2653 (`dragon_plate`). Model 3379 was re-encoded old to `ffff` with the same vertices, faces and colours but different render priorities. Female model 3383 changed geometry: 132 to 124 vertices, 224 to 216 faces, so the female `dragon_plate` cases in `reference.json` would not hold on 170 (new merge counts not computed).

Palette: the colour tables are client constants (`hv`, `class228`), so the cache cannot show them (Evidence).

Toolkit codec, pure Python, `osrs-149` profile: decodes all 35,129 models; 34,963 re-encode byte-identically. The other 166 are the 159 that also differ on 430 plus 7 added `ffff` models, which matches the known compression-mode issue (issue 17 (`git show 2a78edd:.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md`); the cause for the 7 is a Guess).

## 4. Does the 2018 source become an exact match?

Guess, well supported: the tree's client is a decompile of a revision-170 gamepack, so for archive 34 it is the matching code apart from decompiler errors.

| Area | With archive 34 | Newly verifiable |
| --- | --- | --- |
| Model decoding, `ffff` footer | `ModelData.java:334` footer test and the 23- and 18-byte footers fit; no new format | Nothing new: 149 decoding is already client-run on all 33,196 models |
| Kits, appearance | data identical to 430 | the 12-entry palette row 4 (`class228.java:16`) becomes the right table instead of a known mismatch |
| Sequence opcodes, held items | same opcode set | `Sequence.java:145-211` becomes the data's own decoder; the 149 one never ran ([deobfuscation-value](deobfuscation-value.md) section 1) |
| Frames | walk clip identical | nothing for the walk bake |
| Player composition | `PlayerComposition.java` and the appearance block reader (`Player.java:180-221`) match the data | the player's sequence choice, whose 149 reader was not located, becomes source-backed |
| Textures | texture files identical | rasterizer names exact; no textured case is added |

None of this is client-run evidence; that needs a 170 jar matching the tree's `@ObfuscatedName` values.

## 5. Costs and risks

- Evidence base on 149 (Evidence): the `gamepack-149.jar` references (`reference.json`, `PoseReference`, `Osrs149Reference`), snapshot 430 fixtures and the kits dump. 83 files in `src`, `tests` and `docs` mention `osrs-149`, `gamepack-149` or 430; `formats/__init__.py:28-35` accepts only the `osrs-149` profile for `ffff`.
- To redo on a switch (Evidence for the list): the dumper run and kits dump, the Blender sweep over 35,129 models, the appearance and pose references, fixture hashes and the `dragon_plate` female cases.
- Dumper: `LegacyAnimationData.java:180` turns off `rev220FrameSounds` and `rev226`, still right for 170 because opcode 13 reads 24-bit values (`Sequence.java:203-209`) (Evidence). Kits, items and sequences use no opcode outside the 430 set (Evidence).
- A 170 client (Evidence): none in the local code, clone and scratch folders, only `gamepack-149.jar` and RS2 jars. OpenRS2 `/clients` has no `oldschool` row, and `/caches/runescape/34/gamepack.jar` answers 404. `runetech/osrs-gamepacks` `gamepacks/osrs-170.jar` answers 200 (2,120,589 bytes); `archive.runestats.com/osrs/2018-05-10-rev170.tar.gz`, archive 34's listed source, answers 200 (46,071,342 bytes). Neither was downloaded; neither has a published hash.
- Guess: archive 34 may not be the first or last cache of revision 170; OpenRS2 timestamps are capture dates.

## 6. Recommendation

Stay on 149 for the product. Use archive 34 only as a second reference for name mapping and cross-checks.

Reasoning (Evidence): for everything CharacterCreator and the walk bake use, 34 is byte-identical to 430 apart from two worn models of item 2653. Switching adds no needed data and drops the client-run evidence until a 170 jar is obtained, checked and every harness re-run.

Cheap uses of archive 34:

1. Where 430 and 34 data are identical (kits, clip 819, textures), the 149 client's output and the 2018 source should agree; a disagreement points at a constant change like palette row 4.
2. Rerun `compare.py` before trusting a 2018 name for a new data type.
3. If a 170 jar is fetched, check its class names against `@ObfuscatedName` (`ModelData` is `do`) first.

Failure cases: needing content added after July 2017 (1,941 models, 984 items, 349 sequences) makes a switch worthwhile, with its own client evidence. Identical bytes do not prove the two clients treat them alike.
