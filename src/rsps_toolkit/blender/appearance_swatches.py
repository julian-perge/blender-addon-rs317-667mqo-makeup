"""Square swatch icons for the colour dropdowns, in the client's colours at the add-on's Brightness setting."""

import bpy
import bpy.utils.previews

from ..formats.colour import face_colour_to_rgb
from . import preferences

SIZE = 16

_previews = None
# The Brightness setting the stored swatches were drawn at. A different setting draws them again.
_drawn_at: float | None = None


def rgb(colour: int) -> tuple[float, float, float]:
    """The colour as the client draws it at the add-on's Brightness setting, each channel from 0 to 1."""
    red, green, blue = (min(channel, 255) / 255 for channel in face_colour_to_rgb(colour, preferences.brightness()))
    return red, green, blue


def hex_code(colour: int) -> str:
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb(colour))


def icon(colour: int) -> int:
    """The icon id of the swatch for a packed HSL colour."""
    global _previews, _drawn_at
    if _previews is None:
        _previews = bpy.utils.previews.new()
    brightness = preferences.brightness()
    if brightness != _drawn_at:
        _previews.clear()
        _drawn_at = brightness
    key = str(colour)
    swatch = _previews.get(key)
    if swatch is None:
        swatch = _previews.new(key)
        pixels = [*rgb(colour), 1.0] * (SIZE * SIZE)
        swatch.icon_size = (SIZE, SIZE)  # pyrefly: ignore[bad-assignment]
        swatch.icon_pixels_float = pixels  # pyrefly: ignore[bad-assignment]
        swatch.image_size = (SIZE, SIZE)  # pyrefly: ignore[bad-assignment]
        swatch.image_pixels_float = pixels  # pyrefly: ignore[bad-assignment]
    return swatch.icon_id


def unregister() -> None:
    global _previews, _drawn_at
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
    _previews = None
    _drawn_at = None
