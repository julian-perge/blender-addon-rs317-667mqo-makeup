"""Whether a placement shares the mesh of its loc model, and the vertices of a placement that does not. Nothing here
imports bpy.

A placement shares when its object can hold the whole transform and the client draws the model unchanged. It gets its
own vertices in two cases. The client bends a contoured loc on uneven ground to the terrain (`ObjectComposition.java`
lines 600 to 606 with `Model.method2720` or `ModelData.method2625`, from line 1141). And Blender cannot hold the
transform of a diagonal wall decoration with different x and z scales as a location, a rotation and a scale (guess 2
of the spec of issue 35).

Every rule follows the 2018 Old School client, as the spec of issue 35 lists them. Revision 149 is not checked against
it, and the rules have no second reader.
"""

from collections.abc import Callable, Mapping, Sequence
from math import cos, pi, sin, sqrt

from .loc_definition import LocDefinition
from .model import Vertex
from .region import Placement
from .region_loc import shown_loc_id
from .region_placement import DIAGONAL_MOVE, DIAGONAL_TURN, TILE, TURN_UNITS, PlacedPart

_SINE = int(65536.0 * sin(DIAGONAL_TURN * 0.0030679615))
_COSINE = int(65536.0 * cos(DIAGONAL_TURN * 0.0030679615))
"""The entries for 256 units of the client's SINE and COSINE tables (`Graphics3D.java` lines 97 to 98)."""


def own_vertices(
    placement: Placement,
    part: PlacedPart,
    locs: Mapping[int, LocDefinition],
    vertices: Sequence[Vertex],
    height: Callable[[int, int], int],
) -> tuple[tuple[float, float, float], ...] | None:
    """The vertices of one part of a placement in Blender units, relative to `part.location`, or None when the part
    shares the mesh of its loc model.

    `vertices` are the vertices of the part's model as the cache stores them, with the models of `part.model` joined in
    order and the mirror not yet applied. The result keeps their order. When `part.model.mirrored` is true, the caller
    swaps the first and the last corner of each face, as `ModelData.method2633` (lines 1380 to 1390) does. An object
    with these vertices takes no rotation and no scale.

    `height(x, y)` is the height of the tile corner (x, y) in game units, as `place_scenery` reads it. The client's test
    that the model stays inside its 104 tile scene (`Model.java`, `method2720`) is left out, because the region is not a
    scene and `height` also reads the neighbour regions. The owner chose this in the Decisions comment on issue 44.

    A contoured ground above 0 on a model with no height is refused, because the client divides by that height
    (`Model.java` line 430). The owner chose this in the same comment.
    """
    raw = locs[placement.loc]
    shown_id = shown_loc_id(placement.loc, locs)
    if shown_id is None:
        raise ValueError(f"The placement at ({placement.x}, {placement.y}) shows nothing, so it has no vertices")
    shown = locs[shown_id]
    contoured = shown.contoured_ground >= 0
    if not contoured and not part.own_mesh:
        return None
    game = [client_vertex(vertex, part, shown) for vertex in vertices]
    if contoured:
        contour = _contour(placement, part, raw, shown, game, height)
        if contour is None and not part.own_mesh:
            return None
        if contour is not None:
            game = [(x, y, z) for (x, _, z), y in zip(game, contour, strict=True)]
    return tuple(_to_blender(vertex, placement, part) for vertex in game)


def client_vertex(vertex: Vertex, part: PlacedPart, shown: LocDefinition) -> Vertex:
    """A vertex after the steps of `ObjectComposition.getModel` (lines 786 to 819), in game axes and whole units: the
    mirror (`ModelData.method2633`), the diagonal turn and move (`method2663` and `method2630`), the quarter turns
    (`method2649`, `method2627` and `method2641`), the scale (`method2674`) and the offset (`method2630`)."""
    x, y, z = vertex
    if part.model.mirrored:
        z = -z
    if part.model_type == 4 and part.model_rotation > 3:
        x, z = (_SINE * z + _COSINE * x) >> 16, (_COSINE * z - _SINE * x) >> 16
        x, z = x + DIAGONAL_MOVE[0], z + DIAGONAL_MOVE[1]
    quarters = part.model_rotation & 3
    if quarters == 1:
        x, z = z, -x
    elif quarters == 2:
        x, z = -x, -z
    elif quarters == 3:
        x, z = -z, x
    scale_x, scale_height, scale_z = shown.scale
    if (scale_x, scale_height, scale_z) != (128, 128, 128):
        x, y, z = _divide(x * scale_x, 128), _divide(scale_height * y, 128), _divide(scale_z * z, 128)
    offset_x, offset_height, offset_z = shown.offset
    return x + offset_x, y + offset_height, z + offset_z


