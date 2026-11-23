"""Scripted use (spec 170): every function takes its inputs as arguments, with the add-on not enabled."""

import math
import os
import struct
from pathlib import Path

import bpy
import pytest
from js5_builder import build_region_cache, item_definition, region_textures, rewrite_cache
from mathutils import Vector

from rsps_toolkit.animation.clip import CacheClip, pose_vertices, read_sequence
from rsps_toolkit.blender import (
    appearance_clip,
    appearance_collection,
    appearance_held,
    appearance_preview,
    region_files,
    region_import,
    scripting,
)
from rsps_toolkit.blender.axes import game_to_blender
from rsps_toolkit.blender.face_materials import srgb_to_linear
from rsps_toolkit.formats import decode, face_colour_to_rgb
from rsps_toolkit.formats.appearance_look import Look, look_preset
from rsps_toolkit.formats.appearance_preset import loads_preset
from rsps_toolkit.formats.cache_profile import shared_profile
from rsps_toolkit.formats.chathead import player_head_model
from rsps_toolkit.formats.item_wear import load_item_wear
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.lighting import PLAYER_LIGHTING, light
from rsps_toolkit.formats.region import ground_height, load_terrain

FIXTURES = Path(__file__).parent.parent / "fixtures"
INVENTORY = FIXTURES / "inventory"
TEXTURED_MODEL = FIXTURES / "models" / "osrs" / "135.dat"
# iz.p offsets 511 to 542 of gamepack 149 for an item with ambient 0 and contrast 0 (docs/research/item-light.md).
BASE_ITEM_LIGHT = (64, 768, -50, -10, -50)
BRIGHTNESS = 0.6
WALK_CLIP = FIXTURES / "animation149" / "walk"


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
    """The appearance cache with the items and inventory models of fixtures/inventory, item 9000, whose inventory
    model 135 has textured faces, a stand-in for the Fire cape 6570 that wears model 135 (texture 16), and the textures
    and sprites of fixtures/region."""

    def add(parts: dict[str, dict[int, bytes]]) -> None:
        parts |= region_textures()
        parts["items"][6570] = item_definition("Textured cape", male=(135, -1, -1), female=(135, -1, -1))
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
    shading = light(model, BASE_ITEM_LIGHT)
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


def test_an_item_with_a_textured_inventory_model_shows_its_texture(cache):
    # Issue 103: the inventory model 135 of item 9000 names texture 16 (fixtures/models/osrs), and dv.ae lights it
    # (docs/research/textured-light.md).
    mesh = mesh_of(scripting.import_item(cache, 9000, brightness=BRIGHTNESS))

    shown = {material.get(appearance_preview.TEXTURE_KEY) for material in mesh.materials}  # pyrefly: ignore
    assert 16 in shown


def test_an_item_whose_texture_the_cache_lacks_is_refused_and_nothing_is_left(cache):
    rewrite_cache(cache, lambda parts: parts["textures"].pop(16))

    with pytest.raises(OSError, match="texture 16"):
        scripting.import_item(cache, 9000, brightness=BRIGHTNESS)

    assert (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.images)) == (0, 0, 0)


def test_an_item_that_the_cache_lacks_is_refused(cache):
    with pytest.raises(ValueError, match="no item 4"):
        scripting.import_item(cache, 4, brightness=BRIGHTNESS)


def polygon_values(mesh: bpy.types.Mesh, name: str) -> list[int]:
    values = [0] * len(mesh.polygons)
    mesh.attributes[name].data.foreach_get("value", values)  # pyrefly: ignore[missing-attribute]
    return values


def test_a_player_who_wears_an_item_with_textured_faces_shows_its_texture(cache):
    # Issue 103. The stand-in cape wears model 135, whose textured faces name texture 16 (fixtures/models/osrs).
    player = scripting.create_player(cache, Look(items=(6570,)), brightness=BRIGHTNESS)

    mesh = mesh_of(player.parts[0])
    body = shared_profile(cache).assemble(loads_preset(player.collection[appearance_preview.PRESET_KEY]))
    faces = appearance_preview.face_indices(mesh)
    assert faces is not None
    slots = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", slots)
    shown = [mesh.materials[slot].get(appearance_preview.TEXTURE_KEY) for slot in slots]  # pyrefly: ignore
    assert 16 in shown
    assert shown == [body.face_textures[face] for face in faces]
    image = next(m for m in mesh.materials if m.get(appearance_preview.TEXTURE_KEY) == 16)  # pyrefly: ignore
    assert any(node.type == "TEX_IMAGE" and node.image is not None for node in image.node_tree.nodes)  # pyrefly: ignore
    assert polygon_values(mesh, appearance_preview.LIT_SLOT_ATTRIBUTE) == slots


