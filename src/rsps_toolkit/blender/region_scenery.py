"""The scenery of a region: one Blender object for each model that a level 0 placement shows.

Placements whose models, recolours and retextures are the same share one mesh, and their objects hold the scale, the
turn and the position (ADR 0022). A placement that the client bends to uneven ground, or whose transform Blender cannot
hold, gets a mesh of its own with the vertices already moved, and its object holds only the position (ADR 0023). The
meshes are made with `model_to_object`, so they keep the look of model import and have no baked loc light.

A wall of type 2 and a wall decoration of type 8 show two models. Each model is one object, and the second is named with
` part 2`. The names of the objects and meshes are the owner's choice of 2026-11-14 (issue 49, Decisions). Two
placements of one loc on one tile get the same name, and Blender adds `.001` to the second, which the owner chose in the
same comment.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

import bpy

from ..formats.loc_definition import LocDefinition
from ..formats.model import Model
from ..formats.region_contour import own_vertices
from ..formats.region_placement import PlacedLoc, PlacedPart
from .mesh import model_to_object

type MeshKey = tuple[tuple[int, ...], tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]
"""The models of a part, and the recolours and retextures of the loc that shows them."""


@dataclass(frozen=True)
class SceneryCounts:
    placements: int
    """The level 0 placements of the landscape."""
    objects: int
    """The objects made. A placement with two models makes two."""
    shared_meshes: int
    """The meshes that the objects of placements without an own mesh share."""
    own_meshes: int
    """The meshes of one object each, for placements bent to uneven ground or with a transform that Blender cannot hold."""
    shown_nothing: int
    """The placements that show no model: their impostor is -1, or their loc has no model for their type."""

    @property
    def placements_made(self) -> int:
        """The placements that made at least one object."""
        return self.placements - self.shown_nothing


def mesh_key(part: PlacedPart, shown: LocDefinition) -> MeshKey:
    return part.model.model_ids, shown.recolours, shown.retextures


def scenery_objects(
    collection: bpy.types.Collection,
    placed: Sequence[PlacedLoc],
    locs: Mapping[int, LocDefinition],
    models: Mapping[MeshKey, Model],
    images: Mapping[int, bpy.types.Image],
    height: Callable[[int, int], int],
    brightness: float,
) -> SceneryCounts:
    """Link one new object to `collection` for each part of each placement in `placed`, in that order.

    `placed` is what `region_placement.place_scenery` gives. `locs` holds the loc definitions by id. `models` holds the
    model of each `mesh_key`, with its cache models joined and the loc's recolours and retextures applied. `images`
    holds the decoded image of each texture that the models use. `height` is the height of a tile corner, as
    `place_scenery` takes it. `brightness` is the Brightness preference that the face colours are shown at.
    """
    shared: dict[MeshKey, bpy.types.Mesh] = {}
    objects = own = nothing = 0
    for placed_loc in placed:
        placement, shown_id = placed_loc.placement, placed_loc.shown_id
        if shown_id is None or not placed_loc.parts:
            nothing += 1
            continue
        shown = locs[shown_id]
        for index, part in enumerate(placed_loc.parts):
            key = mesh_key(part, shown)
            model = models[key]
            name = f"Loc {placement.loc} at {placement.x}_{placement.y}" + (" part 2" if index else "")
            vertices = own_vertices(placement, part, locs, model.vertices, height)
            if vertices is None:
                if key not in shared:
                    shared[key] = _mesh(model, _shared_name(shown_id, shown, part), images, brightness)
                obj = bpy.data.objects.new(name, shared[key])
                # `own_vertices` gives None only for a part whose transform Blender can hold, and such a part always
                # has a rotation and a scale (`PlacedPart.own_mesh`).
                assert part.rotation is not None and part.scale is not None
                obj.rotation_euler = (0.0, 0.0, part.rotation)
                obj.scale = part.scale
            else:
                obj = bpy.data.objects.new(name, _mesh(_moved(model, vertices, part), name, images, brightness))
                own += 1
            obj.location = part.location
            collection.objects.link(obj)
            objects += 1
    return SceneryCounts(len(placed), objects, len(shared), own, nothing)


def _moved(model: Model, vertices: Sequence[tuple[float, float, float]], part: PlacedPart) -> Model:
    """The model with the own vertices of a part, which are in Blender axes, back in game axes and rounded to whole game
    units, so that what model import stores matches the mesh. Only the turn of a type 11 object gives vertices that are
    not whole units. The owner chose the rounding on 2026-11-14 (issue 49, Decisions).

    A mirrored part also gets the first and last corner of each face swapped, as `ModelData.method2633` (lines 1380 to
    1390) does, because the own vertices hold the mirror already."""
    faces = [(c, b, a) for a, b, c in model.faces] if part.model.mirrored else model.faces
    return replace(model, vertices=[(round(x), round(-z), round(y)) for x, y, z in vertices], faces=faces)


def _shared_name(shown_id: int, shown: LocDefinition, part: PlacedPart) -> str:
    models = "+".join(str(model_id) for model_id in part.model.model_ids)
    recoloured = " recoloured" if shown.recolours or shown.retextures else ""
    return f"Loc {shown_id} model {models}{recoloured}"


def _mesh(model: Model, name: str, images: Mapping[int, bpy.types.Image], brightness: float) -> bpy.types.Mesh:
    """A new mesh of the model, made as model import makes it, with the textures from `images`."""
    obj = model_to_object(model, name, images.get, brightness)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bpy.data.objects.remove(obj)
    mesh.name = name
    return mesh
