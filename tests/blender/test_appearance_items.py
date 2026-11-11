from pathlib import Path

import bpy
import pytest

from rsps_toolkit.blender import appearance_items, appearance_props, preferences
from rsps_toolkit.formats import cache_profile
from rsps_toolkit.formats.item_wear import ItemWear, load_item_wear

FIXTURES = Path(__file__).parent.parent / "fixtures" / "appearance"


@pytest.fixture
def props(monkeypatch, dump):
    monkeypatch.setattr(preferences, "cache_folder", lambda: dump)
    cache_profile.clear_shared_profiles()
    for cls in (*appearance_props.classes, *appearance_items.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    scene_props = bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    scene_props.female = False
    scene_props.equipment = (0, 0, 0, 0, 274, 0, 282, 292, 256, 289, 298, 266)
    yield scene_props
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_items.classes)):
        bpy.utils.unregister_class(cls)


def pick(slot, item):
    return bpy.ops.rsps.pick_item(slot=slot, item=str(item))  # pyrefly: ignore[missing-attribute]


def take_off(slot):
    return bpy.ops.rsps.clear_slot(slot=slot)  # pyrefly: ignore[missing-attribute]


def popup(slot):
    """What the search popup of a slot lists. The popup reads only the operator's slot, so a stand-in is enough."""
    return appearance_items._slot_items(type("Operator", (), {"slot": slot})(), bpy.context)


def listed(slot):
    return [identifier for identifier, _, _ in popup(slot)]


def wear_with(monkeypatch, hides=None, status=None):
    """Replace the recent cache's wear data for a few items, for cases no fixture item shows."""
    real = load_item_wear()
    stub = ItemWear(real.slot_of, {**real.hides, **(hides or {})}, {**real.status, **(status or {})})
    monkeypatch.setattr(appearance_props, "item_wear", lambda: stub)


def test_the_search_popup_lists_the_items_of_its_slot_for_the_body_type(props):
    assert listed(4) == ["3140", "2653"]
    assert listed(7) == ["4087"]
    assert listed(0) == ["1149"]


def test_a_slot_without_items_offers_no_item_to_wear(props):
    assert listed(2) == [appearance_items.NO_ITEMS]
    with pytest.raises(RuntimeError, match="neck slot"):
        pick(2, appearance_items.NO_ITEMS)


def test_picking_an_item_fills_its_slot_with_item_id_plus_512_and_the_kit_shows_its_name(props):
    pick(4, 2653)
    assert props.equipment[4] == 512 + 2653
    assert appearance_items.worn_item_name(4) == "Zamorak platebody"
    assert appearance_items.worn_item_name(0) is None


def test_taking_off_a_body_slot_restores_its_default_kit_and_other_slots_empty(props):
    pick(4, 2653)
    take_off(4)
    assert props.equipment[4] == 274
    pick(3, 35)
    take_off(3)
    assert props.equipment[3] == 0


def test_without_a_cache_folder_the_popup_says_so(props, monkeypatch):
    monkeypatch.setattr(preferences, "cache_folder", lambda: None)
    ((identifier, name, _),) = popup(4)
    assert identifier == appearance_items.NO_ITEMS and "Set the Cache folder" in name


def test_a_torso_item_that_hides_the_arms_ticks_covers_arms_and_take_off_brings_the_arms_back(props):
    props.equipment[6] = 256 + 27
    pick(4, 2653)
    assert props.covers_arms and props.equipment[6] == 0
    take_off(4)
    assert not props.covers_arms and props.equipment[6] == 256 + 27


def test_a_torso_item_that_keeps_the_arms_puts_the_arms_back(props, monkeypatch):
    wear_with(monkeypatch, hides={3140: frozenset()})
    props.equipment[6] = 256 + 27
    pick(4, 2653)
    pick(4, 3140)
    assert not props.covers_arms and props.equipment[6] == 256 + 27


def test_a_med_helm_covers_the_hair_but_not_the_jaw(props):
    pick(0, 1149)
    assert props.covers_hair and props.equipment[8] == 0
    assert not props.covers_jaw and props.equipment[11] == 266


