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


def test_an_undefined_windows_1252_byte_reads_as_a_question_mark():
    # RuneLite's InputStream.readString (cache/src/main/java/net/runelite/cache/io/InputStream.java:198-225 at commit
    # bb0fa42b3) maps 0x80 to the euro sign and 0x81, which its table leaves as 0, to "?".
    enum = decode_enum(0, bytes([5, 0, 1, 0, 0, 0, 7, 0x41, 0x81, 0x80, 0, 0]))
    assert enum.string_values == ("A?€",)


def test_bytes_after_the_closing_opcode_are_refused():
    with pytest.raises(ValueError, match="1 byte"):
        decode_enum(0, bytes([0, 0]))
