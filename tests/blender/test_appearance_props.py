import bpy
import pytest

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
def test_kit_dropdowns_read_and_write_the_equipment_slots(props, monkeypatch, tmp_path):
    import shutil
    from pathlib import Path

    from rsps_toolkit.blender import preferences

    (tmp_path / "kits").mkdir()
    (tmp_path / "enums").mkdir()
    fixtures = Path(__file__).parent.parent / "fixtures/appearance"
    shutil.copy(fixtures / "KitDefinitions.json", tmp_path / "kits")
    shutil.copy(fixtures / "KitStyleEnums.json", tmp_path / "enums/Enums.json")
    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: tmp_path)
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
    props, monkeypatch, tmp_path
):
    import shutil
    from pathlib import Path

    from rsps_toolkit.blender import preferences

    fixtures = Path(__file__).parent.parent / "fixtures/appearance"
    for folder in ("kits", "enums"):
        (tmp_path / folder).mkdir()
    shutil.copy(fixtures / "KitDefinitions.json", tmp_path / "kits")
    shutil.copy(fixtures / "KitStyleEnums.json", tmp_path / "enums/Enums.json")
    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: tmp_path)
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

    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: tmp_path)
    cache_profile.clear_shared_profiles()
    appearance_props.kit_choices(props, 2)
    assert "KitDefinitions.json" in appearance_props.profile_error
    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: None)
    appearance_props.kit_choices(props, 2)
    assert "dump folder" in appearance_props.profile_error


@pytest.fixture
def named_kits_folder(monkeypatch, tmp_path):
    import shutil
    from pathlib import Path

    from rsps_toolkit.blender import preferences

    fixtures = Path(__file__).parent.parent / "fixtures/appearance"
    for folder in ("kits", "enums"):
        (tmp_path / folder).mkdir()
    shutil.copy(fixtures / "KitDefinitions.json", tmp_path / "kits")
    shutil.copy(fixtures / "KitStyleEnums.json", tmp_path / "enums/Enums.json")
    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: tmp_path)
    cache_profile.clear_shared_profiles()
    return tmp_path


def redump(path, change):
    """Rewrite a catalog of the dump as a re-run of the dumper would, with a modified time a second later than before,
    so the test does not depend on the file system's clock resolution."""
    import json
    import os

    before = path.stat().st_mtime_ns
    rows = json.loads(path.read_text())
    change(rows)
    path.write_text(json.dumps(rows))
    os.utime(path, ns=(before + 1_000_000_000, before + 1_000_000_000))


def leg_labels(props):
    return {name: label for name, label, _ in appearance_props.kit_choices(props, 5)}


def test_the_kit_dropdowns_see_a_kit_a_re_dump_added_by_its_style_name(props, named_kits_folder):
    # The user chose that each catalog file whose modified time changes is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Kit 9101 is a copy of kit 101, which uses the model of the Leggings style (see
    # test_kit_names.py), under an id the fixture KitDefinitions.json lacks.
    def add_leggings(rows):
        rows.append({**next(row for row in rows if row["id"] == 101), "id": 9101})

    props.female = False
    assert "9101" not in leg_labels(props)
    redump(named_kits_folder / "kits/KitDefinitions.json", add_leggings)
    assert leg_labels(props)["9101"] == "Leggings"


def test_the_kit_dropdowns_see_a_style_a_re_dump_renamed(props, named_kits_folder):
    # The user chose that each catalog file whose modified time changes is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Enum 778 lists the leg style names, Leggings among them (see test_kit_names.py).
    def rename_leggings(enums):
        legs = next(enum for enum in enums if enum["id"] == 778)
        legs["stringVals"] = ["Re-dumped leggings" if name == "Leggings" else name for name in legs["stringVals"]]

    props.female = False
    assert leg_labels(props)["101"] == "Leggings"
    redump(named_kits_folder / "enums/Enums.json", rename_leggings)
    assert leg_labels(props)["101"] == "Re-dumped leggings"


def test_the_kit_dropdowns_see_a_kit_a_re_dump_added_just_after_the_kits_were_read(
    props, named_kits_folder, monkeypatch
):
    # The user chose that each catalog file whose modified time changes is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10), so a re-dump that lands just after the kit catalog was read is seen at the next listing.
    # Kit 9101 is a copy of kit 101, which uses the model of the Leggings style (see test_kit_names.py), under an id
    # the fixture KitDefinitions.json lacks.
    def add_leggings(rows):
        rows.append({**next(row for row in rows if row["id"] == 101), "id": 9101})

    real = cache_profile.load_kits
    redumped = []

    def load_then_redump(path):
        kits = real(path)
        if not redumped:
            redump(path, add_leggings)
            redumped.append(path)
        return kits

    props.female = False
    # Choosing the body type reads the kit catalog, so the store is cleared to make the dropdowns' kit names the first
    # to read it, the order in which a re-dump between reading the kits and naming them could be missed.
    cache_profile.clear_shared_profiles()
    monkeypatch.setattr(cache_profile, "load_kits", load_then_redump)
    leg_labels(props)
    assert leg_labels(props)["9101"] == "Leggings"


@pytest.fixture
def kits_folder(monkeypatch, tmp_path):
    import shutil
    from pathlib import Path

    from rsps_toolkit.blender import preferences

    (tmp_path / "kits").mkdir()
    shutil.copy(Path(__file__).parent.parent / "fixtures/appearance/KitDefinitions.json", tmp_path / "kits")
    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: tmp_path)
    cache_profile.clear_shared_profiles()
    return tmp_path


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


def test_without_a_dump_folder_the_appearance_stays_empty(props, monkeypatch):
    from rsps_toolkit.blender import preferences

    monkeypatch.setattr(preferences, "cache_dump_folder", lambda: None)
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
