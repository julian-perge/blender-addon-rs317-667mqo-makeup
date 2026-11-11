from pathlib import Path

import pytest

from rsps_toolkit.formats.appearance import load_kits
from rsps_toolkit.formats.kit_definition import decode_kit

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"


def test_every_raw_kit_decodes_to_the_runelite_definition():
    expected = load_kits(FIXTURES / "KitDefinitions.json")
    decoded = {int(path.stem): decode_kit(int(path.stem), path.read_bytes()) for path in (FIXTURES / "kits").iterdir()}
    assert decoded == expected


def test_retextures_are_read_as_unsigned_pairs_like_recolours():
    # No snapshot 430 kit has opcode 41. RuneLite KitLoader.java line 85 (commit bb0fa42b3) reads it as a count byte,
    # then that many pairs of a find short and a replace short. RuneLite reads 0xFFFE as -2, and the toolkit stores it as
    # 0xFFFE, as load_kits does with the RuneLite JSON.
    kit = decode_kit(0, bytes([41, 1, 0xFF, 0xFE, 0, 7, 0]))
    assert kit.retextures == ((0xFFFE, 7),)


def test_an_unknown_opcode_is_refused():
    with pytest.raises(ValueError, match="opcode 4$"):
        decode_kit(0, bytes([1, 0, 4, 0]))


def test_bytes_after_the_closing_opcode_are_refused():
    with pytest.raises(ValueError, match="1 byte"):
        decode_kit(0, bytes([1, 0, 0, 9]))
