"""The version-1 contract and pinned client fixture supply all animation expectations."""

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import cast

import pytest

from rsps_toolkit.animation.bundle import InvalidAnimationBundle, load_bundle

FIXTURE = Path(__file__).parents[1] / "fixtures/animations/2013"


def change(root, update):
    path = root / "animations/manifest.json"
    manifest = json.loads(path.read_text())
    update(manifest)
    path.write_text(json.dumps(manifest))


def test_loads_the_2013_reference_bundle(bundle_root):
    reference = json.loads((FIXTURE / "reference.json").read_text())
    request = json.loads((FIXTURE / "request.json").read_text())
    bundle = load_bundle(bundle_root)
    sequence_id = reference["sequence_id"]
    sequence = bundle.sequences[sequence_id]
    assert sequence.frame_ids == tuple(reference["frame_ids"])
    assert sequence.durations == tuple(reference["durations"])
    assert sequence.tick_ns == 20_000_000
    assert sequence.clock == "actor-render-v1"
    assert set(bundle.recipes) == set(request["recipes"])
    assert bundle.source.cache_revision == request["source"]["cache_revision"]
    assert dict(bundle.source.cache_hashes) == request["source"]["cache_hashes"]
    for key, expected in reference["frames"].items():
        actual = bundle.frames[int(key)]
        assert actual.map_id == expected["map_id"]
        assert actual.indices == tuple(expected["indices"])
        assert actual.x == tuple(expected["x"])
        assert actual.y == tuple(expected["y"])
        assert actual.z == tuple(expected["z"])
    for key, expected in reference["frame_maps"].items():
        actual = bundle.frame_maps[int(key)]
        assert actual.types == tuple(expected["types"])
        assert actual.labels == tuple(tuple(labels) for labels in expected["labels"])
    for key, expected in request["recipes"].items():
        actual = bundle.recipes[key]
        assert actual.sequence_ids == tuple(expected["sequence_ids"])
        assert actual.recolours == tuple(tuple(pair) for pair in expected["recolours"])
        for part, source in zip(actual.parts, expected["parts"], strict=True):
            assert part.key == source["key"]
            assert part.model_ids == tuple(source["model_ids"])
            assert part.offset == tuple(source["offset"])
    assert (bundle.textures[34].direction, bundle.textures[34].speed) == (1, 2)
    assert (bundle.textures[8].direction, bundle.textures[8].speed) == (0, 0)
    assert bundle.textures[34].sampling_size == 128
    assert bundle.models[5409].data == (FIXTURE / "raw/7/5409/0.dat").read_bytes()
    with pytest.raises(TypeError):
        cast(dict[int, object], bundle.frames)[1] = bundle.frames[sequence.frame_ids[0]]


@pytest.mark.parametrize("version", [2, True, 1.0, "1", None])
def test_rejects_wrong_version(bundle_root, version):
    change(bundle_root, lambda m: m.update(version=version))
    with pytest.raises(InvalidAnimationBundle, match="version"):
        load_bundle(bundle_root)


@pytest.mark.parametrize("section", ["frames", "frame_maps", "models", "textures", "sequences"])
def test_rejects_missing_dependencies(bundle_root, section):
    change(bundle_root, lambda m: m[section].pop(next(iter(m[section]))))
    with pytest.raises(InvalidAnimationBundle, match="frame|map|model|texture|sequence"):
        load_bundle(bundle_root)


@pytest.mark.parametrize(
    "field,value",
    [("types", 99), ("types", True), ("types", 1.5), ("labels", None), ("labels", [False]), ("labels", [-1])],
)
def test_rejects_invalid_frame_map_fields(bundle_root, field, value):
    def invalid(m):
        frame = next(iter(m["frames"].values()))
        m["frame_maps"][str(frame["map_id"])][field][frame["indices"][0]] = value

    change(bundle_root, invalid)
    with pytest.raises(InvalidAnimationBundle, match="map|type|label"):
        load_bundle(bundle_root)


@pytest.mark.parametrize(
    "field,value",
    [("clock", "modern"), ("tick_ns", True), ("durations", [0]), ("frame_ids", [True]), ("weapon_override", 256)],
)
def test_rejects_unsupported_sequence_metadata(bundle_root, field, value):
    change(bundle_root, lambda m: next(iter(m["sequences"].values())).update({field: value}))
    with pytest.raises(InvalidAnimationBundle, match="sequence|clock|tick|duration|frame|override"):
        load_bundle(bundle_root)


