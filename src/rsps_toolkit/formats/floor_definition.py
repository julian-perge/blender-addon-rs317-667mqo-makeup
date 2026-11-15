"""Decodes underlay and overlay definitions from their raw bytes in the cache. Nothing here imports bpy.

Underlays are config group 1 and overlays are config group 4 of index 2. The rules come from the 2018 Old School client
(`FloorUnderlayDefinition.java` lines 61 to 170 and `Overlay.java` lines 97 to 211), and the tests check them against
RuneLite's UnderlayLoader and OverlayLoader. The client skips an opcode that it does not know. These decoders refuse it,
and they also refuse bytes after the closing opcode 0, so a wrong parse cannot pass without notice.
"""

from dataclasses import dataclass

from ._stream import Reader
from .js5 import Js5Store

CONFIG_INDEX = 2
UNDERLAY_GROUP = 1
OVERLAY_GROUP = 4


@dataclass(frozen=True)
class Underlay:
    """The colour of an underlay as 0xRRGGBB, and the hue, saturation, lightness and hue multiplier that the client
    computes from it (`FloorUnderlayDefinition.java` lines 101 to 170)."""

    colour: int
    hue: int
    saturation: int
    lightness: int
    hue_multiplier: int


@dataclass(frozen=True)
class Overlay:
    """An overlay. The colours are 0xRRGGBB. The texture is -1 for none. The other colour is -1 for none, and then the
    other hue, saturation and lightness are 0.

    `hides_underlay` is the client's `isHidden`, with RuneLite's name. It is True unless opcode 5 clears it. The only use
    of it that is checked is `class24.java` lines 224 to 230: a flat tile gets tile flag 2340 only when its overlay keeps
    the flag. It does not decide whether the overlay is drawn. The overlay that the client does not draw is the one with
    colour 0xFF00FF (`class24.java` lines 252 to 253, and "Hidden overlay" in `GLOSSARY.md`)."""

    colour: int
    texture: int
    hides_underlay: bool
    other_colour: int
    hue: int
    saturation: int
    lightness: int
    other_hue: int
    other_saturation: int
    other_lightness: int


def read_underlays(store: Js5Store) -> dict[int, Underlay]:
    """Every underlay of the cache, by its id, which is its file id in the config group."""
    return {i: decode_underlay(i, data) for i, data in store.files(CONFIG_INDEX, UNDERLAY_GROUP).items()}


def read_overlays(store: Js5Store) -> dict[int, Overlay]:
    """Every overlay of the cache, by its id, which is its file id in the config group."""
    return {i: decode_overlay(i, data) for i, data in store.files(CONFIG_INDEX, OVERLAY_GROUP).items()}


def decode_underlay(underlay_id: int, data: bytes) -> Underlay:
    """Read one underlay. Opcode 1 holds the colour (`FloorUnderlayDefinition.java` lines 88 to 93), which is 0 when no
    opcode sets it (line 52)."""
    reader = Reader(data)
    colour = 0
    while (opcode := reader.u8()) != 0:
        if opcode == 1:
            colour = _u24(reader)
        else:
            raise ValueError(f"Underlay {underlay_id} has unknown opcode {opcode}")
    _check_end(reader, "Underlay", underlay_id)
    hue, saturation, lightness, multiplier = _underlay_hsl(colour)
    return Underlay(colour, hue, saturation, lightness, multiplier)


def decode_overlay(overlay_id: int, data: bytes) -> Overlay:
    """Read one overlay (`Overlay.java` lines 131 to 144). Opcode 8 holds no value. The defaults come from the
    constructor (lines 84 to 89). `post` (lines 97 to 106) computes the hue, saturation and lightness of the colour, and
    of the other colour only when there is one."""
    reader = Reader(data)
    colour, texture, hides_underlay, other_colour = 0, -1, True, -1
    while (opcode := reader.u8()) != 0:
        if opcode == 1:
            colour = _u24(reader)
        elif opcode == 2:
            texture = reader.u8()
        elif opcode == 5:
            hides_underlay = False
        elif opcode == 7:
            other_colour = _u24(reader)
        elif opcode != 8:
            raise ValueError(f"Overlay {overlay_id} has unknown opcode {opcode}")
    _check_end(reader, "Overlay", overlay_id)
    other = _overlay_hsl(other_colour) if other_colour != -1 else (0, 0, 0)
    return Overlay(colour, texture, hides_underlay, other_colour, *_overlay_hsl(colour), *other)


def _hsl(colour: int) -> tuple[float, float, float]:
    """The hue as a fraction of a turn from -1/6 to 5/6, and the saturation and the lightness from 0 to 1, as both
    `setHSL` methods compute them. The hue is negative when red is highest and blue is above green
    (`FloorUnderlayDefinition.java` lines 102 to 144, `Overlay.java` lines 153 to 195)."""
    red = (colour >> 16 & 255) / 256.0
    green = (colour >> 8 & 255) / 256.0
    blue = (colour & 255) / 256.0
    low = min(red, green, blue)
    high = max(red, green, blue)
    hue = saturation = 0.0
    lightness = (high + low) / 2.0
    if low != high:
        if lightness < 0.5:
            saturation = (high - low) / (low + high)
        if lightness >= 0.5:
            saturation = (high - low) / (2.0 - high - low)
        if red == high:
            hue = (green - blue) / (high - low)
        elif green == high:
            hue = 2.0 + (blue - red) / (high - low)
        elif blue == high:
            hue = 4.0 + (red - green) / (high - low)
    return hue / 6.0, saturation, lightness


def _underlay_hsl(colour: int) -> tuple[int, int, int, int]:
    """The hue of an underlay is scaled by its hue multiplier, not by 256 (`FloorUnderlayDefinition.java` lines 145 to
    169). Python's `int` truncates toward zero, as Java's cast does, which matters for a negative hue."""
    hue, saturation, lightness = _hsl(colour)
    if lightness > 0.5:
        multiplier = int(512.0 * (1.0 - lightness) * saturation)
    else:
        multiplier = int(512.0 * lightness * saturation)
    multiplier = max(multiplier, 1)
    return int(hue * multiplier), _clamp(int(saturation * 256.0)), _clamp(int(lightness * 256.0)), multiplier


def _overlay_hsl(colour: int) -> tuple[int, int, int]:
    """The hue of an overlay is scaled by 256, and it is not clamped (`Overlay.java` lines 196 to 209)."""
    hue, saturation, lightness = _hsl(colour)
    return int(hue * 256.0), _clamp(int(256.0 * saturation)), _clamp(int(256.0 * lightness))


def _clamp(value: int) -> int:
    return min(max(value, 0), 255)


def _u24(reader: Reader) -> int:
    return int.from_bytes(reader.take(3))


def _check_end(reader: Reader, kind: str, definition_id: int) -> None:
    if reader.remaining:
        raise ValueError(f"{kind} {definition_id} has {reader.remaining} byte(s) after its closing opcode")
