import bpy
import pytest
from js5_builder import rewrite_cache

from rsps_toolkit.blender import appearance_props
from rsps_toolkit.formats import cache_profile
from rsps_toolkit.formats.appearance_preset import AppearancePreset

FEMALE = AppearancePreset(149, 430, True, (0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0), (1, 2, 3, 4, 5))


@pytest.fixture
def props():
    for cls in appearance_props.classes:
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    yield bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    appearance_props.unregister_properties()
    for cls in reversed(appearance_props.classes):
        bpy.utils.unregister_class(cls)


def test_preset_round_trips_through_the_properties(props):
    appearance_props.from_preset(props, FEMALE)
    assert appearance_props.to_preset(props) == FEMALE


def test_a_preset_for_another_revision_is_refused_and_changes_nothing(props):
    appearance_props.from_preset(props, FEMALE)
    other = AppearancePreset(170, 430, False, (0,) * 12, (0,) * 5)
    with pytest.raises(ValueError, match="revision 170"):
        appearance_props.from_preset(props, other)
    assert appearance_props.to_preset(props) == FEMALE


# Kit ids come from KitDefinitions.json: kit 18 is a male torso kit, kit 56 a female torso kit, and kit 64 is not a
# male torso kit. Kit 14 is the clean-shaven jaw and kit 101 is named Leggings (see test_kit_names.py).
def test_kit_dropdowns_read_and_write_the_equipment_slots(props, monkeypatch, cache):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    cache_profile.clear_shared_profiles()
    props.female = False
    choices = [name for name, _, _ in appearance_props.kit_choices(props, 2)]
    assert "none" not in choices and "18" in choices and "64" not in choices
    labels = {name: label for name, label, _ in appearance_props.kit_choices(props, 5)}
    assert labels["101"] == "Leggings"
    assert {name: label for name, label, _ in appearance_props.kit_choices(props, 1)}["14"] == "Clean-shaven"
    assert "hidden" not in [name for name, _, _ in appearance_props.kit_choices(props, 3)]
    props.equipment[6] = 0
    assert props.kit_arms == "other"
    props.kit_torso = "18"
    assert props.equipment[4] == 18 + 256 and props.kit_torso == "18"
    props.female = True
    female_choices = [name for name, _, _ in appearance_props.kit_choices(props, 2)]
    assert "18" not in female_choices and "56" in female_choices
    assert [name for name, _, _ in appearance_props.kit_choices(props, 1)] == ["none", "other"]


def test_colour_choices_are_limited_to_each_slots_palette_row(props):
    from rsps_toolkit.formats.appearance import load_palette
    from rsps_toolkit.formats.cache_profile import PALETTE_PATH

    lengths = [len(row) for row in load_palette(PALETTE_PATH).primary_choices]
    props.colours = (99, 99, 99, 99, 99)
    assert list(props.colours) == [n - 1 for n in lengths]


def test_a_preset_with_an_unavailable_colour_choice_is_refused_not_clamped(props):
    appearance_props.from_preset(props, FEMALE)
    with pytest.raises(ValueError, match="Colour slot 3 has choices 0 to 5"):
        appearance_props.from_preset(props, AppearancePreset(149, 430, False, (0,) * 12, (0, 0, 0, 6, 0)))
    assert appearance_props.to_preset(props) == FEMALE


def test_a_slot_that_holds_an_item_or_the_other_bodys_kit_shows_other_and_picking_it_changes_nothing(
    props, monkeypatch, cache
):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    cache_profile.clear_shared_profiles()
    props.female = False
    props.equipment = (0, 0, 0, 0, 512 + 2653, 0, 282, 292, 256, 289, 298, 266)
    assert props.kit_torso == "other"
    props.kit_torso = "other"
    assert props.equipment[4] == 512 + 2653
    props.female = True
    assert props.kit_legs == "other"
    assert props.equipment[7] == 292


def test_the_panel_can_say_why_kits_are_missing(props, monkeypatch, tmp_path):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_folder", lambda: tmp_path)
    cache_profile.clear_shared_profiles()
    appearance_props.kit_choices(props, 2)
    assert "main_file_cache.dat2" in appearance_props.profile_error
    monkeypatch.setattr(preferences, "cache_folder", lambda: None)
    appearance_props.kit_choices(props, 2)
    assert "Set the Cache folder" in appearance_props.profile_error


@pytest.fixture
def kits_folder(monkeypatch, cache):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    cache_profile.clear_shared_profiles()
    return cache


def add_leggings(parts):
    """Kit 9101 is a copy of kit 101, which uses the model of the Leggings style (see test_kit_names.py), under an id
    the fixture cache lacks."""
    parts["kits"][9101] = parts["kits"][101]


