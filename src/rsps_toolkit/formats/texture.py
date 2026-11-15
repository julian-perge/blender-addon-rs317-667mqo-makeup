"""Decodes the texture definitions of cache index 9 and makes the pixels of a texture. Nothing here imports bpy.

Group 0 of index 9 holds one file for each texture, and the file id is the texture id (`TextureProvider.java` lines 64
to 71). The rules come from the 2018 Old School client (`Texture.java` lines 38 to 79 and 85 to 179), and the tests
check them against RuneLite's TextureDefinition and SpriteLoader. Snapshot 430 stores the layout from before revision
233, which RuneLite reads with `setRev233(false)`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from ._stream import Reader
from .js5 import Js5Store, NotInCacheError
from .sprite import Sprite, canvas_pixels, decode_sprites

SPRITE_INDEX = 8
TEXTURE_INDEX = 9
TEXTURE_GROUP = 0

SIZE = 128
"""The width and height of the pixels of a texture. The client makes them at 64 in low memory mode and at 128 otherwise
(`GameCanvas.java` line 445), and it only ever sets low memory mode to false (`Client.java` line 1214,
`AbstractSoundSystem.java` line 503)."""


@dataclass(frozen=True)
class TextureDefinition:
    """The parts of a texture definition that its pixels and its drawing use.

    `sprites` are the ids of its sprite groups in index 8, 1 to 4 of them. `operations` has one entry for each sprite
    after the first, and only operation 0 writes pixels (`Texture.java` lines 131 to 175). `colours` has one entry for
    each sprite, as an unsigned 32-bit number. A colour whose top byte is 3 tints the grey entries of that sprite's
    palette (lines 114 to 125).

    `opaque` is True when the client draws the pixels of colour 0 as black. When it is False, the client leaves those
    pixels out, so they are transparent (`Graphics3D.java` lines 2116 and 2182)."""

    sprites: tuple[int, ...]
    operations: tuple[int, ...]
    colours: tuple[int, ...]
    opaque: bool


def read_textures(
    store: Js5Store, texture_ids: Iterable[int]
) -> dict[int, tuple[TextureDefinition, dict[int, tuple[Sprite, ...]]]]:
    """The texture definitions of the cache with these ids, each with the decoded sprite groups of index 8 that it
    names, by id. A texture id that the cache lacks is an error, which the owner chose on 2026-11-14 (issue 47,
    Decisions)."""
    files = store.files(TEXTURE_INDEX, TEXTURE_GROUP)
    textures = {}
    for texture_id in texture_ids:
        if texture_id not in files:
            raise NotInCacheError(
                f"Group {TEXTURE_GROUP} of index {TEXTURE_INDEX} of the cache has no texture {texture_id}"
            )
        texture = decode_texture(texture_id, files[texture_id])
        sprites = {
            sprite_id: decode_sprites(sprite_id, store.container(SPRITE_INDEX, sprite_id))
            for sprite_id in texture.sprites
        }
        textures[texture_id] = (texture, sprites)
    return textures


def decode_texture(texture_id: int, data: bytes) -> TextureDefinition:
    """Read one texture definition (`Texture.java` lines 38 to 79). The client throws on a sprite count outside 1 to 4,
    and this decoder refuses it. The decoder also refuses bytes after the definition, so a wrong parse cannot pass
    without notice. Only flag 1 makes a texture opaque (line 41). RuneLite reads any flag other than 0 as opaque, and
    the two readings agree on every texture of snapshot 430.

    The definition also stores an average colour, a second list of operations that the client never reads again, and
    the direction and speed of an animated texture. They are read and not kept. The client uses the average colour in
    low memory mode (`Region.java` lines 1862, 1885 and 1964), for a texture whose sprites are not loaded
    (`Graphics3D.java` lines 1430 to 1433 and 2473 to 2476), and for the minimap colour of a textured overlay
    (`class24.java` line 250). Here a missing sprite group is refused (issue 39, Decisions), and nothing here draws a
    minimap or animates a texture."""
    reader = Reader(data)
    reader.u16()
    opaque = reader.u8() == 1
    count = reader.u8()
    if not 1 <= count <= 4:
        raise ValueError(f"Texture {texture_id} has {count} sprites; the client reads 1 to 4")
    sprites = tuple(reader.u16() for _ in range(count))
    operations = tuple(reader.u8() for _ in range(count - 1))
    reader.take(count - 1)
    colours = tuple(int.from_bytes(reader.take(4)) for _ in range(count))
    reader.take(2)
    if reader.remaining:
        raise ValueError(f"Texture {texture_id} has {reader.remaining} byte(s) after its definition")
    return TextureDefinition(sprites, operations, colours, opaque)


def texture_pixels(
    texture: TextureDefinition, sprites: Mapping[int, tuple[Sprite, ...]], brightness: float
) -> tuple[int, ...]:
    """The SIZE by SIZE pixels of a texture as 0xRRGGBB colours, row by row from the top, at a brightness setting
    (0.9, 0.8, 0.7 or 0.6), as `Texture.method2706` makes them (`Texture.java` lines 85 to 179).

    `sprites` holds the decoded sprite groups of index 8 by id. The client uses frame 0 of each group (`Sequence.java`
    line 381, `class224.java` lines 107 to 116). A sprite canvas must be SIZE or 64 pixels wide, and the client doubles
    each pixel of a canvas that is 64 wide (lines 137 to 162).

    A sprite group that is missing from `sprites`, or that has no frames, is refused, which the owner chose on
    2026-11-14 (issue 39, Decisions). The client draws such a texture in its average colour."""
    pixels: list[int] = [0] * (SIZE * SIZE)
    for position, sprite_id in enumerate(texture.sprites):
        frames = sprites.get(sprite_id)
        if not frames:
            raise ValueError(f"Sprite group {sprite_id} is missing or has no frames")
        sprite = frames[0]
        indices = canvas_pixels(sprite)
        if position > 0 and texture.operations[position - 1] != 0:
            continue
        palette = [_adjust_rgb(colour, brightness) for colour in _tint(sprite.palette, texture.colours[position])]
        if sprite.canvas_width == SIZE:
            pixels = [palette[indices[i]] for i in range(SIZE * SIZE)]
        elif sprite.canvas_width == 64:
            pixels = [
                palette[indices[(row >> 1 << 6) + (column >> 1)]] for row in range(SIZE) for column in range(SIZE)
            ]
        else:
            raise ValueError(f"Sprite {sprite_id} is {sprite.canvas_width} pixels wide; a texture needs 64 or {SIZE}")
    return tuple(pixels)


def _tint(palette: tuple[int, ...], colour: int) -> tuple[int, ...]:
    """Lines 114 to 125: a colour whose top byte is 3 scales each grey palette entry (equal red, green and blue) by its
    red, green and blue."""
    if colour & 0xFF000000 != 0x03000000:
        return palette
    red_blue = colour & 0xFF00FF
    green = colour >> 8 & 0xFF
    tinted = []
    for entry in palette:
        if entry >> 8 == entry & 0xFFFF:
            grey = entry & 0xFF
            entry = ((red_blue * grey) >> 8) & 0xFF00FF | (green * grey) & 0xFF00
        tinted.append(entry)
    return tuple(tinted)


def _adjust_rgb(colour: int, brightness: float) -> int:
    """`Graphics3D.adjustRGB` (`Graphics3D.java` lines 246 to 257): each channel becomes `(c / 256) ** brightness * 256`,
    cut to a whole number."""
    red = int(((colour >> 16) / 256.0) ** brightness * 256.0)
    green = int(((colour >> 8 & 0xFF) / 256.0) ** brightness * 256.0)
    blue = int(((colour & 0xFF) / 256.0) ** brightness * 256.0)
    return blue + (green << 8) + (red << 16)
