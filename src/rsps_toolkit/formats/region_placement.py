"""Where each level 0 placement of a region stands, and the transform that its Blender object needs. Nothing here imports
bpy.

Every rule follows the 2018 Old School client (`PacketBuffer.java`, `Region.java`, `ObjectComposition.java`,
`ModelData.java` and `Model.java`), as the spec of issue 35 lists them. Revision 149 is not checked against it, and the
rules have no second reader.

The client works in game units, with y pointing down. The transform is in Blender axes, where a game point (x, y, z)
becomes (x, z, -y), as in `model_to_object`. The client turns a model by `n` units of a turn of 2048 with
`ModelData.method2663` (lines 1332 to 1343), which is a turn of -2 pi n / 2048 radians about Blender z.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import cos, pi, sin

from .loc_definition import LocDefinition
from .region import Placement
from .region_loc import LocModel, pick_model, shown_loc_id

TILE = 128
TURN_UNITS = 2048
DIAGONAL_TURN = 256
"""The turn of a diagonal wall decoration and of an object of type 11, an eighth of a turn."""
DIAGONAL_MOVE = (45, -45)
"""The move that the client gives the model of a diagonal wall decoration, (45, 0, -45) in game axes
(`ObjectComposition.java` line 789), in Blender x and y."""
DEFAULT_DISPLACEMENT = 16

_TURN_TO_RADIANS = -2 * pi / TURN_UNITS

type Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


class Slot(StrEnum):
    """The kind of thing that the client makes of a placement (`PacketBuffer.java` lines 212 to 503)."""

    WALL = "wall"
    WALL_DECORATION = "wall decoration"
    OBJECT = "object"
    GROUND_DECORATION = "ground decoration"


def slot_of(loc_type: int) -> Slot:
    """The slot of a loc type: 0 to 3 the wall, 4 to 8 the wall decoration, 9 to 21 the object, 22 the ground decoration
    (`PacketBuffer.java` lines 212 to 503, `class50.java` lines 67 to 72)."""
    if not 0 <= loc_type <= 22:
        raise ValueError(f"The loc type is {loc_type}, outside 0 to 22")
    if loc_type <= 3:
        return Slot.WALL
    if loc_type <= 8:
        return Slot.WALL_DECORATION
    if loc_type <= 21:
        return Slot.OBJECT
    return Slot.GROUND_DECORATION


@dataclass(frozen=True)
class PlacedPart:
    """One model of a placement, with where it stands. Most placements have one part. A wall of type 2 and a wall
    decoration of type 8 have two."""

    slot: Slot
    model_type: int
    """The loc type that the client passes to `ObjectComposition.getModel` for this part. It differs from the placement's
    type for a wall decoration, which asks for type 4."""
    model_rotation: int
    """The rotation, 0 to 7, that the client passes to `getModel`. Above 3 it means the mirror flips and, for type 4, the
    diagonal turn."""
    model: LocModel
    location: tuple[float, float, float]
    """Where the model's origin goes, in Blender units: the position on the tile, the height, the wall decoration
    offset, and the model's own offset and diagonal move."""
    ground: tuple[float, float, float]
    """Where the client draws the model, in Blender units: the position on the tile, the height and the wall decoration
    offset. The model's own offset and diagonal move are not in it, because the client puts them in the model's
    vertices."""
    rotation: float | None
    """The turn about Blender z in radians, or None when the transform is not a location, a rotation and a scale."""
    scale: tuple[float, float, float] | None
    """The scale in Blender x, y and z, or None when the transform is not a location, a rotation and a scale. The mirror
    is a scale of -1 on y."""
    linear: Matrix
    """The exact 3 by 3 matrix that takes a Blender model vertex to its place relative to `location`. It holds also when
    `rotation` and `scale` are None."""

    @property
    def own_mesh(self) -> bool:
        """True when Blender cannot hold the transform as location, rotation and scale, so that the placement needs its
        own mesh with the vertices already transformed."""
        return self.rotation is None


