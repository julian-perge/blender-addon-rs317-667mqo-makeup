import pytest

from rsps_toolkit.formats.region import Tile
from rsps_toolkit.formats.region_shapes import Corner, TilePoint, tile_triangles

SW, SE, NE, NW = Corner.SW, Corner.SE, Corner.NE, Corner.NW
UNDERLAY, OVERLAY = False, True


def p(x: int, y: int, *corners: Corner) -> TilePoint:
    return TilePoint(x, y, corners)


# The triangles of SceneTileModel (the client's shapes 2 to 12, so overlay shapes 1 to 11), by overlay shape and
# rotation. They are the output of the constructor of `SceneTileModel.java` from line 80, with the tables of lines 76
# to 77, for a tile at (0, 0). The constructor was run in a scratch copy of the class, and its vertex x, vertex z,
# vertex height and the three vertex indices and colour choice of each triangle were printed and written out here.
# The corner heights were chosen so that each corner and each mean of two corners is a different height.
SCENE_TILE_MODEL = {
    (1, 0): [
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 128, NW)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(0, 128, NW)),
    ],
    (1, 1): [
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(128, 128, NE)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 128, NE)),
    ],
    (1, 2): [
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 0, SE)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(128, 0, SE)),
    ],
    (1, 3): [
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(0, 0, SW)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 0, SW)),
    ],
    (2, 0): [
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(128, 128, NE)),
        (UNDERLAY, p(0, 0, SW), p(128, 128, NE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(64, 128, NE, NW), p(0, 128, NW)),
    ],
    (2, 1): [
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 0, SE)),
        (UNDERLAY, p(0, 128, NW), p(128, 0, SE), p(128, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(128, 64, SE, NE), p(128, 128, NE)),
    ],
    (2, 2): [
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(0, 0, SW)),
        (UNDERLAY, p(128, 128, NE), p(0, 0, SW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(64, 0, SW, SE), p(128, 0, SE)),
    ],
    (2, 3): [
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 128, NW)),
        (UNDERLAY, p(128, 0, SE), p(0, 128, NW), p(0, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(0, 64, SW, NW), p(0, 0, SW)),
    ],
    (3, 0): [
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(64, 128, NE, NW)),
        (UNDERLAY, p(0, 0, SW), p(64, 128, NE, NW), p(0, 128, NW)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 128, NE, NW)),
    ],
    (3, 1): [
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 64, SE, NE)),
        (UNDERLAY, p(0, 128, NW), p(128, 64, SE, NE), p(128, 128, NE)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(128, 64, SE, NE)),
    ],
    (3, 2): [
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(64, 0, SW, SE)),
        (UNDERLAY, p(128, 128, NE), p(64, 0, SW, SE), p(128, 0, SE)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 0, SW, SE)),
    ],
    (3, 3): [
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 64, SW, NW)),
        (UNDERLAY, p(128, 0, SE), p(0, 64, SW, NW), p(0, 0, SW)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(0, 64, SW, NW)),
    ],
    (4, 0): [
        (UNDERLAY, p(0, 0, SW), p(64, 128, NE, NW), p(0, 128, NW)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(128, 128, NE)),
        (OVERLAY, p(0, 0, SW), p(128, 128, NE), p(64, 128, NE, NW)),
    ],
    (4, 1): [
        (UNDERLAY, p(0, 128, NW), p(128, 64, SE, NE), p(128, 128, NE)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 0, SE)),
        (OVERLAY, p(0, 128, NW), p(128, 0, SE), p(128, 64, SE, NE)),
    ],
    (4, 2): [
        (UNDERLAY, p(128, 128, NE), p(64, 0, SW, SE), p(128, 0, SE)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(0, 0, SW)),
        (OVERLAY, p(128, 128, NE), p(0, 0, SW), p(64, 0, SW, SE)),
    ],
    (4, 3): [
        (UNDERLAY, p(128, 0, SE), p(0, 64, SW, NW), p(0, 0, SW)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 128, NW)),
        (OVERLAY, p(128, 0, SE), p(0, 128, NW), p(0, 64, SW, NW)),
    ],
    (5, 0): [
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(64, 128, NE, NW), p(0, 128, NW)),
    ],
    (5, 1): [
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(128, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(128, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(128, 64, SE, NE), p(128, 128, NE)),
    ],
    (5, 2): [
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(64, 0, SW, SE), p(128, 0, SE)),
    ],
    (5, 3): [
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(0, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(0, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(0, 64, SW, NW), p(0, 0, SW)),
    ],
    (6, 0): [
        (UNDERLAY, p(64, 0, SW, SE), p(128, 0, SE), p(128, 128, NE)),
        (UNDERLAY, p(64, 0, SW, SE), p(128, 128, NE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(64, 0, SW, SE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(64, 128, NE, NW), p(0, 128, NW)),
    ],
    (6, 1): [
        (UNDERLAY, p(0, 64, SW, NW), p(0, 0, SW), p(128, 0, SE)),
        (UNDERLAY, p(0, 64, SW, NW), p(128, 0, SE), p(128, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(0, 64, SW, NW), p(128, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(128, 64, SE, NE), p(128, 128, NE)),
    ],
    (6, 2): [
        (UNDERLAY, p(64, 128, NE, NW), p(0, 128, NW), p(0, 0, SW)),
        (UNDERLAY, p(64, 128, NE, NW), p(0, 0, SW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(64, 128, NE, NW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(64, 0, SW, SE), p(128, 0, SE)),
    ],
    (6, 3): [
        (UNDERLAY, p(128, 64, SE, NE), p(128, 128, NE), p(0, 128, NW)),
        (UNDERLAY, p(128, 64, SE, NE), p(0, 128, NW), p(0, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(128, 64, SE, NE), p(0, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(0, 64, SW, NW), p(0, 0, SW)),
    ],
    (7, 0): [
        (UNDERLAY, p(64, 0, SW, SE), p(128, 0, SE), p(128, 128, NE)),
        (UNDERLAY, p(64, 0, SW, SE), p(128, 128, NE), p(0, 128, NW)),
        (UNDERLAY, p(64, 0, SW, SE), p(0, 128, NW), p(0, 64, SW, NW)),
        (OVERLAY, p(0, 0, SW), p(64, 0, SW, SE), p(0, 64, SW, NW)),
    ],
    (7, 1): [
        (UNDERLAY, p(0, 64, SW, NW), p(0, 0, SW), p(128, 0, SE)),
        (UNDERLAY, p(0, 64, SW, NW), p(128, 0, SE), p(128, 128, NE)),
        (UNDERLAY, p(0, 64, SW, NW), p(128, 128, NE), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 128, NW), p(0, 64, SW, NW), p(64, 128, NE, NW)),
    ],
    (7, 2): [
        (UNDERLAY, p(64, 128, NE, NW), p(0, 128, NW), p(0, 0, SW)),
        (UNDERLAY, p(64, 128, NE, NW), p(0, 0, SW), p(128, 0, SE)),
        (UNDERLAY, p(64, 128, NE, NW), p(128, 0, SE), p(128, 64, SE, NE)),
        (OVERLAY, p(128, 128, NE), p(64, 128, NE, NW), p(128, 64, SE, NE)),
    ],
    (7, 3): [
        (UNDERLAY, p(128, 64, SE, NE), p(128, 128, NE), p(0, 128, NW)),
        (UNDERLAY, p(128, 64, SE, NE), p(0, 128, NW), p(0, 0, SW)),
        (UNDERLAY, p(128, 64, SE, NE), p(0, 0, SW), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 0, SE), p(128, 64, SE, NE), p(64, 0, SW, SE)),
    ],
    (8, 0): [
        (UNDERLAY, p(0, 0, SW), p(64, 0, SW, SE), p(0, 64, SW, NW)),
        (OVERLAY, p(64, 0, SW, SE), p(128, 0, SE), p(128, 128, NE)),
        (OVERLAY, p(64, 0, SW, SE), p(128, 128, NE), p(0, 128, NW)),
        (OVERLAY, p(64, 0, SW, SE), p(0, 128, NW), p(0, 64, SW, NW)),
    ],
    (8, 1): [
        (UNDERLAY, p(0, 128, NW), p(0, 64, SW, NW), p(64, 128, NE, NW)),
        (OVERLAY, p(0, 64, SW, NW), p(0, 0, SW), p(128, 0, SE)),
        (OVERLAY, p(0, 64, SW, NW), p(128, 0, SE), p(128, 128, NE)),
        (OVERLAY, p(0, 64, SW, NW), p(128, 128, NE), p(64, 128, NE, NW)),
    ],
    (8, 2): [
        (UNDERLAY, p(128, 128, NE), p(64, 128, NE, NW), p(128, 64, SE, NE)),
        (OVERLAY, p(64, 128, NE, NW), p(0, 128, NW), p(0, 0, SW)),
        (OVERLAY, p(64, 128, NE, NW), p(0, 0, SW), p(128, 0, SE)),
        (OVERLAY, p(64, 128, NE, NW), p(128, 0, SE), p(128, 64, SE, NE)),
    ],
    (8, 3): [
        (UNDERLAY, p(128, 0, SE), p(128, 64, SE, NE), p(64, 0, SW, SE)),
        (OVERLAY, p(128, 64, SE, NE), p(128, 128, NE), p(0, 128, NW)),
        (OVERLAY, p(128, 64, SE, NE), p(0, 128, NW), p(0, 0, SW)),
        (OVERLAY, p(128, 64, SE, NE), p(0, 0, SW), p(64, 0, SW, SE)),
    ],
    (9, 0): [
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(32, 64, SW, NW)),
        (UNDERLAY, p(128, 0, SE), p(64, 96, NE, NW), p(32, 64, SW, NW)),
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 96, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(32, 64, SW, NW), p(0, 128, NW)),
        (OVERLAY, p(32, 64, SW, NW), p(64, 96, NE, NW), p(0, 128, NW)),
        (OVERLAY, p(64, 96, NE, NW), p(128, 128, NE), p(0, 128, NW)),
    ],
    (9, 1): [
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 96, NE, NW)),
        (UNDERLAY, p(0, 0, SW), p(96, 64, SE, NE), p(64, 96, NE, NW)),
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(96, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(64, 96, NE, NW), p(128, 128, NE)),
        (OVERLAY, p(64, 96, NE, NW), p(96, 64, SE, NE), p(128, 128, NE)),
        (OVERLAY, p(96, 64, SE, NE), p(128, 0, SE), p(128, 128, NE)),
    ],
    (9, 2): [
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(96, 64, SE, NE)),
        (UNDERLAY, p(0, 128, NW), p(64, 32, SW, SE), p(96, 64, SE, NE)),
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 32, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(96, 64, SE, NE), p(128, 0, SE)),
        (OVERLAY, p(96, 64, SE, NE), p(64, 32, SW, SE), p(128, 0, SE)),
        (OVERLAY, p(64, 32, SW, SE), p(0, 0, SW), p(128, 0, SE)),
    ],
    (9, 3): [
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 32, SW, SE)),
        (UNDERLAY, p(128, 128, NE), p(32, 64, SW, NW), p(64, 32, SW, SE)),
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(32, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(64, 32, SW, SE), p(0, 0, SW)),
        (OVERLAY, p(64, 32, SW, SE), p(32, 64, SW, NW), p(0, 0, SW)),
        (OVERLAY, p(32, 64, SW, NW), p(0, 128, NW), p(0, 0, SW)),
    ],
    (10, 0): [
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(32, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(64, 96, NE, NW), p(32, 64, SW, NW)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 96, NE, NW)),
        (UNDERLAY, p(0, 0, SW), p(32, 64, SW, NW), p(0, 128, NW)),
        (UNDERLAY, p(32, 64, SW, NW), p(64, 96, NE, NW), p(0, 128, NW)),
        (UNDERLAY, p(64, 96, NE, NW), p(128, 128, NE), p(0, 128, NW)),
    ],
    (10, 1): [
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 96, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(96, 64, SE, NE), p(64, 96, NE, NW)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(96, 64, SE, NE)),
        (UNDERLAY, p(0, 128, NW), p(64, 96, NE, NW), p(128, 128, NE)),
        (UNDERLAY, p(64, 96, NE, NW), p(96, 64, SE, NE), p(128, 128, NE)),
        (UNDERLAY, p(96, 64, SE, NE), p(128, 0, SE), p(128, 128, NE)),
    ],
    (10, 2): [
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(96, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(64, 32, SW, SE), p(96, 64, SE, NE)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(64, 32, SW, SE)),
        (UNDERLAY, p(128, 128, NE), p(96, 64, SE, NE), p(128, 0, SE)),
        (UNDERLAY, p(96, 64, SE, NE), p(64, 32, SW, SE), p(128, 0, SE)),
        (UNDERLAY, p(64, 32, SW, SE), p(0, 0, SW), p(128, 0, SE)),
    ],
    (10, 3): [
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(64, 32, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(32, 64, SW, NW), p(64, 32, SW, SE)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(32, 64, SW, NW)),
        (UNDERLAY, p(128, 0, SE), p(64, 32, SW, SE), p(0, 0, SW)),
        (UNDERLAY, p(64, 32, SW, SE), p(32, 64, SW, NW), p(0, 0, SW)),
        (UNDERLAY, p(32, 64, SW, NW), p(0, 128, NW), p(0, 0, SW)),
    ],
    (11, 0): [
        (OVERLAY, p(0, 0, SW), p(96, 32, SE), p(32, 32, SW)),
        (OVERLAY, p(0, 0, SW), p(128, 0, SE), p(96, 32, SE)),
        (UNDERLAY, p(0, 0, SW), p(32, 32, SW), p(0, 128, NW)),
        (UNDERLAY, p(32, 32, SW), p(96, 32, SE), p(0, 128, NW)),
        (UNDERLAY, p(96, 32, SE), p(128, 128, NE), p(0, 128, NW)),
        (UNDERLAY, p(128, 0, SE), p(128, 128, NE), p(96, 32, SE)),
    ],
    (11, 1): [
        (OVERLAY, p(0, 128, NW), p(32, 32, SW), p(32, 96, NW)),
        (OVERLAY, p(0, 128, NW), p(0, 0, SW), p(32, 32, SW)),
        (UNDERLAY, p(0, 128, NW), p(32, 96, NW), p(128, 128, NE)),
        (UNDERLAY, p(32, 96, NW), p(32, 32, SW), p(128, 128, NE)),
        (UNDERLAY, p(32, 32, SW), p(128, 0, SE), p(128, 128, NE)),
        (UNDERLAY, p(0, 0, SW), p(128, 0, SE), p(32, 32, SW)),
    ],
    (11, 2): [
        (OVERLAY, p(128, 128, NE), p(32, 96, NW), p(96, 96, NE)),
        (OVERLAY, p(128, 128, NE), p(0, 128, NW), p(32, 96, NW)),
        (UNDERLAY, p(128, 128, NE), p(96, 96, NE), p(128, 0, SE)),
        (UNDERLAY, p(96, 96, NE), p(32, 96, NW), p(128, 0, SE)),
        (UNDERLAY, p(32, 96, NW), p(0, 0, SW), p(128, 0, SE)),
        (UNDERLAY, p(0, 128, NW), p(0, 0, SW), p(32, 96, NW)),
    ],
    (11, 3): [
        (OVERLAY, p(128, 0, SE), p(96, 96, NE), p(96, 32, SE)),
        (OVERLAY, p(128, 0, SE), p(128, 128, NE), p(96, 96, NE)),
        (UNDERLAY, p(128, 0, SE), p(96, 32, SE), p(0, 0, SW)),
        (UNDERLAY, p(96, 32, SE), p(96, 96, NE), p(0, 0, SW)),
        (UNDERLAY, p(96, 96, NE), p(0, 128, NW), p(0, 0, SW)),
        (UNDERLAY, p(128, 128, NE), p(0, 128, NW), p(96, 96, NE)),
    ],
}

