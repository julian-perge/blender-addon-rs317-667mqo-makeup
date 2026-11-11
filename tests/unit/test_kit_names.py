from pathlib import Path

from rsps_toolkit.formats.appearance import load_kits
from rsps_toolkit.formats.kit_names import load_kit_names

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"
KITS = load_kits(FIXTURES / "KitDefinitions.json")
NAMES = load_kit_names(FIXTURES / "KitStyleEnums.json", KITS)


def test_kit_101_is_leggings_by_its_model_28339():
    # Enum 779 lists model 28339 at key 7 and enum 778 names key 7 "Leggings" (read from the snapshot 430 dump).
    assert KITS[101].model_ids == (28339,)
    assert NAMES[101] == "Leggings"


def test_the_jaw_kit_without_a_chathead_model_is_clean_shaven_and_the_first_kit_is_a_goatee():
    # Kit 14 is the only jaw kit with no chathead model, and the style list's one style without a model is key 0.
    assert KITS[14].chathead_models[0] == -1
    assert NAMES[14] == "Clean-shaven" and NAMES[10] == "Goatee"


def test_every_kit_in_a_named_body_part_has_a_name():
    named_parts = (0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13)
    assert all(kit.id in NAMES for kit in KITS.values() if kit.body_part in named_parts and not kit.non_selectable)


def test_hands_and_feet_use_the_wiki_names_in_kit_id_order():
    # From the user's reading of the wiki makeover images, not from the cache; the order is unverified.
    assert [NAMES[i] for i in (42, 43)] == ["Basic", "Elven"]
    assert [NAMES[i] for i in (33, 34)] == ["Basic", "Plain"]
    assert [NAMES[i] for i in (67, 68, 79, 80)] == ["Basic", "Plain", "Basic", "Elven"]


def test_names_are_unique_within_a_body_part():
    for category in {kit.body_part for kit in KITS.values()}:
        named = [NAMES[k.id] for k in KITS.values() if k.body_part == category and k.id in NAMES]
        assert len(named) == len(set(named))
