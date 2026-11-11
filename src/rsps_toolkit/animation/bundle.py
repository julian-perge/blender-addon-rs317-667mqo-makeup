"""Load the version-1 animation bundle without importing Blender."""

import hashlib
import json
import re
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from ..formats import decode
from ..formats.model import Vertex


class InvalidAnimationBundle(ValueError):  # noqa: N818 - The approved plan fixes this public exception name.
    """The bundle cannot produce a complete supported animation asset."""


@dataclass(frozen=True)
class Source:
    cache_revision: int
    openrs2_archive_id: int
    cache_hashes: Mapping[str, str]


@dataclass(frozen=True)
class ModelResource:
    path: Path
    sha256: str
    data: bytes


@dataclass(frozen=True)
class TextureMotion:
    path: Path
    sha256: str
    width: int
    height: int
    sampling_size: int
    direction: int
    speed: int
    sprite_ids: tuple[int, ...]
    tick_ns: int


@dataclass(frozen=True)
class Sequence:
    frame_ids: tuple[int, ...]
    durations: tuple[int, ...]
    tick_ns: int
    clock: str
    shield_override: int
    weapon_override: int
    client_fields: Mapping[str, int | bool | tuple[int, ...] | None]


@dataclass(frozen=True)
class Frame:
    map_id: int
    indices: tuple[int, ...]
    x: tuple[int, ...]
    y: tuple[int, ...]
    z: tuple[int, ...]


@dataclass(frozen=True)
class FrameMap:
    types: tuple[int, ...]
    labels: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class PartRecipe:
    key: str
    model_ids: tuple[int, ...]
    offset: Vertex
    recolours: tuple[tuple[int, int], ...]
    retextures: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Recipe:
    parts: tuple[PartRecipe, ...]
    recolours: tuple[tuple[int, int], ...]
    sequence_ids: tuple[int, ...]


@dataclass(frozen=True)
class AnimationBundle:
    root: Path
    source: Source
    models: Mapping[int, ModelResource]
    textures: Mapping[int, TextureMotion]
    sequences: Mapping[int, Sequence]
    frames: Mapping[int, Frame]
    frame_maps: Mapping[int, FrameMap]
    recipes: Mapping[str, Recipe]


def _require(condition: bool, field: str) -> None:
    if not condition:
        raise InvalidAnimationBundle(field)