# `Region.java` lines 1853 and 1880 (`drawTileUnderlay`): the north-east triangle, then the south-west triangle.
DRAW_TILE_UNDERLAY = [
    (p(128, 128, NE), p(0, 128, NW), p(128, 0, SE)),
    (p(0, 0, SW), p(128, 0, SE), p(0, 128, NW)),
]


def triangles(tile: Tile) -> list[tuple[bool, TilePoint, TilePoint, TilePoint]]:
    return [(triangle.overlay, *triangle.points) for triangle in tile_triangles(tile)]


@pytest.mark.parametrize(("shape", "rotation"), SCENE_TILE_MODEL)
def test_a_tile_with_an_overlay_shape_from_1_to_11_gets_the_triangles_of_scene_tile_model(shape, rotation):
    tile = Tile(0, 0, 1, 1, shape, rotation)
    assert triangles(tile) == SCENE_TILE_MODEL[shape, rotation]


@pytest.mark.parametrize("rotation", range(4))
def test_a_tile_without_an_overlay_gets_two_underlay_triangles_on_the_north_west_to_south_east_edge(rotation):
    # `class24.java` lines 238 to 239 give `addTile` shape 0 for a tile with no overlay, and `Region.java` lines 324
    # to 325 make it a `SceneTilePaint` with the underlay colours, which `drawTileUnderlay` draws without a rotation.
    tile = Tile(0, 0, 1, 0, 0, rotation)
    assert triangles(tile) == [(UNDERLAY, *points) for points in DRAW_TILE_UNDERLAY]


@pytest.mark.parametrize("rotation", range(4))
def test_a_tile_with_overlay_shape_0_gets_two_overlay_triangles_on_the_north_west_to_south_east_edge(rotation):
    # `class24.java` line 241 gives `addTile` shape 1 for overlay shape 0, and `Region.java` lines 344 to 345 make it
    # a `SceneTilePaint` with the overlay colours, which `drawTileUnderlay` draws without a rotation. The owner chose
    # this over the rotated SceneTileModel table for shape 1 on 2026-11-14 (issue 40).
    tile = Tile(0, 0, 1, 1, 0, rotation)
    assert triangles(tile) == [(OVERLAY, *points) for points in DRAW_TILE_UNDERLAY]


def test_a_tile_with_an_overlay_byte_of_0_has_no_overlay_whatever_its_shape():
    # `class24.java` line 188 reads the overlay id. When it is 0, lines 238 to 239 take the path of a tile with no
    # overlay.
    tile = Tile(0, 0, 1, 0, 5, 2)
    assert triangles(tile) == [(UNDERLAY, *points) for points in DRAW_TILE_UNDERLAY]
