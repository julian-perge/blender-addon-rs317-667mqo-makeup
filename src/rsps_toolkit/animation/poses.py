"""Legacy assembly and integer transforms from the pinned revision-1 client."""

from bisect import bisect_right
from collections.abc import Sequence as Collection
from dataclasses import dataclass
from fractions import Fraction
from math import cos, sin

from ..formats import Model, decode
from ..formats.model import Face, Vertex
from .bundle import AnimationBundle, Frame, FrameMap, PartRecipe, Sequence, TextureMotion


@dataclass(frozen=True)
class CompiledPart:
    key: str
    models: tuple[Model, ...]
    model_vertex_indices: tuple[tuple[int, ...], ...]
    model_rest_vertices: tuple[tuple[Vertex, ...], ...]
    vertices: tuple[Vertex, ...]
    faces: tuple[Face, ...]
    texture_triangles: tuple[Face, ...]
    vertex_skins: tuple[int, ...] | None
    face_skins: tuple[int, ...] | None
    face_alphas: tuple[int, ...]
    assembled_indices: tuple[int, ...]


@dataclass(frozen=True)
class AnimationAsset:
    bundle: AnimationBundle
    recipe_id: str
    sequence_id: int | None
    parts: tuple[CompiledPart, ...]
    vertices: tuple[Vertex, ...]
    vertex_skins: tuple[int, ...]
    face_alphas: tuple[int, ...]
    face_skins: tuple[int, ...] | None
    sequence: Sequence | None
    pose_starts_ns: tuple[int, ...]
    duration_ns: int | None


@dataclass(frozen=True)
class PartPose:
    key: str
    vertices: tuple[Vertex, ...]
    face_alphas: tuple[int, ...]


@dataclass(frozen=True)
class Pose:
    parts: tuple[PartPose, ...]


@dataclass(frozen=True)
class _Merged:
    vertices: tuple[Vertex, ...]
    faces: tuple[Face, ...]
    texture_triangles: tuple[Face, ...]
    vertex_skins: tuple[int, ...]
    face_skins: tuple[int, ...] | None
    face_alphas: tuple[int, ...]
    vertex_maps: tuple[tuple[int, ...], ...]


def _merge(parts: Collection[Model | CompiledPart]) -> _Merged:
    vertices: list[Vertex] = []
    skins: list[int] = []
    faces: list[Face] = []
    triangles: list[Face] = []
    index_of: dict[Vertex, int] = {}
    for part in parts:

        def vertex(index: int) -> int:
            position = part.vertices[index]
            if position not in index_of:
                index_of[position] = len(vertices)
                vertices.append(position)
                skins.append(0 if part.vertex_skins is None else part.vertex_skins[index])
            return index_of[position]

        # Class104_Sub18_Sub16_Sub5.java:453-464 visits face corners before texture corners; method907 keeps the first skin on exact coordinate reuse.
        faces.extend((vertex(a), vertex(b), vertex(c)) for a, b, c in part.faces)
        triangles.extend((vertex(a), vertex(b), vertex(c)) for a, b, c in part.texture_triangles)
    face_skins = None
    if any(part.face_skins is not None for part in parts):
        face_skins = tuple(
            label
            for part in parts
            for label in (part.face_skins if part.face_skins is not None else (0,) * len(part.faces))
        )
    return _Merged(
        tuple(vertices),
        tuple(faces),
        tuple(triangles),
        tuple(skins),
        face_skins,
        tuple(alpha for part in parts for alpha in part.face_alphas),
        tuple(tuple(index_of.get(position, -1) for position in part.vertices) for part in parts),
    )


def _int32(value: int) -> int:
    return ((value + 2**31) & 0xFFFFFFFF) - 2**31