def test_a_textured_corner_holds_its_light_value_over_128_as_a_grey(cache):
    # The client multiplies each texel by the light value over 128 (docs/research/textured-light.md, section 2).
    player = scripting.create_player(cache, Look(items=(6570,)), brightness=BRIGHTNESS)

    mesh = mesh_of(player.parts[0])
    body = shared_profile(cache).assemble(loads_preset(player.collection[appearance_preview.PRESET_KEY]))
    shading = light(body, PLAYER_LIGHTING)
    faces = appearance_preview.face_indices(mesh)
    assert faces is not None
    colours = lit_colours(mesh)
    polygon = next(p for p, face in enumerate(faces) if body.face_textures[face] is not None)
    face = faces[polygon]
    third = shading.corner_c[face]
    values = (shading.corner_a[face],) * 3 if third == -1 else (shading.corner_a[face], shading.corner_b[face], third)
    start = mesh.polygons[polygon].loop_start
    for corner, value in enumerate(values):
        grey = srgb_to_linear(value / 128)
        assert colours[4 * (start + corner) : 4 * (start + corner) + 4] == pytest.approx([grey, grey, grey, 1.0])


@pytest.mark.skipif(
    not (os.environ.get("RSPS_SNAPSHOT_430_CACHE") and Path(os.environ["RSPS_SNAPSHOT_430_CACHE"]).is_dir()),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)
def test_vial_of_water_shows_its_glass_faces_and_its_faces_of_alpha_254_cover_nothing():
    # Model 2789 of Vial of water 227 has two faces of alpha 254 and faces of alpha 128 and 32 (RuneLite's model export
    # of snapshot 430, docs/research/textured-light.md, section 4).
    snapshot = Path(os.environ["RSPS_SNAPSHOT_430_CACHE"])
    mesh = mesh_of(scripting.import_item(snapshot, 227, brightness=BRIGHTNESS))

    slots = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", slots)
    alphas = [mesh.materials[slot].get(appearance_preview.ALPHA_KEY) for slot in slots]  # pyrefly: ignore
    assert alphas.count(254) == 2
    assert {128, 32} <= set(alphas)
    # ep.g copies the pixel beside a face of alpha 254 in place of the face, so the face covers nothing.
    glass = next(m for m in mesh.materials if m.get(appearance_preview.ALPHA_KEY) == 254)  # pyrefly: ignore
    covers = [node.inputs["Fac"].default_value for node in glass.node_tree.nodes if node.type == "MIX_SHADER"]  # pyrefly: ignore
    assert covers == [0.0]


@pytest.mark.skipif(
    not (os.environ.get("RSPS_SNAPSHOT_430_CACHE") and Path(os.environ["RSPS_SNAPSHOT_430_CACHE"]).is_dir()),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)
def test_a_male_player_who_wears_the_fire_cape_shows_its_24_faces_of_texture_40():
    # Issue 103: the male worn model 9638 of the Fire cape 6570 has texture 40 on 24 of its 63 faces (RuneLite's model
    # export of snapshot 430, docs/research/textured-light.md, section 4).
    snapshot = Path(os.environ["RSPS_SNAPSHOT_430_CACHE"])
    player = scripting.create_player(snapshot, Look(items=(6570,)), brightness=BRIGHTNESS)

    mesh = mesh_of(player.parts[0])
    slots = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", slots)
    shown = [mesh.materials[slot].get(appearance_preview.TEXTURE_KEY) for slot in slots]  # pyrefly: ignore
    assert shown.count(40) == 24


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

    # `appearance_collection.build_collection` names the rig after the collection, with `_rig`.
    assert (player.collection.name, player.rig.name, player.parts[0].name) == ("Hero", "Hero_rig", "Hero")


def test_a_look_that_cannot_be_built_is_refused_and_nothing_is_left(cache):
    with pytest.raises(ValueError, match="Item 229 has no equipment slot"):
        scripting.create_player(cache, Look(items=(229,)), brightness=BRIGHTNESS)

    assert (len(bpy.data.objects), len(bpy.data.collections)) == (0, 0)


def xyz(vector: Vector) -> tuple[float, float, float]:
    return vector.x, vector.y, vector.z


def origin(obj: bpy.types.Object) -> tuple[float, float, float]:
    """The world place of the object's origin, after the constraints."""
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.update()
    return xyz(obj.matrix_world.to_translation())


def joint_point(rig: bpy.types.Object, joint: str, offset: tuple[float, float, float]) -> tuple[float, float, float]:
    """The world place of a point given in the axes of the posed joint, from the head of the joint."""
    assert rig.pose is not None
    return xyz(rig.matrix_world @ rig.pose.bones[joint].matrix @ Vector(offset))


# Issue 170, gap e: on a rig with a small scale, a new Child Of constraint of Blender 5.3 cancelled the scale of the rig
# and the held item came out far too large. The item has to take the scale of the rig.
def test_an_item_on_a_joint_of_a_scaled_rig_takes_the_scale_of_the_rig(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS, location=(100.0, 200.0, 0.0))
    player.rig.scale = (0.01, 0.01, 0.01)
    item = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)

    constraint = scripting.attach_to_joint(item, player.rig, "hand.R")

    assert (constraint.type, item.constraints[0]) == ("CHILD_OF", constraint)
    assert origin(item) == pytest.approx(joint_point(player.rig, "hand.R", (0.0, 0.0, 0.0)), abs=1e-4)
    scale = item.matrix_world.to_scale()
    assert (scale.x, scale.y, scale.z) == pytest.approx((0.01, 0.01, 0.01))


