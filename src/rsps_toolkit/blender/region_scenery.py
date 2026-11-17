"""The scenery of a region: one Blender object for each model that a level 0 placement shows.

Placements share one mesh when every input of the loc light is the same: the models, the recolours, the retextures,
the rotation, the mirror, the scale, the diagonal turn, the ambient, the contrast and `nonFlatShading` (ADR 0027). The
mesh stays in model axes, and the objects hold the scale, the turn and the position (ADR 0022). A placement that the
client bends to uneven ground, or whose transform Blender cannot hold, gets a mesh of its own with the vertices already
moved, and its object holds only the position (ADR 0023).

The meshes are made with `model_to_object`, so they keep the materials of model import. Each mesh also has the loc light
of its placement (`region_loc_light.loc_light`) in the corner colour attribute `rs_lit`, which the materials do not draw
yet (issue 130).

A wall of type 2 and a wall decoration of type 8 show two models. Each model is one object, and the second is named with
` part 2`. The names of the objects and meshes are the owner's choice of 2026-11-14 (issue 49, Decisions). Two
placements of one loc on one tile get the same name, and Blender adds `.001` to the second, which the owner chose in the
same comment.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

import bpy

from ..formats.colour import face_colour_to_rgb
from ..formats.lighting import Shading
from ..formats.loc_definition import LocDefinition
from ..formats.model import Model
from ..formats.region_contour import own_vertices
from ..formats.region_loc_light import loc_light, refuse_undrawn_decoration
from ..formats.region_placement import PlacedLoc, PlacedPart
from .appearance_preview import LIT_ATTRIBUTE
from .face_materials import srgb_to_linear
from .mesh import MaterialKey, model_to_object

type ModelKey = tuple[tuple[int, ...], tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]
"""The models of a part, and the recolours and retextures of the loc that shows them."""

type MeshKey = tuple[ModelKey, int, bool, bool, tuple[int, int, int], int, int, bool]
"""The model key, and every other input of the loc light (ADR 0027): the quarter turns, the mirror, the diagonal turn,
the scale, the ambient, the contrast and `nonFlatShading`."""


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


def model_key(part: PlacedPart, shown: LocDefinition) -> ModelKey:
    return part.model.model_ids, shown.recolours, shown.retextures


def mesh_key(part: PlacedPart, shown: LocDefinition) -> MeshKey:
    """The inputs of the loc light of a part with a shared mesh. The offset only moves the model, so it is not one of
    them. The contour is not either, because a part that the client bends gets its own mesh (`own_vertices`)."""
    diagonal = part.model_type == 4 and part.model_rotation > 3
    return (
        model_key(part, shown),
        part.model_rotation & 3,
        part.model.mirrored,
        diagonal,
        shown.scale,
        shown.ambient,
        shown.contrast,
        shown.non_flat_shading,
    )


def scenery_objects(
    collection: bpy.types.Collection,
    placed: Sequence[PlacedLoc],
    locs: Mapping[int, LocDefinition],
    models: Mapping[ModelKey, Model],
    render_types: Mapping[tuple[int, ...], Sequence[int]],
    images: Mapping[int, bpy.types.Image],
    height: Callable[[int, int], int],
    brightness: float,
) -> SceneryCounts:
    """Link one new object to `collection` for each part of each placement in `placed`, in that order.

    `placed` is what `region_placement.place_scenery` gives. `locs` holds the loc definitions by id. `models` holds the
    model of each `model_key`, with its cache models joined and the loc's recolours and retextures applied.
    `render_types` holds the stored render type of each face of the joined models of each part, by its model ids
    (`lighting.joined_render_types`). `images` holds the decoded image of each texture that the models use. `height`
    is the height of a tile corner, as `place_scenery` takes it. `brightness` is the Brightness preference that the
    face colours and the `rs_lit` colours are shown at.

    The meshes of one call share one new material for each material key (issue 67). `import_region` calls this once
    for each import, so no material comes from an earlier import, and its cleanup still removes every material made.
    """
    shared: dict[MeshKey, bpy.types.Mesh] = {}
    materials: dict[MaterialKey, bpy.types.Material] = {}
    objects = own = nothing = 0
    for placed_loc in placed:
        placement, shown_id = placed_loc.placement, placed_loc.shown_id
        if shown_id is None or not placed_loc.parts:
            nothing += 1
            continue
        shown = locs[shown_id]
        # A placement that reuses a shared mesh is not lit again, so `loc_light` cannot refuse it. The refusal runs here
        # for every placement instead.
        refuse_undrawn_decoration(placement, locs[placement.loc], shown)
        for index, part in enumerate(placed_loc.parts):
            key = mesh_key(part, shown)
            model = models[model_key(part, shown)]
            name = f"Loc {placement.loc} at {placement.x}_{placement.y}" + (" part 2" if index else "")
            vertices = own_vertices(placement, part, locs, model.vertices, height)
            types = render_types[part.model.model_ids]
            if vertices is None:
                if key not in shared:
                    mesh = _mesh(model, _shared_name(shown_id, shown, part), images, brightness, materials)
                    # A shared mesh keeps the model's corner order, which is the reverse of the light's order for a
                    # mirrored part (`loc_light`).
                    shading = loc_light(placement, part, locs, model, height, types)
                    _write_lit(mesh, model, shading, part.model.mirrored, brightness)
                    shared[key] = mesh
                obj = bpy.data.objects.new(name, shared[key])
                # `own_vertices` gives None only for a part whose transform Blender can hold, and such a part always
                # has a rotation and a scale (`PlacedPart.own_mesh`).
                assert part.rotation is not None and part.scale is not None
                obj.rotation_euler = (0.0, 0.0, part.rotation)
                obj.scale = part.scale
            else:
                mesh = _mesh(_moved(model, vertices, part), name, images, brightness, materials)
                # `_moved` gives an own mesh the light's corner order already.
                _write_lit(mesh, model, loc_light(placement, part, locs, model, height, types), False, brightness)
                obj = bpy.data.objects.new(name, mesh)
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


def _mesh(
    model: Model,
    name: str,
    images: Mapping[int, bpy.types.Image],
    brightness: float,
    materials: dict[MaterialKey, bpy.types.Material],
) -> bpy.types.Mesh:
    """A new mesh of the model, made as model import makes it, with the textures from `images`. For each material key
    of the model that is already in `materials` it uses that material, and it puts each new material in `materials`."""
    obj = model_to_object(model, name, images.get, brightness, materials=materials)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bpy.data.objects.remove(obj)
    mesh.name = name
    return mesh


def _write_lit(mesh: bpy.types.Mesh, model: Model, shading: Shading, reverse: bool, brightness: float) -> None:
    """Write the loc light of `model` to the corner colour attribute `rs_lit` of its mesh, as the player's `rs_lit` is
    written (`appearance_preview`), with `reverse` when the corners of each polygon are in the reverse of the shading's
    order. The mesh has one polygon for each face of the model that does not repeat a vertex (`model_to_object`).

    An untextured corner holds its lit colour at `brightness`. A textured corner holds its light value over 128 as a
    grey, because the client multiplies each texel by it (`Graphics3D.rasterTextureAffine` line 1489 and
    `rasterTextureAffineLine`) and the texture image already has the brightness. A face with the third value -1 shows
    its first value at every corner, and a face with -2, which the client does not draw, gets black with the alpha 0.
    The owner chose the grey and the alpha 0 on 2026-11-17 (issue 129).
    """
    values: list[float] = []
    for face, corners in enumerate(model.faces):
        if len(set(corners)) < 3:
            continue
        third = shading.corner_c[face]
        if third == -2:
            values += [0.0] * 12
            continue
        first = shading.corner_a[face]
        shades = (first,) * 3 if third == -1 else (first, shading.corner_b[face], third)
        if reverse:
            shades = shades[::-1]
        for shade in shades:
            if shading.light_values[face]:
                grey = srgb_to_linear(shade / 128)
                values += [grey, grey, grey, 1.0]
            else:
                red, green, blue = face_colour_to_rgb(shade, brightness)
                values += [srgb_to_linear(red / 255), srgb_to_linear(green / 255), srgb_to_linear(blue / 255), 1.0]
    colours = mesh.color_attributes.new(LIT_ATTRIBUTE, "FLOAT_COLOR", "CORNER")
    colours.data.foreach_set("color", values)
    mesh.color_attributes.active_color = colours
    mesh.color_attributes.render_color_index = mesh.color_attributes.find(LIT_ATTRIBUTE)