@dataclass(frozen=True)
class PlacedLoc:
    placement: Placement
    parts: tuple[PlacedPart, ...]
    """Empty when the placement shows nothing: its impostor is -1, or its loc has no model for its type."""


@dataclass
class _Record:
    placement: Placement
    raw: LocDefinition
    """The loc that the landscape names. The footprint and the height come from it."""
    shown: LocDefinition | None
    """The loc that the placement shows, which differs from `raw` for an impostor. The model, scale and offset come from it."""
    parts: list[tuple[int, int, LocModel]]
    offset: tuple[int, int] | None = None
    """The wall decoration offset of the first part, in game x and z, which a later wall can rescale."""


def place_scenery(
    placements: Sequence[Placement], locs: Mapping[int, LocDefinition], height: Callable[[int, int], int]
) -> list[PlacedLoc]:
    """The parts and transforms of level 0 placements, in the order given, which must be the order of the landscape file.

    `height(x, y)` is the height of the tile corner (x, y) in game units, counted from the region's south-west corner,
    as the client stores it. A tile outside the region has the height of the neighbour region.

    The order matters because the offset of a wall decoration depends on the wall on its tile. A decoration that comes
    after a wall reads the wall's displacement (`PacketBuffer.java` lines 413 to 467, `Region.java` lines 770 to 773). A
    wall of type 0 or 2, or an object of type 9, that comes after a decoration scales the offsets of the decoration
    (`PacketBuffer.java` lines 295 to 297, 358 to 360 and 398 to 400, `Region.method3030`, lines 656 to 665).
    """
    walls: dict[tuple[int, int], LocDefinition] = {}
    decorations: dict[tuple[int, int], _Record] = {}
    records: list[_Record] = []
    for placement in placements:
        if placement.level != 0:
            raise ValueError(f"A placement is on level {placement.level}, and only level 0 is placed")
        if not 0 <= placement.rotation <= 3:
            raise ValueError(f"A placement has the rotation {placement.rotation}, outside 0 to 3")
        slot_of(placement.loc_type)
        if placement.loc not in locs:
            raise ValueError(
                f"A placement at ({placement.x}, {placement.y}) names the loc {placement.loc}, which is unknown"
            )
        raw = locs[placement.loc]
        shown_id = shown_loc_id(placement.loc, locs)
        shown = None if shown_id is None else locs[shown_id]
        record = _Record(placement, raw, shown, _models(shown, placement.loc_type, placement.rotation))
        records.append(record)
        tile = (placement.x, placement.y)
        # An animated loc or a loc with impostors is a DynamicObject, which the client adds even when it has no model to
        # show (`PacketBuffer.java` lines 214 to 218 and the same test in each branch).
        added = bool(record.parts) or raw.animation != -1 or raw.impostors is not None
        loc_type = placement.loc_type
        if loc_type <= 3:
            if added:
                walls[tile] = raw
            if loc_type in (0, 2):
                _rescale_decoration(decorations.get(tile), raw.decor_displacement)
        elif loc_type <= 8:
            wall = walls.get(tile)
            record.offset = _decoration_offset(loc_type, placement.rotation, wall)
            if added:
                decorations[tile] = record
        elif loc_type == 9:
            _rescale_decoration(decorations.get(tile), raw.decor_displacement)
    return [_place(record, height) for record in records]


def _models(shown: LocDefinition | None, loc_type: int, rotation: int) -> list[tuple[int, int, LocModel]]:
    """The `getModel` calls of `PacketBuffer.addObject` for a placement, as (type, rotation, model), without the calls
    that give no model.

    Whether `getModel` gives a model depends on the loc type only (`ObjectComposition.java` lines 694 to 751), and the
    two calls of a placement have the same type. So both calls give a model or neither does. For a wall of type 2 the
    client would also keep one model if only one existed (`Region.addBoundary`, lines 420 to 421), which this code does
    as well."""
    if shown is None:
        return []
    if loc_type == 2:
        calls = [(2, rotation + 4), (2, (rotation + 1) & 3)]
    elif loc_type in (4, 5):
        calls = [(4, rotation)]
    elif loc_type == 6:
        calls = [(4, rotation + 4)]
    elif loc_type == 7:
        calls = [(4, ((rotation + 2) & 3) + 4)]
    elif loc_type == 8:
        calls = [(4, rotation + 4), (4, ((rotation + 2) & 3) + 4)]
    elif loc_type in (10, 11):
        calls = [(10, rotation)]
    else:
        calls = [(loc_type, rotation)]
    picked = [
        (model_type, model_rotation, pick_model(shown, model_type, model_rotation))
        for model_type, model_rotation in calls
    ]
    return [(model_type, model_rotation, model) for model_type, model_rotation, model in picked if model is not None]