def test_the_offset_of_an_attached_object_is_in_the_axes_of_the_joint_in_game_units(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    player.rig.scale = (0.5, 0.5, 0.5)
    item = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)

    scripting.attach_to_joint(item, player.rig, "spine", offset=(3.0, -4.0, 12.0), rotation=(0.0, 0.0, 1.5))

    assert origin(item) == pytest.approx(joint_point(player.rig, "spine", (3.0, -4.0, 12.0)), abs=1e-4)
    assert (item.rotation_euler.x, item.rotation_euler.y, item.rotation_euler.z) == pytest.approx((0.0, 0.0, 1.5))


def test_an_attached_object_follows_its_joint_through_a_baked_clip(cache):
    scene = bpy.context.scene
    assert scene is not None
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    item = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)
    scripting.attach_to_joint(item, player.rig, "hand.R")
    appearance_clip.bake_clip_to_rig(player.collection, WALK_CLIP, start=0)

    places = []
    for frame in (0, 20):
        scene.frame_set(frame)
        assert origin(item) == pytest.approx(joint_point(player.rig, "hand.R", (0.0, 0.0, 0.0)), abs=1e-4)
        places.append(Vector(origin(item)))
    # The hand swings during a walk, so the two frames give two places.
    assert (places[0] - places[1]).length > 1.0


def test_a_joint_that_the_rig_does_not_have_is_refused_with_the_joints_it_has(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    item = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)

    with pytest.raises(ValueError, match=r"Player_rig has no joint 'wing'\. Its joints are .*spine.*hand\.R"):
        scripting.attach_to_joint(item, player.rig, "wing")

    assert len(item.constraints) == 0


def test_a_label_bone_is_not_a_joint(cache):
    # The rig also has hidden label bones, which the user and a script do not animate (GLOSSARY.md, Joint).
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    item = scripting.import_item(cache, 1823, brightness=BRIGHTNESS)
    assert player.rig.pose is not None
    label = next(bone.name for bone in player.rig.pose.bones if bone.name.startswith("label_"))

    with pytest.raises(ValueError, match="has no joint"):
        scripting.attach_to_joint(item, player.rig, label)


SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
needs_snapshot_430 = pytest.mark.skipif(
    "RSPS_SNAPSHOT_430_CACHE" not in os.environ or not SNAPSHOT_430.is_dir(),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)
# Sequence 819 is the walk of the fixture tests/fixtures/animation149/walk, which has 49 Blender frames
# (tests/blender/test_appearance_clip.py).
WALK, WALK_FRAMES = 819, 49


def timing(scene: bpy.types.Scene) -> tuple[int, float, int, int]:
    return scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end


# Issue 170, gap f: a bake from a script starts before frame 0 and leaves the frame range of the scene alone.
@needs_snapshot_430
def test_bake_clip_bakes_a_sequence_of_the_cache_before_frame_0_and_leaves_the_scene_timing():
    scene = bpy.context.scene
    assert scene is not None
    scene.render.fps, scene.frame_start, scene.frame_end = 30, 5, 77
    player = scripting.create_player(SNAPSHOT_430, Look(), brightness=BRIGHTNESS)

    strip = scripting.bake_clip(player.collection, SNAPSHOT_430, WALK, start=-20)

    assert (strip.frame_start, strip.frame_end) == (-20, -20 + WALK_FRAMES)
    assert player.rig.animation_data is not None
    assert strip == player.rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips[0]
    assert timing(scene) == (30, 1.0, 5, 77)


@needs_snapshot_430
def test_bake_clip_repeats_a_walk_until_a_frame():
    player = scripting.create_player(SNAPSHOT_430, Look(), brightness=BRIGHTNESS)

    # The function takes the player or its collection.
    strip = scripting.bake_clip(player, SNAPSHOT_430, WALK, start=0, repeat_until=90)

    assert (strip.frame_start, strip.frame_end) == (0, 90)
    assert strip.repeat == pytest.approx(90 / WALK_FRAMES)


@needs_snapshot_430
def test_bake_clip_sets_the_scene_timing_when_the_script_asks():
    scene = bpy.context.scene
    assert scene is not None
    scene.render.fps, scene.frame_start, scene.frame_end = 30, 5, 77
    player = scripting.create_player(SNAPSHOT_430, Look(), brightness=BRIGHTNESS)

    scripting.bake_clip(player.collection, SNAPSHOT_430, WALK, start=1, set_scene_timing=True)

    # The Bake Clip button sets 50 frames in a second and the range of the first clip (`bake_clip_to_rig`).
    assert timing(scene) == (50, 1.0, 1, WALK_FRAMES)


