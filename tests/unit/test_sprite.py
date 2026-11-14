import pytest

from rsps_toolkit.formats.sprite import Sprite, canvas_pixels, decode_sprites


def two_frames() -> bytes:
    """A group of two frames on a 3 by 3 canvas, laid out as `class171.java` lines 314 to 379 read it."""
    return b"".join(
        [
            bytes([0, 1, 2]),  # Frame 0 has flag 0, so its 2 by 1 pixels are stored row by row.
            bytes([1, 1, 2, 3, 1]),  # Frame 1 has flag 1, so its 2 by 2 pixels are stored column by column.
            bytes([0x10, 0x20, 0x30, 0, 0, 0, 0xFF, 0xFF, 0xFF]),  # The palette stores its entries 1 to 3.
            bytes([0, 3, 0, 3, 3]),  # The canvas is 3 by 3 pixels, and the palette has 3 + 1 entries.
            bytes([0, 0, 0, 1, 0, 0, 0, 1]),  # Frame 0 is at x 0 and y 0, and frame 1 is at x 1 and y 1.
            bytes([0, 2, 0, 2, 0, 1, 0, 2]),  # Frame 0 is 2 by 1 pixels, and frame 1 is 2 by 2 pixels.
            bytes([0, 2]),  # The group has 2 frames.
        ]
    )


def test_two_frames_share_the_palette_and_a_stored_black_becomes_1():
    # Lines 347 to 354: entry 0 stays 0 and a stored 0 becomes 1. Lines 370 to 375: flag 1 stores x in the outer loop.
    palette = (0, 0x102030, 1, 0xFFFFFF)
    assert decode_sprites(1, two_frames()) == (
        Sprite(3, 3, 0, 0, 2, 1, palette, bytes([1, 2])),
        Sprite(3, 3, 1, 1, 2, 2, palette, bytes([1, 3, 2, 1])),
    )


def test_the_canvas_has_index_0_around_a_frame_at_an_offset():
    # IndexedSprite.java lines 35 to 52.
    frame = decode_sprites(1, two_frames())[1]
    assert canvas_pixels(frame) == bytes([0, 0, 0, 0, 1, 3, 0, 2, 1])


@pytest.mark.parametrize(
    ("data", "part"),
    [
        (bytes(7) + bytes([0, 1]), "footer"),
        (bytes([0, 1, 0, 1, 255, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1]), "palette"),
    ],
    ids=["footer", "palette"],
)
def test_a_group_too_short_for_its_footer_or_its_palette_is_refused(data, part):
    # The client reads these groups from before byte 0, which throws in Java.
    with pytest.raises(ValueError, match=f"Sprite group 1 is too short for its {part}"):
        decode_sprites(1, data)


def test_bytes_between_the_pixels_and_the_palette_are_refused():
    data = two_frames()
    with pytest.raises(ValueError, match="1 byte"):
        decode_sprites(1, data[:8] + bytes(1) + data[8:])


def test_a_frame_flag_other_than_0_and_1_is_refused_before_its_pixels_are_read():
    # The client reads pixels only for flags 0 and 1 (lines 364 to 376), so this group of one 200 by 200 frame with
    # flag 2 stores no pixels. The owner chose to refuse any other flag on 2026-11-14 (issue 39, Decisions).
    data = bytes([2, 0, 200, 0, 200, 0, 0, 0, 0, 0, 0, 200, 0, 200, 0, 1])
    with pytest.raises(ValueError, match="Frame 0 of sprite group 1 has flag 2"):
        decode_sprites(1, data)


def test_a_frame_that_reaches_past_the_end_of_its_canvas_is_refused():
    # A 2 by 1 frame at (2, 1) on a 3 by 2 canvas. IndexedSprite.java line 42 writes it to positions 5 and 6 of an
    # array of 6, which throws in Java.
    frame = Sprite(3, 2, 2, 1, 2, 1, (0, 1), bytes([1, 1]))
    with pytest.raises(ValueError, match="past the end of its canvas"):
        canvas_pixels(frame)


def test_a_frame_of_width_0_gives_an_empty_canvas_at_any_offset():
    # IndexedSprite.java line 41 writes no pixel of a frame of width 0, so the client does not throw.
    frame = Sprite(4, 4, 0, 9, 0, 1, (0,), b"")
    assert canvas_pixels(frame) == bytes(16)
