from rsps_toolkit.formats.item_wear import load_item_wear

WEAR = load_item_wear()


def test_worn_items_have_the_recent_caches_slot_and_unequippable_items_have_none():
    assert [WEAR.slot_of[i] for i in (1149, 3140, 2653, 4087, 9771, 35)] == [0, 4, 4, 7, 1, 3]
    assert 229 not in WEAR.slot_of


def test_platebodies_hide_the_arms_and_aprons_keep_them():
    assert all(WEAR.hides[i] == {6} for i in (2653, 1127, 75, 4720))
    assert WEAR.hides[1101] == frozenset()


def test_full_helms_hide_hair_and_jaw_med_helms_the_hair_and_partyhats_nothing():
    assert WEAR.hides[1163] == {8, 11}
    assert WEAR.hides[1149] == {8}
    assert WEAR.hides[1038] == frozenset()


def test_items_whose_worn_models_changed_since_snapshot_430_are_marked():
    assert WEAR.models_changed(544) and WEAR.models_changed(10350)
    assert not WEAR.models_changed(1127)