@pytest.mark.parametrize("section,asset", [("models", "5409"), ("textures", "34")])
def test_rejects_missing_or_changed_resource_bytes(bundle_root, section, asset):
    manifest = json.loads((bundle_root / "animations/manifest.json").read_text())
    path = bundle_root / manifest[section][asset]["path"]
    data = bytearray(path.read_bytes())
    data[0] ^= 1
    path.write_bytes(data)
    before = path.read_bytes()
    with pytest.raises(InvalidAnimationBundle, match=asset):
        load_bundle(bundle_root)
    assert path.read_bytes() == before
    path.unlink()
    with pytest.raises(InvalidAnimationBundle, match=asset):
        load_bundle(bundle_root)


@pytest.mark.parametrize("path", ["../outside.dat", "/tmp/outside.dat"])
def test_rejects_escaping_resource_paths(bundle_root, path):
    change(bundle_root, lambda m: m["models"]["5409"].update(path=path))
    with pytest.raises(InvalidAnimationBundle, match="path|5409"):
        load_bundle(bundle_root)


def test_rejects_symlinks_escaping_the_bundle(bundle_root, tmp_path):
    resource = bundle_root / "dump_index/models/5409.dat"
    outside = tmp_path.parent / f"{tmp_path.name}-outside.dat"
    try:
        outside.write_bytes(resource.read_bytes())
        resource.unlink()
        resource.symlink_to(outside)
        with pytest.raises(InvalidAnimationBundle, match="path|5409"):
            load_bundle(bundle_root)
    finally:
        outside.unlink(missing_ok=True)


@pytest.mark.parametrize("section", ["source", "recipes", "models", "textures", "sequences", "frames", "frame_maps"])
def test_requires_all_sections(bundle_root, section):
    change(bundle_root, lambda m: m.pop(section))
    with pytest.raises(InvalidAnimationBundle, match=section):
        load_bundle(bundle_root)


@pytest.mark.parametrize(
    "field,value",
    [("offset", [0, False, 0]), ("offset", [0, 0]), ("recolours", [[1]]), ("retextures", [[-1, 2]]), ("key", None)],
)
def test_rejects_malformed_recipe_parts(bundle_root, field, value):
    change(bundle_root, lambda m: m["recipes"]["default-male-whip"]["parts"][0].update({field: value}))
    with pytest.raises(InvalidAnimationBundle, match=field):
        load_bundle(bundle_root)


def test_rejects_duplicate_json_keys(bundle_root):
    path = bundle_root / "animations/manifest.json"
    path.write_text('{"version":1,"version":1}')
    with pytest.raises(InvalidAnimationBundle, match="Duplicate.*version"):
        load_bundle(bundle_root)


def test_rejects_wrong_png_dimensions_even_with_valid_hash(bundle_root):
    change(bundle_root, lambda m: m["textures"]["34"].update(width=1))
    with pytest.raises(InvalidAnimationBundle, match="34|width"):
        load_bundle(bundle_root)


def test_rejects_incompatible_resource_hash(bundle_root):
    change(bundle_root, lambda m: m["models"]["5409"].update(sha256="0" * 64))
    with pytest.raises(InvalidAnimationBundle, match="5409"):
        load_bundle(bundle_root)


def test_rejects_invalid_source_hashes(bundle_root):
    change(bundle_root, lambda m: m["source"]["cache_hashes"].update({"main_file_cache.idx7": "invalid"}))
    with pytest.raises(InvalidAnimationBundle, match="cache_hashes|idx7"):
        load_bundle(bundle_root)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_rejects_nonfinite_json_numbers(bundle_root, constant):
    path = bundle_root / "animations/manifest.json"
    path.write_text(path.read_text()[:-1] + ',"extra":' + constant + "}")
    with pytest.raises(InvalidAnimationBundle, match="Non-finite"):
        load_bundle(bundle_root)


def png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


@pytest.mark.parametrize("pixels", [b"", bytes(128 * 513 - 1), bytes(128 * 513 + 1), b"\x05" + bytes(128 * 513 - 1)])
def test_rejects_incomplete_or_invalid_png_scanlines(bundle_root, pixels):
    path = bundle_root / "textures/34.png"
    original = path.read_bytes()
    path.write_bytes(original[:33] + png_chunk(b"IDAT", zlib.compress(pixels)) + png_chunk(b"IEND", b""))
    change(bundle_root, lambda m: m["textures"]["34"].update(sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with pytest.raises(InvalidAnimationBundle, match="34"):
        load_bundle(bundle_root)


def test_rejects_png_encoding_it_cannot_validate(bundle_root):
    path = bundle_root / "textures/34.png"
    original = path.read_bytes()
    header = struct.pack(">IIBBBBB", 128, 128, 16, 6, 0, 0, 0)
    path.write_bytes(original[:8] + png_chunk(b"IHDR", header) + original[33:])
    change(bundle_root, lambda m: m["textures"]["34"].update(sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with pytest.raises(InvalidAnimationBundle, match="34"):
        load_bundle(bundle_root)
