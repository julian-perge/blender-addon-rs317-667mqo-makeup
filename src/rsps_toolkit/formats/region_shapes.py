"""The triangles of one terrain tile, as the client builds them in `Region.addTile` (`Region.java` lines 321 to 355)
and draws a `SceneTilePaint` in `drawTileUnderlay` (`Region.java` from line 1790)."""

from dataclasses import dataclass
from enum import Enum

from .region import Tile


class Corner(Enum):
    """A corner of a tile. Its value is its offset in tiles from the south-west corner, so the corner's height is the
    height of the tile at that offset (`class24.java` lines 190 to 193)."""

    SW = (0, 0)
    SE = (1, 0)
    NE = (1, 1)
    NW = (0, 1)


@dataclass(frozen=True)
class TilePoint:
    """One vertex of a tile triangle."""

    x: int
    """Game units east of the tile's west edge, from 0 to 128."""
    y: int
    """Game units north of the tile's south edge, from 0 to 128."""
    corners: tuple[Corner, ...]
    """The one or two corners that give the point its height and colours, in the order SW, SE, NE, NW. For two
    corners, the client takes the sum of their values shifted right by 1 (`SceneTileModel.java` lines 124 to 220)."""


@dataclass(frozen=True)
class TileTriangle:
    """One triangle of a tile."""

    overlay: bool
    """True when the triangle takes the overlay colours and texture, and false when it takes the underlay colours
    (`SceneTileModel.java` lines 264 to 277)."""
    points: tuple[TilePoint, TilePoint, TilePoint]
    """The points in the order that the client draws them."""


# The 16 points of `SceneTileModel.java` lines 124 to 220, by their number.
POINTS = {
    1: TilePoint(0, 0, (Corner.SW,)),
    2: TilePoint(64, 0, (Corner.SW, Corner.SE)),
    3: TilePoint(128, 0, (Corner.SE,)),
    4: TilePoint(128, 64, (Corner.SE, Corner.NE)),
    5: TilePoint(128, 128, (Corner.NE,)),
    6: TilePoint(64, 128, (Corner.NE, Corner.NW)),
    7: TilePoint(0, 128, (Corner.NW,)),
    8: TilePoint(0, 64, (Corner.SW, Corner.NW)),
    9: TilePoint(64, 32, (Corner.SW, Corner.SE)),
    10: TilePoint(96, 64, (Corner.SE, Corner.NE)),
    11: TilePoint(64, 96, (Corner.NE, Corner.NW)),
    12: TilePoint(32, 64, (Corner.SW, Corner.NW)),
    13: TilePoint(32, 32, (Corner.SW,)),
    14: TilePoint(96, 32, (Corner.SE,)),
    15: TilePoint(96, 96, (Corner.NE,)),
    16: TilePoint(32, 96, (Corner.NW,)),
}

# `SceneTileModel.java` line 76: the point numbers of each shape. The client never builds shapes 0 and 1 from this
# table, because `addTile` draws them as a `SceneTilePaint` (`Region.java` lines 324 to 325 and 344 to 345).
SHAPE_POINTS = (
    (1, 3, 5, 7),
    (1, 3, 5, 7),
    (1, 3, 5, 7),
    (1, 3, 5, 7, 6),
    (1, 3, 5, 7, 6),
    (1, 3, 5, 7, 6),
    (1, 3, 5, 7, 6),
    (1, 3, 5, 7, 2, 6),
    (1, 3, 5, 7, 2, 8),
    (1, 3, 5, 7, 2, 8),
    (1, 3, 5, 7, 11, 12),
    (1, 3, 5, 7, 11, 12),
    (1, 3, 5, 7, 13, 14),
)

# `SceneTileModel.java` line 77: four numbers for each triangle of each shape. The first is 0 for underlay and 1 for
# overlay, and the other three are indices into the points of the shape.
SHAPE_TRIANGLES = (
    (0, 1, 2, 3, 0, 0, 1, 3),
    (1, 1, 2, 3, 1, 0, 1, 3),
    (0, 1, 2, 3, 1, 0, 1, 3),
    (0, 0, 1, 2, 0, 0, 2, 4, 1, 0, 4, 3),
    (0, 0, 1, 4, 0, 0, 4, 3, 1, 1, 2, 4),
    (0, 0, 4, 3, 1, 0, 1, 2, 1, 0, 2, 4),
    (0, 1, 2, 4, 1, 0, 1, 4, 1, 0, 4, 3),
    (0, 4, 1, 2, 0, 4, 2, 5, 1, 0, 4, 5, 1, 0, 5, 3),
    (0, 4, 1, 2, 0, 4, 2, 3, 0, 4, 3, 5, 1, 0, 4, 5),
    (0, 0, 4, 5, 1, 4, 1, 2, 1, 4, 2, 3, 1, 4, 3, 5),
    (0, 0, 1, 5, 0, 1, 4, 5, 0, 1, 2, 4, 1, 0, 5, 3, 1, 5, 4, 3, 1, 4, 2, 3),
    (1, 0, 1, 5, 1, 1, 4, 5, 1, 1, 2, 4, 0, 0, 5, 3, 0, 5, 4, 3, 0, 4, 2, 3),
    (1, 0, 5, 4, 1, 0, 1, 5, 0, 0, 4, 3, 0, 4, 5, 3, 0, 5, 2, 3, 0, 1, 2, 5),
)

# `Region.java` lines 1853 and 1880 (`drawTileUnderlay`): the north-east triangle, then the south-west triangle.
PAINT_POINTS = (
    (POINTS[5], POINTS[7], POINTS[3]),
    (POINTS[1], POINTS[3], POINTS[7]),
)


def tile_triangles(tile: Tile) -> tuple[TileTriangle, ...]:
    """The triangles of one tile. `class24.java` lines 238 to 241 give `addTile` shape 0 for a tile with no overlay
    and the overlay shape + 1 for the others. A tile with no underlay and no overlay still gets two triangles here,
    though the client builds nothing for it (`class24.java` line 189), so the caller drops it."""
    if tile.overlay == 0:
        return tuple(TileTriangle(False, points) for points in PAINT_POINTS)
    shape = tile.overlay_shape + 1
    if shape == 1:
        return tuple(TileTriangle(True, points) for points in PAINT_POINTS)
    rotation = tile.overlay_rotation
    points = [POINTS[rotate_point(number, rotation)] for number in SHAPE_POINTS[shape]]
    table = SHAPE_TRIANGLES[shape]
    triangles = []
    for start in range(0, len(table), 4):
        part, a, b, c = table[start : start + 4]
        a, b, c = (rotate_index(index, rotation) for index in (a, b, c))
        triangles.append(TileTriangle(part == 1, (points[a], points[b], points[c])))
    return tuple(triangles)


def rotate_point(number: int, rotation: int) -> int:
    """The number that point `number` takes at this rotation (`SceneTileModel.java` lines 112 to 122). The corner
    points 1, 3, 5 and 7 keep their numbers, because `rotate_index` rotates the corner indices of the triangle table
    instead."""
    if number % 2 == 0 and number <= 8:
        return ((number - 2 * rotation - 1) & 7) + 1
    if 8 < number <= 12:
        return ((number - 9 - rotation) & 3) + 9
    if 12 < number <= 16:
        return ((number - 13 - rotation) & 3) + 13
    return number


def rotate_index(index: int, rotation: int) -> int:
    """`SceneTileModel.java` lines 249 to 259. An index below 4 names a corner point, and the rotation moves it."""
    return (index - rotation) & 3 if index < 4 else index
