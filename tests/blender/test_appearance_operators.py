import dataclasses
import json
import shutil
from pathlib import Path

import bmesh
import bpy
import pytest
from js5_builder import rewrite_cache

from rsps_toolkit.blender import (
    appearance_clip,
    appearance_collection,
    appearance_items,
    appearance_preview,
    appearance_props,
    preferences,
)
from rsps_toolkit.blender.face_materials import DEFAULT_BRIGHTNESS, srgb_to_linear
from rsps_toolkit.formats import cache_profile
from rsps_toolkit.formats.appearance_preset import AppearancePreset, dumps_preset, loads_preset
from rsps_toolkit.formats.colour import face_colour_to_rgb

FIXTURES = Path(__file__).parent.parent / "fixtures" / "appearance"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())


@pytest.fixture(autouse=True)
def registered(clean):
    for cls in (*appearance_props.classes, *appearance_collection.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    yield
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_collection.classes)):
        bpy.utils.unregister_class(cls)


def create(**options):
    return bpy.ops.rsps.create_appearance_preview(**options)  # pyrefly: ignore[missing-attribute]


def active():
    layer = bpy.context.view_layer
    assert layer is not None and layer.objects.active is not None
    return layer.objects.active


def mesh_of(obj):
    assert isinstance(obj.data, bpy.types.Mesh)
    return obj.data


def case(outfit, female, colours):
    return next(
        c for c in REFERENCE["cases"] if (c.get("outfit"), c["female"], c["colours"]) == (outfit, female, colours)
    )


def show(reference_case):
    preset = AppearancePreset(
        149, 430, reference_case["female"], tuple(reference_case["equipment"]), tuple(reference_case["colours"])
    )
    appearance_props.from_preset(bpy.context.scene.rs_appearance, preset)  # pyrefly: ignore[missing-attribute]
    return preset


def painted_last(before):
    """Faces not covered by an exactly stacked face, worked out from the client's recorded vertices and priorities."""
    last = {}
    for i, face in enumerate(before["faces"]):
        corners = [tuple(before["vertices"][v]) for v in face]
        start = corners.index(min(corners))
        key = tuple(corners[start:] + corners[:start])
        if key not in last or (before["render_priorities"][i], i) > last[key]:
            last[key] = (before["render_priorities"][i], i)
    return {i for _, i in last.values()}


@pytest.mark.parametrize("outfit", [None, "dragon_plate", "excalibur"])
@pytest.mark.parametrize("female", [False, True])
def test_preview_has_the_clients_geometry_and_lit_colours(dump, outfit, female):
    reference = case(outfit, female, [1, 2, 3, 4, 5])
    show(reference)
    assert create(dump_folder=str(dump)) == {"FINISHED"}
    parts = appearance_collection.parts(appearance_preview.collection_of(active()))  # pyrefly: ignore[bad-argument-type]
    assert [obj.get(appearance_collection.PART_KEY) for obj in parts] == ["Body"] + (
        ["Weapon"] if outfit == "excalibur" else []
    )
    before = reference["before_lighting"]
    kept = [i for i, face in enumerate(before["faces"]) if len(set(face)) == 3 and i in painted_last(before)]
    by_corners = {tuple(before["faces"][i]): i for i in kept}
    seen_vertices, seen_faces = set(), []
    for obj in parts:
        mesh = mesh_of(obj)
        model_vertex = appearance_preview.vertex_indices(mesh)
        seen_vertices |= set(model_vertex)
        colours = mesh.color_attributes[appearance_preview.LIT_ATTRIBUTE].data  # pyrefly: ignore[missing-attribute]
        for polygon in mesh.polygons:
            face = by_corners[tuple(model_vertex[v] for v in polygon.vertices)]  # pyrefly: ignore[not-iterable]
            seen_faces.append(face)
            flat = before["flat_shaded"][face]
            shades = (
                [reference["lit"]["shade_a"][face]] * 3
                if flat
                else [reference["lit"][k][face] for k in ("shade_a", "shade_b", "shade_c")]
            )
            expected = [
                tuple(srgb_to_linear(c / 255) for c in face_colour_to_rgb(shade, DEFAULT_BRIGHTNESS))
                for shade in shades
            ]
            for corner, want in zip(polygon.loop_indices, expected, strict=True):
                assert tuple(colours[corner].color[:3]) == pytest.approx(want, abs=1e-6)
    assert seen_vertices == set(range(before["vertex_count"]))
    assert sorted(seen_faces) == kept


