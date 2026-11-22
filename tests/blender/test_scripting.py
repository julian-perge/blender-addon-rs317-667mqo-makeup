"""Scripted use (spec 170): every function takes its inputs as arguments, with the add-on not enabled."""

import struct
from pathlib import Path

import bpy
import pytest
from js5_builder import item_definition, rewrite_cache

from rsps_toolkit.blender import appearance_collection, appearance_preview, scripting
from rsps_toolkit.blender.face_materials import srgb_to_linear
from rsps_toolkit.formats import decode, face_colour_to_rgb
from rsps_toolkit.formats.appearance_look import Look
from rsps_toolkit.formats.appearance_preset import loads_preset
from rsps_toolkit.formats.lighting import light_hsl

FIXTURES = Path(__file__).parent.parent / "fixtures"
INVENTORY = FIXTURES / "inventory"
TEXTURED_MODEL = FIXTURES / "models" / "osrs" / "135.dat"
# iz.p offsets 511 to 542 of gamepack 149 for an item with ambient 0 and contrast 0 (docs/research/item-light.md).
BASE_ITEM_LIGHT = (64, 768, -50, -10, -50)
BRIGHTNESS = 0.6


@pytest.fixture(autouse=True)
def empty_file_and_no_add_on():
    """Scripted use runs with the add-on not enabled, so no test here registers it."""
    bpy.ops.wm.read_homefile(use_empty=True)
    preferences = bpy.context.preferences
    assert preferences is not None
    assert "rsps_toolkit" not in preferences.addons
    assert not hasattr(bpy.types.Scene, "rs_appearance")


def raw_files(folder: Path) -> dict[int, bytes]:
    return {int(path.stem): path.read_bytes() for path in folder.glob("*.dat")}


@pytest.fixture
def cache(cache) -> Path:
    """The appearance cache with the items and inventory models of fixtures/inventory, and item 9000, whose inventory
    model 135 has textured faces."""

    def add(parts: dict[str, dict[int, bytes]]) -> None:
        parts["items"] |= raw_files(INVENTORY / "items")
        parts["items"][9000] = bytes([1]) + struct.pack(">H", 135) + item_definition("Textured thing")
        parts["models"] |= raw_files(INVENTORY / "models")
        parts["models"][135] = TEXTURED_MODEL.read_bytes()

    rewrite_cache(cache, add)
    return cache


def mesh_of(obj: bpy.types.Object) -> bpy.types.Mesh:
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


def lit_colours(mesh: bpy.types.Mesh) -> list[float]:
    attribute = mesh.color_attributes[appearance_preview.LIT_ATTRIBUTE]
    assert isinstance(attribute, bpy.types.FloatColorAttribute)
    values = [0.0] * (len(attribute.data) * 4)
    attribute.data.foreach_get("color", values)
    return values


def test_import_item_makes_the_inventory_model_with_the_item_light_in_rs_lit(cache):
    scene = bpy.context.scene
    assert scene is not None
    props = bpy.data.collections.new("Props")
    scene.collection.children.link(props)

    obj = scripting.import_item(cache, 1823, brightness=BRIGHTNESS, collection=props)

    # The owner chose the name in issue 170 (spec 170, section 4).
    assert obj.name == "Waterskin(4) 1823"
    assert [o.name for o in props.objects] == ["Waterskin(4) 1823"]
    mesh = mesh_of(obj)
    assert [material.name for material in mesh.materials if material] == [appearance_preview.MATERIAL_NAME]
    # The Waterskin(4) 1823 shows model 2699 with no recolour (RuneLite's row in fixtures/inventory).
    model = decode((INVENTORY / "models" / "2699.dat").read_bytes(), profile="osrs-149")
    shading = light_hsl(model, BASE_ITEM_LIGHT)
    expected: list[float] = []
    for face, corners in enumerate(model.faces):
        if len(set(corners)) < 3:  # A face that repeats a vertex stays out of the mesh (ADR 0005).
            continue
        first = shading.corner_a[face]
        shades = (first,) * 3 if model.flat_shaded[face] else (first, shading.corner_b[face], shading.corner_c[face])
        for shade in shades:
            expected += [*(srgb_to_linear(c / 255) for c in face_colour_to_rgb(shade, BRIGHTNESS)), 1.0]
    assert lit_colours(mesh) == pytest.approx(expected)


