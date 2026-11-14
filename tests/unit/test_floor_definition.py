import pytest
from js5_builder import REGION_FIXTURES
from runelite_json import load_overlays, load_underlays

from rsps_toolkit.formats.floor_definition import Overlay, Underlay, decode_overlay, decode_underlay

FLOORS = REGION_FIXTURES / "floors.json"


def test_every_underlay_of_the_nine_terrains_equals_runelites_underlay_loader():
    decoded = {
        int(path.stem): decode_underlay(int(path.stem), path.read_bytes())
        for path in (REGION_FIXTURES / "underlays").glob("*.dat")
    }
    assert len(decoded) == 18
    assert decoded == load_underlays(FLOORS)


def test_every_overlay_of_the_nine_terrains_equals_runelites_overlay_loader():
    decoded = {
        int(path.stem): decode_overlay(int(path.stem), path.read_bytes())
        for path in (REGION_FIXTURES / "overlays").glob("*.dat")
    }
    assert len(decoded) == 28
    assert decoded == load_overlays(FLOORS)


def test_overlay_opcode_8_reads_no_value():
    # Overlay.java line 140 reads nothing for opcode 8. The other values are the defaults of the constructor (lines 85 to
    # 88): colour 0, no texture, isHidden set, and no other colour. post (lines 97 to 106) gives colour 0 hue, saturation and
    # lightness 0.
    assert decode_overlay(0, bytes([8, 0])) == Overlay(
        colour=0,
        texture=-1,
        hides_underlay=True,
        other_colour=-1,
        hue=0,
        saturation=0,
        lightness=0,
        other_hue=0,
        other_saturation=0,
        other_lightness=0,
    )


def test_an_underlay_with_red_highest_and_blue_above_green_has_a_negative_hue():
    # No fixture underlay has a negative hue. For 0xFF0080, FloorUnderlayDefinition.java lines 102 to 169 give:
    # lightness (255/256 + 0) / 2 = 0.498, below 0.5, so saturation 1 (clamped to 255) and lightness int(127.5) = 127;
    # hue (0 - 128/256) / (255/256) / 6 = -0.0837; multiplier int(512 * 0.498 * 1) = 255; hue int(-0.0837 * 255) = -21,
    # truncated toward zero.
    assert decode_underlay(0, bytes([1, 0xFF, 0x00, 0x80, 0])) == Underlay(
        colour=0xFF0080, hue=-21, saturation=255, lightness=127, hue_multiplier=255
    )


@pytest.mark.parametrize("data", [bytes([2, 0]), bytes([1, 0, 0, 0, 3, 0])], ids=["opcode 2", "opcode 3 after 1"])
def test_an_underlay_with_an_unknown_opcode_is_refused(data):
    # FloorUnderlayDefinition.java line 89 reads only opcode 1.
    with pytest.raises(ValueError, match="unknown opcode"):
        decode_underlay(7, data)


def test_an_overlay_with_an_unknown_opcode_is_refused():
    # Overlay.java lines 132 to 141 read opcodes 1, 2, 5, 7 and 8.
    with pytest.raises(ValueError, match="unknown opcode 3"):
        decode_overlay(7, bytes([3, 0]))


@pytest.mark.parametrize("decode", [decode_underlay, decode_overlay])
def test_a_floor_definition_with_bytes_after_its_end_is_refused(decode):
    with pytest.raises(ValueError, match="after its closing opcode"):
        decode(7, bytes([1, 0x10, 0x20, 0x30, 0, 0]))