def _decoration_offset(loc_type: int, rotation: int, wall: LocDefinition | None) -> tuple[int, int]:
    """The offset of a wall decoration from the middle of its tile, in game x and z (`PacketBuffer.java` lines 413 to
    467 with `class50.java` lines 69 to 72)."""
    if loc_type == 5:
        displacement = DEFAULT_DISPLACEMENT if wall is None else wall.decor_displacement
        return displacement * (1, 0, -1, 0)[rotation], displacement * (0, -1, 0, 1)[rotation]
    if loc_type in (6, 8):
        displacement = DEFAULT_DISPLACEMENT // 2 if wall is None else _divide(wall.decor_displacement, 2)
        return displacement * (1, -1, -1, 1)[rotation], displacement * (-1, -1, 1, 1)[rotation]
    return 0, 0


def _rescale_decoration(record: _Record | None, displacement: int) -> None:
    """`Region.method3030` (lines 656 to 665): the offsets of the decoration on the tile become displacement * offset / 16
    when the displacement is not 16."""
    if displacement == DEFAULT_DISPLACEMENT or record is None or record.offset is None:
        return
    x, z = record.offset
    record.offset = _divide(displacement * x, DEFAULT_DISPLACEMENT), _divide(displacement * z, DEFAULT_DISPLACEMENT)


def _divide(value: int, divisor: int) -> int:
    """Java's integer division, which rounds toward zero."""
    quotient = abs(value) // divisor
    return quotient if value >= 0 else -quotient


def _footprint(loc: LocDefinition, rotation: int) -> tuple[int, int]:
    """The width and length of a placement, swapped at rotations 1 and 3 (`PacketBuffer.java` lines 169 to 177)."""
    return (loc.length, loc.width) if rotation in (1, 3) else (loc.width, loc.length)


def _tile_height(raw: LocDefinition, placement: Placement, height: Callable[[int, int], int]) -> int:
    """The mean of the four corner heights under the footprint (`PacketBuffer.java` lines 179 to 198). The client's test
    against the 104 tile width of its scene (lines 179 and 189) is left out, because the region is not a scene."""
    width, length = _footprint(raw, placement.rotation)
    x0, x1 = placement.x + (width >> 1), placement.x + ((width + 1) >> 1)
    y0, y1 = placement.y + (length >> 1), placement.y + ((length + 1) >> 1)
    return (height(x1, y1) + height(x0, y1) + height(x1, y0) + height(x0, y0)) >> 2


def _position(raw: LocDefinition, placement: Placement) -> tuple[int, int]:
    """The game x and z of a placement's origin on the ground, before the wall decoration offset. Types 10 and 11 stand at
    the middle of their footprint (`PacketBuffer.java` lines 199 to 200 and 478). Every other type stands at the
    middle of its tile, because the client gives `method2911` a footprint of 1 by 1 for them (lines 236 and 393)."""
    if placement.loc_type in (10, 11):
        width, length = _footprint(raw, placement.rotation)
        return placement.x * TILE + width * TILE // 2, placement.y * TILE + length * TILE // 2
    return placement.x * TILE + TILE // 2, placement.y * TILE + TILE // 2


def _turn(units: int) -> Matrix:
    angle = units * _TURN_TO_RADIANS
    c, s = cos(angle), sin(angle)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _dot(row: tuple[float, float, float], vector: tuple[float, float, float]) -> float:
    return row[0] * vector[0] + row[1] * vector[1] + row[2] * vector[2]


