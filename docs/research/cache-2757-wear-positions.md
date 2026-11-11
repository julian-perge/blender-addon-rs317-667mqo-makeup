# Item wear positions from cache 2757

Researched 2026-11-07 against OpenRS2 cache 2757 (OSRS live, build 242, 2026-11-03), snapshot 430 (build 149) and the add-on's current data. Each claim is **Evidence** (read or measured, source named) or **Guess**. No file from the download was executed. Scripts and outputs are in `<scratch folder 2026-11-07-cache2757>/`.

## Summary

- Cache 2757 carries wear positions: 6,390 of its 34,766 items set `wearPos1`, and 419 set `wearPos3` (Evidence, `analysis.json`).
- The hide rule transfers to snapshot 430 well: of the 3,508 snapshot 430 items with a worn model, 2,659 keep the same name and the same six worn model ids, and 185 ids are emptied in 2757 (Evidence, section 3).
- `brings_own_arms` agrees with 2757 on all 306 torso items, for both bodies (Evidence, section 4.2). 64 of the 76 ids in `data/platebodies.json` hide the arms in 2757; the other 12 are emptied ids.
- 352 head items hide the hair, the jaw or both; the panel has no data for these today (Evidence, section 4.3).
- `wearPos1` never disagrees with `data/item_slots.json`; 2757 adds a slot for 294 items that osrsbox does not list (Evidence, section 4.4).

## 1. Download and decoding

Evidence: `https://archive.openrs2.org/caches.json` lists id 2757 as `oldschool`, `live`, build 242, timestamp `2026-11-03T10:00:06Z`, size 213,756,908. The cache page `https://archive.openrs2.org/caches/runescape/2757` links `/caches/runescape/2757/disk.zip`. Downloaded with curl to `<data workspace>/caches/osrs/openrs2-2757/downloads/disk.zip` (212,685,624 bytes) and unzipped to `cache/` next to it, with `metadata.json` (the `caches.json` record) and `provenance.json` (SHA-256 of every file) in the layout of `openrs2-430`. `main_file_cache.dat2` is `4cabf5ce...5fee`. `keys.json` is empty (`[]`, 0 keys in `caches.json`).

Evidence: the user's dumper cannot open this cache. `java -jar target/osrs-cache-dumper.jar ... items` stops with `Missing cache file main_file_cache.idx16`; cache 2757 has no index 16. Nothing was written under `exports/osrs/`.

Evidence: `<scratch folder 2026-11-07-cache2757>/items.py` (PEP 723, adapted from `tests/fixtures/animation149/export_clip.py`) reads index 2 group 10. It handles every item opcode of RuneLite's `ItemLoader`, stops on an unknown opcode, and checks that each definition ends exactly at its closing opcode 0. All 34,766 items of 2757 and all 21,392 of 430 pass. Cache 2757 uses opcodes 2 to 16, 27, 30 to 54, 65, 75, 94 to 115, 139, 140, 148, 149, 160, 161, 249 and 251; worn model ids now come from the 4-byte opcodes 45 to 50 instead of 23 to 26.

Evidence, cross-check: `CrossCheck.java` runs RuneLite's own `ItemLoader` (cache library 1.13.6 from the dumper's shaded jar, whose `ItemLoader.java` source is byte-identical to master `8f2aca1`) on a copy of the cache. Name, `wearPos1` to `wearPos3` and the four main model fields agree for all 34,766 items. For snapshot 430, `items.py` also agrees with the dumper's `exports/osrs/openrs2-430/dump/items/ItemDefinitions.json` on all 21,392 items.

## 2. What the opcodes mean

Evidence: RuneLite's `ItemLoader.java` at commit [`8f2aca1`](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/cache/src/main/java/net/runelite/cache/definitions/loaders/ItemLoader.java#L112-L149) reads opcode 13 as `wearPos1`, opcode 14 as `wearPos2` and opcode 27 as `wearPos3`, each one signed byte. `ItemDefinition.java` defaults all three to -1 (lines 56 to 58 at the same commit).

Evidence: the values are equipment slot numbers. RuneLite's [`KitType.java`](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/runelite-api/src/main/java/net/runelite/api/kit/KitType.java#L39-L50) lists the twelve appearance slots in order: 0 head, 1 cape, 2 amulet, 3 weapon, 4 torso, 5 shield, 6 arms, 7 legs, 8 hair, 9 hands, 10 boots, 11 jaw. This is the add-on's `SLOT_LABELS` order (`src/rsps_toolkit/formats/appearance.py:20`). Every value in 2757 is -1 or 0 to 11.

