"""The loc shadows of the level 0 placements of a region, which `region_colours.corner_light` takes away from the terrain
light. Nothing here imports bpy.

The client writes a loc shadow at a tile corner into `class50.field449` while it adds the placements of a scene
(`PacketBuffer.addObject`, lines 160 to 503). Only walls of types 0, 1 and 3 and objects of types 10 and 11 write one,
and only when their loc has `casts_shadow`. Every rule follows the 2018 Old School client, as the spec of issue 35 lists
them. Revision 149 is not checked against it, and the rules have no second reader.

The corners are counted from the south-west corner of the region, as `Terrain.tile` counts them. A placement at the
east or north edge of the region writes at corner 64, and an object wider than one tile there writes past it, as the
client does. The client's two tests that can stop an object from being added (`Region.addEntityMarker`, lines 538 to
551) are left out: no footprint leaves the region's scene, and no tile of region 48_50 holds the 5 objects that the
second test needs. A region with a tile of 5 or more objects would get shadows that the client does not write.

Only the placements of the region itself write shadows, because the import does not read neighbour scenery (decision 1
of the spec of issue 35). The client also writes the shadows of the neighbour regions' locs, and `corner_light` reads
the shadows one corner west and south of a corner. So a corner at the region's edge is lighter than in the client where
a neighbour loc stands next to that edge.
"""

from collections.abc import Callable, Mapping, Sequence
from math import sqrt

from .loc_definition import LocDefinition
from .model import Vertex
from .region_contour import client_vertex
from .region_loc import LocModel
from .region_placement import PlacedLoc

WALL_SHADOW = 50
DEFAULT_OBJECT_SHADOW = 15
"""The shadow of an object that is not a `Model` (`PacketBuffer.java` line 479)."""
MAX_OBJECT_SHADOW = 30

_WALL_CORNERS = {
    # PacketBuffer.java lines 254 to 284: a wall of type 0 writes at the 2 corners of the tile side that it stands on.
    0: (((0, 0), (0, 1)), ((0, 1), (1, 1)), ((1, 0), (1, 1)), ((0, 0), (1, 0))),
    # Lines 307 to 316 and 370 to 379: a wall corner of type 1 or 3 writes at the one corner that it stands on.
    1: (((0, 1),), ((1, 1),), ((1, 0),), ((0, 0),)),
    3: (((0, 1),), ((1, 1),), ((1, 0),), ((0, 0),)),
}


def loc_shadows(
    placed: Sequence[PlacedLoc],
    locs: Mapping[int, LocDefinition],
    model_vertices: Callable[[LocModel], Sequence[Vertex]],
) -> dict[tuple[int, int], int]:
    """The loc shadow at each tile corner, by the corner's x and y. A corner that the result leaves out has the shadow 0.

    `placed` is what `place_scenery` gives for the level 0 placements, in the order of the landscape file. `locs` holds
    the loc definitions by id. `model_vertices` gives the vertices of a part's model as the cache stores them, with the
    models of the `LocModel` joined in order, as `region_contour.own_vertices` takes them.

    A wall writes 50 whatever the corner held, also when it has no model for its type (lines 254 to 284 for type 0, 307
    to 316 for type 1 and 370 to 379 for type 3). An object writes at every corner of its footprint and keeps the larger
    shadow (lines 487 to 493). Its shadow is the XYZMag of its model over 4, at most 30 (lines 479 to 485). An object
    that is not a `Model` writes 15: a loc with the non-flat-shading flag gives a `ModelData` (`ObjectComposition.java`
    lines 584 to 595), and an animated loc or a loc with impostors is a `DynamicObject` (`PacketBuffer.java` lines 472 to
    476), which the client adds also when it shows nothing. Any other object with no model for its type writes nothing,
    the non-flat-shading one included, because `getModel` returns null before it tests the flag (`ObjectComposition.java`
    lines 579 to 583, `PacketBuffer.java` line 478).
    """
    shadows: dict[tuple[int, int], int] = {}
    for placed_loc in placed:
        placement = placed_loc.placement
        raw = locs[placement.loc]
        if not raw.casts_shadow:
            continue
        loc_type = placement.loc_type
        if loc_type in _WALL_CORNERS:
            for dx, dy in _WALL_CORNERS[loc_type][placement.rotation]:
                shadows[(placement.x + dx, placement.y + dy)] = WALL_SHADOW
            continue
        if loc_type not in (10, 11):
            continue
        shadow = _object_shadow(placed_loc, raw, model_vertices)
        if shadow is None:
            continue
        # PacketBuffer.java lines 169 to 177: the footprint swaps its width and length at rotations 1 and 3.
        width, length = (raw.length, raw.width) if placement.rotation in (1, 3) else (raw.width, raw.length)
        for dx in range(width + 1):
            for dy in range(length + 1):
                corner = (placement.x + dx, placement.y + dy)
                shadows[corner] = max(shadows.get(corner, 0), shadow)
    return shadows


def _object_shadow(
    placed_loc: PlacedLoc, raw: LocDefinition, model_vertices: Callable[[LocModel], Sequence[Vertex]]
) -> int | None:
    """The shadow of an object of type 10 or 11, or None when the client adds no object for it."""
    if raw.animation != -1 or raw.impostors is not None:
        return DEFAULT_OBJECT_SHADOW
    if not placed_loc.parts:
        return None
    if raw.non_flat_shading:
        return DEFAULT_OBJECT_SHADOW
    (part,) = placed_loc.parts
    # A loc with impostors returned above, so the loc that the placement shows is the loc that the landscape names.
    vertices = [client_vertex(vertex, part, raw) for vertex in model_vertices(part.model)]
    return min(_xyz_mag(vertices) // 4, MAX_OBJECT_SHADOW)


def _xyz_mag(vertices: Sequence[Vertex]) -> int:
    """The largest distance of a vertex from the model's vertical axis. The client adds 0.99 to the root and drops the
    fraction (`Model.calculateBoundsCylinder`, lines 620 to 626)."""
    largest = max((x * x + z * z for x, _, z in vertices), default=0)
    return int(sqrt(largest) + 0.99)