def _div(value: int, divisor: int) -> int:
    return -(abs(value) // divisor) if value < 0 else value // divisor


def _part(
    bundle: AnimationBundle, recipe: PartRecipe, recolours: tuple[tuple[int, int], ...], recipe_id: str
) -> CompiledPart:
    models = tuple(decode(bundle.models[model_id].data) for model_id in recipe.model_ids)
    for model in models:
        for old, new in (*recipe.recolours, *recolours):
            model.face_colours = [new if colour == old else colour for colour in model.face_colours]
        for old, new in recipe.retextures:
            model.face_textures = [new if texture == old else texture for texture in model.face_textures]
        for texture_id in model.face_textures:
            if texture_id is not None and texture_id not in bundle.textures:
                raise ValueError(f"Recipe {recipe_id} part {recipe.key} references missing texture {texture_id}")
    if len(models) == 1:
        model = models[0]
        vertices = tuple(model.vertices)
        faces = tuple(model.faces)
        triangles = tuple(model.texture_triangles)
        skins = None if model.vertex_skins is None else tuple(model.vertex_skins)
        face_skins = None if model.face_skins is None else tuple(model.face_skins)
        alphas = tuple(model.face_alphas)
        maps = (tuple(range(len(vertices))),)
    else:
        merged = _merge(models)
        vertices, faces, triangles = merged.vertices, merged.faces, merged.texture_triangles
        skins, face_skins, alphas, maps = merged.vertex_skins, merged.face_skins, merged.face_alphas, merged.vertex_maps
    dx, dy, dz = recipe.offset
    vertices = tuple((_int32(x + dx), _int32(y + dy), _int32(z + dz)) for x, y, z in vertices)
    rest = tuple(
        tuple((_int32(x + dx), _int32(y + dy), _int32(z + dz)) for x, y, z in model.vertices) for model in models
    )
    return CompiledPart(recipe.key, models, maps, rest, vertices, faces, triangles, skins, face_skins, alphas, ())


def compile_asset(bundle: AnimationBundle, recipe_id: str, sequence_id: int | None) -> AnimationAsset:
    if recipe_id not in bundle.recipes:
        raise ValueError(f"Unknown recipe {recipe_id}")
    recipe = bundle.recipes[recipe_id]
    if sequence_id is not None and sequence_id not in recipe.sequence_ids:
        raise ValueError(f"Unselected sequence {sequence_id} is not selected by recipe {recipe_id}")
    sequence = None if sequence_id is None else bundle.sequences[sequence_id]
    parts = tuple(_part(bundle, part, recipe.recolours, recipe_id) for part in recipe.parts)
    assembled = _merge(parts)
    compiled = []
    for part, mapping in zip(parts, assembled.vertex_maps, strict=True):
        if sequence is not None and (
            any(index < 0 for index in mapping)
            or any(index < 0 for model_map in part.model_vertex_indices for index in model_map)
        ):
            raise ValueError(f"Unsupported unreferenced vertex correspondence in part {part.key}")
        compiled.append(
            CompiledPart(
                part.key,
                part.models,
                part.model_vertex_indices,
                part.model_rest_vertices,
                part.vertices,
                part.faces,
                part.texture_triangles,
                part.vertex_skins,
                part.face_skins,
                part.face_alphas,
                mapping,
            )
        )
    starts = []
    elapsed = 0
    if sequence is not None:
        for duration in sequence.durations:
            starts.append(elapsed)
            elapsed += duration * sequence.tick_ns
    return AnimationAsset(
        bundle,
        recipe_id,
        sequence_id,
        tuple(compiled),
        assembled.vertices,
        assembled.vertex_skins,
        assembled.face_alphas,
        assembled.face_skins,
        sequence,
        tuple(starts),
        elapsed if sequence is not None else None,
    )


# Class104_Sub18_Sub17_Sub4.java:2413-2414 uses this decimal angle step, so replacing it with pi/1024 can change truncated entries.
_SINE = tuple(int(65536.0 * sin(i * 0.0030679615)) for i in range(2048))
_COSINE = tuple(int(65536.0 * cos(i * 0.0030679615)) for i in range(2048))


def _groups(labels: tuple[int, ...] | None) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    if labels is not None:
        for index, label in enumerate(labels):
            result.setdefault(label, []).append(index)
    return result


def evaluate_frame(
    vertices: tuple[Vertex, ...],
    vertex_skins: tuple[int, ...],
    alphas: tuple[int, ...],
    face_skins: tuple[int, ...] | None,
    frame: Frame,
    frame_map: FrameMap,
) -> tuple[tuple[Vertex, ...], tuple[int, ...]]:
    points = list(vertices)
    result_alphas = list(alphas)
    vertex_groups = _groups(vertex_skins)
    face_groups = _groups(face_skins)
    pivot = (0, 0, 0)
    for index, dx, dy, dz in zip(frame.indices, frame.x, frame.y, frame.z, strict=True):
        kind = frame_map.types[index]
        labels = frame_map.labels[index]
        affected = [i for label in labels for i in vertex_groups.get(label, ())]
        if kind == 0:
            if affected:
                pivot = tuple(
                    _int32(_div(_int32(sum(points[i][axis] for i in affected)), len(affected)) + delta)
                    for axis, delta in enumerate((dx, dy, dz))
                )
            else:
                pivot = (dx, dy, dz)
        elif kind == 1:
            for i in affected:
                x, y, z = points[i]
                points[i] = (_int32(x + dx), _int32(y + dy), _int32(z + dz))
        elif kind in (2, 3):
            px, py, pz = pivot
            for i in affected:
                x, y, z = points[i]
                x, y, z = _int32(x - px), _int32(y - py), _int32(z - pz)
                if kind == 2:
                    rx, ry, rz = (dx & 255) * 8, (dy & 255) * 8, (dz & 255) * 8
                    if rz:
                        s, c = _SINE[rz], _COSINE[rz]
                        x, y = _int32(y * s + x * c) >> 16, _int32(y * c - x * s) >> 16
                    if rx:
                        s, c = _SINE[rx], _COSINE[rx]
                        y, z = _int32(y * c - z * s) >> 16, _int32(y * s + z * c) >> 16
                    if ry:
                        s, c = _SINE[ry], _COSINE[ry]
                        x, z = _int32(z * s + x * c) >> 16, _int32(z * c - x * s) >> 16
                else:
                    x, y, z = _div(_int32(x * dx), 128), _div(_int32(y * dy), 128), _div(_int32(z * dz), 128)
                points[i] = (_int32(x + px), _int32(y + py), _int32(z + pz))
        elif kind == 5:
            for label in labels:
                for i in face_groups.get(label, ()):
                    result_alphas[i] = min(255, max(0, _int32(result_alphas[i] + _int32(dx * 8))))
        else:
            raise ValueError(f"Unsupported transform type {kind}")
    return tuple(points), tuple(result_alphas)


def _time(elapsed_ns: int) -> None:
    if type(elapsed_ns) is not int or elapsed_ns < 0:
        raise ValueError("Elapsed game time must be a nonnegative integer number of nanoseconds")


def sample_pose(asset: AnimationAsset, elapsed_ns: int) -> Pose:
    _time(elapsed_ns)
    if asset.sequence is None:
        return Pose(tuple(PartPose(part.key, part.vertices, part.face_alphas) for part in asset.parts))
    if asset.duration_ns is None or elapsed_ns >= asset.duration_ns:
        raise ValueError("Elapsed time is outside this clip's period")
    pose_index = bisect_right(asset.pose_starts_ns, elapsed_ns) - 1
    frame = asset.bundle.frames[asset.sequence.frame_ids[pose_index]]
    vertices, alphas = evaluate_frame(
        asset.vertices,
        asset.vertex_skins,
        asset.face_alphas,
        asset.face_skins,
        frame,
        asset.bundle.frame_maps[frame.map_id],
    )
    parts = []
    face = 0
    for part in asset.parts:
        count = len(part.faces)
        parts.append(
            PartPose(part.key, tuple(vertices[i] for i in part.assembled_indices), alphas[face : face + count])
        )
        face += count
    return Pose(tuple(parts))


def texture_offset(motion: TextureMotion, elapsed_ns: int) -> tuple[Fraction, Fraction]:
    _time(elapsed_ns)
    if motion.direction not in (0, 1, 2, 3, 4):
        raise ValueError(f"Unsupported texture direction {motion.direction}")
    step = (elapsed_ns // motion.tick_ns) * motion.speed
    size = motion.sampling_size
    if motion.direction in (1, 3):
        return Fraction(0), Fraction((step if motion.direction == 1 else -step) % size, size)
    if motion.direction in (2, 4):
        return Fraction((-step if motion.direction == 2 else step) % size, size), Fraction(0)
    return Fraction(0), Fraction(0)
