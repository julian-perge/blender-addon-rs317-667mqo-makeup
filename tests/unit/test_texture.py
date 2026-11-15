import gzip

import pytest
from js5_builder import REGION_FIXTURES, build_region_cache

from rsps_toolkit.formats.js5 import Js5Store, NotInCacheError
from rsps_toolkit.formats.sprite import Sprite, decode_sprites
from rsps_toolkit.formats.texture import TextureDefinition, decode_texture, read_textures, texture_pixels

BRIGHTNESS = (0.9, 0.8, 0.7, 0.6)


def reference() -> tuple[dict[int, bool], dict[tuple[int, float], tuple[int, ...]]]:
    """RuneLite's reading of the textures, written by `tests/fixtures/TextureReference.java`: the opaque flag of each
    texture, and its 128 by 128 pixels at each brightness, row by row from the top."""
    lines = iter(gzip.decompress((REGION_FIXTURES / "textures.txt.gz").read_bytes()).decode().splitlines())
    opaque: dict[int, bool] = {}
    pixels: dict[tuple[int, float], tuple[int, ...]] = {}
    for header in lines:
        _, texture, _, flag = header.split()
        opaque[int(texture)] = flag == "true"
        for _ in BRIGHTNESS:
            _, brightness = next(lines).split()
            rows = [next(lines) for _ in range(128)]
            pixels[int(texture), float(brightness)] = tuple(int(pixel, 16) for row in rows for pixel in row.split())
    return opaque, pixels


def test_every_texture_of_snapshot_430_at_each_brightness_equals_runelites_texture_definition():
    sprites = {
        int(path.stem): decode_sprites(int(path.stem), path.read_bytes())
        for path in (REGION_FIXTURES / "sprites").glob("*.dat")
    }
    textures = {
        int(path.stem): decode_texture(int(path.stem), path.read_bytes())
        for path in (REGION_FIXTURES / "textures").glob("*.dat")
    }
    opaque, expected = reference()
    assert len(textures) == 59
    assert {texture_id: texture.opaque for texture_id, texture in textures.items()} == opaque
    assert expected.keys() == {(texture_id, brightness) for texture_id in textures for brightness in BRIGHTNESS}
    for (texture_id, brightness), pixels in expected.items():
        assert texture_pixels(textures[texture_id], sprites, brightness) == pixels, (texture_id, brightness)


def test_the_cache_reader_gives_each_texture_with_the_sprite_groups_it_names(tmp_path):
    build_region_cache(tmp_path, definitions=True)

    textures = read_textures(Js5Store(tmp_path), [1, 3])

    opaque, expected = reference()
    assert set(textures) == {1, 3}
    for texture_id, (texture, sprites) in textures.items():
        assert texture.opaque == opaque[texture_id]
        assert texture_pixels(texture, sprites, 0.8) == expected[texture_id, 0.8]


def test_the_cache_reader_refuses_a_texture_that_index_9_lacks(tmp_path):
    # The owner chose on 2026-11-14 that a texture id that index 9 lacks stops the import (issue 47, Decisions).
    build_region_cache(tmp_path, definitions=True, textures_left_out=(3,))

    with pytest.raises(NotInCacheError, match="Group 0 of index 9 of the cache has no texture 3"):
        read_textures(Js5Store(tmp_path), [1, 3])


# Every texture of snapshot 430 has one sprite and colour 0, so the tests below build their textures. They use
# brightness 1.0, which the client never uses: it starts at 0.8 (`GameCanvas.java` line 445), and its settings go from
# 0.9 to 0.6. At 1.0, `Graphics3D.adjustRGB` (lines 246 to 257) keeps each channel, because (c / 256) ** 1 * 256 is c,
# so each expected pixel is a palette colour.


def plain(colour: int, width: int = 128) -> tuple[Sprite, ...]:
    """A group of one frame that fills its square canvas and has palette index 1 at every pixel."""
    return (Sprite(width, width, 0, 0, width, width, (0, colour), bytes([1]) * (width * width)),)