def _contour(
    placement: Placement,
    part: PlacedPart,
    raw: LocDefinition,
    shown: LocDefinition,
    vertices: Sequence[Vertex],
    height: Callable[[int, int], int],
) -> list[int] | None:
    """The game y of each vertex after the contour, or None when the client returns the model unchanged.

    A loc that is animated or has impostors is a DynamicObject (`PacketBuffer.java` lines 214 to 218 and the same test
    in each branch). `DynamicObject.getModel` places the contour at the footprint of the shown loc, swapped by the
    rotation of the part, and contours the lit model (`ObjectComposition.method5092`). Any other loc places it at the
    footprint of the placed loc, swapped by the placement's rotation (`PacketBuffer.java` lines 165 to 200), and
    contours the lit model unless it is non-flat-shading (`ObjectComposition.java` lines 584 to 606).
    """
    dynamic = raw.animation != -1 or raw.impostors is not None
    footprint_loc, rotation = (shown, part.model_rotation) if dynamic else (raw, placement.rotation)
    width, length = (
        (footprint_loc.length, footprint_loc.width)
        if rotation in (1, 3)
        else (footprint_loc.width, footprint_loc.length)
    )
    position_x = placement.x * TILE + width * TILE // 2
    position_z = placement.y * TILE + length * TILE // 2
    x0, x1 = placement.x + (width >> 1), placement.x + ((width + 1) >> 1)
    y0, y1 = placement.y + (length >> 1), placement.y + ((length + 1) >> 1)
    reference = (height(x1, y1) + height(x0, y1) + height(x1, y0) + height(x0, y0)) >> 2

    if not dynamic and shown.non_flat_shading:
        # ModelData.method2625 with the box of method2637.
        west = position_x + min((x for x, _, _ in vertices), default=999999)
        east = position_x + max((x for x, _, _ in vertices), default=-999999)
        south = position_z + min((z for _, _, z in vertices), default=99999)
        north = position_z + max((z for _, _, z in vertices), default=-99999)
    else:
        # Model.method2720 with the radius of calculateBoundsCylinder.
        radius = int(sqrt(max((x * x + z * z for x, _, z in vertices), default=0)) + 0.99)
        west, east = position_x - radius, position_x + radius
        south, north = position_z - radius, position_z + radius
    west, east, south, north = west >> 7, (east + 127) >> 7, south >> 7, (north + 127) >> 7
    if all(reference == height(x, y) for x, y in ((west, south), (east, south), (west, north), (east, north))):
        return None

    contoured_ground = shown.contoured_ground
    model_height = max((-y for _, y, _ in vertices if y < 0), default=0)
    heights = []
    for x, y, z in vertices:
        ground = _ground(position_x + x, position_z + z, height)
        if contoured_ground == 0:
            heights.append(ground + y - reference)
            continue
        if model_height == 0:
            raise ValueError(
                f"The contoured loc at ({placement.x}, {placement.y}) has a model with no height, and the client "
                "divides by it"
            )
        share = _divide(-y << 16, model_height)
        if share < contoured_ground:
            heights.append(_divide((contoured_ground - share) * (ground - reference), contoured_ground) + y)
        elif dynamic:
            # ObjectComposition.method5092 contours a copy that already holds every height (Model.toSharedModel).
            heights.append(y)
        else:
            # Model.method2720 and ModelData.method2625 give the contoured model a new height array and write only the
            # vertices that they bend, so the client draws every other vertex at height 0.
            heights.append(0)
    return heights


def _ground(x: int, z: int, height: Callable[[int, int], int]) -> int:
    """The terrain height under the game point (x, z), as `Model.method2720` blends the four corners of its tile."""
    fraction_x, fraction_z = x & 127, z & 127
    tile_x, tile_z = x >> 7, z >> 7
    south = (height(tile_x, tile_z) * (128 - fraction_x) + height(tile_x + 1, tile_z) * fraction_x) >> 7
    north = (height(tile_x, tile_z + 1) * (128 - fraction_x) + fraction_x * height(tile_x + 1, tile_z + 1)) >> 7
    return (south * (128 - fraction_z) + north * fraction_z) >> 7


def _to_blender(vertex: Vertex, placement: Placement, part: PlacedPart) -> tuple[float, float, float]:
    """A client vertex in Blender axes, turned by the 256 units that the client gives an object of type 11 when it draws
    it (`PacketBuffer.java` line 478), moved to the ground of the part and made relative to `part.location`."""
    x, y, z = vertex
    blender_x, blender_y, blender_z = float(x), float(z), float(-y)
    if placement.loc_type == 11:
        angle = -2 * pi * DIAGONAL_TURN / TURN_UNITS
        blender_x, blender_y = (
            cos(angle) * blender_x - sin(angle) * blender_y,
            sin(angle) * blender_x + cos(angle) * blender_y,
        )
    ground, location = part.ground, part.location
    return (
        blender_x + ground[0] - location[0],
        blender_y + ground[1] - location[1],
        blender_z + ground[2] - location[2],
    )


def _divide(value: int, divisor: int) -> int:
    """Java's integer division by a positive divisor, which rounds toward zero."""
    quotient = abs(value) // divisor
    return quotient if value >= 0 else -quotient
