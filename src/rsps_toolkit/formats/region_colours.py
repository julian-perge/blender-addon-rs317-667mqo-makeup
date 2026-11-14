"""The lit colours at the corners of a level 0 terrain tile, as the 2018 client gives them to `Region.addTile` in
`class24.method457` (`class24.java` lines 98 to 287). Nothing here imports bpy.

A colour is a 16-bit HSL face colour, the same kind that a model face holds, after the light of the corner has replaced
its lightness. `face_colour_to_rgb` shows it at the Brightness preference. The colour `HIDDEN` marks a part that the
client does not draw.

The tiles and corners are counted from the south-west corner of the terrain's region, as `Terrain.tile` counts them.
The client works on its 104-tile scene, and cuts the blend short at the scene's edge. Here the 9 regions of the terrain
take the place of the scene, so the blend of a tile at the region's edge reads the underlays of the neighbour region
(ADR 0023, Edges). The blend reads 4 tiles to the west and south of a tile and 5 to the east and north, and the light
reads 1 corner further, so every tile of the region has what they read.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isqrt

from .floor_definition import Overlay, Underlay
from .region import Terrain

HIDDEN = 12345678
"""The colour of a part that the client does not draw (`class16.java` line 167, `KeyFocusListener.java` line 244)."""

HIDDEN_OVERLAY_COLOUR = 0xFF00FF

NO_SHADOWS: Mapping[tuple[int, int], int] = {}

LIGHT_SCALE = isqrt(5100) * 768 >> 8
"""The client divides the light by this number, 213 (`class24.java` lines 100 to 101)."""

BLEND_BEHIND = 4
BLEND_AHEAD = 5

_CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))


@dataclass(frozen=True)
class TileColours:
    """The lit colours of one tile at its corners, in the order south-west, south-east, north-east, north-west, which is
    the order of `region_shapes.Corner`."""

    underlay: tuple[int, int, int, int]
    """`HIDDEN` at every corner when the tile has no underlay."""
    overlay: tuple[int, int, int, int] | None
    """None when the tile has no overlay, so it has no overlay part (spec 35, decision 10). `HIDDEN` at every corner for a
    hidden overlay. For a textured overlay, each corner holds the light alone, from 2 to 126, which shades the
    texture."""
    texture: int
    """The texture of the overlay, or -1 for none."""


def corner_light(terrain: Terrain, x: int, y: int, shadows: Mapping[tuple[int, int], int] = NO_SHADOWS) -> int:
    """The terrain light at corner (x, y) of level 0 (`class24.java` lines 107 to 115). It comes from the slope between the
    heights of the 4 corners next to it, less the loc shadows near it: half the shadow at the corner, a quarter of the
    shadows at the corners west and south of it, and an eighth of the shadows at the corners east and north of it. The
    light is not clamped here, so a heavy shadow can make it negative. `shadows` gives the loc shadow at a corner by its
    x and y, and a corner that it leaves out has the shadow 0."""

    def height(corner_x: int, corner_y: int) -> int:
        return terrain.tile(0, corner_x, corner_y).height

    def shadow(corner_x: int, corner_y: int) -> int:
        return shadows.get((corner_x, corner_y), 0)

    slope_x = height(x + 1, y) - height(x - 1, y)
    slope_y = height(x, y + 1) - height(x, y - 1)
    length = isqrt(slope_x * slope_x + slope_y * slope_y + 65536)
    normal_x = _div(slope_x << 8, length)
    normal_up = _div(65536, length)
    normal_y = _div(slope_y << 8, length)
    light = _div(normal_x * -50 + normal_y * -50 + normal_up * -10, LIGHT_SCALE) + 96
    darkness = (
        (shadow(x - 1, y) >> 2)
        + (shadow(x, y - 1) >> 2)
        + (shadow(x + 1, y) >> 3)
        + (shadow(x, y + 1) >> 3)
        + (shadow(x, y) >> 1)
    )
    return light - darkness


def blended_underlay(terrain: Terrain, x: int, y: int, underlays: Mapping[int, Underlay]) -> int:
    """The underlay colour of tile (x, y) of level 0 before the light, or -1 when the tile has no underlay
    (`class24.java` lines 198 and 202 to 206). `underlays` holds the underlay definitions by id.

    The client keeps running sums over columns and then rows (lines 127 to 180). At tile x they hold the columns x - 4 to
    x + 5, because the column x + 5 is added before the column x - 5 is taken away, and the same holds for the rows. So
    the blend covers 10 by 10 tiles, not 11 by 11. Only tiles with an underlay count. The hue is the sum of the hues,
    times 256, over the sum of the hue multipliers (line 203). The saturation and lightness are the means (lines 204 to
    205).
    """
    if terrain.tile(0, x, y).underlay == 0:
        return -1
    hue = saturation = lightness = multiplier = count = 0
    for tile_x in range(x - BLEND_BEHIND, x + BLEND_AHEAD + 1):
        for tile_y in range(y - BLEND_BEHIND, y + BLEND_AHEAD + 1):
            underlay_id = terrain.tile(0, tile_x, tile_y).underlay
            if underlay_id == 0:
                continue
            underlay = underlays[underlay_id - 1]
            hue += underlay.hue
            saturation += underlay.saturation
            lightness += underlay.lightness
            multiplier += underlay.hue_multiplier
            count += 1
    return _pack_hsl(_div(hue * 256, multiplier), _div(saturation, count), _div(lightness, count))


def tile_colours(
    terrain: Terrain,
    x: int,
    y: int,
    underlays: Mapping[int, Underlay],
    overlays: Mapping[int, Overlay],
    shadows: Mapping[tuple[int, int], int] = NO_SHADOWS,
) -> TileColours | None:
    """The lit colours of tile (x, y) of level 0, or None for a tile with no underlay and no overlay, which has no faces
    (`class24.java` line 189). `underlays` and `overlays` hold the floor definitions by id, and `shadows` is as
    `corner_light` takes it.

    The underlay colour takes the light of each corner as its lightness (`class16.java` lines 165 to 178). A tile with no
    overlay has no overlay colours. The client gives `addTile` the overlay colours 0 there (line 239), but `addTile` reads
    only the underlay colours for it (`Region.java` lines 324 to 325). An overlay
    with a texture gives the light alone (`class24.java` lines 249 to 251, `KeyFocusListener.java` lines 245 to 252). An
    overlay with the colour 0xFF00FF is not drawn (lines 252 to 255). Any other overlay colour takes the light as the
    underlay colour does (lines 257 and 287). The other colour of an overlay and the random hue and lightness offsets
    change only the minimap colour (lines 207 to 215, 258 to 266 and 274 to 285), so they are not used here.
    """
    tile = terrain.tile(0, x, y)
    if tile.underlay == 0 and tile.overlay == 0:
        return None
    lights = [corner_light(terrain, x + dx, y + dy, shadows) for dx, dy in _CORNERS]
    blended = blended_underlay(terrain, x, y, underlays)
    underlay = _lit(blended, lights)
    if tile.overlay == 0:
        return TileColours(underlay, None, -1)
    overlay = overlays[tile.overlay - 1]
    if overlay.texture >= 0:
        return TileColours(underlay, _lit_texture(lights), overlay.texture)
    if overlay.colour == HIDDEN_OVERLAY_COLOUR:
        return TileColours(underlay, (HIDDEN,) * 4, -1)
    return TileColours(underlay, _lit(_pack_hsl(overlay.hue, overlay.saturation, overlay.lightness), lights), -1)


def _lit(colour: int, lights: list[int]) -> tuple[int, int, int, int]:
    """`class16.method185` (`class16.java` lines 165 to 178) at each corner. For a colour that is not -1 or -2, it is the
    same as `KeyFocusListener.adjustHSLListness0` (`KeyFocusListener.java` lines 254 to 261)."""
    if colour == -1:
        return (HIDDEN,) * 4
    a, b, c, d = ((colour & 65408) + _clamp_lightness(_div((colour & 127) * light, 128)) for light in lights)
    return a, b, c, d


def _lit_texture(lights: list[int]) -> tuple[int, int, int, int]:
    """`KeyFocusListener.adjustHSLListness0` for the colour -1 (`KeyFocusListener.java` lines 245 to 252)."""
    a, b, c, d = (_clamp_lightness(light) for light in lights)
    return a, b, c, d


def _clamp_lightness(lightness: int) -> int:
    return min(max(lightness, 2), 126)


def _pack_hsl(hue: int, saturation: int, lightness: int) -> int:
    """`class158.method3315` (`class158.java` lines 81 to 100). The saturation halves at each lightness step. The hue is
    not masked, so a negative hue gives a negative colour, as in the client."""
    for step in (179, 192, 217, 243):
        if lightness > step:
            saturation = _div(saturation, 2)
    return (_div(saturation, 32) << 7) + (_div(hue, 4) << 10) + _div(lightness, 2)


def _div(numerator: int, denominator: int) -> int:
    """Java's division of whole numbers, which rounds toward zero."""
    quotient = abs(numerator) // abs(denominator)
    return quotient if (numerator < 0) == (denominator < 0) else -quotient