def _multiply(a: Matrix, b: Matrix) -> Matrix:
    columns = [(b[0][j], b[1][j], b[2][j]) for j in range(3)]
    return (
        (_dot(a[0], columns[0]), _dot(a[0], columns[1]), _dot(a[0], columns[2])),
        (_dot(a[1], columns[0]), _dot(a[1], columns[1]), _dot(a[1], columns[2])),
        (_dot(a[2], columns[0]), _dot(a[2], columns[1]), _dot(a[2], columns[2])),
    )


def _apply(matrix: Matrix, vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return _dot(matrix[0], vector), _dot(matrix[1], vector), _dot(matrix[2], vector)


def _place(record: _Record, height: Callable[[int, int], int]) -> PlacedLoc:
    shown = record.shown
    if shown is None or not record.parts:
        return PlacedLoc(record.placement, ())
    x, z = _position(record.raw, record.placement)
    floor = _tile_height(record.raw, record.placement, height)
    parts = []
    for index, part in enumerate(record.parts):
        # Region.java lines 1438 to 1463: the offset moves only the first model of a wall decoration.
        offset = record.offset if record.offset is not None and index == 0 else (0, 0)
        parts.append(_transform(record.placement, shown, part, (x + offset[0], z + offset[1], -floor)))
    return PlacedLoc(record.placement, tuple(parts))


def _transform(
    placement: Placement,
    shown: LocDefinition,
    part: tuple[int, int, LocModel],
    origin: tuple[float, float, float],
) -> PlacedPart:
    """The part of a placement with its transform. `origin` is the ground position with the wall decoration offset and
    the height, in Blender units."""
    model_type, model_rotation, model = part
    orientation = DIAGONAL_TURN if placement.loc_type == 11 else 0
    diagonal = model_type == 4 and model_rotation > 3
    quarters = model_rotation & 3
    scale_x, scale_height, scale_z = (value / 128 for value in shown.scale)

    # The client's steps on a model vertex, in order (`ObjectComposition.java` lines 786 to 819): the mirror, the diagonal
    # turn and move, the quarter turns, the scale, the offset, and then the orientation of the draw.
    mirror: Matrix = ((1, 0, 0), (0, -1 if model.mirrored else 1, 0), (0, 0, 1))
    steps = mirror
    move = (0.0, 0.0, 0.0)
    if diagonal:
        steps = _multiply(_turn(DIAGONAL_TURN), steps)
        move = (*DIAGONAL_MOVE, 0)
    quarter_turn = _turn(512 * quarters)
    scale: Matrix = ((scale_x, 0, 0), (0, scale_z, 0), (0, 0, scale_height))
    orient = _turn(orientation)
    linear = _multiply(orient, _multiply(scale, _multiply(quarter_turn, steps)))
    own = _apply(orient, _apply(scale, _apply(quarter_turn, move)))
    shown_offset = (shown.offset[0], shown.offset[2], -shown.offset[1])
    turned_offset = _apply(orient, shown_offset)
    location = (
        origin[0] + own[0] + turned_offset[0],
        origin[1] + own[1] + turned_offset[1],
        origin[2] + own[2] + turned_offset[2],
    )

    # A quarter turn swaps the scale on x and z. A scale that differs between x and z cannot follow a turn of 45 degrees.
    rotation: float | None = (orientation + 512 * quarters + (DIAGONAL_TURN if diagonal else 0)) * _TURN_TO_RADIANS
    plain_scale: tuple[float, float, float] | None
    if diagonal and scale_x != scale_z:
        rotation, plain_scale = None, None
    else:
        along_x, along_y = (scale_z, scale_x) if quarters % 2 and not diagonal else (scale_x, scale_z)
        plain_scale = (along_x, along_y * (-1 if model.mirrored else 1), scale_height)
    return PlacedPart(
        slot_of(placement.loc_type),
        model_type,
        model_rotation,
        model,
        location,
        origin,
        rotation,
        plain_scale,
        linear,
    )