def test_unticking_a_covers_toggle_puts_back_the_kit_from_before_or_the_default(props, monkeypatch):
    wear_with(monkeypatch, hides={1149: frozenset()})
    pick(0, 1149)
    assert not props.covers_hair
    props.equipment[8] = 256 + 3
    props.covers_hair = True
    assert props.equipment[8] == 0
    props.covers_hair = False
    assert props.equipment[8] == 256 + 3
    props.equipment[8] = 0
    props.covers_hair = False
    assert props.equipment[8] == 256 + 0


def test_a_kit_kept_from_the_other_body_type_is_not_put_back(props, monkeypatch):
    wear_with(monkeypatch, hides={1149: frozenset()})
    pick(0, 1149)
    props.covers_hair = True
    props.covered_kits[8] = 256 + 3
    props.female = True
    props.equipment[0] = 512 + 1149
    props.equipment[8] = 0
    props.covers_hair = False
    assert props.equipment[8] == 256 + 45


def test_taking_off_a_head_item_uncovers_hair_and_jaw(props):
    pick(0, 1149)
    props.covers_jaw = True
    take_off(0)
    assert props.equipment[8] == 256 and props.equipment[11] == 266


def test_a_head_item_does_not_count_as_covering_a_jaw_the_female_body_has_no_kit_for(props):
    props.female = True
    props.equipment = (0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0)
    pick(0, 1149)
    assert not props.covers_jaw
    assert not appearance_props.covered(props, 11)


def test_an_item_that_hides_a_kit_in_the_game_keeps_its_toggle_ticked(props):
    props.equipment[6] = 256 + 27
    pick(4, 2653)
    assert appearance_props.locked(props, 4, 6)
    props.covers_arms = False
    assert props.covers_arms and props.equipment[6] == 0
    take_off(4)
    assert props.equipment[6] == 256 + 27


def test_an_item_remodelled_since_snapshot_430_starts_ticked_but_can_be_unticked(props, monkeypatch):
    wear_with(monkeypatch, status={2653: "models_changed"})
    pick(4, 2653)
    assert props.covers_arms and not appearance_props.locked(props, 4, 6)
    props.covers_arms = False
    assert not props.covers_arms and props.equipment[6] == 282


def test_an_item_that_hides_nothing_keeps_a_free_toggle(props):
    pick(0, 1149)
    assert not appearance_props.locked(props, 0, 11)
    props.covers_jaw = True
    assert props.covers_jaw
    props.covers_jaw = False
    assert not props.covers_jaw


def test_a_torso_item_that_hides_the_hands_covers_them_and_take_off_brings_them_back(props, monkeypatch):
    wear_with(monkeypatch, hides={2653: frozenset({6, 9})})
    pick(4, 2653)
    assert props.covers_arms and props.covers_hands
    assert props.equipment[6] == 0 and props.equipment[9] == 0
    assert appearance_props.locked(props, 4, 9)
    take_off(4)
    assert props.equipment[9] == 289


def test_a_weapon_that_hides_the_hands_and_shield_empties_both_and_gives_the_shield_back(props, monkeypatch):
    wear_with(monkeypatch, hides={35: frozenset({5, 9})})
    props.equipment[5] = 512 + 1149
    pick(3, 35)
    assert props.weapon_covers_hands and props.covers_shield
    assert props.equipment[5] == 0 and props.equipment[9] == 0
    assert appearance_props.covered(props, 9)
    take_off(3)
    assert props.equipment[5] == 512 + 1149 and props.equipment[9] == 289


def test_a_weapon_that_hides_nothing_keeps_the_hands_and_a_free_shield_toggle(props, monkeypatch):
    wear_with(monkeypatch, hides={35: frozenset()})
    props.equipment[5] = 512 + 1149
    pick(3, 35)
    assert not props.weapon_covers_hands and not props.covers_shield
    props.covers_shield = True
    assert props.equipment[5] == 0
    props.covers_shield = False
    assert props.equipment[5] == 512 + 1149
