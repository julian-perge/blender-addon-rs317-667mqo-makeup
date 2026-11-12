import json
from pathlib import Path

import pytest
from js5_builder import item_definition
from runelite_json import load_items

from rsps_toolkit.formats.item_definition import decode_item

FIXTURES = Path(__file__).parents[1] / "fixtures"
# Each folder holds raw item definitions in items/<id>.dat and their RuneLite-decoded rows in ItemDefinitions.json.
ITEM_FOLDERS = [
    FIXTURES / "appearance",
    FIXTURES / "animation149/held-1365",
    FIXTURES / "animation149/held-717",
    FIXTURES / "animation149/held-909",
]


def decode_folder(folder: Path):
    return {int(path.stem): decode_item(int(path.stem), path.read_bytes()) for path in (folder / "items").iterdir()}


@pytest.mark.parametrize("folder", ITEM_FOLDERS, ids=lambda folder: folder.name)
def test_every_raw_item_decodes_to_the_worn_fields_of_the_runelite_definition(folder):
    decoded = decode_folder(folder)
    assert {item_id: item.worn for item_id, item in decoded.items()} == load_items(folder / "ItemDefinitions.json")


# The appearance folder's JSON keeps only the worn-model fields, so it has no wear positions to compare.
@pytest.mark.parametrize("folder", ITEM_FOLDERS[1:], ids=lambda folder: folder.name)
def test_wear_positions_match_the_runelite_definition(folder):
    decoded = decode_folder(folder)
    expected = {
        row["id"]: (row["wearPos1"], row["wearPos2"], row["wearPos3"])
        for row in json.loads((folder / "ItemDefinitions.json").read_text())
    }
    assert {item_id: item.wear_positions for item_id, item in decoded.items()} == expected


def test_the_female_offset_of_excalibur_is_read():
    # The item 35 row of appearance/ItemDefinitions.json has maleOffset 0 and femaleOffset 6.
    item = decode_item(35, (FIXTURES / "appearance/items/35.dat").read_bytes())
    assert (item.worn.male_offset, item.worn.female_offset) == (0, 6)


def test_an_unknown_opcode_is_refused():
    with pytest.raises(ValueError, match="opcode 10$"):
        decode_item(0, bytes([11, 10, 0]))


def test_bytes_after_the_closing_opcode_are_refused():
    with pytest.raises(ValueError, match="2 byte"):
        decode_item(0, bytes([11, 0, 1, 2]))


def test_the_test_encoder_writes_what_the_decoder_reads():
    item = decode_item(
        9000,
        item_definition(
            "Test item", male=(10, 11, 12), female=(20, -1, -1), recolours=((1, 2),), retextures=((3, 4), (5, 6))
        ),
    )
    assert item.worn.name == "Test item"
    assert item.worn.male_models == (10, 11, 12) and item.worn.female_models == (20, -1, -1)
    assert item.worn.recolours == ((1, 2),) and item.worn.retextures == ((3, 4), (5, 6))
    assert decode_item(9001, item_definition("Bare")).worn.male_models == (-1, -1, -1)