@needs_snapshot_430
def test_a_sequence_that_the_cache_lacks_is_refused():
    player = scripting.create_player(SNAPSHOT_430, Look(), brightness=BRIGHTNESS)

    with pytest.raises(LookupError, match="no sequence 999999"):
        scripting.bake_clip(player.collection, SNAPSHOT_430, 999999)


def place(rig: bpy.types.Object, frame: int) -> tuple[float, float, float]:
    scene = bpy.context.scene
    assert scene is not None
    scene.frame_set(frame)
    return xyz(rig.location)


# Issue 170, gap g: a clip does not move the place of an actor. A walk moves 1 tile of 128 game units in 0.6 seconds,
# which is 30 frames at the 50 frames in a second of a clip (ADR 0035).
def test_key_travel_moves_the_rig_one_tile_in_30_frames_at_one_speed(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS, location=(64.0, 64.0, 0.0))

    last = scripting.key_travel(player.rig, [(64.0, 64.0, 0.0), (64.0, 448.0, -30.0)], start=10)

    assert last == 100
    assert place(player.rig, 10) == pytest.approx((64.0, 64.0, 0.0))
    assert place(player.rig, 100) == pytest.approx((64.0, 448.0, -30.0))
    # One speed: after 30 of the 90 frames the rig is a third of the way, in height too.
    assert place(player.rig, 40) == pytest.approx((64.0, 192.0, -10.0), abs=1e-3)
    assert place(player.rig, 0) == pytest.approx((64.0, 64.0, 0.0))
    assert place(player.rig, 150) == pytest.approx((64.0, 448.0, -30.0))


def test_key_travel_at_run_speed_takes_half_the_frames_and_turns_corners(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)

    last = scripting.key_travel(
        player.rig, [(0.0, 0.0, 0.0), (256.0, 0.0, 0.0), (256.0, 128.0, 0.0)], start=0, run=True
    )

    assert last == 45
    assert place(player.rig, 30) == pytest.approx((256.0, 0.0, 0.0))
    assert place(player.rig, 15) == pytest.approx((128.0, 0.0, 0.0), abs=1e-3)