def test_preview_stores_the_source_preset(dump):
    preset = show(case("dragon_plate", True, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    obj = active()
    assert loads_preset(appearance_preview.collection_of(obj)[appearance_preview.PRESET_KEY]) == preset  # pyrefly: ignore[unsupported-operation]


def test_a_missing_model_cancels_and_creates_nothing(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    rewrite_cache(dump, lambda parts: parts["models"].pop(230))
    with pytest.raises(RuntimeError, match="Model 230"):
        create(dump_folder=str(dump))
    assert not bpy.data.objects


def test_no_dump_folder_is_an_error(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    with pytest.raises(RuntimeError, match="Set the Cache folder"):
        create()


def update(**options):
    return bpy.ops.rsps.update_appearance_preview(**options)  # pyrefly: ignore[missing-attribute]


def players():
    return [c for c in bpy.data.collections if appearance_preview.PRESET_KEY in c]


def stored(collection):
    return loads_preset(collection[appearance_preview.PRESET_KEY])


def test_update_replaces_the_players_contents_and_the_stored_preset(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    old_name = players()[0].name
    preset = show(case("dragon_plate", True, [1, 2, 3, 4, 5]))
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    (collection,) = players()
    assert collection.name == old_name == "Player"
    assert stored(collection) == preset
    expected = case("dragon_plate", True, [1, 2, 3, 4, 5])["before_lighting"]["vertex_count"]
    assert len(appearance_collection.mesh_data(collection).vertices) == expected
    assert active() is appearance_collection.mesh_of(collection)
    assert appearance_collection.mesh_of(collection).name == "Player"


def test_update_turns_culling_on_again_for_the_shared_lit_material(dump):
    # The user chose that Update turns culling on again for a lit material made before players culled (issue 28,
    # decision 3, 2026-11-10).
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    material = bpy.data.materials[appearance_preview.MATERIAL_NAME]
    material.use_backface_culling = False
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert material.use_backface_culling


WALK = Path(__file__).parent.parent / "fixtures" / "animation149" / "walk"


def baked_player(dump, method, clip=WALK):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, clip)
    return collection


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_update_bakes_the_players_clip_again_and_leaves_no_old_action(dump, capfd, method):
    baked_player(dump, method)
    capfd.readouterr()
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert "baked clip" not in capfd.readouterr().out
    (rebuilt,) = players()
    assert appearance_collection.baked_clip(rebuilt) == method
    assert not appearance_collection.is_edited(rebuilt)
    users = [action for action in bpy.data.actions if action.users == 0]
    assert users == []


def test_update_keeps_the_clip_strips_frames_and_the_users_own_animation(dump):
    collection = baked_player(dump, "bones")
    appearance_clip.bake_clip_to_rig(collection, WALK.parent / "idle", start=60)
    rig = appearance_collection.armature_of(collection)
    wave, step = bpy.data.actions.new("wave"), bpy.data.actions.new("step")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    track = rig.animation_data.nla_tracks.new()  # pyrefly: ignore[missing-attribute]
    track.name = "mine"
    placed = track.strips.new("step", 5, step)
    placed.influence = 0.5
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    (rebuilt,) = players()
    animation = appearance_collection.armature_of(rebuilt).animation_data
    assert animation.action == wave  # pyrefly: ignore[missing-attribute]
    (copied,) = animation.nla_tracks["mine"].strips  # pyrefly: ignore[missing-attribute]
    assert (copied.action, copied.frame_start, round(copied.influence, 3)) == (step, 5, 0.5)
    clips = animation.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore[missing-attribute]
    assert [strip.frame_start for strip in clips] == [1, 60]
    assert not appearance_collection.is_edited(rebuilt)


def duplicate(**options):
    return bpy.ops.rsps.duplicate_player(**options)  # pyrefly: ignore[missing-attribute]


def test_duplicate_builds_a_copy_beside_the_players_with_its_own_clips_and_animation(dump):
    collection = baked_player(dump, "bones")
    appearance_clip.bake_clip_to_rig(collection, WALK.parent / "idle", start=60)
    rig = appearance_collection.armature_of(collection)
    wave, step = bpy.data.actions.new("wave"), bpy.data.actions.new("step")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    track = rig.animation_data.nla_tracks.new()  # pyrefly: ignore[missing-attribute]
    track.name = "mine"
    track.strips.new("step", 5, step)
    originals = {strip.action for track in rig.animation_data.nla_tracks for strip in track.strips}  # pyrefly: ignore[missing-attribute]
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    # The user chose that a copy is named after the original with Blender's next number (plan 14, 2026-11-10).
    assert copy.name == "Player.001"
    assert stored(copy) == stored(collection)
    assert appearance_collection.armature_of(copy).name == f"{copy.name}_rig"
    assert [obj.name for obj in appearance_collection.parts(copy)] == [copy.name]
    assert x_extent(copy)[0] > x_extent(collection)[1]
    animation = appearance_collection.armature_of(copy).animation_data
    clips = animation.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore[missing-attribute]
    assert [strip.frame_start for strip in clips] == [1, 60]
    (mine,) = animation.nla_tracks["mine"].strips  # pyrefly: ignore[missing-attribute]
    assert mine.frame_start == 5
    copied = {strip.action for track in animation.nla_tracks for strip in track.strips} | {animation.action}  # pyrefly: ignore[missing-attribute]
    assert not copied & (originals | {wave})
    assert animation.action.name.startswith("wave") and mine.action.name.startswith("step")  # pyrefly: ignore[missing-attribute]
    assert rig.animation_data.action == wave  # pyrefly: ignore[missing-attribute]
    assert panel().source_player == copy.name
    assert active() is appearance_collection.mesh_of(copy)
    assert not appearance_collection.is_edited(copy) and not appearance_collection.is_edited(collection)


def test_duplicating_an_edited_player_is_refused_and_adds_nothing(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    appearance_collection.mesh_data(collection).vertices[0].co.z += 7
    objects = set(bpy.data.objects)
    with pytest.raises(RuntimeError, match="has edits"):
        duplicate(dump_folder=str(dump))
    assert players() == [collection] and set(bpy.data.objects) == objects


def test_duplicating_a_player_in_edit_mode_is_refused_and_adds_nothing(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    obj = appearance_collection.mesh_of(collection)
    bpy.ops.object.mode_set(mode="EDIT")
    with pytest.raises(RuntimeError, match="Leave Edit Mode"):
        duplicate(dump_folder=str(dump))
    assert players() == [collection] and obj.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")


def test_duplicating_a_player_whose_clip_cannot_be_baked_again_adds_nothing(dump, tmp_path):
    clip = tmp_path / "walk"
    shutil.copytree(WALK, clip)
    collection = baked_player(dump, "bones", clip)
    shutil.rmtree(clip)
    objects = set(bpy.data.objects)
    with pytest.raises(RuntimeError, match="The clip folder lacks"):
        duplicate(dump_folder=str(dump))
    assert players() == [collection] and set(bpy.data.objects) == objects


def location_curve(action, bone):
    (bag,) = action.layers[0].strips[0].channelbags
    return bag.fcurves.find(f'pose.bones["{bone}"].location', index=2)


def test_strips_sharing_one_action_on_the_original_share_one_copied_action_on_the_duplicate(dump):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    bone = next(b for b in rig.pose.bones if not b.name.startswith(appearance_collection.BONE_PREFIX))  # pyrefly: ignore[missing-attribute]
    bone.keyframe_insert("location", frame=1)
    animation = rig.animation_data
    assert animation is not None and animation.action is not None and animation.action_slot is not None
    wave, slot = animation.action, animation.action_slot
    animation.action = None
    track = animation.nla_tracks.new()
    track.name = "mine"
    for start in (5, 200):
        track.strips.new("wave", start, wave).action_slot = slot
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    strips = appearance_collection.armature_of(copy).animation_data.nla_tracks["mine"].strips  # pyrefly: ignore[missing-attribute]
    actions = {strip.action for strip in strips}
    assert len(actions) == 1 and wave not in actions
    assert [strip.action_slot.identifier for strip in strips] == [slot.identifier] * 2


def test_keys_changed_on_a_duplicate_leave_the_originals_keys_alone(dump):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    bone = next(b for b in rig.pose.bones if not b.name.startswith(appearance_collection.BONE_PREFIX))  # pyrefly: ignore[missing-attribute]
    bone.location = (0.0, 0.0, 1.0)
    bone.keyframe_insert("location", frame=1)
    animation = rig.animation_data
    assert animation is not None and animation.action is not None and animation.action_slot is not None
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    copied = appearance_collection.armature_of(copy).animation_data
    assert copied is not None and copied.action is not None and copied.action is not animation.action
    assert copied.action_slot is not None and copied.action_slot.identifier == animation.action_slot.identifier
    location_curve(copied.action, bone.name).keyframe_points[0].co.y = 5.0
    assert location_curve(animation.action, bone.name).keyframe_points[0].co.y == 1.0


def test_duplicating_a_player_with_a_shape_key_clip_bakes_the_copy_its_own_keys(dump):
    collection = baked_player(dump, "shape keys")
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    assert appearance_collection.baked_clip(copy) == "shape keys"
    ours, theirs = (appearance_collection.mesh_data(c).shape_keys for c in (copy, collection))
    assert ours is not None and theirs is not None and ours is not theirs
    assert [key.name for key in ours.key_blocks] == [key.name for key in theirs.key_blocks]
    for mine, original in zip(ours.key_blocks, theirs.key_blocks, strict=True):
        assert [point.co[:] for point in mine.data] == [point.co[:] for point in original.data]  # pyrefly: ignore[missing-attribute]
    assert ours.animation_data.action is not theirs.animation_data.action  # pyrefly: ignore[missing-attribute]
    keys = [appearance_collection.keys_hash(key.animation_data.action) for key in (ours, theirs)]  # pyrefly: ignore[missing-attribute]
    assert keys[0] == keys[1]
    assert not appearance_collection.is_edited(copy)


def test_duplicate_leaves_the_panel_on_the_original_while_it_holds_changes_not_yet_applied(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    changed = show(case("dragon_plate", True, [1, 2, 3, 4, 5]))
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    assert len(players()) == 2
    assert panel().source_player == collection.name
    assert appearance_props.to_preset(panel()) == changed


def test_duplicating_an_old_label_only_player_gives_the_copy_joints_and_says_its_own_keys_stayed_behind(dump, capfd):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    del rig[appearance_collection.JOINT_RIG_KEY]
    wave = bpy.data.actions.new("wave")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    capfd.readouterr()
    assert duplicate(dump_folder=str(dump)) == {"FINISHED"}
    assert "were not copied" in capfd.readouterr().out
    copy = next(c for c in players() if c is not collection)
    copy_rig = appearance_collection.armature_of(copy)
    assert appearance_collection.is_joint_rig(copy_rig)
    assert copy_rig.animation_data.action is None  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.baked_clip(copy) == "bones"
    assert rig.animation_data.action == wave  # pyrefly: ignore[missing-attribute]


@pytest.mark.parametrize("method", ["shape keys", "bones"])
@pytest.mark.parametrize("rebuild", [duplicate, update], ids=["duplicate", "update"])
def test_duplicate_and_update_bake_the_clips_again_without_changing_the_scenes_rate_or_range(dump, method, rebuild):
    baked_player(dump, method)
    scene = bpy.context.scene
    assert scene is not None
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.frame_start, scene.frame_end = 3, 500
    assert rebuild(dump_folder=str(dump)) == {"FINISHED"}
    assert (scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end) == (24, 1.0, 3, 500)
    if active().mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def test_update_moves_a_users_strip_from_the_clip_track_to_the_users_track(dump):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    turn = bpy.data.actions.new("turn")
    clips = rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK]  # pyrefly: ignore[missing-attribute]
    clips.strips.new("turn", 270, turn)
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    (rebuilt,) = players()
    tracks = appearance_collection.armature_of(rebuilt).animation_data.nla_tracks  # pyrefly: ignore[missing-attribute]
    assert [s.frame_start for s in tracks[appearance_clip.CLIP_TRACK].strips] == [1]
    assert [(s.frame_start, s.action) for s in tracks[appearance_clip.USER_TRACK].strips] == [(270, turn)]
    assert [track.name for track in tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    assert turn.users > 0


def test_update_keeps_the_users_track_above_the_clips(dump):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    turn = bpy.data.actions.new("turn")
    rig.animation_data.nla_tracks[appearance_clip.USER_TRACK].strips.new("turn", 270, turn)  # pyrefly: ignore[missing-attribute]
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    (rebuilt,) = players()
    tracks = appearance_collection.armature_of(rebuilt).animation_data.nla_tracks  # pyrefly: ignore[missing-attribute]
    assert [track.name for track in tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    assert [s.action for s in tracks[appearance_clip.USER_TRACK].strips] == [turn]
    assert appearance_collection.armature_of(rebuilt).animation_data.action_blend_type == "COMBINE"  # pyrefly: ignore[missing-attribute]


def test_update_from_pose_mode_leaves_the_rebuilt_rig_active_in_pose_mode(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    rig = appearance_collection.armature_of(collection)
    bpy.context.view_layer.objects.active = rig  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="POSE")
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    (rebuilt,) = players()
    assert active() is appearance_collection.armature_of(rebuilt)
    assert active().mode == "POSE"
    bpy.ops.object.mode_set(mode="OBJECT")


def test_update_gives_an_old_label_only_player_joints_and_says_its_own_keys_stayed_behind(dump, capfd):
    collection = baked_player(dump, "bones")
    rig = appearance_collection.armature_of(collection)
    del rig[appearance_collection.JOINT_RIG_KEY]
    rig.animation_data.action = bpy.data.actions.new("wave")  # pyrefly: ignore[missing-attribute]
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    capfd.readouterr()
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert "were not carried over" in capfd.readouterr().out
    (rebuilt,) = players()
    new_rig = appearance_collection.armature_of(rebuilt)
    assert appearance_collection.is_joint_rig(new_rig)
    assert new_rig.animation_data.action is None  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.baked_clip(rebuilt) == "bones"


def test_update_warns_when_the_clip_folder_is_gone(dump, capfd, tmp_path):
    clip = tmp_path / "walk"
    shutil.copytree(WALK, clip)
    baked_player(dump, "bones", clip)
    shutil.rmtree(clip)
    capfd.readouterr()
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert "the baked clip could not be baked again" in capfd.readouterr().out
    (rebuilt,) = players()
    assert appearance_collection.baked_clip(rebuilt) is None


def test_update_of_a_player_baked_without_a_record_warns_that_the_clip_was_removed(dump, capfd):
    collection = baked_player(dump, "shape keys")
    del collection[appearance_collection.CLIP_KEY]
    capfd.readouterr()
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert "the baked clip (shape keys) was removed; bake it again" in capfd.readouterr().out


def test_update_of_a_player_without_a_clip_does_not_warn_about_one(dump, capfd):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    capfd.readouterr()
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert "baked clip" not in capfd.readouterr().out


def test_a_failed_update_keeps_the_old_player_and_preset(dump):
    first = show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    mesh = appearance_collection.mesh_data(collection)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    rewrite_cache(dump, lambda parts: parts["models"].pop(3379))
    with pytest.raises(RuntimeError, match="Model 3379"):
        update(dump_folder=str(dump))
    assert players() == [collection]
    assert appearance_collection.mesh_data(collection) is mesh
    assert stored(collection) == first
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1


def test_repeated_updates_do_not_leak_data(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    materials = len(bpy.data.materials)
    for outfit in ("dragon_plate", "excalibur", None, "dragon_chain"):
        show(case(outfit, False, [0, 0, 0, 0, 0]))
        assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert len(players()) == 1
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1 and len(bpy.data.materials) == materials
    assert len(bpy.data.objects) == 2


def test_update_needs_a_player(dump):
    with pytest.raises(RuntimeError, match="poll"):
        update(dump_folder=str(dump))


def test_an_edited_player_is_kept_and_the_update_is_a_separate_copy(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (old,) = players()
    appearance_collection.mesh_data(old).vertices[0].co.x += 7
    edited_x = appearance_collection.mesh_data(old).vertices[0].co.x
    preset = show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert len(players()) == 2
    assert appearance_collection.mesh_data(old).vertices[0].co.x == edited_x
    new = next(c for c in players() if c is not old)
    assert stored(new) == preset
    assert not appearance_collection.is_edited(new)
    assert active() is appearance_collection.mesh_of(new)


def rig_location(collection=None):
    if collection is None:
        collection = appearance_preview.collection_of(active())
        assert collection is not None
    location = appearance_collection.armature_of(collection).location
    return (location.x, location.y, location.z)


def x_extent(collection):
    obj = appearance_collection.mesh_of(collection)
    xs = [(obj.matrix_world @ vertex.co).x for vertex in mesh_of(obj).vertices]
    return min(xs), max(xs)


def test_the_copy_of_an_edited_player_stands_to_the_right_of_it(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (old,) = players()
    appearance_collection.mesh_data(old).vertices[0].co.z += 7
    update(dump_folder=str(dump))
    new = next(c for c in players() if c is not old)
    assert x_extent(new)[0] == pytest.approx(x_extent(old)[1] + appearance_collection.PLAYER_GAP, abs=1e-3)
    assert not appearance_collection.is_edited(new)


def test_a_second_player_is_created_to_the_right_of_the_first(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (first,) = players()
    assert rig_location(first) == (0, 0, 0)
    create(dump_folder=str(dump))
    second = next(c for c in players() if c is not first)
    assert x_extent(second)[0] == pytest.approx(x_extent(first)[1] + appearance_collection.PLAYER_GAP, abs=1e-3)
    assert not appearance_collection.is_edited(second)


def test_two_players_keep_their_own_mesh_and_rig_data(dump):
    # Issue 12 asks that two players built in one file use their own mesh and armature data, and its decisions 1 and 2
    # (2026-11-10) set this check: every part's mesh, the Excalibur player's Weapon included, and the rig, and that
    # moving a vertex of one player leaves the other unedited.
    show(case("excalibur", False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    create(dump_folder=str(dump))
    first, second = players()
    first_parts, second_parts = appearance_collection.parts(first), appearance_collection.parts(second)
    assert len(first_parts) == len(second_parts) == 2
    assert not {obj.data for obj in first_parts} & {obj.data for obj in second_parts}
    assert appearance_collection.armature_data(first) != appearance_collection.armature_data(second)
    appearance_collection.mesh_data(first).vertices[0].co.x += 1
    assert appearance_collection.is_edited(first) and not appearance_collection.is_edited(second)


def test_updating_a_player_that_stands_aside_keeps_it_there(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    create(dump_folder=str(dump))
    location = rig_location()
    assert location[0] > 0
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(dump_folder=str(dump))
    assert rig_location() == location


def test_updating_a_moved_turned_and_scaled_player_keeps_it_so(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (old,) = players()
    rig = appearance_collection.armature_of(old)
    rig.location = (40.0, -12.0, 3.0)
    rig.rotation_euler.z = 1.2
    rig.scale = (2.0, 2.0, 2.0)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(dump_folder=str(dump))
    (player,) = players()
    rig = appearance_collection.armature_of(player)
    assert rig_location(player) == (40.0, -12.0, 3.0)
    assert rig.rotation_euler.z == pytest.approx(1.2)
    assert (rig.scale.x, rig.scale.y, rig.scale.z) == (2.0, 2.0, 2.0)
    assert not appearance_collection.is_edited(player)


def test_updating_a_player_keeps_its_rigs_parent_and_constraints(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (old,) = players()
    anchor = bpy.data.objects.new("Anchor", None)
    bpy.context.scene.collection.objects.link(anchor)  # pyrefly: ignore[missing-attribute]
    anchor.location = (5.0, 0.0, 0.0)
    rig = appearance_collection.armature_of(old)
    rig.parent = anchor
    rig.constraints.new("LIMIT_ROTATION")
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(dump_folder=str(dump))
    (player,) = players()
    rig = appearance_collection.armature_of(player)
    assert rig.parent == anchor
    assert [constraint.type for constraint in rig.constraints] == ["LIMIT_ROTATION"]


def test_one_undo_restores_the_previous_player(dump):
    first = show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    vertices = len(appearance_collection.mesh_data(players()[0]).vertices)
    # Background Blender pushes undo states only when asked, so the test pushes one after each operator.
    bpy.ops.ed.undo_push(message="Player created")
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(dump_folder=str(dump))
    bpy.ops.ed.undo_push(message="Player updated")
    assert len(appearance_collection.mesh_data(players()[0]).vertices) != vertices
    bpy.ops.ed.undo()
    (collection,) = players()
    assert len(appearance_collection.mesh_data(collection).vertices) == vertices
    assert stored(collection) == first


def test_empty_equipment_cancels_with_a_message_and_creates_nothing(dump):
    appearance_props.from_preset(
        bpy.context.scene.rs_appearance,  # pyrefly: ignore[missing-attribute]
        AppearancePreset(149, 430, False, (0,) * 12, (0,) * 5),
    )
    with pytest.raises(RuntimeError, match="nothing to assemble"):
        create(dump_folder=str(dump))
    assert not bpy.data.objects and not bpy.data.collections


def test_update_refuses_a_player_holding_objects_the_add_on_did_not_make_and_changes_nothing(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    mesh = appearance_collection.mesh_data(collection)
    collection.objects.link(bpy.data.objects.new("MyEmpty", None))
    collection.objects.link(bpy.data.objects.new("MyCamera", bpy.data.cameras.new("MyCamera")))
    cameras = len(bpy.data.cameras)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    with pytest.raises(RuntimeError, match="MyEmpty, MyCamera"):
        update(dump_folder=str(dump))
    assert players() == [collection]
    assert appearance_collection.mesh_data(collection) is mesh
    assert sorted(obj.name for obj in collection.objects) == ["MyCamera", "MyEmpty", "Player", "Player_rig"]
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1 and len(bpy.data.cameras) == cameras


def test_update_refuses_a_player_in_edit_mode_and_keeps_the_edit(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = players()
    obj = appearance_collection.mesh_of(collection)
    bpy.ops.object.mode_set(mode="EDIT")
    edited = bmesh.from_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    edited.verts.ensure_lookup_table()
    edited.verts[0].co.x += 50
    moved = edited.verts[0].co.x
    bmesh.update_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    with pytest.raises(RuntimeError, match="Edit Mode"):
        update(dump_folder=str(dump))
    assert players() == [collection] and obj.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")
    assert appearance_collection.mesh_data(collection).vertices[0].co.x == pytest.approx(moved)


@pytest.mark.parametrize("kind", ["mesh", "armature"])
def test_create_refuses_while_any_mesh_or_armature_is_in_edit_mode_and_changes_nothing(dump, kind):
    show(case(None, False, [0, 0, 0, 0, 0]))
    if kind == "mesh":
        other = bpy.data.objects.new("Other", bpy.data.meshes.new("Other"))
    else:
        other = bpy.data.objects.new("Other", bpy.data.armatures.new("Other"))
    assert bpy.context.scene is not None
    bpy.context.scene.collection.objects.link(other)
    layer = bpy.context.view_layer
    assert layer is not None
    layer.objects.active = other
    bpy.ops.object.mode_set(mode="EDIT")
    with pytest.raises(RuntimeError, match="Leave Edit Mode on Other"):
        create(dump_folder=str(dump))
    assert players() == [] and other.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")


def panel():
    return bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]


def make_player(dump, outfit):
    show(case(outfit, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    (collection,) = [c for c in players() if c.name not in seen]
    seen.add(collection.name)
    return collection


seen: set[str] = set()


def test_create_ties_the_panel_to_the_new_player(dump):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    assert panel().source_player == players()[0].name


def test_updating_a_player_the_panel_is_not_tied_to_is_refused_and_changes_nothing(dump):
    seen.clear()
    first = make_player(dump, None)
    second = make_player(dump, "dragon_plate")
    stored_second = stored(second)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    assert panel().source_player == second.name
    with pytest.raises(RuntimeError, match="Load Player Settings"):
        update(dump_folder=str(dump))
    assert stored(second) == stored_second and len(players()) == 2


def test_load_player_settings_fills_the_panel_from_the_players_stored_preset(dump):
    seen.clear()
    first = make_player(dump, None)
    make_player(dump, "dragon_plate")
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.load_player_settings() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert appearance_props.to_preset(panel()) == stored(first)
    assert panel().source_player == first.name
    assert update(dump_folder=str(dump)) == {"FINISHED"}


def select(obj):
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    appearance_collection.follow_selection(bpy.context)


def test_selecting_another_player_loads_its_settings_into_the_panel(dump):
    seen.clear()
    first = make_player(dump, None)
    make_player(dump, "dragon_plate")
    select(appearance_collection.armature_of(first))
    assert appearance_props.to_preset(panel()) == stored(first)
    assert panel().source_player == first.name
    assert not appearance_collection.holds_unapplied_settings(panel())


def test_selecting_a_players_weapon_loads_its_settings(armed_dump):
    seen.clear()
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(armed_dump))
    (plain,) = players()
    appearance_props.from_preset(panel(), AppearancePreset(149, 430, False, ARMED, (0,) * 5))
    create(dump_folder=str(armed_dump))
    armed = next(c for c in players() if c is not plain)
    select(appearance_collection.mesh_of(plain))
    (weapon,) = (obj for obj in armed.objects if obj.get(appearance_collection.PART_KEY) == "Weapon")
    select(weapon)
    assert panel().source_player == armed.name
    assert appearance_props.to_preset(panel()) == stored(armed)


def test_selecting_another_player_keeps_changes_not_yet_applied_with_update(dump):
    seen.clear()
    first = make_player(dump, None)
    second = make_player(dump, "dragon_plate")
    panel().colours[0] = 1
    changed = appearance_props.to_preset(panel())
    select(appearance_collection.mesh_of(first))
    assert appearance_props.to_preset(panel()) == changed
    assert panel().source_player == second.name
    assert appearance_collection.holds_unapplied_settings(panel())


def test_selecting_a_player_keeps_the_settings_of_a_preset_file(dump):
    seen.clear()
    first = make_player(dump, None)
    from_file = show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = ""
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == ""
    assert appearance_props.to_preset(panel()) == from_file


def test_selecting_an_object_of_no_player_leaves_the_panel_as_it_is(dump):
    seen.clear()
    first = make_player(dump, None)
    lamp = bpy.data.objects.new("Lamp", bpy.data.lights.new("Lamp", "POINT"))
    bpy.context.scene.collection.objects.link(lamp)  # pyrefly: ignore[missing-attribute]
    select(lamp)
    assert panel().source_player == first.name
    assert appearance_props.to_preset(panel()) == stored(first)


def test_selecting_a_renamed_player_whose_settings_the_panel_holds_ties_the_panel_to_it(dump):
    seen.clear()
    first = make_player(dump, None)
    first.name = "Guard"
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == "Guard"


def test_a_panel_tied_to_a_deleted_player_keeps_its_settings_and_may_update_another(dump):
    seen.clear()
    first = make_player(dump, None)
    second = make_player(dump, "dragon_plate")
    held = appearance_props.to_preset(panel())
    appearance_collection.remove_collection(second)
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == ""
    assert appearance_props.to_preset(panel()) == held
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert stored(players()[0]) == held


def test_a_player_whose_settings_the_panel_refuses_leaves_the_panel_and_says_why(dump):
    seen.clear()
    first = make_player(dump, None)
    second = make_player(dump, "dragon_plate")
    first[appearance_preview.PRESET_KEY] = dumps_preset(dataclasses.replace(stored(first), client_revision=170))
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == second.name
    assert "client revision 170" in panel().last_error


def test_the_panel_follows_the_active_player_after_an_undo(dump):
    seen.clear()
    first = make_player(dump, None)
    make_player(dump, "dragon_plate")
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    appearance_collection.follow_active_player()
    assert panel().source_player == first.name


def test_a_panel_loaded_from_a_preset_file_may_update_any_player(dump):
    seen.clear()
    make_player(dump, None)
    panel().source_player = ""
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = ""
    assert update(dump_folder=str(dump)) == {"FINISHED"}


def test_an_edited_players_copy_becomes_the_tied_player(dump):
    seen.clear()
    first = make_player(dump, None)
    appearance_collection.mesh_data(first).vertices[0].co.x += 7
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = first.name
    update(dump_folder=str(dump))
    copy = next(c for c in players() if c is not first)
    assert panel().source_player == copy.name


ARMED = (0, 0, 0, 512 + 1333, 274, 512 + 1201, 282, 292, 256, 289, 298, 266)


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_update_bakes_a_clip_with_held_items_again_with_them(armed_dump, method):
    appearance_props.from_preset(bpy.context.scene.rs_appearance, AppearancePreset(149, 430, False, ARMED, (0,) * 5))  # pyrefly: ignore[missing-attribute]
    create(dump_folder=str(armed_dump))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, FIXTURES.parent / "animation149/held-1365", action=True, dump_folder=str(armed_dump))
    assert update(dump_folder=str(armed_dump)) == {"FINISHED"}
    (rebuilt,) = players()
    names = sorted(obj.name for obj in appearance_collection.parts(rebuilt))
    assert names == ["Player", "Player Shield", "Player Steel axe", "Player Weapon"]
    axe = next(obj for obj in appearance_collection.parts(rebuilt) if obj.name == "Player Steel axe")
    bpy.context.scene.frame_set(1)  # pyrefly: ignore[missing-attribute]
    assert not axe.hide_viewport
    assert not appearance_collection.is_edited(rebuilt)


def count_item_catalog_loads(monkeypatch):
    """Wrap the item catalog reader so a test sees the cache folder of each parse. The user accepted tying the count to
    the reader's name (spec of the shared catalog cache, Testing Decisions, seam 2)."""
    loads = []
    real = cache_profile.read_items

    def counted(store):
        loads.append(store.folder)
        return real(store)

    monkeypatch.setattr(cache_profile, "read_items", counted)
    return loads


def test_create_twice_and_update_once_read_the_item_catalog_once(dump, monkeypatch):
    # The user chose that Create and Update share one parsed copy of the catalogs per cache folder (issue 29,
    # decision 2, 2026-11-10).
    loads = count_item_catalog_loads(monkeypatch)
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(dump_folder=str(dump))
    create(dump_folder=str(dump))
    assert update(dump_folder=str(dump)) == {"FINISHED"}
    assert loads == [dump]


def test_create_reuses_the_item_catalog_the_panel_read(dump, monkeypatch):
    # The user chose that the panel and Create share one parsed copy of the catalogs per cache folder (issue 29,
    # decision 2, 2026-11-10). Item 35 is named Excalibur in the fixture ItemDefinitions.json.
    monkeypatch.setattr(preferences, "cache_folder", lambda: dump)
    loads = count_item_catalog_loads(monkeypatch)
    assert appearance_items.item_name(35) == "Excalibur"
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert loads == [dump]


def test_changing_the_dump_folder_preference_uses_that_folders_item_catalog(dump, monkeypatch, tmp_path_factory):
    # The user asked that changing the cache folder preference uses that folder's catalog, as before (spec of the
    # shared catalog cache, user story 5).
    other = tmp_path_factory.mktemp("other_dump")
    shutil.copytree(dump, other, dirs_exist_ok=True)
    rewrite_cache(other, rename_item(35, "Excalibur", "Renamed sword"))
    loads = count_item_catalog_loads(monkeypatch)
    monkeypatch.setattr(preferences, "cache_folder", lambda: dump)
    assert appearance_items.item_name(35) == "Excalibur"
    monkeypatch.setattr(preferences, "cache_folder", lambda: other)
    assert appearance_items.item_name(35) == "Renamed sword"
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert loads == [dump, other]


def test_a_missing_item_group_names_the_preference_at_every_create(dump):
    # The user asked that a missing catalog gives the same message at every Create (spec of the shared catalog cache,
    # user story 6). spec/remove-dumper-and-legacy-revisions.md made the message name the Cache folder preference.
    rewrite_cache(dump, lambda parts: parts["items"].clear())
    show(case(None, False, [0, 0, 0, 0, 0]))
    for _ in range(2):
        with pytest.raises(RuntimeError, match=r"no group 10 .*Set the Cache folder in the add-on preferences"):
            create(dump_folder=str(dump))
    assert not players()


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_a_held_item_bake_reuses_the_item_catalog_create_read(armed_dump, monkeypatch, method):
    # The user chose that held-item bakes share Create's parsed copy of the catalogs (issue 29, decision 2,
    # 2026-11-10).
    loads = count_item_catalog_loads(monkeypatch)
    appearance_props.from_preset(bpy.context.scene.rs_appearance, AppearancePreset(149, 430, False, ARMED, (0,) * 5))  # pyrefly: ignore[missing-attribute]
    create(dump_folder=str(armed_dump))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, FIXTURES.parent / "animation149/held-1365", action=True, dump_folder=str(armed_dump))
    assert "Player Steel axe" in [obj.name for obj in appearance_collection.parts(collection)]
    assert loads == [armed_dump]


def rename_item(item_id, old, new):
    """A cache change that renames an item, by replacing the zero-ended name text in its definition."""

    def change(parts):
        parts["items"][item_id] = parts["items"][item_id].replace(old.encode() + b"\0", new.encode() + b"\0")

    return change


def test_the_item_search_after_create_sees_a_renamed_item(dump, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Item 35 is named Excalibur in the fixture ItemDefinitions.json.
    monkeypatch.setattr(preferences, "cache_folder", lambda: dump)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert appearance_items.item_name(35) == "Excalibur"
    rewrite_cache(dump, rename_item(35, "Excalibur", "Renamed sword"))
    assert appearance_items.item_name(35) == "Renamed sword"


def search_labels(slot):
    """The labels the item search popup of a slot lists, by item id. The popup reads only the operator's slot, so a
    stand-in is enough."""
    choices = appearance_items._slot_items(type("Operator", (), {"slot": slot})(), bpy.context)
    return {identifier: label for identifier, label, _ in choices}


def test_the_item_search_popup_after_create_lists_a_renamed_item(dump, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Item 2653 is the Zamorak platebody, a male body item, in the fixture
    # ItemDefinitions.json.
    monkeypatch.setattr(preferences, "cache_folder", lambda: dump)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert "Zamorak platebody" in search_labels(4)["2653"]
    rewrite_cache(dump, rename_item(2653, "Zamorak platebody", "Renamed platebody"))
    label = search_labels(4)["2653"]
    assert "Renamed platebody" in label and "Zamorak platebody" not in label


def test_create_after_create_sees_an_item_a_changed_cache_added_and_reads_the_catalog_once_more(dump, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use, and that an
    # unchanged one is shared (issue 29, decisions 2 and 3, 2026-11-10). Item 9035 is a copy of Excalibur (item 35)
    # under an id the fixture ItemDefinitions.json lacks.
    def add_sword(parts):
        parts["items"][9035] = parts["items"][35]

    loads = count_item_catalog_loads(monkeypatch)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create(dump_folder=str(dump)) == {"FINISHED"}
    equipment = list(case("excalibur", False, [0, 0, 0, 0, 0])["equipment"])
    equipment[3] = 512 + 9035
    bpy.context.scene.rs_appearance.equipment = equipment  # pyrefly: ignore[missing-attribute]
    rewrite_cache(dump, add_sword)
    assert create(dump_folder=str(dump)) == {"FINISHED"}
    assert create(dump_folder=str(dump)) == {"FINISHED"}
    assert loads == [dump] * 2


def test_create_after_create_sees_a_kit_a_changed_cache_removed(dump):
    # The user chose that each catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10), so Create refuses a look whose kit the changed cache lacks instead of building it from the
    # old catalog. The default male look wears torso kit 18 (equipment 274 in reference.json).
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create(dump_folder=str(dump)) == {"FINISHED"}
    rewrite_cache(dump, lambda parts: parts["kits"].pop(18))
    with pytest.raises(RuntimeError):
        create(dump_folder=str(dump))
    assert len(players()) == 1
