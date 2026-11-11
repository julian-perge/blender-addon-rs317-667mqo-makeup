# Tests and reference data

Read this before adding fixtures, changing expected values or running tests.

## Commands

```bash
uv run pytest
BLENDER_USER_RESOURCES="$PWD/.blender-test-profile" scripts/test-blender.sh
prek run --all-files --hook-stage pre-push
PYTHONPATH=src uv run python3 <script.py>
```

- `uv run pytest` runs unit tests without Blender.
- `scripts/test-blender.sh` runs `tests/blender/` in headless Blender, importing the extension from `src/` without installing it. Extra arguments go to pytest.
- The pre-push hook runs the Blender tests.
- Ad-hoc scripts need `PYTHONPATH=src` because uv does not install the package.

For dump round trips and installed-extension checks, read [Blender execution and packaging](blender.md).

## Fixture provenance

Real models in `tests/fixtures/models/` come from the Old School dump at `<data workspace>/dump/dump_index/models/` and the 667 cache. Each model's neighboring `<id>.json` is RuneLite's decoding and supplies its expected values. After adding a model, regenerate those references with the command in [ModelReference.java](../../tests/fixtures/ModelReference.java).

Apply [Coding standards](../../CODING_STANDARDS.md) when choosing expected values. Round-trip tests compare decoded models, not bytes.

Preset, drop model and PMN expectations in `tests/fixtures/presets/`, `tests/fixtures/drops/` and `tests/fixtures/pmn/` come from the original exporter. Their recording procedures are in [preset_reference.py](../../tests/fixtures/preset_reference.py), [drop_reference.py](../../tests/fixtures/drop_reference.py) and [pmn_reference.py](../../tests/fixtures/pmn_reference.py). Never regenerate them from the current exporter.

## Reference data

The local data workspace `<data workspace>/` separates source caches, generated exports, source references and legacy RS2 material. Its index and reversible move record are `README.md` and `layout-migration.json` there. The old paths (`dump`, `dump317`, `decompiled-clients` and the 2013 cache folder) remain relative symlinks, so existing scripts and Blender texture settings still resolve.

- `dump/` is the output of `osrs-cache-dumper` (Java 25, Maven, `net.runelite:cache:1.13.6`; its README lists the targets) for the first Old School cache, revision 1, 22 Feb 2013. `dump_index/models/<id>.dat` holds 27,612 decompressed old-format models, `textures/<id>.png` 55 textures on their full canvas (128 or 64 pixels square), `items/ItemDefinitions.json` maps item ids to model ids (the Abyssal whip 4151 uses inventory model 5412 and male worn model 5409), and `item_icons/<itemId>.png` holds rendered inventory icons. Its `models_obj/` OBJ previews drop skins and priorities, so use them to check geometry and UVs, never to edit.
- The dump's textures 0 to 49 show the same pictures as `texture_dump.zip`, but none is pixel-identical: colours differ by 4 to 9 of 255 on average. The cause, read from the code but not recomputed: the dumper's `textures` target draws them through RuneLite's `TextureDefinition.method2680` at `JagexColor.BRIGHTNESS_MIN`, while `texture_dump.zip` and the 317 extractor write the stored palette.
- `dump317/` holds the 317 cache's 7,456 models and 50 textures in the same layout, written by the dumper's 317 extractor, which [Model format references](../research/model-formats.md) describes with the cache. The owner chose Java for it, and the dumper repository stays local: never add a remote to it or push it. The 9.7 MB 317 cache zip is committed in the dumper's test resources.
- `caches/osrs/` holds the OpenRS2 caches: `openrs2-430/` (snapshot 430, revision 149; the add-on's Cache folder preference points at its `cache/` folder, and the tests that read it need `RSPS_SNAPSHOT_430_CACHE` set to that folder; they skip when it is unset), `openrs2-34/` (revision 170) and `openrs2-2757/` (build 242). The dumper cannot open cache 2757, which has no index 16, so `scripts/generate-item-wear.py` has its own decoder.
- Cache 430's dump needs `kits/KitDefinitions.json`, made with the dumper's `kits` target on a temporary copy of the cache.

## Freeze-prone models

Tests using fixtures with faces that repeat a vertex (`osrs` 0, 49 and 3153; `worn` 3443 and 6658) and the `rs667` fixtures need:

```python
@pytest.mark.timeout(10, method="thread")
```

The 667 importer keeps these faces in the mesh, where they can freeze Edit Mode. The thread method terminates the entire Blender run with exit code 1: it stopped a measured Edit Mode freeze within a second of the limit, while the signal method did not.

Neither timeout method stopped `bmesh.ops.triangulate` on model 6658. A hang inside a bmesh call still needs killing by hand.
