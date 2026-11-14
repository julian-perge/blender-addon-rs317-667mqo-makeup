import pytest
from js5_builder import REGION_FIXTURES, build_region_cache
from runelite_json import load_overlays, load_underlays

from rsps_toolkit.formats.floor_definition import Overlay
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.region import AREA_SIZE, EMPTY_TILE, LEVELS, Terrain, Tile, load_terrain
from rsps_toolkit.formats.region_colours import HIDDEN, TileColours, blended_underlay, corner_light, tile_colours

FLOORS = REGION_FIXTURES / "floors.json"
UNDERLAYS = load_underlays(FLOORS)
OVERLAYS = load_overlays(FLOORS)

# The expected values of region 48_50 below come from the lines of the 2018 client, run in a scratch Java program that
# is not in the repo: `class24.java` lines 98 to 116 (the corner light), 119 to 216 (the blend), and 238 to 287 (the
# overlay), with `class158.java` lines 81 to 100, `class16.java` lines 165 to 178 and `KeyFocusListener.java` lines 242
# to 263 copied as they are. Its input was RuneLite's reading of the 9 terrains (`terrain-<x>_<y>.txt.gz`) and of the
# floor definitions (`floors.json`), with the 192 tiles of the 9 regions in place of the client's 104-tile scene and every
# loc shadow 0. A line-by-line port of the blend of RuneLite's 2018 `MapImageDumper` (May 2018 tree,
# `MapImageDumper.java` lines 229 to 341), also not in the repo, gave the same blended colour as these lines on all 3,656
# tiles of 48_50 that have an underlay.


@pytest.fixture(scope="module")
def terrain(tmp_path_factory) -> Terrain:
    folder = tmp_path_factory.mktemp("cache")
    build_region_cache(folder)
    return load_terrain(Js5Store(folder), 48, 50)


def flat_terrain(tiles: dict[tuple[int, int], Tile]) -> Terrain:
    """Region 48_50 with height 0 everywhere, no underlay and no overlay, except the tiles given by their region x and y."""
    columns = [[[EMPTY_TILE] * AREA_SIZE for _ in range(AREA_SIZE)] for _ in range(LEVELS)]
    for (x, y), tile in tiles.items():
        columns[0][x + 64][y + 64] = tile
    return Terrain(48, 50, tuple(tuple(tuple(column) for column in level) for level in columns), ())


# Tiles of 48_50 and their blended underlay colours. The blend reads 4 tiles to the west and south and 5 to the east and
# north, so the tiles with an x or y of 3 or less, or of 59 or more, read the underlays of a neighbour region. Tiles
# (5, 5) and (58, 58) are near the edge, but their blend stays inside the region, and (32, 32) is in the middle.
BLENDED = {
    (0, 9): 6803,
    (0, 44): 8855,
    (0, 63): 14108,
    (2, 47): 11036,
    (5, 5): 9876,
    (32, 32): 12962,
    (58, 58): 16159,
    (60, 3): 11927,
    (63, 0): 14106,
    (63, 63): 16158,
}


@pytest.mark.parametrize(("x", "y"), BLENDED)
def test_the_blended_underlay_colour_of_a_tile_equals_the_clients(terrain, x, y):
    assert blended_underlay(terrain, x, y, UNDERLAYS) == BLENDED[(x, y)]


def test_a_tile_with_no_underlay_has_no_blended_colour(terrain):
    # Tile (0, 0) of 48_50 has only an overlay. class24.java lines 198 and 202 leave the colour at -1.
    assert terrain.tile(0, 0, 0).underlay == 0
    assert blended_underlay(terrain, 0, 0, UNDERLAYS) == -1


