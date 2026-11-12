"""The model the client poses while a clip plays on a player, and the player's objects that show it.

A clip is posed on the worn model, read back from the player's worn mesh objects. An action sequence with held items
is posed on the held variant instead, assembled from the cache (`appearance_held`), which is what the client's `hu.l`
builds; `formats.appearance.held_equipment` cites it. Both bakes take their frames from here, so neither knows which
of the two models a clip uses.
"""

import functools
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import bpy

from ..animation.clip import ClipSource, PosedFrame, pose_vertices, read_sequence, source_of
from ..animation.frames import frame_schedule
from ..formats.appearance import held_equipment
from ..formats.appearance_preset import loads_preset
from ..formats.model import Vertex
from . import appearance_collection, appearance_fades, appearance_held, appearance_preview

# A clip record keeps the sequence's shield-hand and weapon-hand values under this key.
_HELD_RECORD = "held"


@dataclass(frozen=True)
class PosedPart:
    """One mesh object of the player, with the clip's frames and fades cut down to its own vertices and polygons."""

    obj: bpy.types.Object
    frames: tuple[PosedFrame, ...]
    fades: list[appearance_fades.FadeGroup]


@dataclass(frozen=True, eq=False)
class PosedPlayer:
    """A clip posed on a player (`pose_player`)."""

    # The bone bake fits the rig's bones to the posed model at rest, which these two are.
    vertices: tuple[Vertex, ...]
    labels: tuple[int, ...]
    frames: tuple[PosedFrame, ...]
    schedule: tuple[tuple[int, int], ...]
    # These are the twelve slots the client shows while the clip plays. None means the worn ones.
    equipment: tuple[int, ...] | None
    # A bake adds this to its clip record, so that `shown_equipment` gives the same slots for the record.
    record: dict[str, list[int]]
    _pieces: Callable[[], list[appearance_held.Piece]]

    def ensure_parts(
        self, earlier_of: Callable[[list[bpy.types.Object]], appearance_fades.EarlierFades] | None = None
    ) -> list[PosedPart]:
        """The player's objects that show the posed model, each with its own frames and fades.

        `earlier_of` gives what the clips already baked on the rig do to each label group of the given objects, the
        ones that show the clip (`fade_groups`).

        A held item the player has no object for gets one, bound to the rig, with the label bones only it carries.
        That changes the file, so a bake calls this after its own refusals.
        """
        cut = [(piece, piece.frames(self.frames)) for piece in self._pieces()]
        earlier = None if earlier_of is None else earlier_of([piece.obj for piece, _ in cut])
        grouped = iter(
            appearance_fades.fade_groups([(*piece.faces, frames) for piece, frames in cut if piece.faces], earlier)
        )
        return [PosedPart(piece.obj, frames, next(grouped) if piece.faces else []) for piece, frames in cut]


def pose_player(
    collection: bpy.types.Collection, clip: ClipSource | Path, *, action: bool = False, cache_folder: str = ""
) -> PosedPlayer:
    """Pose the model the client shows while the clip plays on the player, changing nothing in the file.

    `cache_folder` overrides the add-on preference for the cache a held variant is assembled from. Raises ValueError
    for a player whose meshes no longer hold the model as built.
    """
    source = source_of(clip)
    sequence = read_sequence(source)
    held = appearance_held.held_items(sequence, action)
    variant = None if held is None else appearance_held.variant(collection, held, cache_folder)
    if held is None or variant is None:
        vertices, labels, faces, worn = _worn_inputs(appearance_collection.worn_parts(collection))
        frames = pose_vertices(vertices, labels, source, *(faces or ()))
        return PosedPlayer(vertices, labels, frames, frame_schedule(sequence, action=action), None, {}, lambda: worn)
    vertices, labels, faces = appearance_held.variant_inputs(variant)
    frames = pose_vertices(vertices, labels, source, *(faces or ()))
    return PosedPlayer(
        vertices,
        labels,
        frames,
        frame_schedule(sequence, action=action),
        variant.equipment,
        {_HELD_RECORD: list(held)},
        functools.partial(appearance_held.ensure_pieces, collection, variant),
    )


def shown_equipment(collection: bpy.types.Collection, record: dict) -> tuple[int, ...] | None:
    """The slots the client shows while a recorded clip plays on the player, or None when they are the worn ones."""
    held = record.get(_HELD_RECORD)
    if held is None:
        return None
    return tuple(held_equipment(loads_preset(collection[appearance_preview.PRESET_KEY]).equipment, *held))


def _worn_inputs(objects: list[bpy.types.Object]):
    """The merged model's vertices and labels, read back from the player's worn mesh objects, every polygon's label
    and rest alpha in object order (None when a mesh lacks them), and each object as a Piece.

    The client poses the merged model as one, and a pivot is the centre of every vertex with its labels, so the
    parts are posed together. A vertex two parts share is the same merged vertex in both.
    """
    positions: dict[int, Vertex] = {}
    labels: dict[int, int] = {}
    pieces = []
    faces: tuple[list[int], list[int]] | None = ([], [])
    for obj in objects:
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        indices = tuple(appearance_preview.vertex_indices(mesh))
        for vertex, index, label in zip(mesh.vertices, indices, _labels(obj), strict=True):
            positions[index] = (round(vertex.co.x), round(-vertex.co.z), round(vertex.co.y))
            labels[index] = label
        part_faces = appearance_fades.face_inputs(mesh)
        start = 0 if faces is None else len(faces[0])
        pieces.append(appearance_held.Piece(obj, indices, tuple(range(start, start + len(mesh.polygons))), part_faces))
        if faces is not None and part_faces is not None:
            faces[0].extend(part_faces[0])
            faces[1].extend(part_faces[1])
        else:
            faces = None
    if sorted(positions) != list(range(len(positions))):
        raise ValueError("The player's meshes do not hold every vertex of the model they were built from")
    order = range(len(positions))
    merged_faces = None if faces is None else (tuple(faces[0]), tuple(faces[1]))
    return tuple(positions[i] for i in order), tuple(labels[i] for i in order), merged_faces, pieces


def _labels(obj: bpy.types.Object) -> tuple[int, ...]:
    names = {group.index: group.name for group in obj.vertex_groups}
    labels = []
    for vertex in obj.data.vertices:  # pyrefly: ignore[missing-attribute]
        if len(vertex.groups) != 1:
            raise ValueError(f"Vertex {vertex.index} is in {len(vertex.groups)} vertex groups, a player vertex has one")
        name = names[vertex.groups[0].group]
        if not name.startswith(appearance_collection.BONE_PREFIX):
            raise ValueError(f"Vertex group {name!r} is not a label_<n> group")
        labels.append(int(name.removeprefix(appearance_collection.BONE_PREFIX)))
    return tuple(labels)
