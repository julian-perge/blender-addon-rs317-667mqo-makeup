# Weapon stance sets: which stand, walk and run sequences a weapon gives the player

Researched 2026-11-09 by reading bytecode, local caches and remote source files. Remote files were streamed over HTTPS at pinned commits and filtered in memory; nothing was cloned or saved. No client and no Blender was run. Every statement is tagged **[evidence]** (read or run, source named) or **[guess]**. Scripts and the two linearised bytecode listings are in `<scratch folder 2026-11-09-weapon-stance-sets>/`.

**Status (2026-11-09):** used by plan 13 (`.scratch/osrs-focus/plans/13-weapon-stances.md`). The user approved downloading Alter's two files and the plugin's `data.json`; `scripts/generate-weapon-clips.py` writes `src/rsps_toolkit/data/weapon_clips.json` from them, with Alter's set winning where the two disagree. The panel's Stance and Attack buttons read it.

## Summary

- **Source to use:** Alter's two JSON files, `item_bas.json` (item id to set number) and `bas_mappings.json` (set number to a named set of seven sequence ids). BSD 2-Clause, 97,533 bytes together, data of December 2024 (revision 228 era). They must be downloaded to be used; URLs are in section 2.
- **Second source, for cross-checking and gaps:** the Weapon Animation Replacer plugin's `data.json` (BSD 2-Clause, 91,085 bytes), recorded from the live client. It agrees with Alter on 340 of the 347 snapshot 430 weapons both list.
- **The ids apply to revision 149 as sequences.** All 129 sequence ids Alter names for snapshot 430 weapons exist in the snapshot 430 cache, all use frame map 0 (the player's), and all have the same frame count and durations in the 2026 cache. No id was renumbered.
- **Whether each weapon had the same set in July 2017 is not verified.** Assignments do change: Dharok's greataxe runs with 824 in Alter (2024) and with 11466 in the plugin (2026), and 11466 is not in snapshot 430.
- **Coverage:** 911 snapshot 430 items take the weapon slot. Alter lists 712 of them (78.2%): 357 with a set other than the unarmed one, 355 with the unarmed set. Of the 199 it does not list, 69 are named "null" and most of the rest are quest props; at least 19 of them are known from other tables to need another set.
- **No cache holds this table.** Neither snapshot 430 nor the build 242 cache maps a weapon to stance sequences.

## Sources and naming

- Client: `<reference work folder>/gamepack-149.jar`, SHA-256 `19c492cc...cbdd` (matches [the appearance README](../../tests/fixtures/appearance/README.md)) **[evidence]**. Offsets are `javap -p -c -cp gamepack-149.jar <class>` offsets inside the named method. The methods are control-flow obfuscated, so they were read in execution order with `linear.py`, which follows each `goto` and the opaque integer-argument checks; `be_a.linear.txt` and `ea_fc.linear.txt` are its output.
- Names: RuneLite source in `<RuneLite May 2018 tree>/runescape-client/src/main/java/`. Its `pom.xml` line 46 sets `rs.version` 170, so it is the revision 170 client **[evidence]**. `<data workspace>/runelite-1.13.6-sources` holds three cache-library files and no `Player` or `Actor`; `<data workspace>/decompiled-clients` holds only the 317 and 667 clients **[evidence]**.
- 149 classes used here **[evidence by identical structure with the 170 source]**: `be` = `Player`, `ca` = `Actor`, `fe` = `Buffer` (`fe.d` reads two bytes big-endian, offsets 2 to 51 of `fe.d(int)`), `hu` = `PlayerComposition`.
- Sequence names are RuneLite's `gameval/AnimationID.java` names as stored in `src/rsps_toolkit/data/animation_names.json` (commit `2136d50`).

## 1. What the revision 149 client reads

**[evidence]** `be.a(fe,int)` is the appearance decoder (170: `Player.decodeApperance`, `Player.java:180-278`). It reads, in this order: body type (u8, offsets 456-461), skull icon (s8, 33-45), overhead icon (s8, 425-437), twelve equipment slots (loop from 90), five colours (loop from 646), then **seven unsigned shorts**, then the name (792-800), combat level (832-842), total level (510-522) and the hidden flag (8-15). Each short that equals 65535 is stored as -1. The offsets are not ascending because the method's blocks are shuffled; the order given is the order of execution.

| Order | 149 field | 170 field | Role | Offsets in `be.a` | Unarmed id and name |
| ---: | --- | --- | --- | --- | --- |
| 1 | `ca.am` | `idlePoseAnimation` | stand | 323-335, -1 at 465-475 and 955-959 | 808 `HUMAN_READY` |
| 2 | `ca.aw`, copied to `ca.aq` | `field892`, copied to `field889` | turn on the spot, both directions | 395-407, copy at 552-561 | 823 `HUMAN_TURNONSPOT` |
| 3 | `ca.aa` | `field890` | walk | 274-286 | 819 `HUMAN_WALK_F` |
| 4 | `ca.ag` | `field891` | walk while facing backwards | 305-317 | 820 `HUMAN_WALK_B` |
| 5 | `ca.aj` | `field882` | walk sideways, left | 654-666 | 821 `HUMAN_WALK_L` |
| 6 | `ca.ax` | `field893` | walk sideways, right | 707-719 | 822 `HUMAN_WALK_R` |
| 7 | `ca.ad` | `field894` | run | 757-769 | 824 `HUMAN_RUNNING` |

**[evidence]** How the client uses them, in `ea.fc(ca,byte)` (170: `class68.java:216-325`):

- Offsets 0-8: the pose sequence `ca.bc` is set to `am` (stand) at the start of every movement step.
- Offsets 917-936: `d = (target orientation - angle) & 2047`, wrapped to -1024..1024. The choice starts as `ag` (723-730). `d` in -256..256 gives `aa` (216-223). `d` in 256..767 gives `ax` (1152-1157, 801-806, 823-830). `d` in -768..-256 gives `aj` (1643-1648, 859-864, 627-634). A choice of -1 falls back to `aa` (890-903).
- Offsets 1331-1375 and 709-717: when the step speed is 8 or more, the pose equals `aa` and `ad` is not -1, the pose becomes `ad`. So run replaces only the forward walk; a sideways or backwards step at run speed keeps its walk clip.
- `ap.fb(ca,int,int)` offsets 1235-1339 and 1433-1551 (170: `FaceNormal.java:103-123`): while turning with the pose equal to `am`, the pose becomes `aw` or `aq`, or `aa` when that is -1.

**[evidence]** The client has no defaults. `ca.<init>` stores -1 in all eight fields and in `ca.bc` (offsets 26-29, 54-85, 218-221, 274-287; each constant times the field's getter multiplier is -1, checked by `inv.py`). An unarmed player's ids come from the server.

**[evidence]** The unarmed set is 808, 823, 819, 820, 821, 822, 824 in every table read: RSMod v1 writes exactly these in this order when no weapon is worn (`PlayerUpdateBlockSegment.kt:172`), RSMod v2 names them `human_ready`, `human_turnonspot`, `human_walk_f`, `human_walk_b`, `human_walk_l`, `human_walk_r`, `human_running` (`BaseBas.kt`), Alter calls the set `bas.default_player`, and the plugin's "Unarmed" set, recorded from live players, holds the same seven. [The clip coverage runs](osrs-149-animation.md#clip-coverage-2026-11-07) already record 808, 819 and 824 on the default body. **[guess]** Jagex's server sent the same seven in July 2017; no 2017 capture was read.

**[evidence]** The block is unchanged in order today: rsprot's build 242 encoder writes `readyAnim, turnAnim, walkAnim, walkAnimBack, walkAnimLeft, walkAnimRight, runAnim` ([`PlayerAppearanceEncoder.kt` lines 140 to 150](https://github.com/blurite/rsprot/blob/00b2e758ba2326dceffa2d48d9064c66d64e7cc5/protocol/osrs-242/osrs-242-desktop/src/main/kotlin/net/rsprot/protocol/game/outgoing/codec/playerinfo/extendedinfo/PlayerAppearanceEncoder.kt#L140-L150)). RuneLite's API names them `getIdlePoseAnimation`, `getIdleRotateLeft`/`getIdleRotateRight`, `getWalkAnimation`, `getWalkRotate180`, `getWalkRotateLeft`, `getWalkRotateRight`, `getRunAnimation` (`runelite-api/.../Actor.java` lines 178 to 249 at `2136d50`). The 170 source labels the NPC equivalents of fields 5 and 6 `rotate90RightAnimation` and `rotate90LeftAnimation` (`GrandExchangeEvent.java:272-273`), the reverse of today's names; this note uses today's.

## 2. Open sources with a weapon to stance table

All seven ids below are in the order of section 1. Counts against "snapshot 430 weapons" use the 911 items of section 5.

| Source | File | Shape | Size | Licence | Data date | Snapshot 430 weapons listed |
| --- | --- | --- | ---: | --- | --- | ---: |
| **Alter** | `data/cfg/items/renderAnimations/item_bas.json` and `bas_mappings.json` | item id to set number; set number to a named set (`bas.abyssal_whip`) with seven stance ids plus attack and block ids | 15,074 and 82,459 bytes | BSD 2-Clause | 2024-12-26, revision 228 | 712 |
| **Weapon Animation Replacer** | `src/main/resources/com/weaponanimationreplacer/data.json` | `animationSets`: 138 named sets; `poseanims`: set name to example item ids (466 ids under 90 names) | 91,085 bytes | BSD 2-Clause | 2026-08-03, live game | 361 |
| RSMod v2 | `api/cache-enricher/src/main/resources/org/rsmod/api/cache/enricher/obj/objs.toml`, with `.data/symbols/obj.sym` for ids | per item by internal name; only fields that differ from the unarmed set | 718,971 and 947,594 bytes | ISC | file edited 2025-01 to 2025-04; README says revision 233 | 753 |
| RSMod v1 | `data/cfg/items.yml` | per item id, `render_animations` list of seven | 4,307,611 bytes | Apache-2.0 | 2019-03, revision 180 | 326 |

Pinned URLs:

- Alter, commit `9ddbbbe`: <https://github.com/AlterRSPS/Alter/blob/9ddbbbe3bdf47d79ff919a12d01ce1a7e6be6169/data/cfg/items/renderAnimations/item_bas.json> and <https://github.com/AlterRSPS/Alter/blob/9ddbbbe3bdf47d79ff919a12d01ce1a7e6be6169/data/cfg/items/renderAnimations/bas_mappings.json>
- Plugin, commit `504f6bd`: <https://github.com/geheur/weapon-animation-replacer/blob/504f6bd6d208aeca18e6ebb0dfd05f45a50a2daf/src/main/resources/com/weaponanimationreplacer/data.json>
- RSMod v2, commit `fa13b3f`: <https://github.com/rsmod/rsmod/blob/fa13b3f67172ef36e15d6b1514358aee61411796/api/cache-enricher/src/main/resources/org/rsmod/api/cache/enricher/obj/objs.toml>
- RSMod v1, commit `c58e5ce`: <https://github.com/Tomm0017/rsmod/blob/c58e5ce7541e00bba57cc9cedf1330b5dcbcfa42/data/cfg/items.yml>

### Alter (recommended)

- **[evidence]** `item_bas.json` holds 970 items (highest id 29851); 712 are snapshot 430 weapons and the other 258 have ids above 21391, so every entry at or below the snapshot's last id is a snapshot 430 weapon. `bas_mappings.json` holds 177 named sets; the items use 143 of them.
- **[evidence]** The server joins them in the order ready, turn, walk, walk back, walk left, walk right, run (`game-server/.../ItemMetadataService.kt` lines 154 to 170).
- **[evidence]** Licence: the `LICENSE` file is BSD 2-Clause, "Copyright (c) 2023, Alter". The README badge says ISC (line 75), which disagrees with the file.
- **[evidence]** Origin: commit `ec42670` of 2024-12-26 added both files with the message "Thanks to @Z-Kris most of render animations added for most of the items". Where those values were taken from is not stated, and Z-Kris has no public repository holding them.
- **[evidence]** RSMod v2 carries the same data: on the 702 snapshot 430 weapons both list, all 702 sets are equal, and both files hold 50 distinct sets and 513 items with a set other than the unarmed one. They are one dataset, not two witnesses.

### Weapon Animation Replacer (independent check)

- **[evidence]** Its developer tool records `getIdlePoseAnimation()`, `getIdleRotateRight()`, `getWalkAnimation()`, `getWalkRotate180()`, `getWalkRotateLeft()`, `getWalkRotateRight()` and `getRunAnimation()` of players seen in the live client, keyed by the worn weapon (`src/test/java/.../WeaponAnimationReplacerToolsPlugin.java` lines 246 to 277). **[guess]** every set in `data.json` came from that recorder; `AnimationSets.java` writes them out by hand.
- **[evidence]** `data.json` stores each set as stand, walk, run, walk back, left, right, turn (`Swap.java:393-402`), which is not the appearance order.
- **[evidence]** `poseanims` lists only example ids per set; the plugin widens them at run time through RuneLite's `ItemVariationMapping` (`Constants.java:58-71`), which was not read. Its true reach is larger than the 361 listed.
- **[evidence]** Against Alter, on snapshot 430 weapons: 347 in both, 340 equal. The 7 that differ: Dharok's greataxe 4718 and Meat tenderiser 7449 (run 824 in Alter, 11466 in the plugin), Dragon cane 12373 and Royal sceptre 12439 (staff set in Alter, unarmed in the plugin), Mouse toy 6541 (unarmed in Alter, whip set in the plugin), Butterfly net 10010 (staff set in Alter; stand 809 with the unarmed walk in the plugin), Keris 10581 (unarmed in Alter, staff set in the plugin). Which side is right for the last five is not known.

### RSMod v2 and RSMod v1 (not recommended)

- **[evidence]** RSMod v2 lists 51 snapshot 430 weapons that Alter does not, every one with a weapon category and no stance field, which its code reads as the unarmed set (`ParamBuilds.kt:168-174`, `DefaultObjCacheEnricher.kt:63-69`). For 18 of them another table gives a different set: Boxing gloves 7671 and 7673 (stand 3677, walk 3680 in RSMod v1; the plugin agrees for 7671), the eleven Crystal halberd ids 13091 to 13101 (staff set in RSMod v1), and Toxic blowpipe (empty) 12924, Heavy casket 19941, Large spade 20164, Clueless scroll 20249 and Hand fan 21354 (plugin). So "listed without stance fields" there means "not recorded", and Alter's explicit list is the safer one.
- **[evidence]** RSMod v1 holds 3,249 equipment entries but only 367 carry a `render_animations` list; the other 2,882 say `render_animations: null`, among them the Bronze, Iron and Steel spears (1237, 1239, 1241). Where it and Alter both list a snapshot 430 weapon (308 items) 288 are equal. Among the 20 differences: RSMod v1 makes the Saradomin sword and five other godsword-set items walk backwards with 7049, which is `HUMAN_POH_BUILD_DWH`, a plain error; and it gives the Abyssal bludgeon the Granite maul set, although snapshot 430 already holds 1652, 3293 and 2847, named `ABYSSAL_BLUDGEON_READY`, `_WALK` and `_RUN`, which Alter and the plugin use.

### Checked and rejected

- **osrsbox-db** (GPL-3.0): no animation ids. `docs/items-json/4151.json` has `weapon.stances`, which are combat styles (`combat_style`, `attack_type`, `experience`) **[evidence]**.
- **OSRS Wiki**: searches for `"1660" "1661" whip` and `"7053" "7052" godsword` return only "List of sound IDs" and "NPC IDs" **[evidence]**. **[guess]** the wiki has no stance id table.
- **RuneLite**: `gameval/AnimationID` gives a name per sequence id. The local 2018 `runelite-api/.../AnimationID.java` has 107 constants and, apart from `IDLE = -1`, none for standing, walking or running. Neither maps a weapon to a set **[evidence]**.
- **Kronos** (revision 184, `Leif-Yggdrasil/Kronos-184-Fixed`): `kronos-server/data/items/weapon_types.json` (47,330 bytes) holds named weapon types with a `renderAnimations` list of seven, and `item_info.json` (2,343,702 bytes) gives 626 items a `weapon_type`. The repository has no licence **[evidence]**, so it is not usable.
- **Elvarg**: `camelot317/Elvarg` (GPL-3.0, last commit 2017-03-05) has `Elvarg - Server/data/cache/definitions/items.txt` (2,786,581 bytes) with `StandAnim`, `WalkAnim`, `RunAnim` and four turn fields per item. It is the only table from 2017, and it is wrong where it can be checked: the whip's `StandAnim` is 1832, which is `HUMAN_RUBBER_CHICKEN_READY`, and its default `Turn90CCWAnim` is 821, the same as `Turn90CWAnim` **[evidence]**. `RSPSApp/elvarg-rsps` has the same fields in a 15,862,516 byte `items.json` and no licence.
- **OpenRune-Server** (ISC): `.data/raw-cache/server/items.toml` (1,372,747 bytes) holds the RSMod v2 data by symbolic names such as `seq.slayer_abyssal_whip_walk`, so it needs a name table for both items and sequences **[evidence]**.
- **Zenyte**: a GitHub search found only unlicensed re-uploads with no stars; none was read.

## 3. Does a cache hold this? No

**[evidence]** `scan2757.py` decodes every param, item, enum, struct, db table and db row of the build 242 cache (`<data workspace>/caches/osrs/openrs2-2757/cache`) with the formats of RuneLite's cache library 1.13.6, and refuses unknown opcodes. All 2,776 params, 34,766 items, 5,970 enums, 4,048 structs, 271 tables and 17,104 rows decode. Findings:

- One param has type seq: 1323 (default 7336). No item sets it. 72 structs do; they are boss information records (struct 375 is "Tombs of Amascut: Entry Mode").
- The 1,972 weapon-slot items use 82 different params, none of type seq. The whip, Rune 2h sword, Rune crossbow, Staff of air, Armadyl godsword, Granite maul and Dharok's greataxe hold none of their stance ids in any param.
- No enum has sequence values. The enums keyed by item that include at least three sample weapons hold integers such as 500 and 600 (906; **[guess]** special attack energy), texts describing special attacks (1739) and booleans (4391).
- Two db tables have a sequence column: 176 (99 rows; the first is "Bronze cannon") and 185 (3 rows; "Eternal brazier"). Their sequence values are 13174 to 13586.
- Rows of table 88 contain numbers such as 1660 to 1664 and 2561 to 2563, but they are sound ids with names (`mta_deposit_bone` 1660, `staff_lunge` 2561).
- The item category (opcode 94) is not a stance key: the Rune 2h sword and the Armadyl godsword are both category 61 and have different stance sets.

**[evidence]** The same scan on snapshot 430 finds 470 params (none of type seq), no enum with sequence values, one struct and no db tables. Its weapons carry no params at all.

**[evidence]** This matches the protocol: the build 242 server still sends the seven ids in the appearance block (section 1), and RSMod v2 has to add them as its own server-side params (`bas_readyanim` to `bas_running`, `BaseParams.kt:164-170`) from an outside file.

## 4. Do the ids apply to revision 149?

**[evidence]** As sequences, yes. `compare.py` and `seqcompare3.py`, run against `<data workspace>/caches/osrs/openrs2-430/cache` through the repo's `Js5Store`:

- Snapshot 430 has 7,636 sequences, ids 0 to 7635. Alter names 129 distinct sequence ids for the 712 snapshot 430 weapons it lists. All 129 exist in snapshot 430 and all 129 are in `animation_names.json`, so every frame uses frame map 0.
- Against the build 242 cache, all 129 have the same frame count, the same per-frame durations and the same other opcodes. Left out of that comparison: frame sounds, whose encoding changed, and opcode 16 with one byte, which the 2026 files add in front. For 80 of them every frame file is byte-identical. For the other 49 (the godsword, Zamorakian spear, bludgeon, ballista, Elder maul, Dinh's bulwark, pet rock and butterfly net families among them) the frame bytes differ. **[guess]** those are the same clips exported again; frame map 0 itself grew from 227 to 245 transforms between the two caches **[evidence]**. This does not matter to the add-on, which reads frames from snapshot 430.

Sample, from Alter. Every id below exists in snapshot 430.

| Item | Alter set | Stand | Turn | Walk | Back | Left | Right | Run |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4151 Abyssal whip | `bas.abyssal_whip` | 808 | 823 | 1660 | 1660 | 1660 | 1660 | 1661 |
| 1333 Rune scimitar | `bas.scimitar` | 808 | 823 | 819 | 820 | 821 | 822 | 824 |
| 1319 Rune 2h sword | `bas.2h_sword` | 2561 | 823 | 2562 | 2562 | 2562 | 2562 | 2563 |
| 861 Magic shortbow | `bas.shortbow` | 808 | 823 | 819 | 820 | 821 | 822 | 824 |
| 9185 Rune crossbow | `bas.crossbow` | 4591 | 823 | 4226 | 4227 | 821 | 822 | 4228 |
| 1381 Staff of air | `bas.polestaff` | 813 | 1209 | 1205 | 1206 | 1207 | 1208 | 1210 |
| 3204 Dragon halberd | `bas.halberd` | 813 | 1209 | 1205 | 1206 | 1207 | 1208 | 1210 |
| 11802 Armadyl godsword | `bas.2h_straight_sword` | 7053 | 7044 | 7052 | 7052 | 7048 | 7047 | 7043 |
| 1249 Dragon spear | `bas.dragon_spear` | 813 | 1209 | 1205 | 1206 | 1207 | 1208 | 1210 |
| 4153 Granite maul | `bas.granite_maul` | 1662 | 823 | 1663 | 1663 | 1663 | 1663 | 1664 |
| 4718 Dharok's greataxe | `bas.dharoks_greataxe` | 2065 | 823 | 2064 | 2064 | 2064 | 2064 | 824 |
| 12926 Toxic blowpipe | `bas.toxic_blowpipe` | 813 | 1209 | 1205 | 1206 | 1207 | 1208 | 1210 |

RuneLite names: 808 `HUMAN_READY`, 813 `HUMAN_STAFFREADY`, 819 `HUMAN_WALK_F`, 820 `HUMAN_WALK_B`, 821 `HUMAN_WALK_L`, 822 `HUMAN_WALK_R`, 823 `HUMAN_TURNONSPOT`, 824 `HUMAN_RUNNING`, 1205 `HUMAN_HALBERDWALK_F`, 1206 `HUMAN_HALBERDWALK_B`, 1207 `HUMAN_HALBERDWALK_L`, 1208 `HUMAN_HALBERDWALK_R`, 1209 `HUMAN_HALBERDTURNONSPOT`, 1210 `HUMAN_HALBERDRUNNING`, 1660 `SLAYER_ABYSSAL_WHIP_WALK`, 1661 `SLAYER_ABYSSAL_WHIP_RUN`, 1662 `SLAYER_GRANITE_MAUL_READY`, 1663 `SLAYER_GRANITE_MAUL_WALK`, 1664 `SLAYER_GRANITE_MAUL_RUN`, 2064 `BARROW_DHAROK_WALK`, 2065 `BARROW_DHAROK_READY`, 2561 `HUMAN_DH_WEAPON_READY`, 2562 `HUMAN_DH_WEAPON_WALK`, 2563 `HUMAN_DH_WEAPON_RUN`, 4226 `XBOWS_HUMAN_WALK_F`, 4227 `XBOWS_HUMAN_WALK_B`, 4228 `XBOWS_HUMAN_RUN`, 4591 `XBOWS_HUMAN_READY`, 7043 `DH_SWORD_UPDATE_RUN`, 7044 `DH_SWORD_UPDATE_TURNONSPOT`, 7047 `DH_SWORD_UPDATE_WALK_RIGHT`, 7048 `DH_SWORD_UPDATE_WALK_LEFT`, 7052 `DH_SWORD_UPDATE_WALK`, 7053 `DH_SWORD_UPDATE_READY`.

**[evidence]** Agreement on the sample: RSMod v2 and RSMod v1 give the same seven for all twelve. The plugin lists ten of the twelve (it has no entry for 861 or 12926, and lists 12924, the empty blowpipe, with the staff set) and agrees on nine. The one difference is its run for Dharok's greataxe, 11466, which snapshot 430 does not have. The plugin keeps both a "Dharok's greataxe" set (run 11466) and a "Dharok's greataxe (old run)" set (run 824).

**[guess]** The weapon to set assignment of 2024 was already in force in July 2017 for these weapons. Support: every sequence the sets need was already in the cache, the names of the sequences match the weapons, and RSMod v1 (2019) agrees on all twelve. Against: assignments do change (Dharok's run), and no table from 2017 that can be trusted was found.

## 5. Coverage gap

**[evidence]** Revision 149 item definitions carry no wear position (`cache-2757-wear-positions.md`), so "weapon" here means: a snapshot 430 item with a worn model whose id still exists in cache 2757 with `wearPos1` 3. `src/rsps_toolkit/data/item_wear.json` lists 911 such items; 260 of them hide the shield and 69 are named "null". The 185 snapshot 430 worn items that cache 2757 emptied are not in that file and have no known slot; **[guess]** a few of them are weapons.

**[evidence]** Of the 911 (`compare2.py`, `gap.py`):

| | Items | Share |
| --- | ---: | ---: |
| Listed by Alter | 712 | 78.2% |
| of which a set other than the unarmed one | 357 | 39.2% |
| of which the unarmed set | 355 | 39.0% |
| Not listed by Alter | 199 | 21.8% |
| of which listed by the plugin, RSMod v1 or RSMod v2 | 51 | 5.6% |
| of which in no table | 148 | 16.2% |

- The 712 use 36 distinct sets under 100 set names. The largest: unarmed 355 items, staff and halberd (813, 1209, 1205 to 1208, 1210) 205, banner (1421 to 1427) 43, crossbow 15, 2h sword 14, godsword 12, Dharok's set 8, whip 5.
- The 148 in no table: 69 named "null", and props such as Stone bowl, Beer, Fishbowl, Fungicide spray, Ghost buster 500, the crossbow stocks, Rock hammer and Secateurs. **[guess]** nearly all of them use the unarmed set.
- The 51 listed elsewhere are all in RSMod v2. 19 of them have a known set other than the unarmed one: the 18 of section 2 plus Crate with zanik 8871 (4193, 4194 in RSMod v1). The rest include the six Barrows "0" weapons (4866, 4890, 4914, 4938, 4962, 4986), for which no table gives a set; **[guess]** they share their intact weapon's set.

**[guess]** Using Alter and treating every unlisted weapon as unarmed gives the right set for about 95% of the 911: 712 listed, plus the roughly 150 props and nulls, with about 25 to 35 real weapons wrong until they are added by hand from the plugin and RSMod v1.

## Recommendation

1. Ask the user to approve downloading Alter's two files (97,533 bytes, BSD 2-Clause) and the plugin's `data.json` (91,085 bytes, BSD 2-Clause).
2. Generate one data file from them with a script kept in the repo, as `scripts/generate-item-wear.py` does: per snapshot 430 weapon id, the seven ids and the set name, with the source commit recorded and the BSD notice kept. Refuse any sequence id that snapshot 430 lacks, so a later change such as run 11466 cannot slip in.
3. Let the plugin fill the listed gaps and flag the seven disagreements instead of choosing silently.
4. Keep the panel's own clip choice as the override, since the 2017 assignment is not verified.

## Open questions

- Which set each weapon had in July 2017. A packet capture or a server source from 2017 with trustworthy data would settle it; neither was found.
- Where Alter's values come from. The commit credits Z-Kris and names no source.
- Which side is right on the five Alter and plugin disagreements that are not the Dharok run (Dragon cane, Royal sceptre, Mouse toy, Butterfly net, Keris), and whether the empty Toxic blowpipe 12924 differs from the loaded 12926.
- When Dharok's run changed from 824 to 11466, and whether other sets changed between 2017 and 2024 in the same way.
- What RuneLite's `ItemVariationMapping` adds to the plugin's 466 example ids; it was not read.
- Whether the 49 stance sequences whose frame bytes changed since 2017 look different. This affects only a comparison with today's game, not the add-on.
- The snapshot 430 to `gamepack-149` pairing rests on indirect evidence, as [model-formats.md](model-formats.md) records.