def test_the_blend_covers_the_tiles_from_4_west_to_5_east_and_from_4_south_to_5_north():
    # class24.java lines 127 to 154 add the column 5 east of x and take away the column 5 west of x, after the columns
    # before x, so the sums at x hold the columns x - 4 to x + 5. Lines 163 to 180 do the same for the rows. Underlay 48
    # is definition 47: hue 27, saturation 214, lightness 62, multiplier 104. Underlay 55 is definition 54: hue 0,
    # saturation 0, lightness 118, multiplier 1 (floors.json).
    inside = {(10, 10): Tile(0, 0, 48, 0, 0, 0), (15, 15): Tile(0, 0, 55, 0, 0, 0), (6, 6): Tile(0, 0, 55, 0, 0, 0)}
    outside = {
        (5, 10): Tile(0, 0, 55, 0, 0, 0),
        (16, 10): Tile(0, 0, 55, 0, 0, 0),
        (10, 5): Tile(0, 0, 55, 0, 0, 0),
        (10, 16): Tile(0, 0, 55, 0, 0, 0),
    }
    terrain = flat_terrain(inside | outside)
    # Tiles (10, 10), (15, 15) and (6, 6) are in the window of (10, 10). Line 203: hue 27 * 256 / 106 = 65. Lines 204
    # and 205: saturation 214 / 3 = 71 and lightness (62 + 118 + 118) / 3 = 99. class158.java line 98:
    # (71 / 32 << 7) + (65 / 4 << 10) + 99 / 2 = 256 + 16384 + 49.
    assert blended_underlay(terrain, 10, 10, UNDERLAYS) == 16689


def test_the_light_at_each_corner_of_a_flat_tile_is_84(terrain):
    # Tiles (3, 3) to (7, 7) of 48_50 have the same height (terrain-48_50.txt.gz), so each corner of tile (5, 5) and
    # the 4 corners next to it have the same height. class24.java lines 107 to 113 give 0 for both
    # height differences, a length of sqrt(65536) = 256, and the light (0 * -50 + 0 * -50 + 256 * -10) / 213 + 96 = -12 + 96,
    # where 213 is (int) sqrt(5100) * 768 >> 8 (lines 100 to 101), and Java's division rounds toward zero.
    assert [corner_light(terrain, x, y) for x, y in ((5, 5), (6, 5), (6, 6), (5, 6))] == [84, 84, 84, 84]


def test_the_light_at_each_corner_of_a_sloped_tile_equals_the_clients(terrain):
    # Tile (30, 10) of 48_50. At its south-west corner, the heights west and east are -96 and -152, and south and north
    # 0 and -176. class24.java lines 107 to 113: differences -56 and -176, length (int) sqrt(99648) = 315, normal
    # (-14336 / 315, 65536 / 315, -45056 / 315) = (-45, 208, -143), and light (2250 + 7150 - 2080) / 213 + 96 = 130.
    assert [corner_light(terrain, x, y) for x, y in ((30, 10), (31, 10), (31, 11), (30, 11))] == [130, 130, 96, 96]


def test_a_loc_shadow_at_a_corner_lowers_the_light_of_that_corner_and_its_4_neighbours(terrain):
    # Tiles (3, 3) to (7, 7) of 48_50 have the same height, so each corner here has the light 84 without shadows. class24.java line 114
    # takes away the shadow at the corner shifted right by 1 (20), the shadows west and south shifted right by 2, and the
    # shadows east and north shifted right by 3. So the corner east of the shadow loses 40 >> 2 = 10 from its west
    # shadow, and the corner west of it loses 40 >> 3 = 5 from its east shadow.
    shadows = {(5, 5): 40}
    assert corner_light(terrain, 5, 5, shadows) == 64
    assert corner_light(terrain, 6, 5, shadows) == 74
    assert corner_light(terrain, 5, 6, shadows) == 74
    assert corner_light(terrain, 4, 5, shadows) == 79
    assert corner_light(terrain, 5, 4, shadows) == 79
    assert corner_light(terrain, 6, 6, shadows) == 84