Evidence, how hiding works: the client does not decide it. Jagex's server is not public, so the evidence is from open server code:
- rsprot, the OSRS protocol library, build 242: [`setWornObj`](https://github.com/blurite/rsprot/blob/00b2e758ba2326dceffa2d48d9064c66d64e7cc5/protocol/osrs-242/osrs-242-model/src/main/kotlin/net/rsprot/protocol/game/outgoing/info/playerinfo/PlayerAvatarExtendedInfo.kt#L1361-L1391) stores each worn item's `wearpos2` and `wearpos3`. The [appearance encoder](https://github.com/blurite/rsprot/blob/00b2e758ba2326dceffa2d48d9064c66d64e7cc5/protocol/osrs-242/osrs-242-desktop/src/main/kotlin/net/rsprot/protocol/game/outgoing/codec/playerinfo/extendedinfo/PlayerAppearanceEncoder.kt#L63-L108) ORs them into one mask and writes 0 (empty) for every masked slot, before items (`obj + 0x800`) and kits (`kit + 0x100`).
- RSMod passes `objType.wearpos2` and `objType.wearpos3` of every worn item into that call ([`RspCycle.kt` lines 392 to 399](https://github.com/rsmod/rsmod/blob/fa13b3f67172ef36e15d6b1514358aee61411796/api/net/src/main/kotlin/org/rsmod/api/net/rsprot/RspCycle.kt#L392-L399)).
- LostCity's 2004 server ([`Player.ts` lines 1355 to 1412](https://github.com/LostCityRS/Engine-TS/blob/1d25566cb53e7af1b1cb18ade8af996316c19614/src/engine/entity/Player.ts#L1355-L1412)) collects `wearpos2` and `wearpos3` of every worn item and writes slot value 0 for each.

So an item with `wearPos2` or `wearPos3` equal to 6, 8 or 11 empties the arms, hair or jaw kit. Guess, well supported: Jagex's server behaves the same, because three independent servers agree and the client renders only what the appearance block sends.

## 3. Do the 2757 facts apply to snapshot 430?

All Evidence, from `analyze.py`. Base: the 3,508 snapshot 430 items with a male or female worn model.

| Status in 2757 | Items | Meaning |
| --- | ---: | --- |
| match | 2,659 | same name, same six worn model ids |
| models_changed | 532 | same name, at least one model id differs |
| renamed | 97 | same models; 48 differ only in case or punctuation, such as "Pendant of lucien" |
| renamed_and_models_changed | 35 | such as 430 "Doctors' gown" to "Medical gown", 20601 "Elder maul" to "Wooden table" |
| emptied | 185 | id still present, named "Null", no models: mostly 10601 onwards, plus 9815, 9816 and 14 others up to 13282 |
| missing | 0 | |

The same model id does not mean the same model. Cache 2757 re-encoded these models (all 1,942 below end in the `fffd` or `fffe` footer, which snapshot 430 does not use, per revision-170-cache.md section 3), so `ModelCompare.java` decodes both caches with RuneLite's `ModelLoader` and compares fields. Of the 1,942 models of the 2,659 matching items, 1,799 are identical in vertices, faces, colours, labels, priorities, alphas and textures. Among the matching items, 2,302 have all models identical, 357 have some field changed, and 334 have changed vertices or faces. Examples: female platebody model 468 and the med helm model 395 (Dragon med helm) changed shape; vertex labels are equal in all 1,942.

## 4. Against the current guesses

### 4.1 `data/platebodies.json`

Evidence: 64 of the 76 ids hide the arms (`wearPos1` 4, `wearPos2` 6). The other 12 are emptied ids: 10618 White platebody, 10619 Initiate hauberk, 10620 Proselyte hauberk, 10690, 10691, 10697, 10698, 10776, 10780, 10782, 10798 and 10800. Each shares its wiki page with another id that matches and hides the arms (for example 10776 with 2653 Zamorak platebody). No wiki platebody keeps the arms. Guess: the emptied ids were duplicate copies that Jagex removed after 2017.

### 4.2 `brings_own_arms`

Evidence: over the 306 items that `item_slots.json` puts in the torso slot, the label rule (`src/rsps_toolkit/formats/appearance.py:252`) and 2757 agree on every item for both bodies: 269 bring their own arms and hide slot 6, 37 do not and keep it. No item is ticked wrongly and none is missed. The 37 are the aprons, the chainbodies, leather, hardleather, studded and d'hide bodies, the stripy pirate shirts and the zombie shirt. The agreement holds for the 52 of the 269 whose models changed, including the robe tops whose male model moved from 170 to 26619.

Evidence: 2757 hides the arms for 7 more torso items that osrsbox does not place in the torso slot: the Barrows "0" stages (4872, 4896, 4920, 4944, 4968, 4992) and 6657 Camo top. Two torso items also hide the hands: 284 Plague jacket and 6657 Camo top.

### 4.3 Head items: hair and jaw

Evidence: 568 snapshot 430 items have `wearPos1` 0. 216 hide nothing, 175 hide the hair, 173 hide the hair and the jaw, and 4 hide only the jaw: 3057 Mime mask, 4164 Facemask, 11282 Beret mask, 19988 Blacksmith's helm. Of the 352 that hide something, 260 are matches, 8 are only renamed and 84 changed model ids. Full helms hide the hair and the jaw (1163 Rune full helm), med helms, coifs and most hoods hide the hair (1149 Dragon med helm), and the partyhats and the Black mask hide nothing.

### 4.4 `data/item_slots.json`

Evidence: of the 3,508 items, 2,764 have the same slot in both, 0 disagree, 450 have a slot in neither (unequippable items with held models, such as unstrung bows and fishing rods), and 294 have a slot only in 2757 (172 weapons, 40 shields, 36 jaw, 19 head, 8 hands, 7 torso, 7 legs, 5 cape). The 36 jaw-slot items are Clan wars capes and the Barbarian Assault icons. Guess: Jagex puts them in slot 11 so they can be worn with a cape.

Evidence: for weapons, 228 two-handed items agree (osrsbox two-handed and `wearPos2` 5). 32 hide the shield but are not in osrsbox's two-handed list, such as the god banners, the Barrows "0" weapons and the Toxic blowpipe. 9 Pharaoh's sceptre ids are two-handed in osrsbox but not in 2757; all 9 changed models or names since 2017. Four boxing glove ids hide the shield and the hands.

## 5. Notable items

From `wear_2757_vs_430.json`. "Shape" means vertices or faces of one of the item's models differ between 430 and 2757.

| Id | Item | wearPos1 | Hides | Status | Note |
| ---: | --- | ---: | --- | --- | --- |
| 1127 | Rune platebody | 4 | arms | match | female model 468 changed shape |
| 2653 | Zamorak platebody | 4 | arms | match | female 3383 changed shape, as found in revision-170-cache.md |
| 75 | Khazard armour | 4 | arms | match | female 468 changed shape |
| 4720 | Dharok's platebody | 4 | arms | match | models identical |
| 544 | Monk's robe top | 4 | arms | models_changed | 170 to 26619 male, 348 to 3848 female |
| 284 | Plague jacket | 4 | arms, hands | match | |
| 1113 | Rune chainbody | 4 | none | match | |
| 1101 | Iron chainbody | 4 | none | match | |
| 1163 | Rune full helm | 0 | hair, jaw | match | |
| 11335 | Dragon full helm | 0 | hair, jaw | models_changed | |
| 10350 | 3rd age full helmet | 0 | hair | renamed_and_models_changed | |
| 1149 | Dragon med helm | 0 | hair | match | model 395 changed shape |
| 1169 | Coif | 0 | hair | match | |
| 1506 | Gas mask | 0 | hair, jaw | match | |
| 3057 | Mime mask | 0 | jaw | match | |
| 8921 | Black mask | 0 | none | match | |
| 2631 | Highwayman mask | 0 | none | match | |
| 1038 | Red partyhat | 0 | none | match | |

## 6. Recommendation

1. Generate `data/item_wear.json` from cache 2757 with a script kept in the repo, recording the cache id, build and `dat2` SHA-256. For every snapshot 430 item with a worn model whose status is match, renamed, models_changed or renamed_and_models_changed, store `wearPos1` and the hidden slots. Leave out the 185 emptied ids, or keep them only with an explicit flag.
2. Let it replace both `data/platebodies.json` and `data/item_slots.json`. The slot table only gains items (294) and loses none. The two-handed list becomes "`wearPos2` or `wearPos3` is 5".
3. Drive all three toggles from it: Covers arms from slot 6, Covers hair from slot 8, Covers jaw from slot 11. Lock or default them as the panel does for platebodies today. Keep `brings_own_arms` as a test or a fallback; it agreed on all 306 torso items.
4. Store the status per item. For the 567 items whose model ids changed and the 334 whose models changed shape, the 2017 model is not the one the 2026 hide rule was written for. Guess: the hide rule rarely changes with a remodel; the torso evidence supports this (52 changed torso items, all still agree with the label rule), but no 430 data can check hair and jaw. The panel's toggles let the user override these.

## Files

- Raw per-item results: `<scratch folder 2026-11-07-cache2757>/wear_2757_vs_430.json`. One row per snapshot 430 worn item: `id`, `status`, `name_430`, `name_2757`, `wearPos1` to `wearPos3`, `models_430` and `models_2757` (male and female 0 to 2), `osrsbox_slot`, `wiki_platebody`, `brings_own_arms_male`/`_female`, and `model_fields_changed` for matches.
- Summary counts and lists: `<scratch folder 2026-11-07-cache2757>/analysis.json`.
- Full decodes: `items2757.json`, `items430.json`. RuneLite cross-check: `runelite2757.tsv`, `model_compare.tsv`.
- Scripts: `items.py`, `analyze.py`, `CrossCheck.java`, `ModelCompare.java`. Fetched sources: `ItemLoader.java`, `src/`.
