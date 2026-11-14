"""Decodes the sprite groups of cache index 8. Nothing here imports bpy.

A sprite group holds one or more frames that share one palette and one canvas size. The layout comes from the 2018 Old
School client (`class171.java` lines 314 to 379, `decodeSprite`). The texture tests check it through RuneLite's
SpriteLoader, which reads the same layout.
"""

from dataclasses import dataclass

from ._stream import Reader


@dataclass(frozen=True)
class Sprite:
    """One frame of a sprite group. It is `width` by `height` pixels at (`offset_x`, `offset_y`) on a canvas of
    `canvas_width` by `canvas_height` pixels.

    `pixels` holds one palette index for each pixel of the frame, row by row from the top. The palette holds 0xRRGGBB
    colours. Its entry 0 is 0, because the group stores no colour for it, and a stored colour of 0 becomes 1
    (`class171.java` lines 347 to 354)."""

    canvas_width: int
    canvas_height: int
    offset_x: int
    offset_y: int
    width: int
    height: int
    palette: tuple[int, ...]
    pixels: bytes


def decode_sprites(group_id: int, data: bytes) -> tuple[Sprite, ...]:
    """Read every frame of one sprite group.

    The group ends with the frame count. In front of it are the canvas size, the palette size less 1, and the x
    offsets, y offsets, widths and heights of all frames, and in front of those the palette (lines 317 to 354). The
    pixels of the frames start at byte 0, one frame after the other. Each frame starts with a flag: 0 stores its pixels
    row by row and 1 column by column (lines 358 to 376). The client reads no pixels for any other flag. This decoder
    refuses another flag, which the owner chose on 2026-11-14 (issue 39, Decisions).

    The decoder refuses a group that is too short for its footer or its palette, where the client throws because it
    reads from before byte 0. It also refuses bytes between the pixels of the last frame and the palette, so a wrong
    parse cannot pass without notice."""
    count = Reader(data, len(data) - 2).u16()
    footer_start = len(data) - 7 - count * 8
    if footer_start < 0:
        raise ValueError(f"Sprite group {group_id} is too short for its footer of {count} frames")
    footer = Reader(data, footer_start)
    canvas_width, canvas_height = footer.u16(), footer.u16()
    palette_size = footer.u8() + 1
    offsets_x = [footer.u16() for _ in range(count)]
    offsets_y = [footer.u16() for _ in range(count)]
    widths = [footer.u16() for _ in range(count)]
    heights = [footer.u16() for _ in range(count)]
    palette_start = footer_start - (palette_size - 1) * 3
    if palette_start < 0:
        raise ValueError(f"Sprite group {group_id} is too short for its palette of {palette_size - 1} stored colours")
    colours = Reader(data, palette_start)
    palette = (0, *(int.from_bytes(colours.take(3)) or 1 for _ in range(palette_size - 1)))
    reader = Reader(data[:palette_start])
    frames = []
    for frame, (offset_x, offset_y, width, height) in enumerate(
        zip(offsets_x, offsets_y, widths, heights, strict=True)
    ):
        flag = reader.u8()
        if flag not in (0, 1):
            raise ValueError(f"Frame {frame} of sprite group {group_id} has flag {flag}; the client reads only 0 and 1")
        stored = reader.take(width * height)
        pixels = stored if flag == 0 else b"".join(stored[y::height] for y in range(height))
        frames.append(Sprite(canvas_width, canvas_height, offset_x, offset_y, width, height, palette, pixels))
    if reader.remaining:
        raise ValueError(f"Sprite group {group_id} has {reader.remaining} byte(s) between its pixels and its palette")
    return tuple(frames)


def canvas_pixels(sprite: Sprite) -> bytes:
    """The palette indices of the whole canvas, row by row from the top, with index 0 around the frame, as
    `IndexedSprite.normalize` makes them (`IndexedSprite.java` lines 35 to 52). A frame that reaches past the end of
    the canvas is refused, where the client throws. A frame of width 0 writes no pixel, so it is never refused."""
    if (sprite.width, sprite.height) == (sprite.canvas_width, sprite.canvas_height):
        return sprite.pixels
    canvas = bytearray(sprite.canvas_width * sprite.canvas_height)
    for y in range(sprite.height):
        start = (y + sprite.offset_y) * sprite.canvas_width + sprite.offset_x
        if sprite.width and start + sprite.width > len(canvas):
            raise ValueError("A sprite frame reaches past the end of its canvas")
        canvas[start : start + sprite.width] = sprite.pixels[y * sprite.width : (y + 1) * sprite.width]
    return bytes(canvas)