# The colours of tiles of 48_50 at their corners, in the order south-west, south-east, north-east, north-west.
TILE_COLOURS = {
    # Overlay 6 (definition 5) has texture 1 and no underlay: the underlay part is not drawn (class16.java line 167),
    # and the overlay corners hold the light alone (KeyFocusListener.java lines 245 to 252).
    (0, 0): TileColours((HIDDEN,) * 4, (84, 84, 84, 84), 1),
    # Underlay only, on a slope at the west edge. A tile with no overlay has no overlay colours (spec 35, decision 10).
    (0, 44): TileColours((8851, 8854, 8857, 8853), None, -1),
    # Overlay 10 (definition 9) is a colour over underlay 49.
    (2, 47): TileColours((11025, 11023, 11024, 11023), (24, 21, 23, 21), -1),
    # Overlay 163 (definition 162) has an other colour, which changes only the minimap colour (class24.java 274 to 285).
    (11, 56): TileColours((11027,) * 4, (2457,) * 4, -1),
    # A textured overlay with an underlay. The light of the north-east corner is 149, and the textured overlay clamps it
    # to 126 (KeyFocusListener.java lines 248 to 249).
    (60, 3): TileColours((11919, 11919, 11930, 11924), (84, 84, 126, 112), 1),
    (63, 63): TileColours((16149, 16146, 16146, 16147), None, -1),
}


@pytest.mark.parametrize(("x", "y"), TILE_COLOURS)
def test_the_lit_colours_of_a_tile_equal_the_clients(terrain, x, y):
    assert tile_colours(terrain, x, y, UNDERLAYS, OVERLAYS) == TILE_COLOURS[(x, y)]


def test_a_hidden_overlay_part_is_not_drawn():
    # Overlay 42 is definition 41, with colour 0xFF00FF (floors.json). class24.java lines 252 to 255 give it no texture
    # and the colour -2, which KeyFocusListener.java line 244 turns into 12345678. The underlay is underlay 48 alone, so
    # the blend is its own colour: hue 27 * 256 / 104 = 66, saturation 214, lightness 62, and class158.java line 98 gives
    # (214 / 32 << 7) + (66 / 4 << 10) + 62 / 2 = 17183. The flat light 84 makes class16.java line 169 give
    # 31 * 84 / 128 = 20, and line 176 gives (17183 & 65408) + 20.
    terrain = flat_terrain({(10, 10): Tile(0, 0, 48, 42, 0, 0)})
    assert tile_colours(terrain, 10, 10, UNDERLAYS, OVERLAYS) == TileColours((17172,) * 4, (HIDDEN,) * 4, -1)


def test_an_overlay_with_a_texture_is_textured_even_with_the_hidden_colour():
    # class24.java line 249 checks the texture before line 252 checks the colour 0xFF00FF, so the texture wins, and
    # KeyFocusListener.java lines 245 to 252 give the flat light 84 alone. No overlay of floors.json has both, so this
    # one is made for the test.
    overlay = Overlay(0xFF00FF, 1, True, -1, 0, 0, 0, 0, 0, 0)
    terrain = flat_terrain({(10, 10): Tile(0, 0, 0, 1, 0, 0)})
    assert tile_colours(terrain, 10, 10, UNDERLAYS, {0: overlay}) == TileColours((HIDDEN,) * 4, (84,) * 4, 1)


@pytest.mark.parametrize(
    ("lightness", "expected"),
    [
        # class158.java lines 81 to 98, for hue 40 and saturation 255. The hue gives 40 / 4 << 10 = 10240.
        # Lightness 179 does not halve the saturation (line 82 needs more than 179): 255 / 32 << 7 = 896.
        # Then class16.java line 169 gives the flat light 84 as (179 / 2) * 84 / 128 = 58.
        (179, 10240 + 896 + 58),
        # Lightness 180 halves it once (line 82): 127 / 32 << 7 = 384, and 90 * 84 / 128 = 59.
        (180, 10240 + 384 + 59),
        # Lightness 193 halves it twice (lines 82 and 86): 63 / 32 << 7 = 128, and 96 * 84 / 128 = 63.
        (193, 10240 + 128 + 63),
        # Lightness 218 halves it three times (lines 82, 86 and 90): 31 / 32 = 0, and 109 * 84 / 128 = 71.
        (218, 10240 + 71),
    ],
)
def test_a_light_overlay_colour_has_its_saturation_halved_at_each_lightness_step(lightness, expected):
    # A fourth halving above lightness 243 (line 94) cannot change the colour, because a saturation of at most 255
    # is already below 32 after three. No overlay that 48_50 uses is lighter than 179, so these are made for the test.
    overlay = Overlay(0, -1, True, -1, 40, 255, lightness, 0, 0, 0)
    terrain = flat_terrain({(10, 10): Tile(0, 0, 0, 1, 0, 0)})
    assert tile_colours(terrain, 10, 10, UNDERLAYS, {0: overlay}) == TileColours((HIDDEN,) * 4, (expected,) * 4, -1)


