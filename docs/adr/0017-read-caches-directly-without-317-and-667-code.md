# The add-on reads caches directly, and the 317 and 667 code is gone

This supersedes [ADR 0003](0003-old-school-caches-come-first.md).

On 2026-11-11 the owner approved [the spec](../../spec/old/remove-dumper-and-legacy-revisions.md) that removes the separate Java export tool and the code that served only revisions 317 and 667 (issue 24 (`git show 2a78edd:.scratch/osrs-focus/issues/24-remove-317-and-667-only-code.md`)). The add-on and its tests read Old School caches from raw OpenRS2 downloads in Python. The Cache folder preference is the only cache setting, and it names the `cache/` folder of an OpenRS2 download. Kits, items and enums are decoded from config index 2 (groups 3, 10 and 8), and models are read from index 7. The removed code stays on the branch `publish/fork-main`.

The owner decided four questions in the spec interview:

- The old model format stays. It is also the format of Old School revision 1 (2013), the format the exporter writes, and the format of the 2013 animation bundle and of the `osrs` and `worn` fixtures. Only the 667 importer, the `rs667` fixtures and the 317 and 667 cache files went.
- Old School revision 1 models are tested only through the committed fixtures, because the repo holds no raw revision 1 cache.
- Textures still come from PNG files in the texture folder and `texture_dump.zip`. Decoding textures from cache index 9 is a separate spec.
- Blender 5.2 is the manifest floor (`blender_version_min = "5.2.0"`). The tests run on Blender 5.3, and no Blender 5.2 binary is tested.

`scripts/generate-item-wear.py` now uses the add-on's item decoder (`formats/item_definition.py`). Its output for caches 2757 and 430 is byte-equal to the committed `data/item_wear.json`, so the decoder needed no opcode that the add-on lacked.

Consequences:

- A contributor builds and tests the add-on with no outside tool. Tests that read the real snapshot 430 cache skip unless `RSPS_SNAPSHOT_430_CACHE` names it.
- Upgrade RS Materials reads only the `PMN_` names of the PMN tool. Materials named by the original 317 and 667 importers (`RS_Color_<colour>`, `Texture_<id>`) without stored game values are reported as unreadable.
- A new 2013 animation bundle cannot be made from this repo. The add-on still loads an existing bundle.
