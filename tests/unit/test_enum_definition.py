import json
from pathlib import Path

import pytest

from rsps_toolkit.formats.enum_definition import decode_enum

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"


def test_every_raw_style_enum_decodes_to_the_runelite_definition():
    expected = {
        row["id"]: (tuple(row["keys"]), tuple(row.get("intVals", ())), tuple(row.get("stringVals", ())))
        for row in json.loads((FIXTURES / "KitStyleEnums.json").read_text())
    }
    decoded = {}
    for path in (FIXTURES / "enums").iterdir():
        enum = decode_enum(int(path.stem), path.read_bytes())
        decoded[enum.id] = (enum.keys, enum.int_values, enum.string_values)
    assert decoded == expected


def test_an_unknown_opcode_is_refused():
    with pytest.raises(ValueError, match="opcode 7$"):
        decode_enum(0, bytes([1, 105, 7, 0]))


def test_bytes_after_the_closing_opcode_are_refused():
    with pytest.raises(ValueError, match="1 byte"):
        decode_enum(0, bytes([0, 0]))
