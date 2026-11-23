from pathlib import Path

import pytest
from runelite_json import load_kits

from rsps_toolkit.formats.appearance import default_equipment
from rsps_toolkit.formats.appearance_look import Look, look_preset
from rsps_toolkit.formats.item_wear import load_item_wear

KITS = load_kits(Path(__file__).parents[1] / "fixtures/appearance/KitDefinitions.json")
WEAR = load_item_wear()
# The client's slot numbers (the note of data/item_wear.json).
HEAD, WEAPON, TORSO, SHIELD, ARMS, LEGS, HAIR, HANDS, FEET, JAW = 0, 3, 4, 5, 6, 7, 8, 9, 10, 11


def equipment(look: Look) -> tuple[int, ...]:
    return look_preset(look, KITS, WEAR).equipment


@pytest.mark.parametrize("female", [False, True])
def test_an_empty_look_is_the_default_look_of_its_body_type(female):
    preset = look_preset(Look(female=female), KITS, WEAR)

    assert preset.equipment == tuple(default_equipment(KITS, female=female))
    assert (preset.female, preset.colours) == (female, (0, 0, 0, 0, 0))
    # The kit and item ids are those of snapshot 430, revision 149 (ADR 0003).
    assert (preset.client_revision, preset.snapshot_id) == (149, 430)


def test_a_kit_goes_to_the_slot_of_its_body_part_as_kit_id_plus_256():
    # Kit 18 is a male torso kit (bodyPartId 2 in KitDefinitions.json), and the torso is equipment slot 4.
    assert KITS[18].body_part == 2
    default = default_equipment(KITS)

    worn = equipment(Look(kits={"torso": 18}))

    assert worn[TORSO] == 18 + 256
    assert [value for slot, value in enumerate(worn) if slot != TORSO] == [
        value for slot, value in enumerate(default) if slot != TORSO
    ]


def test_the_colour_choices_go_to_the_preset():
    assert look_preset(Look(colours=(0, 6, 0, 0, 0)), KITS, WEAR).colours == (0, 6, 0, 0, 0)


def test_a_kit_of_another_body_part_is_refused():
    # Kit 0 is a male head kit (bodyPartId 0).
    with pytest.raises(ValueError, match="Kit 0 is not a male torso kit"):
        equipment(Look(kits={"torso": 0}))


def test_a_kit_of_the_other_body_type_is_refused():
    with pytest.raises(ValueError, match="Kit 18 is not a female torso kit"):
        equipment(Look(female=True, kits={"torso": 18}))


def test_a_kit_that_does_not_exist_is_refused():
    with pytest.raises(ValueError, match="Kit 9999 does not exist"):
        equipment(Look(kits={"torso": 9999}))


def test_a_body_part_that_does_not_exist_is_refused_with_the_names_that_do():
    with pytest.raises(ValueError, match="'tail'.*head, jaw, torso, arms, hands, legs, feet"):
        equipment(Look(kits={"tail": 18}))


def test_an_item_goes_to_its_slot_as_item_id_plus_512_and_empties_the_slots_it_hides():
    # data/item_wear.json: the Bronze full helm 1155 has slot 0 and hides 8 and 11, the Bronze platebody 1117 has slot 4
    # and hides 6, and the Leather gloves 1059 have slot 9 and hide nothing.
    default = default_equipment(KITS)

    worn = equipment(Look(items=(1155, 1117, 1059)))

    assert (worn[HEAD], worn[TORSO], worn[HANDS]) == (1155 + 512, 1117 + 512, 1059 + 512)
    assert (worn[HAIR], worn[JAW], worn[ARMS]) == (0, 0, 0)
    assert (worn[LEGS], worn[FEET]) == (default[LEGS], default[FEET])


def test_the_bronze_outfit_of_issue_170_fills_six_slots():
    worn = equipment(Look(items=(1155, 1117, 1189, 1075, 1059, 1061)))

    assert [value - 512 for value in worn if value >= 512] == [1155, 1117, 1189, 1075, 1059, 1061]
    assert [slot for slot, value in enumerate(worn) if value >= 512] == [HEAD, TORSO, SHIELD, LEGS, HANDS, FEET]


def test_a_later_item_empties_the_slot_of_an_earlier_one_as_the_panel_does():
    # The Rune 2h sword 1319 has slot 3 and hides slot 5, and the Bronze kiteshield 1189 has slot 5.
    assert equipment(Look(items=(1189, 1319)))[SHIELD] == 0
    assert equipment(Look(items=(1319, 1189)))[SHIELD] == 1189 + 512


def test_an_item_with_no_slot_is_refused():
    # Item 229 has no slot in data/item_wear.json (tests/unit/test_item_wear.py).
    with pytest.raises(ValueError, match="Item 229 has no equipment slot"):
        equipment(Look(items=(229,)))