def test_a_player_with_travel_keys_takes_a_bone_bake_and_a_baked_player_takes_travel_keys(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    scripting.key_travel(player.rig, [(0.0, 0.0, 0.0), (128.0, 0.0, 0.0)], start=0)

    appearance_clip.bake_clip_to_rig(player.collection, WALK_CLIP, start=0, repeat_until=30)
    scripting.key_travel(player.rig, [(128.0, 0.0, 0.0), (128.0, 128.0, 0.0)], start=30)
    appearance_clip.bake_clip_to_rig(player.collection, WALK_CLIP, start=30, repeat_until=60)

    assert place(player.rig, 15) == pytest.approx((64.0, 0.0, 0.0), abs=1e-3)
    assert place(player.rig, 45) == pytest.approx((128.0, 64.0, 0.0), abs=1e-3)
    assert player.rig.animation_data is not None
    assert len(player.rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips) == 2


def test_key_travel_refuses_fewer_than_two_points_before_any_key(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)

    with pytest.raises(ValueError, match="at least two points"):
        scripting.key_travel(player.rig, [(0.0, 0.0, 0.0)], start=0)

    assert player.rig.animation_data is None


def test_key_travel_refuses_a_point_with_no_height_and_a_step_that_stays_in_place_before_any_key(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)

    with pytest.raises(ValueError, match=r"Point 2 \(128.0, 0.0\) needs x, y and z"):
        scripting.key_travel(player.rig, [(0.0, 0.0, 0.0), (128.0, 0.0)], start=0)
    with pytest.raises(ValueError, match="Points 1 and 2 are at the same x and y"):
        scripting.key_travel(player.rig, [(0.0, 0.0, 0.0), (0.0, 0.0, 50.0)], start=0)

    assert player.rig.animation_data is None


def test_attach_to_joint_refuses_an_object_that_is_attached_or_has_a_parent(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    item = bpy.data.objects.new("Item", None)
    scripting.attach_to_joint(item, player.rig, "hand.R")
    with pytest.raises(ValueError, match="Item is on a joint already"):
        scripting.attach_to_joint(item, player.rig, "hand.L")
    assert len(item.constraints) == 1

    child = bpy.data.objects.new("Child", None)
    child.parent = item
    with pytest.raises(ValueError, match="Child has the parent Item"):
        scripting.attach_to_joint(child, player.rig, "hand.L")
    assert len(child.constraints) == 0


def test_attach_to_joint_turns_an_object_of_another_rotation_mode_by_the_xyz_euler(cache):
    player = scripting.create_player(cache, Look(), brightness=BRIGHTNESS)
    item = bpy.data.objects.new("Item", None)
    item.rotation_mode = "QUATERNION"

    scripting.attach_to_joint(item, player.rig, "hand.R", rotation=(0.5, 0.0, 0.0))

    assert item.rotation_mode == "XYZ"
    assert item.rotation_euler.x == pytest.approx(0.5)


# Sequence 1365 holds a steel axe (tests/blender/test_appearance_clip.py, the clip held-1365).
@needs_snapshot_430
def test_a_bake_of_a_clip_with_a_held_item_reads_no_preference_and_lights_the_item_as_the_player(monkeypatch):
    def refuse() -> float:
        raise AssertionError("scripted use read the Brightness preference")

    monkeypatch.setattr(appearance_held.preferences, "brightness", refuse)
    lit = {}
    for brightness in (0.6, 0.8):
        player = scripting.create_player(SNAPSHOT_430, Look(), brightness=brightness)
        scripting.bake_clip(player, SNAPSHOT_430, 1365, action=True)
        (axe,) = [obj for obj in player.collection.all_objects if "axe" in obj.name]
        attribute = mesh_of(axe).color_attributes["rs_lit"]
        assert isinstance(attribute, bpy.types.FloatColorAttribute)
        values = [0.0] * (len(attribute.data) * 4)
        attribute.data.foreach_get("color", values)
        lit[brightness] = values
        bpy.ops.wm.read_homefile(use_empty=True)

    assert lit[0.6] != lit[0.8]


@pytest.fixture
def region_cache(tmp_path) -> Path:
    """The groups of snapshot 430 that the import of 48_50 reads, with a keys folder that has no key file, so the
    region has its terrain and no scenery (tests/blender/test_region_import.py, `keyless_cache`)."""
    folder = tmp_path / "download" / "cache"
    build_region_cache(folder, definitions=True)
    (tmp_path / "download" / "keys").mkdir()
    return folder


# Region 48_50 starts at world tile (3072, 3200) (GLOSSARY.md, Region).
WEST, SOUTH = 48 * 64, 50 * 64
ORIGIN_TILE = (WEST + 10, SOUTH + 20)


def ground(folder: Path, tile_x: int, tile_y: int) -> float:
    """The Blender height of the centre of a tile of 48_50: the client's ground height there, with y up."""
    terrain = load_terrain(Js5Store(folder), 48, 50)
    return float(-ground_height(terrain, tile_x * 128 + 64, tile_y * 128 + 64))


def terrain_of(regions: scripting.Regions, index: int = 0) -> bpy.types.Object:
    return regions.collections[index].objects[0]


def world_vertices(obj: bpy.types.Object) -> list[tuple[float, float, float]]:
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.update()
    return [xyz(obj.matrix_world @ vertex.co) for vertex in mesh_of(obj).vertices]


def flat(points: list[tuple[float, float, float]]) -> list[float]:
    """The numbers of the points in one list, which pytest.approx can compare."""
    return [number for point in points for number in point]


# Issue 170, gap a: one entry point that takes the cache folder and the brightness, with the add-on not enabled.
def test_import_region_imports_a_region_as_the_operator_places_it(region_cache):
    regions = scripting.import_region(region_cache, 48, 50, brightness=0.8)

    (region,) = regions.collections
    assert region.name == "Region 48_50"
    scene = bpy.context.scene
    assert scene is not None
    assert region.name in scene.collection.children
    assert regions.appended == (False,)
    (report,) = regions.reports
    assert report is not None and report.tiles > 0 and not report.has_key
    terrain = terrain_of(regions)
    assert terrain.name == "Terrain 48_50"
    assert xyz(terrain.location) == (0.0, 0.0, 0.0)
    # With no region origin, a tile centre is where `region_terrain.tile_position` puts it.
    assert xyz(regions.tile_point(WEST + 10, SOUTH + 20)) == (
        10 * 128 + 64,
        20 * 128 + 64,
        ground(region_cache, 10, 20),
    )


# Issue 170, gap h: a chosen tile goes to the origin.
def test_the_centre_of_the_region_origin_tile_goes_to_the_blender_origin_at_its_ground_height(region_cache):
    plain = world_vertices(terrain_of(scripting.import_region(region_cache, 48, 50, brightness=0.8)))
    bpy.ops.wm.read_homefile(use_empty=True)

    regions = scripting.import_region(region_cache, 48, 50, brightness=0.8, origin_tile=ORIGIN_TILE)

    assert xyz(regions.tile_point(*ORIGIN_TILE)) == (0.0, 0.0, 0.0)
    centre = (10 * 128 + 64, 20 * 128 + 64, ground(region_cache, 10, 20))
    moved = world_vertices(terrain_of(regions))
    assert flat(moved) == pytest.approx(flat([(x - centre[0], y - centre[1], z - centre[2]) for x, y, z in plain]))
    # The tile to the east is 128 game units along x, at its own ground height.
    east = regions.tile_point(ORIGIN_TILE[0] + 1, ORIGIN_TILE[1])
    assert xyz(east) == pytest.approx((128.0, 0.0, ground(region_cache, 11, 20) - centre[2]))


def test_a_turn_of_90_degrees_puts_east_on_the_y_axis(region_cache):
    plain = world_vertices(
        terrain_of(scripting.import_region(region_cache, 48, 50, brightness=0.8, origin_tile=ORIGIN_TILE))
    )
    bpy.ops.wm.read_homefile(use_empty=True)

    regions = scripting.import_region(region_cache, 48, 50, brightness=0.8, origin_tile=ORIGIN_TILE, turn=90.0)

    # Counterclockwise seen from above: a point (x, y) goes to (-y, x).
    turned = world_vertices(terrain_of(regions))
    assert flat(turned) == pytest.approx(flat([(-y, x, z) for x, y, z in plain]), abs=1e-3)
    assert terrain_of(regions).rotation_euler.z == pytest.approx(math.pi / 2)
    assert xyz(regions.tile_point(*ORIGIN_TILE)) == pytest.approx((0.0, 0.0, 0.0))
    east = regions.tile_point(ORIGIN_TILE[0] + 1, ORIGIN_TILE[1])
    north = regions.tile_point(ORIGIN_TILE[0], ORIGIN_TILE[1] + 1)
    assert (east.x, east.y) == pytest.approx((0.0, 128.0), abs=1e-4)
    assert (north.x, north.y) == pytest.approx((-128.0, 0.0), abs=1e-4)


def test_a_region_origin_or_a_tile_outside_the_regions_is_refused(region_cache):
    with pytest.raises(ValueError, match=r"Tile \(3136, 3200\) is in none of the regions 48_50"):
        scripting.import_region(region_cache, 48, 50, brightness=0.8, origin_tile=(WEST + 64, SOUTH))
    assert len(bpy.data.collections) == 0

    regions = scripting.import_region(region_cache, 48, 50, brightness=0.8)
    with pytest.raises(ValueError, match=r"Tile \(3071, 3200\) is in none of the regions 48_50"):
        regions.tile_point(WEST - 1, SOUTH)


def test_no_region_and_a_region_named_twice_are_refused(region_cache):
    with pytest.raises(ValueError, match="at least one region"):
        scripting.import_regions(region_cache, [], brightness=0.8)
    with pytest.raises(ValueError, match="Region 48_50 is named twice"):
        scripting.import_regions(region_cache, [(48, 50), (48, 50)], brightness=0.8)
    with pytest.raises(ValueError, match="Region 48_50 is named twice"):
        scripting.import_regions(region_cache, [[48, 50], [48, 50]], brightness=0.8)  # pyrefly: ignore[bad-argument-type]
    assert len(bpy.data.collections) == 0


# Issue 170, gap j: the second run appends the saved region.
def test_with_a_saved_folder_the_first_call_saves_each_region_and_the_next_call_appends_it(region_cache, tmp_path):
    saved = tmp_path / "saved"
    arguments = {"brightness": 0.8, "origin_tile": ORIGIN_TILE, "turn": 90.0, "saved_folder": saved}
    first = scripting.import_region(region_cache, 48, 50, **arguments)
    expected = world_vertices(terrain_of(first))
    assert first.appended == (False,)
    assert [path.name for path in saved.iterdir()] == ["region-48_50.blend"]
    written = (saved / "region-48_50.blend").stat().st_mtime_ns
    bpy.ops.wm.read_homefile(use_empty=True)

    second = scripting.import_region(region_cache, 48, 50, **arguments)

    assert (second.appended, second.reports) == ((True,), (None,))
    assert flat(world_vertices(terrain_of(second))) == pytest.approx(flat(expected))
    assert xyz(second.tile_point(*ORIGIN_TILE)) == pytest.approx((0.0, 0.0, 0.0))
    assert (saved / "region-48_50.blend").stat().st_mtime_ns == written


def test_a_saved_region_of_another_brightness_is_imported_again_and_saved_again(region_cache, tmp_path):
    saved = tmp_path / "saved"
    scripting.import_region(region_cache, 48, 50, brightness=0.8, saved_folder=saved)
    bpy.ops.wm.read_homefile(use_empty=True)

    again = scripting.import_region(region_cache, 48, 50, brightness=0.6, saved_folder=saved)
    bpy.ops.wm.read_homefile(use_empty=True)
    third = scripting.import_region(region_cache, 48, 50, brightness=0.6, saved_folder=saved)

    assert (again.appended, third.appended) == ((False,), (True,))


@needs_snapshot_430
def test_two_regions_stand_side_by_side_and_their_terrain_meets_at_the_shared_edge():
    regions = scripting.import_regions(SNAPSHOT_430, [(48, 50), (49, 50)], brightness=0.8, origin_tile=(WEST, SOUTH))

    assert [collection.name for collection in regions.collections] == ["Region 48_50", "Region 49_50"]
    west, east = (terrain_of(regions, index) for index in (0, 1))
    # A region is 64 tiles of 128 game units wide (GLOSSARY.md, Region and Tile).
    assert east.location.x - west.location.x == pytest.approx(64 * 128)
    assert (east.location.y, east.location.z) == pytest.approx((west.location.y, west.location.z))
    edge_x = west.location.x + 64 * 128
    west_edge = {(round(y), round(z)) for x, y, z in world_vertices(west) if abs(x - edge_x) < 0.01}
    east_edge = {(round(y), round(z)) for x, y, z in world_vertices(east) if abs(x - edge_x) < 0.01}
    assert len(west_edge) >= 64
    assert west_edge == east_edge
    # A tile of the second region has its point one region to the east.
    point = regions.tile_point(WEST + 64 + 3, SOUTH + 5)
    assert (point.x, point.y) == pytest.approx((64 * 128 + 3 * 128, 5 * 128))


@needs_snapshot_430
def test_import_region_passes_the_wall_decoration_clearance_to_the_import():
    regions = scripting.import_region(SNAPSHOT_430, 48, 50, brightness=0.8, decoration_clearance=2.0)

    (report,) = regions.reports
    assert report is not None and report.scenery.moved_decorations > 0


def test_a_region_that_the_cache_lacks_is_refused_before_the_regions_before_it_are_imported(region_cache):
    # The fixture cache holds only region 48_50.
    with pytest.raises(region_import.RefusalError, match="The cache has no terrain for region 20_20"):
        scripting.import_regions(region_cache, [(48, 50), (20, 20)], brightness=0.8)

    assert len(bpy.data.collections) == 0


def test_a_save_that_fails_keeps_the_imported_region_and_warns(region_cache, tmp_path, monkeypatch):
    # On Windows, the move of the new file fails while another Blender has the saved region open.
    def fail(collection, path, key):
        raise PermissionError("the file is in use")

    monkeypatch.setattr(region_files, "save_region", fail)

    with pytest.warns(UserWarning, match=r"Region 48_50 was not saved to .*region-48_50.blend: the file is in use"):
        regions = scripting.import_region(region_cache, 48, 50, brightness=0.8, saved_folder=tmp_path / "saved")

    assert regions.appended == (False,)
    assert regions.collections[0].name == "Region 48_50"


SNAPSHOT = pytest.mark.skipif(
    not (os.environ.get("RSPS_SNAPSHOT_430_CACHE") and Path(os.environ["RSPS_SNAPSHOT_430_CACHE"]).is_dir()),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)


def snapshot() -> Path:
    return Path(os.environ["RSPS_SNAPSHOT_430_CACHE"])


def hidden_on(obj: bpy.types.Object, frame: int) -> tuple[bool, bool]:
    scene = bpy.context.scene
    assert scene is not None
    scene.frame_set(frame)
    return obj.hide_viewport, obj.hide_render


@SNAPSHOT
def test_a_spot_effect_at_a_point_plays_its_sequence_once_and_is_hidden_after_it():
    # The smoke puff 86 shows model 3076 with sequence 654 (fixtures/spot_effects). ap.fb ends the graphic when its
    # frame passes the last one, and frame 0 shows one tick longer than its duration (docs/research/spot-effects.md).
    durations = read_sequence(CacheClip(Js5Store(snapshot()), 654)).durations
    effect = scripting.create_spot_effect(
        snapshot(), 86, brightness=BRIGHTNESS, start=10, location=(128.0, 0.0, 0.0), height=40.0
    )

    assert effect.rig is not None and effect.end is not None
    assert effect.rig.location[:] == (128.0, 0.0, 40.0)
    assert effect.end == 10 + sum(durations) + 1
    strips = effect.rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore
    assert [round(strip.frame_start) for strip in strips] == [10]
    assert hidden_on(effect.mesh, 9) == (True, True)
    assert hidden_on(effect.mesh, 10) == (False, False)
    assert hidden_on(effect.mesh, effect.end - 1) == (False, False)
    assert hidden_on(effect.mesh, effect.end) == (True, True)


@SNAPSHOT
def test_a_spot_effect_on_a_joint_follows_the_joint():
    player = scripting.create_player(snapshot(), Look(), brightness=BRIGHTNESS)
    effect = scripting.create_spot_effect(snapshot(), 86, brightness=BRIGHTNESS, joint=(player.rig, "hand.R"))

    assert effect.rig is not None
    constraint = effect.rig.constraints[0]
    assert isinstance(constraint, bpy.types.ChildOfConstraint)
    assert (constraint.target, constraint.subtarget) == (player.rig, "hand.R")


@SNAPSHOT
def test_a_spot_effect_with_no_sequence_shows_on_its_start_frame_only_with_its_scale():
    # Spot effect 9 has no sequence (fixtures/spot_effects). ap.fb ends a graphic with no sequence on the next tick
    # (offset 2238, docs/research/spot-effects.md).
    effect = scripting.create_spot_effect(snapshot(), 9, brightness=BRIGHTNESS, start=5)

    assert (effect.rig, effect.end) == (None, 6)
    assert hidden_on(effect.mesh, 5) == (False, False)
    assert hidden_on(effect.mesh, 6) == (True, True)
    with pytest.raises(ValueError, match="no sequence"):
        scripting.bake_clip(effect, snapshot(), 654)


@SNAPSHOT
def test_a_spot_effect_takes_its_scale_and_turn_on_its_rig():
    # Spot effect 188 has width 256 and height 128, and 79 has the rotation 270 (fixtures/spot_effects). ej.c turns
    # (x, z) to (z, -x) once for each quarter (spot-effects.md).
    wide = scripting.create_spot_effect(snapshot(), 188, brightness=BRIGHTNESS)
    turned = scripting.create_spot_effect(snapshot(), 79, brightness=BRIGHTNESS)

    assert wide.rig is not None and turned.rig is not None
    assert wide.rig.scale[:] == pytest.approx((2.0, 2.0, 1.0))
    assert turned.rig.rotation_euler.z == pytest.approx(-math.radians(270))


@SNAPSHOT
def test_a_spot_effect_on_a_joint_with_a_height_is_refused_before_any_change():
    player = scripting.create_player(snapshot(), Look(), brightness=BRIGHTNESS)
    before = (len(bpy.data.objects), len(bpy.data.collections))

    with pytest.raises(ValueError, match="no location or height"):
        scripting.create_spot_effect(snapshot(), 86, brightness=BRIGHTNESS, joint=(player.rig, "head"), height=10.0)
    with pytest.raises(LookupError, match="no spot effect 99999"):
        scripting.create_spot_effect(snapshot(), 99999, brightness=BRIGHTNESS)
    assert (len(bpy.data.objects), len(bpy.data.collections)) == before


def posed_positions(obj: bpy.types.Object, frame: int) -> dict[int, Vector]:
    """The evaluated place of each model vertex of the mesh at a frame, in game units in the space of its rig."""
    scene = bpy.context.scene
    assert scene is not None
    scene.frame_set(frame)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    indices = appearance_preview.vertex_indices(mesh_of(obj))
    positions = {index: vertex.co.copy() for index, vertex in zip(indices, mesh.vertices, strict=True)}
    evaluated.to_mesh_clear()
    return positions


@SNAPSHOT
def test_a_player_chathead_plays_chathap1_with_its_chat_frames():
    # jg.p applies the frame and then the chat frame of each step to a chathead (docs/research/chatheads.md). The bake
    # fits joints to those posed vertices, so the mesh follows them to within the rounding of the fit.
    head = scripting.create_player_chathead(snapshot(), Look(), brightness=BRIGHTNESS)
    chathap1 = scripting.chat_clip("chathap1")
    scripting.bake_clip(head, snapshot(), chathap1, start=0)

    profile = shared_profile(snapshot())
    preset = look_preset(Look(), profile.kits, load_item_wear())
    model = player_head_model(
        preset.equipment, profile.kits, profile.items, profile.load_model, preset.colours, profile.palette
    )
    assert model.vertex_skins is not None
    clip = CacheClip(Js5Store(snapshot()), chathap1)
    chat = pose_vertices(tuple(model.vertices), tuple(model.vertex_skins), clip, chat=True)
    plain = pose_vertices(tuple(model.vertices), tuple(model.vertex_skins), clip)
    step = next(i for i, (a, b) in enumerate(zip(chat, plain, strict=True)) if a.vertices != b.vertices)
    frame = sum(f.ticks for f in chat[:step]) + 1
    shown = posed_positions(head.mesh, frame)
    expected = {i: Vector(game_to_blender(chat[step].vertices[i])) for i in shown}
    assert max((shown[i] - expected[i]).length for i in shown) < 1.0


def test_a_duplicated_player_keeps_the_texture_of_its_worn_item(cache):
    # Spec 183, section 1: Duplicate Player rebuilds the player from its stored settings and passes the textures.
    player = scripting.create_player(cache, Look(items=(6570,)), brightness=BRIGHTNESS)

    copy = appearance_collection.duplicate_player(player.collection, str(cache))

    materials = [m for m in mesh_of(appearance_collection.mesh_of(copy)).materials if m is not None]
    assert 16 in {material.get(appearance_preview.TEXTURE_KEY) for material in materials}


@SNAPSHOT
def test_the_chathead_of_man_bakes_chatneu1():
    head = scripting.create_npc_chathead(snapshot(), 3078, brightness=BRIGHTNESS)

    scripting.bake_clip(head, snapshot(), scripting.chat_clip("chatneu1"), start=0, repeat_until=100)

    assert head.collection.name == "Man chathead"
    strips = head.rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore
    assert [(round(s.frame_start), round(s.frame_end)) for s in strips] == [(0, 100)]


@SNAPSHOT
def test_an_npc_with_no_chathead_models_and_an_unknown_chat_clip_are_refused():
    # The cow 2805 has no chathead models (RuneLite's row in fixtures/npc/chathead-models.json).
    with pytest.raises(ValueError, match="no chathead models"):
        scripting.create_npc_chathead(snapshot(), 2805, brightness=BRIGHTNESS)
    with pytest.raises(ValueError, match="not a chat clip"):
        scripting.chat_clip("chathap9")
    assert not bpy.data.objects


def test_removing_a_player_with_a_textured_item_leaves_no_texture_material_or_image(cache):
    player = scripting.create_player(cache, Look(items=(6570,)), brightness=BRIGHTNESS)

    appearance_collection.remove_collection(player.collection)

    assert not [m for m in bpy.data.materials if appearance_preview.TEXTURE_KEY in m]
    assert not bpy.data.images