def test_an_imported_item_has_the_size_of_its_model_in_game_units(cache):
    obj = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)

    # Model 2699 spans game y -33 to 0, and game y points down, so the object is 33 game units tall from z 0.
    model = decode((INVENTORY / "models" / "2699.dat").read_bytes(), profile="osrs-149")
    assert (min(y for _, y, _ in model.vertices), max(y for _, y, _ in model.vertices)) == (-33, 0)
    heights = [vertex.co.z for vertex in mesh_of(obj).vertices]
    assert (min(heights), max(heights)) == (0.0, 33.0)
    assert (obj.scale.x, obj.scale.y, obj.scale.z) == (1.0, 1.0, 1.0)
    scene = bpy.context.scene
    assert scene is not None
    assert obj.name in scene.collection.objects


def test_import_item_takes_a_name(cache):
    assert scripting.import_item(cache, 1823, brightness=BRIGHTNESS, name="Flask").name == "Flask"


def test_an_item_with_a_textured_inventory_model_is_refused_and_nothing_is_left(cache):
    with pytest.raises(ValueError, match="textured"):
        scripting.import_item(cache, 9000, brightness=BRIGHTNESS)

    assert (len(bpy.data.objects), len(bpy.data.meshes)) == (0, 0)


def test_an_item_that_the_cache_lacks_is_refused(cache):
    with pytest.raises(ValueError, match="no item 4"):
        scripting.import_item(cache, 4, brightness=BRIGHTNESS)


# The Steel med helm 1149, the Rune platebody (g) 2653 and the Rune platelegs (t) 4087 are items of the appearance
# fixtures. data/item_wear.json gives them the slots 0, 4 and 7.
ARMOUR = Look(kits={"torso": 18}, colours=(0, 6, 0, 0, 0), items=(1149, 2653, 4087))


def test_create_player_builds_the_look_with_the_rig_at_the_given_place(cache):
    player = scripting.create_player(cache, ARMOUR, brightness=BRIGHTNESS, location=(640.0, 320.0, -12.0))

    assert player.collection.name == "Player"
    assert player.rig == appearance_collection.armature_of(player.collection)
    assert (player.rig.location.x, player.rig.location.y, player.rig.location.z) == (640.0, 320.0, -12.0)
    assert list(player.parts) == appearance_collection.parts(player.collection)
    assert all(part.type == "MESH" and part.parent == player.rig for part in player.parts)
    preset = loads_preset(player.collection[appearance_preview.PRESET_KEY])
    assert (preset.female, preset.colours) == (False, (0, 6, 0, 0, 0))
    assert [value - 512 for value in preset.equipment if value >= 512] == [1149, 2653, 4087]
    assert not appearance_collection.is_edited(player.collection)


def test_create_player_shows_the_lit_colours_at_the_given_brightness(cache):
    dark = scripting.create_player(cache, Look(), brightness=0.9, name="Dark")
    bright = scripting.create_player(cache, Look(), brightness=0.6, name="Bright")

    # The client raises each channel to the power of the brightness, so 0.6 gives lighter colours than 0.9
    # (`face_colour_to_rgb`).
    assert sum(lit_colours(mesh_of(bright.parts[0]))) > sum(lit_colours(mesh_of(dark.parts[0])))


def test_two_players_at_one_place_stand_on_the_same_place(cache):
    # The place is the script's choice (ADR 0031). Only the Create Player button puts a player beside the last one.
    first = scripting.create_player(cache, Look(), brightness=BRIGHTNESS, location=(64.0, 64.0, 0.0))
    second = scripting.create_player(cache, Look(female=True), brightness=BRIGHTNESS, location=(64.0, 64.0, 0.0))

    assert first.collection != second.collection
    assert first.rig.location == second.rig.location
    assert second.collection.name == "Player.001"


def test_create_player_takes_a_name(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS, name="Hero")

    assert (player.collection.name, player.rig.name, player.parts[0].name) == ("Hero", "Hero_rig", "Hero")


def test_a_look_that_cannot_be_built_is_refused_and_nothing_is_left(cache):
    with pytest.raises(ValueError, match="Item 229 has no equipment slot"):
        scripting.create_player(cache, Look(items=(229,)), brightness=BRIGHTNESS)

    assert (len(bpy.data.objects), len(bpy.data.collections)) == (0, 0)