def test_a_colour_with_top_byte_3_tints_only_the_grey_palette_entries():
    # Texture.java lines 114 to 125. Grey 0x80 with colour 0x03FF8040: red and blue (0xFF0040 * 0x80 >> 8) & 0xFF00FF
    # is 0x7F0020, and green (0x80 * 0x80) & 0xFF00 is 0x4000.
    grey = Sprite(128, 128, 0, 0, 128, 128, (0, 0x808080, 0x102030), bytes([1, 2]) * 8192)
    texture = TextureDefinition(sprites=(5,), operations=(), colours=(0x03FF8040,), opaque=True)
    assert texture_pixels(texture, {5: (grey,)}, 1.0) == (0x7F4020, 0x102030) * 8192


def test_a_later_sprite_replaces_the_pixels_only_with_operation_0():
    # Texture.java lines 131 to 175: operation 0 writes every pixel again, and operations 1 to 3 write nothing.
    sprites = {5: plain(0x111111), 6: plain(0x222222)}
    replaced = TextureDefinition(sprites=(5, 6), operations=(0,), colours=(0, 0), opaque=True)
    kept = TextureDefinition(sprites=(5, 6), operations=(1,), colours=(0, 0), opaque=True)
    assert texture_pixels(replaced, sprites, 1.0) == (0x222222,) * 16384
    assert texture_pixels(kept, sprites, 1.0) == (0x111111,) * 16384


def test_a_later_sprite_is_placed_on_its_canvas_even_when_its_operation_writes_nothing():
    # Texture.java lines 97 and 98 place every sprite on its canvas before line 137 reads the operation, so a frame
    # that reaches past the end of its canvas throws for each operation.
    broken = (Sprite(3, 2, 2, 1, 2, 1, (0, 1), bytes([1, 1])),)
    texture = TextureDefinition(sprites=(5, 6), operations=(1,), colours=(0, 0), opaque=True)
    with pytest.raises(ValueError, match="past the end of its canvas"):
        texture_pixels(texture, {5: plain(0x111111), 6: broken}, 1.0)


@pytest.mark.parametrize("sprites", [{}, {5: ()}], ids=["missing", "empty"])
def test_a_missing_or_empty_sprite_group_is_refused(sprites):
    # The client draws such a texture in its average colour (Graphics3D.java lines 2473 to 2476). The owner chose to
    # refuse it on 2026-11-14 (issue 39, Decisions).
    texture = TextureDefinition(sprites=(5,), operations=(), colours=(0,), opaque=True)
    with pytest.raises(ValueError, match="Sprite group 5 is missing or has no frames"):
        texture_pixels(texture, sprites, 1.0)


def test_a_sprite_neither_64_nor_128_wide_is_refused():
    # Texture.java lines 151 to 153 throw.
    texture = TextureDefinition(sprites=(5,), operations=(), colours=(0,), opaque=True)
    with pytest.raises(ValueError, match="32 pixels wide"):
        texture_pixels(texture, {5: plain(0x111111, width=32)}, 1.0)


@pytest.mark.parametrize("count", [0, 5])
def test_a_sprite_count_outside_1_to_4_is_refused(count):
    # Texture.java lines 43 and 76 to 77.
    with pytest.raises(ValueError, match=f"{count} sprites"):
        decode_texture(1, bytes([0, 0, 1, count]) + bytes(64))


def test_bytes_after_the_definition_are_refused():
    # One sprite: average colour, flag, count, sprite id, colour, animation direction and speed (lines 40 to 74).
    data = bytes([0, 0, 1, 1, 0, 7, 0, 0, 0, 0, 0, 0])
    assert decode_texture(1, data) == TextureDefinition(sprites=(7,), operations=(), colours=(0,), opaque=True)
    with pytest.raises(ValueError, match="1 byte"):
        decode_texture(1, data + bytes(1))


def test_only_flag_1_makes_a_texture_opaque():
    # Texture.java line 41.
    data = bytes([0, 0, 2, 1, 0, 7, 0, 0, 0, 0, 0, 0])
    assert not decode_texture(1, data).opaque
