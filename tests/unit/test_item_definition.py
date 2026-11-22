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
    FIXTURES / "inventory",
]
INVENTORY = FIXTURES / "inventory"


def decode_folder(folder: Path):
    return {int(path.stem): decode_item(int(path.stem), path.read_bytes()) for path in (folder / "items").iterdir()}


@pytest.mark.parametrize("folder", ITEM_FOLDERS, ids=lambda folder: folder.name)
def test_every_raw_item_decodes_to_the_worn_fields_of_the_runelite_definition(folder):
    decoded = decode_folder(folder)
    assert {item_id: item.worn for item_id, item in decoded.items()} == load_items(folder / "ItemDefinitions.json")


def test_an_undefined_windows_1252_byte_in_a_name_reads_as_a_question_mark():
    # RuneLite's InputStream.readString (cache/src/main/java/net/runelite/cache/io/InputStream.java:198-225 at commit
    # bb0fa42b3) maps 0x80 to the euro sign and 0x81, which its table leaves as 0, to "?".
    assert decode_item(0, bytes([2, 0x41, 0x81, 0x80, 0, 0])).worn.name == "A?€"


# The appearance folder's JSON keeps only the worn-model fields, so it has no wear positions to compare.
@pytest.mark.parametrize("folder", ITEM_FOLDERS[1:], ids=lambda folder: folder.name)
def test_wear_positions_match_the_runelite_definition(folder):
    decoded = decode_folder(folder)
    expected = {
        row["id"]: (row["wearPos1"], row["wearPos2"], row["wearPos3"])
        for row in json.loads((folder / "ItemDefinitions.json").read_text())
    }
    assert {item_id: item.wear_positions for item_id, item in decoded.items()} == expected


def test_the_inventory_fields_match_the_runelite_definition():
    # RuneLite's ItemLoader reads opcode 1 as inventoryModel, 110 to 112 as resizeX to resizeZ and 113 as ambient.
    decoded = decode_folder(INVENTORY)
    rows = {row["id"]: row for row in json.loads((INVENTORY / "ItemDefinitions.json").read_text())}
    assert {item_id: (item.inventory_model, item.resize, item.ambient) for item_id, item in decoded.items()} == {
        item_id: (row["inventoryModel"], (row["resizeX"], row["resizeY"], row["resizeZ"]), row["ambient"])
        for item_id, row in rows.items()
    }
    # The Waterskin(4) 1823 has inventory model 2699, and the Silverlight key 2399 is the one with a resize.
    assert decoded[1823].inventory_model == 2699
    assert decoded[2399].resize == (85, 85, 85)


def test_the_contrast_is_five_times_the_byte_that_runelite_keeps():
    # The client stores the byte of opcode 114 times 5 (iz.v offsets 1576 to 1587 of gamepack 149: the stored
    # multiplier 1024003749 times the getter's 1880149473 is 5 modulo 2^32, docs/research/item-light.md). RuneLite's
    # row of the Broken glass 1469 holds the byte, 20.
    decoded = decode_folder(INVENTORY)
    rows = {row["id"]: row for row in json.loads((INVENTORY / "ItemDefinitions.json").read_text())}
    assert rows[1469]["contrast"] == 20
    assert {item_id: item.contrast for item_id, item in decoded.items()} == {
        item_id: row["contrast"] * 5 for item_id, row in rows.items()
    }


def test_an_item_with_no_opcode_for_them_has_the_defaults_of_runelite():
    # ItemDefinition.java: inventoryModel has no initialiser in RuneLite and the client leaves it 0, but an item with
    # no opcode 1 is not in snapshot 430, so -1 marks "none" here as for the worn models. resizeX to resizeZ are 128,
    # and ambient and contrast are 0.
    item = decode_item(0, bytes([0]))
    assert (item.inventory_model, item.resize, item.ambient, item.contrast) == (-1, (128, 128, 128), 0, 0)


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
