import json
from pathlib import Path

import pytest

from rsps_toolkit.formats import decode
from rsps_toolkit.formats.item_definition import decode_item
from rsps_toolkit.formats.item_model import inventory_model, item_lighting
from rsps_toolkit.formats.model import Model

# Raw item definitions and inventory models of snapshot 430, with RuneLite's rows in ItemDefinitions.json.
INVENTORY = Path(__file__).parents[1] / "fixtures" / "inventory"
ROWS = {row["id"]: row for row in json.loads((INVENTORY / "ItemDefinitions.json").read_text())}


def item(item_id: int):
    return decode_item(item_id, (INVENTORY / "items" / f"{item_id}.dat").read_bytes())


def load_model(model_id: int) -> Model:
    return decode((INVENTORY / "models" / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def test_an_item_with_no_ambient_and_contrast_gets_the_base_item_light():
    # iz.p offsets 511 to 542 of gamepack 149: dv.ae(64 + ambient, 768 + contrast, -50, -10, -50)
    # (docs/research/item-light.md). The Waterskin(4) 1823 has ambient 0 and contrast 0 in RuneLite's row.
    assert (ROWS[1823]["ambient"], ROWS[1823]["contrast"]) == (0, 0)
    assert item_lighting(item(1823)) == (64, 768, -50, -10, -50)


def test_the_item_light_adds_the_ambient_and_five_times_the_contrast_byte():
    # The same call, for the Broken glass 1469: RuneLite's row has ambient 40 and the contrast byte 20, which the
    # client stores as 100 (iz.v offsets 1576 to 1587).
    assert (ROWS[1469]["ambient"], ROWS[1469]["contrast"]) == (40, 20)
    assert item_lighting(item(1469)) == (64 + 40, 768 + 100, -50, -10, -50)


def test_the_inventory_model_of_an_item_without_changes_is_the_cache_model():
    assert inventory_model(item(1823), load_model) == load_model(2699)


def test_the_inventory_model_is_recoloured_with_the_pairs_of_the_item():
    # RuneLite's row of the Jug 1935: colorFind [127], colorReplace [61], inventoryModel 2390.
    assert (ROWS[1935]["colorFind"], ROWS[1935]["colorReplace"]) == ([127], [61])
    plain = load_model(2390)
    assert 127 in plain.face_colours

    model = inventory_model(item(1935), load_model)

    assert model.face_colours == [61 if colour == 127 else colour for colour in plain.face_colours]
    assert model.vertices == plain.vertices


def test_the_inventory_model_is_scaled_by_the_resize_with_division_toward_zero():
    # dv.h offsets 7 to 72: each coordinate times its resize value, divided by 128 with Java's idiv. The Silverlight
    # key 2399 has the resize 85, 85, 85 and model 17470 in RuneLite's row.
    plain = load_model(17470)

    model = inventory_model(item(2399), load_model)

    def java(value: int) -> int:
        return int(value * 85 / 128)

    assert model.vertices == [(java(x), java(y), java(z)) for x, y, z in plain.vertices]
    # A negative coordinate that floor division would round the other way: -44 * 85 / 128 is -29.2.
    assert min(x for x, _, _ in plain.vertices) == -44
    assert min(x for x, _, _ in model.vertices) == -29
    assert model.faces == plain.faces


def test_an_item_with_no_inventory_model_is_refused():
    with pytest.raises(ValueError, match="Item 7 has no inventory model"):
        inventory_model(decode_item(7, bytes([0])), load_model)