def test_a_lit_colour_brighter_than_126_is_clamped_to_126():
    # The heights fall by 64 for each step east or north, so at each corner of tile (10, 10) class24.java lines 107 to
    # 113 give differences -128 and -128, length (int) sqrt(98304) = 313, normal (-32768 / 313, 65536 / 313,
    # -32768 / 313) = (-104, 209, -104), and light (5200 + 5200 - 2090) / 213 + 96 = 135. The overlay has hue 40,
    # saturation 255 and lightness 250, which class158.java lines 81 to 98 pack as 10240 + 0 + 125. class16.java line
    # 169 gives 125 * 135 / 128 = 131, and lines 172 to 173 lower it to 126.
    tiles = {(x, y): Tile(-64 * (x + y), 0, 0, 0, 0, 0) for x in range(9, 13) for y in range(9, 13)}
    tiles[(10, 10)] = Tile(-64 * 20, 0, 0, 1, 0, 0)
    overlay = Overlay(0, -1, True, -1, 40, 255, 250, 0, 0, 0)
    terrain = flat_terrain(tiles)
    assert [corner_light(terrain, x, y) for x, y in ((10, 10), (11, 10), (11, 11), (10, 11))] == [135] * 4
    colours = tile_colours(terrain, 10, 10, UNDERLAYS, {0: overlay})
    assert colours == TileColours((HIDDEN,) * 4, (10240 + 126,) * 4, -1)


def test_a_tile_with_no_underlay_and_no_overlay_has_no_colours():
    # class24.java line 189 does not call addTile for it.
    terrain = flat_terrain({(10, 11): Tile(0, 0, 48, 0, 0, 0)})
    assert tile_colours(terrain, 10, 10, UNDERLAYS, OVERLAYS) is None


def test_a_shadow_lowers_the_lit_colour_of_a_tile(terrain):
    # Tile (4, 4) of 48_50 has the blended colour 8851 and texture 1. A shadow of 40 at corner (5, 5) gives its
    # north-east corner the light 64 (as in the shadow test above), and its south-east and north-west corners 79.
    # class16.java line 169: (8851 & 127) = 19, so 19 * 84 / 128 = 12, 19 * 79 / 128 = 11 and 19 * 64 / 128 = 9, added to
    # 8851 & 65408 = 8832.
    colours = tile_colours(terrain, 4, 4, UNDERLAYS, OVERLAYS, {(5, 5): 40})
    assert colours == TileColours((8844, 8843, 8841, 8843), (84, 79, 64, 79), 1)


def test_a_heavy_shadow_makes_the_light_negative_and_the_lit_colours_clamp_it_to_2(terrain):
    # Tile (4, 4) of 48_50, with the shadow 127 at corner (5, 5) and at the 4 corners next to it. class24.java line 114
    # gives corner (5, 5) the darkness 63 + 31 + 31 + 15 + 15 = 155, so its light is 84 - 155 = -71. Corners (5, 4) and
    # (4, 5) lose 63 + 15 = 78 and get 6, and corner (4, 4) loses 15 + 15 and gets 54. class16.java line 169 gives
    # 19 * 54 / 128 = 8, 19 * 6 / 128 = 0 and 19 * -71 / 128 = -10, and lines 170 to 171 raise the last two to 2.
    # KeyFocusListener.java lines 246 to 247 raise the light -71 of the textured overlay to 2.
    shadows = {(5, 5): 127, (4, 5): 127, (5, 4): 127, (6, 5): 127, (5, 6): 127}
    assert corner_light(terrain, 5, 5, shadows) == -71
    colours = tile_colours(terrain, 4, 4, UNDERLAYS, OVERLAYS, shadows)
    assert colours == TileColours((8840, 8834, 8834, 8834), (54, 6, 2, 6), 1)
