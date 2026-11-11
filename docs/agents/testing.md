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

For cache round trips and installed-extension checks, read [Blender execution and packaging](blender.md).

## Fixture provenance

Real models in `tests/fixtures/models/` come from Old School caches: `osrs` and `worn` from the first Old School cache (revision 1, 22 Feb 2013), and `osrs149` from snapshot 430. Each model's neighboring `<id>.json` is RuneLite's decoding and supplies its expected values. After adding a model, regenerate those references with the command in [ModelReference.java](../../tests/fixtures/ModelReference.java).

Apply [Coding standards](../../CODING_STANDARDS.md) when choosing expected values. Round-trip tests compare decoded models, not bytes.

Preset, drop model and PMN expectations in `tests/fixtures/presets/`, `tests/fixtures/drops/` and `tests/fixtures/pmn/` come from the original exporter. Their recording procedures are in [preset_reference.py](../../tests/fixtures/preset_reference.py), [drop_reference.py](../../tests/fixtures/drop_reference.py) and [pmn_reference.py](../../tests/fixtures/pmn_reference.py). Never regenerate them from the current exporter.

## Reference data

The local data workspace `<data workspace>/` separates source caches, generated exports, source references and legacy RS2 material. Its index is `README.md` there.

- `caches/osrs/` holds the OpenRS2 caches: `openrs2-430/` (snapshot 430, revision 149; the add-on's Cache folder preference points at its `cache/` folder, and the tests that read it need `RSPS_SNAPSHOT_430_CACHE` set to that folder; they skip when it is unset), `openrs2-34/` (revision 170) and `openrs2-2757/` (build 242). `scripts/generate-item-wear.py` reads items from caches 2757 and 430 with the add-on's item decoder.
- The first Old School cache (OpenRS2 archive 241, revision 1, 22 Feb 2013) is the source of the 2013 animation bundle and of the `osrs` and `worn` fixtures. In it, the Abyssal whip 4151 uses inventory model 5412 and male worn model 5409.
- Textures 0 to 49 that a local export tool (not in this repo) wrote from the 2013 cache show the same pictures as `texture_dump.zip`, but none is pixel-identical: colours differ by 4 to 9 of 255 on average. The cause, read from the code but not recomputed: that tool draws them through RuneLite's `TextureDefinition.method2680` at `JagexColor.BRIGHTNESS_MIN`, while `texture_dump.zip` holds the stored palette.

## Freeze-prone models

Tests using fixtures with faces that repeat a vertex (`osrs` 0, 49 and 3153; `worn` 3443 and 6658) need:

```python
@pytest.mark.timeout(10, method="thread")
```

These faces can freeze Edit Mode when they are in the mesh. Import sets them aside ([ADR 0005](../adr/0005-faces-that-repeat-a-vertex-stay-out-of-the-mesh.md)), and the timeout stops a test that lets one through. The thread method terminates the entire Blender run with exit code 1: it stopped a measured Edit Mode freeze within a second of the limit, while the signal method did not.

Neither timeout method stopped `bmesh.ops.triangulate` on model 6658. A hang inside a bmesh call still needs killing by hand.
