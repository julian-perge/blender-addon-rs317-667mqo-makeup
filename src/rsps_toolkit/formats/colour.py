"""The 317 client's conversion from a 16-bit face colour to RGB (docs/research/model-formats.md), and the original
exporter's conversion back."""

import colorsys


def face_colour_to_rgb(colour: int, brightness: float) -> tuple[int, int, int]:
    """Return 8-bit RGB as the client draws the colour.

    Brightness is the client's display setting, from 0.9 (darkest) to 0.6 (brightest), applied as
    channel ** brightness. The client never produces pure black and gives 0, 0, 1 instead.
    """
    hue = (colour >> 10 & 63) / 64 + 0.5 / 64
    saturation = (colour >> 7 & 7) / 8 + 0.5 / 8
    lightness = (colour & 127) / 128

    if lightness < 0.5:
        q = lightness * (1 + saturation)
    else:
        q = lightness + saturation - lightness * saturation
    p = 2 * lightness - q
    channels = [_hue_to_channel(p, q, (hue + offset) % 1.0) for offset in (1 / 3, 0.0, -1 / 3)]

    r, g, b = (int((int(c * 256) / 256) ** brightness * 256) for c in channels)
    if r == g == b == 0:
        return 0, 0, 1
    return r, g, b


def _hue_to_channel(p: float, q: float, t: float) -> float:
    if 6 * t < 1:
        return p + (q - p) * 6 * t
    if 2 * t < 1:
        return q
    if 3 * t < 2:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def original_exporter_colour(red: float, green: float, blue: float) -> int:
    """The face colour the original exporter wrote for a material's RGB from 0 to 1 (rgb_to_rune_hsl in
    dat_exporter.py at commit 547a2aa).

    It treats HSV as the client's hue, saturation and lightness, which was the original exporter's colour conversion
    bug. It is kept only to write faces exactly as the original exporter did (ADR 0008).
    """
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    return (round(hue * 63) << 10) | (round(saturation * 7) << 7) | round(value * 127)