def leg_labels(props):
    return {name: label for name, label, _ in appearance_props.kit_choices(props, 5)}


def test_the_kit_dropdowns_see_a_kit_a_changed_cache_added_by_its_style_name(props, kits_folder):
    # The user chose that each catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10).
    props.female = False
    assert "9101" not in leg_labels(props)
    rewrite_cache(kits_folder, add_leggings)
    assert leg_labels(props)["9101"] == "Leggings"


def test_the_kit_dropdowns_see_a_style_a_changed_cache_renamed(props, kits_folder):
    # The user chose that each catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Enum 778 lists the leg style names, Leggings among them (see test_kit_names.py).
    def rename_leggings(parts):
        parts["enums"][778] = parts["enums"][778].replace(b"Leggings\0", b"Renamed leggings\0")

    props.female = False
    assert leg_labels(props)["101"] == "Leggings"
    rewrite_cache(kits_folder, rename_leggings)
    assert leg_labels(props)["101"] == "Renamed leggings"


def test_the_kit_dropdowns_see_a_kit_a_cache_change_added_just_after_the_kits_were_read(
    props, kits_folder, monkeypatch
):
    # The user chose that each catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10), so a change that lands just after the kits were read is seen at the next listing.
    real = cache_profile.read_kits
    changed = []

    def read_then_change(store):
        kits = real(store)
        if not changed:
            rewrite_cache(kits_folder, add_leggings)
            changed.append(store)
        return kits

    props.female = False
    # Choosing the body type reads the kits, so the store is cleared to make the dropdowns' kit names the first to read
    # them, the order in which a change between reading the kits and naming them could be missed.
    cache_profile.clear_shared_profiles()
    monkeypatch.setattr(cache_profile, "read_kits", read_then_change)
    leg_labels(props)
    assert leg_labels(props)["9101"] == "Leggings"


# The client's default looks, as recorded in reference.json (client_default_equipment).
MALE_DEFAULT = [0, 0, 0, 0, 274, 0, 282, 292, 256, 289, 298, 266]
FEMALE_DEFAULT = [0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0]


def test_an_empty_appearance_gets_the_clients_default_look(props, kits_folder):
    props.female = False
    props.equipment = (0,) * 12
    appearance_props.fill_scenes()
    assert list(props.equipment) == MALE_DEFAULT


def test_an_appearance_that_holds_anything_is_left_alone(props, kits_folder):
    props.equipment = (0,) * 11 + (266,)
    appearance_props.fill_default_kits(props)
    assert list(props.equipment) == [0] * 11 + [266]


def test_without_a_cache_folder_the_appearance_stays_empty(props, monkeypatch):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_folder", lambda: None)
    props.equipment = (0,) * 12
    appearance_props.fill_default_kits(props)
    assert list(props.equipment) == [0] * 12


def test_switching_body_type_swaps_the_default_look_and_keeps_a_chosen_one(props, kits_folder):
    props.female = False
    props.equipment = MALE_DEFAULT
    props.female = True
    assert list(props.equipment) == FEMALE_DEFAULT
    props.female = False
    assert list(props.equipment) == MALE_DEFAULT
    props.kit_torso = "19"
    props.female = True
    assert props.equipment[4] == 19 + 256


def test_a_colour_dropdown_writes_the_clients_choice_number(props):
    props.colours = (0, 0, 0, 0, 0)
    props.colour_skin = "7"
    props.colour_legs = "15"
    assert list(props.colours) == [0, 0, 15, 0, 7]
    assert (props.colour_skin, props.colour_legs) == ("7", "15")


def test_the_skin_dropdown_lists_tones_light_to_dark_with_names_hex_and_swatches(props):
    items = appearance_props.colour_items(4)
    assert [name for _, name, _, _, _ in items][:2] == ["Tone 1", "Tone 2"]
    assert [identifier for identifier, _, _, _, _ in items][:2] == ["7", "0"]
    assert all(hex_code.startswith("#") and len(hex_code) == 7 for _, _, hex_code, _, _ in items)
    assert [number for _, _, _, _, number in items][-3:] == [8, 9, 10]
    assert bpy.types.UILayout.enum_item_name(props, "colour_skin", "7") == "Tone 1"


def test_a_swatch_is_the_clients_colour_at_the_brightness_setting():
    from rsps_toolkit.blender import appearance_swatches
    from rsps_toolkit.formats.colour import face_colour_to_rgb

    colour = appearance_props.palette().primary_choices[1][0]
    expected = face_colour_to_rgb(colour, 0.8)
    assert appearance_swatches.hex_code(colour) == "#" + "".join(f"{v:02x}" for v in expected)
    assert isinstance(appearance_swatches.icon(colour), int)
    appearance_swatches.unregister()