def _object(value: object, field: str) -> dict[str, object]:
    _require(isinstance(value, dict), f"{field} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, field: str) -> list[object]:
    _require(isinstance(value, list), f"{field} must be an array")
    return cast(list[object], value)


def _integer(value: object, field: str, low: int = -(2**31), high: int = 2**31 - 1) -> int:
    _require(type(value) is int and low <= value <= high, f"Invalid integer in {field}")
    return cast(int, value)


def _integers(value: object, field: str, low: int = -(2**31), high: int = 2**31 - 1) -> tuple[int, ...]:
    return tuple(_integer(item, field, low, high) for item in _array(value, field))


def _ids(value: object, field: str) -> tuple[int, ...]:
    result = _integers(value, field, 0)
    _require(len(set(result)) == len(result), f"Duplicate IDs in {field}")
    return result


def _string(value: object, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"Invalid string in {field}")
    return cast(str, value)


def _hash(value: object, field: str) -> str:
    result = _string(value, field)
    _require(re.fullmatch(r"[0-9a-f]{64}", result) is not None, f"Invalid SHA-256 in {field}")
    return result


def _pairs(value: object, field: str) -> tuple[tuple[int, int], ...]:
    result = []
    for item in _array(value, field):
        pair = _integers(item, field, 0, 65535)
        _require(len(pair) == 2, f"{field} needs ordered pairs")
        result.append((pair[0], pair[1]))
    return tuple(result)


def _records(manifest: dict[str, object], field: str) -> dict[int, dict[str, object]]:
    records = _object(manifest.get(field), field)
    result = {}
    for key, value in records.items():
        _require(re.fullmatch(r"0|[1-9][0-9]*", key) is not None, f"Invalid ID {key} in {field}")
        key_id = _integer(int(key), field, 0)
        result[key_id] = _object(value, f"{field} {key}")
    return result


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> object:
    raise InvalidAnimationBundle(f"Non-finite JSON number {value}")


def _resource(root: Path, record: dict[str, object], label: str) -> tuple[Path, str, bytes]:
    relative = Path(_string(record.get("path"), f"{label} path"))
    path = (root / relative).resolve()
    _require(not relative.is_absolute() and path.is_relative_to(root), f"{label} path escapes bundle root")
    expected = _hash(record.get("sha256"), f"{label} sha256")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise InvalidAnimationBundle(f"Missing {label} resource: {error}") from error
    _require(hashlib.sha256(data).hexdigest() == expected, f"Hash mismatch for {label}")
    return path, expected, data


def _png_dimensions(data: bytes, label: str) -> tuple[int, int]:
    _require(data[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG {label}")
    position = 8
    dimensions = None
    compressed = bytearray()
    ended = False
    idat_closed = False
    while position < len(data):
        _require(position + 12 <= len(data), f"Truncated PNG {label}")
        size = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4 : position + 8]
        end = position + 8 + size
        _require(end + 4 <= len(data), f"Truncated PNG {label}")
        payload = data[position + 8 : end]
        expected = struct.unpack_from(">I", data, end)[0]
        _require(zlib.crc32(kind + payload) == expected, f"PNG checksum mismatch for {label}")
        if position == 8:
            _require(kind == b"IHDR" and size == 13, f"Missing PNG IHDR for {label}")
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            dimensions = (width, height)
            _require(width > 0 and height > 0, f"Invalid PNG dimensions for {label}")
            _require(
                (depth, colour, compression, filtering, interlace) == (8, 6, 0, 0, 0),
                f"Unsupported PNG encoding for {label}; expected non-interlaced 8-bit RGBA",
            )
        elif kind == b"IHDR" or (not kind[0] & 32 and kind not in (b"IDAT", b"IEND")):
            raise InvalidAnimationBundle(f"Unsupported PNG chunk {kind!r} for {label}")
        if kind == b"IDAT":
            _require(not idat_closed, f"Nonconsecutive PNG IDAT chunks for {label}")
            compressed.extend(payload)
        elif compressed:
            idat_closed = True
        position = end + 4
        if kind == b"IEND":
            _require(size == 0 and position == len(data), f"Invalid PNG ending for {label}")
            ended = True
            break
    _require(ended and dimensions is not None and bool(compressed), f"Incomplete PNG {label}")
    width, height = cast(tuple[int, int], dimensions)
    row_size = 1 + width * 4
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(compressed, height * row_size + 1)
    except zlib.error as error:
        raise InvalidAnimationBundle(f"Invalid PNG data for {label}") from error
    _require(
        decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
        f"Incomplete or trailing PNG pixel stream for {label}",
    )
    _require(len(pixels) == height * row_size, f"Incomplete PNG scanlines for {label}")
    _require(all(value <= 4 for value in pixels[::row_size]), f"Invalid PNG row filter for {label}")
    return width, height


def _source(record: dict[str, object]) -> Source:
    revision = _integer(record.get("cache_revision"), "source.cache_revision", 0)
    _require(revision == 1, "Unsupported source.cache_revision")
    archive_id = _integer(record.get("openrs2_archive_id"), "source.openrs2_archive_id", 0)
    raw_hashes = _object(record.get("cache_hashes"), "source.cache_hashes")
    required = {"main_file_cache.dat2", *(f"main_file_cache.idx{i}" for i in (0, 1, 2, 7, 8, 9))}
    _require(required <= raw_hashes.keys(), "Missing source.cache_hashes")
    hashes = {}
    for name, value in raw_hashes.items():
        _require(
            re.fullmatch(r"main_file_cache\.(dat2|idx[0-9]+)", name) is not None, "Invalid source.cache_hashes path"
        )
        hashes[name] = _hash(value, f"source.cache_hashes {name}")
    return Source(revision, archive_id, MappingProxyType(hashes))


def _sequence(record: dict[str, object], sequence_id: int) -> Sequence:
    label = f"sequence {sequence_id}"
    frames = _integers(record.get("frame_ids"), f"{label} frame_ids", 0)
    durations = _integers(record.get("durations"), f"{label} durations", 1)
    _require(bool(frames) and len(frames) == len(durations), f"Invalid {label} frame/duration lengths")
    tick_ns = _integer(record.get("tick_ns"), f"{label} tick_ns", 0)
    clock = _string(record.get("clock"), f"{label} clock")
    _require(tick_ns == 20_000_000 and clock == "actor-render-v1", f"Unsupported {label} clock")
    shield = _integer(record.get("shield_override"), f"{label} shield_override")
    weapon = _integer(record.get("weapon_override"), f"{label} weapon_override")
    _require(shield == -1 and weapon == -1, f"Unsupported equipment override in {label}")
    raw_fields = _object(record.get("client_fields"), f"{label} client_fields")
    fields: dict[str, int | bool | tuple[int, ...] | None] = {}
    for name in ("anInt1261", "anInt1266", "anInt1269", "anInt1273", "anInt1274", "anInt1275"):
        fields[name] = _integer(raw_fields.get(name), f"{label} {name}")
    _require(type(raw_fields.get("aBool1272")) is bool, f"{label} aBool1272 must be boolean")
    fields["aBool1272"] = cast(bool, raw_fields["aBool1272"])
    for name in ("anIntArray1263", "anIntArray1265", "anIntArray1267"):
        _require(name in raw_fields, f"Missing {label} {name}")
        value = raw_fields[name]
        fields[name] = None if value is None else _integers(value, f"{label} {name}")
    return Sequence(frames, durations, tick_ns, clock, shield, weapon, MappingProxyType(fields))


def _recipe(record: dict[str, object], recipe_id: str) -> Recipe:
    label = f"recipe {recipe_id}"
    parts = []
    keys = set()
    for value in _array(record.get("parts"), f"{label} parts"):
        part = _object(value, f"{label} part")
        key = _string(part.get("key"), f"{label} part key")
        _require(key not in keys, f"Duplicate part key {key} in {label}")
        keys.add(key)
        offset = _integers(part.get("offset"), f"{label} {key} offset")
        _require(len(offset) == 3, f"{label} {key} offset needs three coordinates")
        parts.append(
            PartRecipe(
                key,
                _ids(part.get("model_ids"), f"{label} {key} model_ids"),
                cast(Vertex, offset),
                _pairs(part.get("recolours"), f"{label} recolours"),
                _pairs(part.get("retextures"), f"{label} retextures"),
            )
        )
    return Recipe(
        tuple(parts),
        _pairs(record.get("recolours"), f"{label} recolours"),
        _ids(record.get("sequence_ids"), f"{label} sequence_ids"),
    )


def load_bundle(root: Path) -> AnimationBundle:
    """Validate the whole declared bundle before returning immutable playback inputs."""
    try:
        return _load_bundle(root.resolve())
    except InvalidAnimationBundle:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error) as error:
        raise InvalidAnimationBundle(f"Invalid animation bundle: {error}") from error


def _load_bundle(root: Path) -> AnimationBundle:
    manifest_path = (root / "animations/manifest.json").resolve()
    _require(manifest_path.is_relative_to(root), "Manifest path escapes bundle root")
    manifest = _object(
        json.loads(manifest_path.read_text(), object_pairs_hook=_unique_object, parse_constant=_nonfinite), "manifest"
    )
    _require(manifest.get("format") == "rsps-animation", "Unsupported animation format")
    _require(_integer(manifest.get("version"), "version", 0) == 1, "Unsupported animation version")
    source = _source(_object(manifest.get("source"), "source"))
    models = {}
    for model_id, record in _records(manifest, "models").items():
        path, sha256, data = _resource(root, record, f"model {model_id}")
        models[model_id] = ModelResource(path, sha256, data)
    textures = {}
    for texture_id, record in _records(manifest, "textures").items():
        label = f"texture {texture_id}"
        path, sha256, data = _resource(root, record, label)
        width = _integer(record.get("width"), f"{label} width", 1)
        height = _integer(record.get("height"), f"{label} height", 1)
        _require(_png_dimensions(data, label) == (width, height), f"PNG dimensions mismatch for {label}")
        sampling = _integer(record.get("sampling_size"), f"{label} sampling_size", 0)
        tick_ns = _integer(record.get("tick_ns"), f"{label} tick_ns", 0)
        _require(sampling == 128 and tick_ns == 20_000_000, f"Unsupported {label} sampling clock")
        textures[texture_id] = TextureMotion(
            path,
            sha256,
            width,
            height,
            sampling,
            _integer(record.get("direction"), f"{label} direction", 0, 4),
            _integer(record.get("speed"), f"{label} speed", 0, 255),
            _integers(record.get("sprite_ids"), f"{label} sprite_ids", 0),
            tick_ns,
        )
    sequences = {key: _sequence(record, key) for key, record in _records(manifest, "sequences").items()}
    maps = {}
    for map_id, record in _records(manifest, "frame_maps").items():
        label = f"frame map {map_id}"
        types = _integers(record.get("types"), f"{label} types", 0, 255)
        labels = tuple(_integers(value, f"{label} labels", 0, 255) for value in _array(record.get("labels"), label))
        _require(len(types) == len(labels), f"Invalid {label} array lengths")
        maps[map_id] = FrameMap(types, labels)
    frames = {}
    for frame_id, record in _records(manifest, "frames").items():
        label = f"frame {frame_id}"
        map_id = _integer(record.get("map_id"), f"{label} map_id", 0)
        _require(map_id in maps, f"Missing frame map {map_id} for {label}")
        indices = _integers(record.get("indices"), f"{label} indices", 0)
        x, y, z = (_integers(record.get(axis), f"{label} {axis}") for axis in ("x", "y", "z"))
        _require(len(indices) == len(x) == len(y) == len(z), f"Invalid {label} array lengths")
        for index in indices:
            _require(index < len(maps[map_id].types), f"Invalid map index {index} for {label}")
            _require(
                maps[map_id].types[index] in (0, 1, 2, 3, 5), f"Unsupported transform type in {label} map {map_id}"
            )
        frames[frame_id] = Frame(map_id, indices, x, y, z)
    recipes = {
        key: _recipe(_object(value, f"recipe {key}"), key)
        for key, value in _object(manifest.get("recipes"), "recipes").items()
    }
    for sequence_id, sequence in sequences.items():
        for frame_id in sequence.frame_ids:
            _require(frame_id in frames, f"Missing frame {frame_id} for sequence {sequence_id}")
    for key, recipe in recipes.items():
        for sequence_id in recipe.sequence_ids:
            _require(sequence_id in sequences, f"Missing sequence {sequence_id} for recipe {key}")
        for part in recipe.parts:
            for model_id in part.model_ids:
                _require(model_id in models, f"Missing model {model_id} for recipe {key}")
    for model_id, resource in models.items():
        try:
            model = decode(resource.data)
        except (ValueError, IndexError, struct.error) as error:
            raise InvalidAnimationBundle(f"Invalid model {model_id}: {error}") from error
        for texture_id in model.face_textures:
            _require(texture_id is None or texture_id in textures, f"Missing texture {texture_id} for model {model_id}")
    return AnimationBundle(
        root,
        source,
        MappingProxyType(models),
        MappingProxyType(textures),
        MappingProxyType(sequences),
        MappingProxyType(frames),
        MappingProxyType(maps),
        MappingProxyType(recipes),
    )
