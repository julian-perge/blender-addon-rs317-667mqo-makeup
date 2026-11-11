import dataclasses
import json
import math
import os
import shutil
from pathlib import Path

import bpy
import pytest

from rsps_toolkit.animation.clip import pose_vertices, read_sequence
from rsps_toolkit.animation.label_fit import fit_frame, fitted_vertices
from rsps_toolkit.blender import (
    appearance_bone_action,
    appearance_clip,
    appearance_clip_cache,
    appearance_collection,
    appearance_fades,
    appearance_files,
    appearance_pose,
    appearance_preview,
    appearance_props,
    appearance_shape_keys,
)
from rsps_toolkit.formats import decode, encode
from rsps_toolkit.formats.appearance import ITEM_OFFSET, held_equipment
from rsps_toolkit.formats.appearance_preset import AppearancePreset, dumps_preset, loads_preset
from rsps_toolkit.formats.cache_profile import CacheProfile

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIPS = FIXTURES / "animation149"
CLIP = CLIPS / "walk"
POSE = json.loads((CLIP / "pose-male.json").read_text())
# The unchanged revision-149 client's frame index after each tick, recorded by record_sequences.py.
TIMING = {
    (case["sequence"], case["mode"]): case["frames"]
    for case in json.loads((CLIPS / "sequences.json").read_text())["timing"]
}


@pytest.fixture(autouse=True)
def registered(clean):
    for cls in (*appearance_props.classes, *appearance_clip.classes):
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    yield
    appearance_props.unregister_properties()
    for cls in reversed((*appearance_props.classes, *appearance_clip.classes)):
        bpy.utils.unregister_class(cls)


def player(dump, pose=POSE):
    preset = AppearancePreset(149, 430, pose["female"], tuple(pose["equipment"]), tuple(pose["colours"]))
    body, shading = appearance_preview.assemble_lit(preset, dump)
    return appearance_collection.build_collection(body, shading, preset, "Player")


def key_blocks(collection):
    shape_keys = appearance_collection.mesh_data(collection).shape_keys
    assert shape_keys is not None
    return shape_keys.key_blocks


def test_each_walk_frame_becomes_a_shape_key_equal_to_the_clients_pose(dump):
    collection = player(dump)
    assert appearance_clip.bake_clip(collection, CLIP) == 8
    keys = key_blocks(collection)
    assert [k.name for k in keys] == ["Basis"] + [f"clip_{i}" for i in range(8)]
    for index, expected in enumerate(POSE["frames"]):
        for vertex, (x, y, z) in enumerate(zip(expected["e"], expected["l"], expected["s"], strict=True)):
            assert tuple(keys[f"clip_{index}"].data[vertex].co) == pytest.approx((x, z, -y), abs=1e-4)  # pyrefly: ignore[missing-attribute]


def move_whole(collection):
    rig = appearance_collection.armature_of(collection)
    rig.location = (40.0, -12.0, 3.0)
    rig.rotation_euler.z = 1.2
    rig.scale = (2.0, 2.0, 2.0)
    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]


def test_shape_keys_bake_onto_a_player_moved_as_a_whole_with_the_clients_pose(dump):
    collection = player(dump)
    move_whole(collection)
    assert appearance_clip.bake_clip(collection, CLIP) == 8
    first = POSE["frames"][0]
    for vertex, (x, y, z) in enumerate(zip(first["e"], first["l"], first["s"], strict=True)):
        assert tuple(key_blocks(collection)["clip_0"].data[vertex].co) == pytest.approx((x, z, -y), abs=1e-4)  # pyrefly: ignore[missing-attribute]


def shown_keys(collection, count):
    """The index of the one clip key at full value on every frame of the scene's range."""
    scene = bpy.context.scene
    assert scene is not None
    shown = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        values = [round(key_blocks(collection)[f"clip_{i}"].value) for i in range(count)]
        assert sorted(values) == [0] * (count - 1) + [1], f"frame {frame} shows {values}"
        shown.append(values.index(1))
    return shown


def test_each_blender_frame_shows_the_frame_the_client_shows_on_that_tick(dump):
    # The walk is a pose sequence, so the client shows frame 0 one tick longer and the cycle is 49 ticks long.
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    shown = shown_keys(collection, 8)
    client = TIMING[819, "pose"]
    assert shown == client[: len(shown)]
    assert len(shown) == 49 and client[49] == 0


@pytest.mark.parametrize("kind", ["male", "female"])
def test_the_idle_bake_equals_the_clients_pose_and_timing(dump, kind):
    pose = json.loads((CLIPS / f"idle/pose-{kind}.json").read_text())
    collection = player(dump, pose)
    assert appearance_clip.bake_clip(collection, CLIPS / "idle") == 12
    keys = key_blocks(collection)
    for index, expected in enumerate(pose["frames"]):
        for vertex, (x, y, z) in enumerate(zip(expected["e"], expected["l"], expected["s"], strict=True)):
            assert tuple(keys[f"clip_{index}"].data[vertex].co) == pytest.approx((x, z, -y), abs=1e-4)  # pyrefly: ignore[missing-attribute]
    shown = shown_keys(collection, 12)
    assert shown == TIMING[808, "pose"][: len(shown)]
    assert len(shown) == 253


def test_an_action_bake_follows_the_loop_offset_until_the_client_stops_it(dump):
    # Sequence 1499 steps back 4 frames after its last one, 98 times, and then stops (its loop limit is 99).
    pose = json.loads((CLIPS / "loop/pose-male.json").read_text())
    collection = player(dump, pose)
    assert appearance_clip.bake_clip(collection, CLIPS / "loop", action=True) == 26
    client = TIMING[1499, "action"]
    assert shown_keys(collection, 26) == client[: client.index(-1)]


def test_the_operator_bakes_an_action_when_asked(dump):
    collection = player(dump, json.loads((CLIPS / "loop/pose-male.json").read_text()))
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.bake_clip(directory=str(CLIPS / "loop"), play_as="ACTION") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    client = TIMING[1499, "action"]
    assert bpy.context.scene.frame_end == client.index(-1)  # pyrefly: ignore[missing-attribute]


def test_baking_again_replaces_the_keys(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    appearance_clip.bake_clip(collection, CLIP)
    keys = key_blocks(collection)
    assert len(keys) == 9


def test_the_rest_mesh_is_unchanged_so_the_player_does_not_count_as_edited(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    assert not appearance_collection.is_edited(collection)


def test_an_edited_player_is_refused(dump):
    collection = player(dump)
    appearance_collection.mesh_data(collection).vertices[0].co.x += 3
    with pytest.raises(ValueError, match="has edits"):
        appearance_clip.bake_clip(collection, CLIP)


def test_the_operator_bakes_the_active_player(dump):
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.bake_clip(directory=str(CLIP)) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert len(key_blocks(collection)) == 9


def test_the_operator_names_a_folder_without_clip_files(dump, tmp_path):
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    with pytest.raises(RuntimeError, match="sequence.dat"):
        bpy.ops.rsps.bake_clip(directory=str(tmp_path))  # pyrefly: ignore[missing-attribute]


def test_baking_sets_game_speed_playback(dump):
    collection = player(dump)
    bpy.context.scene.render.fps_base = 1.001  # pyrefly: ignore[missing-attribute]
    appearance_clip.bake_clip(collection, CLIP)
    assert bpy.context.scene.render.fps == 50  # pyrefly: ignore[missing-attribute]
    assert bpy.context.scene.render.fps_base == 1.0  # pyrefly: ignore[missing-attribute]


def in_two_groups(collection):
    obj = appearance_collection.mesh_of(collection)
    own = appearance_collection.mesh_data(collection).vertices[0].groups[0].group
    next(group for group in obj.vertex_groups if group.index != own).add([0], 0.5, "ADD")
    return obj


def test_a_vertex_in_two_groups_is_named(dump):
    collection = player(dump)
    in_two_groups(collection)
    with pytest.raises(ValueError, match="Vertex 0 is in 2 vertex groups"):
        appearance_pose.pose_player(collection, CLIP)


def test_the_operator_refuses_a_vertex_in_two_groups_as_an_edit_and_adds_no_keys(dump):
    collection = player(dump)
    obj = in_two_groups(collection)
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    with pytest.raises(RuntimeError, match="Player has edits, so a clip cannot be baked onto it"):
        bpy.ops.rsps.bake_clip(directory=str(CLIP))  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.mesh_data(collection).shape_keys is None


def test_sculpting_a_clip_key_counts_as_edited(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    key_blocks(collection)["clip_3"].data[0].co.x += 40  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.is_edited(collection)


def test_a_key_the_user_added_is_refused_by_name_and_kept(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    obj = appearance_collection.mesh_of(collection)
    smile = obj.shape_key_add(name="smile", from_mix=False)
    smile.data[0].co.x += 10  # pyrefly: ignore[missing-attribute]
    with pytest.raises(ValueError, match="'smile'"):
        appearance_clip.bake_clip(collection, CLIP)
    assert [k.name for k in key_blocks(collection)] == ["Basis"] + [f"clip_{i}" for i in range(8)] + ["smile"]


def test_baking_refuses_a_player_in_edit_mode(dump):
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.armature_of(collection)  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="EDIT")
    with pytest.raises(ValueError, match="Edit Mode"):
        appearance_clip.bake_clip(collection, CLIP)
    assert appearance_collection.mesh_data(collection).shape_keys is None


def broken_last_frame(monkeypatch):
    """Give the clip's last frame a vertex with no position, so the bake fails after it has started adding keys."""
    real = appearance_pose.pose_vertices

    def posed(*args):
        frames = real(*args)
        last = frames[-1]
        vertices = (*last.vertices[:-1], (None, None, None))
        return (*frames[:-1], dataclasses.replace(last, vertices=vertices))  # pyrefly: ignore[bad-argument-type]

    monkeypatch.setattr(appearance_pose, "pose_vertices", posed)


def curves(collection):
    action = appearance_collection.mesh_data(collection).shape_keys.animation_data.action  # pyrefly: ignore[missing-attribute]
    bags = [bag for layer in action.layers for strip in layer.strips for bag in strip.channelbags]
    return sorted(curve.data_path for bag in bags for curve in bag.fcurves)


CLIP_CURVES = [f'key_blocks["clip_{i}"].value' for i in range(8)]


def test_a_failed_bake_keeps_the_previous_clip(dump, monkeypatch):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    before = [(k.name, tuple(k.data[5].co)) for k in key_blocks(collection)]  # pyrefly: ignore[missing-attribute]
    broken_last_frame(monkeypatch)
    with pytest.raises((RuntimeError, ValueError, TypeError)):
        appearance_clip.bake_clip(collection, CLIP)
    assert [(k.name, tuple(k.data[5].co)) for k in key_blocks(collection)] == before  # pyrefly: ignore[missing-attribute]
    assert curves(collection) == CLIP_CURVES
    assert not appearance_collection.is_edited(collection)


def test_a_failed_first_bake_leaves_no_keys(dump, monkeypatch):
    collection = player(dump)
    broken_last_frame(monkeypatch)
    with pytest.raises((RuntimeError, ValueError, TypeError)):
        appearance_clip.bake_clip(collection, CLIP)
    assert appearance_collection.mesh_data(collection).shape_keys is None


def test_baking_again_keeps_one_curve_per_key(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    appearance_clip.bake_clip(collection, CLIP)
    assert curves(collection) == CLIP_CURVES


def test_the_operator_names_a_truncated_frame(dump, tmp_path):
    collection = player(dump)
    clip = tmp_path / "clip"
    shutil.copytree(CLIP, clip)
    frame = clip / "frames/207_364.dat"
    frame.write_bytes(frame.read_bytes()[:3])
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    with pytest.raises(RuntimeError, match="frame file ends early"):
        bpy.ops.rsps.bake_clip(directory=str(clip))  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.mesh_data(collection).shape_keys is None


# The largest distance, in game units, between the fitted label transforms and the client's vertices, as measured in
# tests/unit/test_label_fit.py (ERROR_BOUNDS there): the client truncates coordinates to integers, which no bone can.
CLIENT_BOUND = {("walk", "male"): 1.77, ("idle", "female"): 1.21, ("run", "male"): 2.02, ("loop", "male"): 1.56}
# Blender stores bones, keys and evaluated vertices in 32-bit floats, so the armature result differs from the
# 64-bit fit by rounding. The largest difference measured on 2026-11-07, over the first 300 Blender frames of the walk,
# idle, run and loop bone bakes, was 6.2e-5 game units.
RIG_ROUNDING = 1e-4


def posed_mesh(collection, frame):
    """The player's vertices in game coordinates after the Armature modifier, on a Blender frame."""
    bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
    evaluated = appearance_collection.mesh_of(collection).evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [(v.co.x, -v.co.z, v.co.y) for v in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def mesh_labels(collection):
    """Each vertex's label, read from the name of the one vertex group it is in."""
    names = {group.index: group.name for group in appearance_collection.mesh_of(collection).vertex_groups}
    vertices = appearance_collection.mesh_data(collection).vertices
    return tuple(int(names[v.groups[0].group].removeprefix("label_")) for v in vertices)


def fitted_clip(collection, pose, clip):
    """The pure fit of every frame of the clip, from the client's rest vertices and the mesh's labels."""
    rest = tuple(zip(pose["rest"]["e"], pose["rest"]["l"], pose["rest"]["s"], strict=True))
    labels = mesh_labels(collection)
    return [
        fitted_vertices(rest, labels, fit_frame(rest, labels, f.vertices)) for f in pose_vertices(rest, labels, clip)
    ]


def largest_distance(a, b):
    return max(math.dist(p, q) for p, q in zip(a, b, strict=True))


def test_every_blender_frame_of_the_bone_walk_poses_the_fitted_frame_the_client_shows(dump):
    collection = player(dump)
    assert appearance_clip.bake_clip_to_rig(collection, CLIP) == 8
    fitted = fitted_clip(collection, POSE, CLIP)
    shown = TIMING[819, "pose"][:49]
    assert (bpy.context.scene.frame_start, bpy.context.scene.frame_end) == (1, 49)  # pyrefly: ignore[missing-attribute]
    for frame, index in enumerate(shown, start=1):
        vertices = posed_mesh(collection, frame)
        assert largest_distance(vertices, fitted[index]) <= RIG_ROUNDING
        client = POSE["frames"][index]
        assert (
            largest_distance(vertices, zip(client["e"], client["l"], client["s"], strict=True))
            <= CLIENT_BOUND["walk", "male"]
        )


@pytest.mark.parametrize(
    ("clip", "kind", "mode"), [("idle", "female", "pose"), ("run", "male", "pose"), ("loop", "male", "action")]
)
def test_sampled_frames_of_other_bone_clips_pose_the_fitted_frame_the_client_shows(dump, clip, kind, mode):
    pose = json.loads((CLIPS / f"{clip}/pose-{kind}.json").read_text())
    collection = player(dump, pose)
    appearance_clip.bake_clip_to_rig(collection, CLIPS / clip, action=mode == "action")
    fitted = fitted_clip(collection, pose, CLIPS / clip)
    sequence = {"idle": 808, "run": 824, "loop": 1499}[clip]
    shown = TIMING[sequence, mode]
    end = bpy.context.scene.frame_end  # pyrefly: ignore[missing-attribute]
    for frame in sorted({1, 2, end // 3, end // 2, end - 1, end}):
        index = shown[frame - 1]
        vertices = posed_mesh(collection, frame)
        assert largest_distance(vertices, fitted[index]) <= RIG_ROUNDING
        client = pose["frames"][index]
        assert (
            largest_distance(vertices, zip(client["e"], client["l"], client["s"], strict=True))
            <= CLIENT_BOUND[clip, kind]
        )


def test_blender_frame_0_shows_the_bone_clip_player_at_rest(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    rest = zip(POSE["rest"]["e"], POSE["rest"]["l"], POSE["rest"]["s"], strict=True)
    assert largest_distance(posed_mesh(collection, 0), rest) <= RIG_ROUNDING


def clip_strips(collection):
    animation = appearance_collection.armature_of(collection).animation_data
    track = None if animation is None else animation.nla_tracks.get(appearance_clip.CLIP_TRACK)
    return [] if track is None else list(track.strips)


def clip_action(collection):
    (strip,) = clip_strips(collection)
    return strip.action


def first_curve(action):
    return action.layers[0].strips[0].channelbags[0].fcurves[0]  # pyrefly: ignore[missing-attribute]


def test_the_bone_clip_keys_are_constant_and_the_player_is_not_edited(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    action = clip_action(collection)
    bags = [bag for layer in action.layers for strip in layer.strips for bag in strip.channelbags]  # pyrefly: ignore[missing-attribute]
    points = [point for bag in bags for curve in bag.fcurves for point in curve.keyframe_points]
    assert points and {point.interpolation for point in points} == {"CONSTANT"}
    assert not appearance_collection.is_edited(collection)


def test_the_clip_is_a_strip_that_plays_from_the_start_frame_and_holds_its_last_pose_after(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP, start=10)
    (strip,) = clip_strips(collection)
    assert (strip.frame_start, strip.frame_end, strip.extrapolation) == (10, 59, "HOLD_FORWARD")
    assert appearance_collection.armature_of(collection).animation_data.action is None  # pyrefly: ignore[missing-attribute]
    fitted = fitted_clip(collection, POSE, CLIP)
    shown = TIMING[819, "pose"]
    for offset in (0, 7, 30, 47):
        assert largest_distance(posed_mesh(collection, 10 + offset), fitted[shown[offset]]) <= RIG_ROUNDING
    rest = list(zip(POSE["rest"]["e"], POSE["rest"]["l"], POSE["rest"]["s"], strict=True))
    assert largest_distance(posed_mesh(collection, 5), rest) <= RIG_ROUNDING
    assert largest_distance(posed_mesh(collection, 70), fitted[shown[47]]) <= RIG_ROUNDING


def test_a_gap_between_clips_holds_the_earlier_clips_last_pose(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    appearance_clip.bake_clip_to_rig(collection, CLIPS / "idle", start=80)
    fitted = fitted_clip(collection, POSE, CLIP)
    last = fitted[TIMING[819, "pose"][47]]
    for frame in (50, 65, 79):
        assert largest_distance(posed_mesh(collection, frame), last) <= RIG_ROUNDING


def test_the_bake_keeps_an_empty_track_for_the_users_keys_above_the_clips(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    tracks = appearance_collection.armature_of(collection).animation_data.nla_tracks  # pyrefly: ignore[missing-attribute]
    assert [track.name for track in tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    assert len(tracks[appearance_clip.USER_TRACK].strips) == 0


def test_the_users_keys_add_to_the_clip_pose_so_a_rest_key_leaves_the_clip_playing(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    rig = appearance_collection.armature_of(collection)
    animation = rig.animation_data
    assert animation.action_blend_type == "COMBINE"  # pyrefly: ignore[missing-attribute]
    scene = bpy.context.scene
    scene.frame_set(3)  # pyrefly: ignore[missing-attribute]
    clip_pose = [bone.matrix_basis.copy() for bone in rig.pose.bones]  # pyrefly: ignore[missing-attribute]
    rest = bpy.data.actions.new("rest")
    animation.action = rest  # pyrefly: ignore[missing-attribute]
    for bone in rig.pose.bones:  # pyrefly: ignore[missing-attribute]
        for index, value in enumerate((1.0, 0.0, 0.0, 0.0)):
            path = f'pose.bones["{bone.name}"].rotation_quaternion'
            rest.fcurve_ensure_for_datablock(rig, path, index=index).keyframe_points.insert(1, value)
    slot = animation.action_slot  # pyrefly: ignore[missing-attribute]
    animation.action = None  # pyrefly: ignore[missing-attribute]
    strip = animation.nla_tracks[appearance_clip.USER_TRACK].strips.new("rest", 1, rest)  # pyrefly: ignore[missing-attribute]
    strip.action_slot = slot
    strip.blend_type = animation.action_blend_type  # pyrefly: ignore[missing-attribute]
    scene.frame_set(4)  # pyrefly: ignore[missing-attribute]
    scene.frame_set(3)  # pyrefly: ignore[missing-attribute]
    for bone, before in zip(rig.pose.bones, clip_pose, strict=True):  # pyrefly: ignore[missing-attribute]
        assert [v for row in bone.matrix_basis for v in row] == pytest.approx(
            [v for row in before for v in row], abs=1e-5
        )


def test_baking_bones_again_on_the_same_frame_replaces_the_strip(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    appearance_clip.bake_clip_to_rig(collection, CLIPS / "idle")
    assert list(bpy.data.actions) == [clip_action(collection)]
    assert bpy.context.scene.frame_end == 253  # pyrefly: ignore[missing-attribute]


def test_clips_line_up_as_strips_and_an_overlapping_one_is_refused(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    with pytest.raises(ValueError, match="over the strip"):
        appearance_clip.bake_clip_to_rig(collection, CLIPS / "idle", start=30)
    appearance_clip.bake_clip_to_rig(collection, CLIPS / "idle", start=50)
    assert [(s.frame_start, s.frame_end) for s in clip_strips(collection)] == [(1, 50), (50, 303)]
    assert bpy.context.scene.frame_end == 302  # pyrefly: ignore[missing-attribute]
    assert len(bpy.data.actions) == 2


def test_the_bone_bake_refuses_an_edited_player_and_adds_no_action(dump):
    collection = player(dump)
    appearance_collection.mesh_data(collection).vertices[0].co.x += 3
    with pytest.raises(ValueError, match="has edits"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert len(bpy.data.actions) == 0


def test_the_bone_bake_refuses_a_player_in_edit_mode(dump):
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.armature_of(collection)  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="EDIT")
    with pytest.raises(ValueError, match="Edit Mode"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert len(bpy.data.actions) == 0


def test_the_bone_bake_refuses_a_player_with_clip_shape_keys(dump):
    collection = player(dump)
    appearance_clip.bake_clip(collection, CLIP)
    with pytest.raises(ValueError, match="Player has shape keys"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert clip_strips(collection) == []
    assert len(key_blocks(collection)) == 9


def test_the_shape_key_bake_refuses_a_player_whose_rig_has_clip_strips(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    with pytest.raises(ValueError, match="NLA strips on RS clips"):
        appearance_clip.bake_clip(collection, CLIP)
    assert appearance_collection.mesh_data(collection).shape_keys is None


def test_removing_the_clip_strips_lets_the_shape_key_bake_run(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    animation = appearance_collection.armature_of(collection).animation_data
    animation.nla_tracks.remove(animation.nla_tracks[appearance_clip.CLIP_TRACK])  # pyrefly: ignore[missing-attribute]
    assert appearance_clip.bake_clip(collection, CLIP) == 8


def test_the_users_own_action_stays_active_and_is_not_an_edit(dump):
    collection = player(dump)
    rig = appearance_collection.armature_of(collection)
    mine = bpy.data.actions.new("wave")
    rig.animation_data_create().action = mine
    assert not appearance_collection.is_edited(collection)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert rig.animation_data.action == mine  # pyrefly: ignore[missing-attribute]
    assert len(clip_strips(collection)) == 1


def test_a_failed_bone_bake_keeps_the_previous_clip_and_leaves_no_new_action(dump, monkeypatch):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    before = clip_action(collection)
    broken_last_frame(monkeypatch)
    with pytest.raises((RuntimeError, ValueError, TypeError)):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert list(bpy.data.actions) == [before]
    assert clip_action(collection) == before


def test_a_failure_while_writing_keys_removes_the_half_made_action(dump, monkeypatch):
    collection = player(dump)

    def broken(*args):
        raise RuntimeError("stopped while writing keys")

    monkeypatch.setattr(appearance_bone_action, "_write_channel", broken)
    with pytest.raises(RuntimeError, match="stopped while writing keys"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert len(bpy.data.actions) == 0
    assert clip_strips(collection) == []


def test_the_operator_bakes_bones_from_the_current_frame(dump):
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    bpy.context.scene.frame_set(20)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.bake_clip(directory=str(CLIP), method="BONES") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert [s.frame_start for s in clip_strips(collection)] == [20]
    assert appearance_collection.mesh_data(collection).shape_keys is None


def test_posing_a_bone_of_a_player_without_a_clip_counts_as_edited(dump):
    collection = player(dump)
    rig = appearance_collection.armature_of(collection)
    rig.pose.bones[0].location.x += 2  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.is_edited(collection)


def test_a_bone_clip_player_is_not_edited_on_another_frame_but_is_after_a_key_moves(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    bpy.context.scene.frame_set(5)  # pyrefly: ignore[missing-attribute]
    assert not appearance_collection.is_edited(collection)
    first_curve(clip_action(collection)).keyframe_points[2].co.y += 1.0
    assert appearance_collection.is_edited(collection)


def test_a_bone_bake_records_its_clip_on_the_strips_action(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP, action=True, start=7)
    record = json.loads(clip_action(collection)[appearance_collection.CLIP_KEY])
    assert record == {"folder": str(CLIP.resolve()), "method": "BONES", "action": True, "smooth": False}
    assert appearance_clip.recorded_clips(collection) == [(json.dumps(record), 7)]


def test_a_second_bone_bake_refuses_a_clip_whose_keys_were_edited(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    action = clip_action(collection)
    first_curve(action).keyframe_points[2].co.y += 1.0
    with pytest.raises(ValueError, match="has edits"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert clip_action(collection) == action


SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
needs_cache = pytest.mark.skipif(
    not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder"
)


@needs_cache
def test_the_operator_bakes_the_chosen_clip_from_the_cache_and_records_it(dump, monkeypatch):
    monkeypatch.setattr(appearance_clip_cache.preferences, "cache_folder", lambda: SNAPSHOT_430)
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.bake_clip(sequence=819) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    keys = key_blocks(collection)
    for index, expected in enumerate(POSE["frames"]):
        points = keys[f"clip_{index}"].data
        assert [round(-p.co.z) for p in points] == expected["l"]  # pyrefly: ignore[missing-attribute]
    record = json.loads(collection[appearance_collection.CLIP_KEY])
    assert record == {"cache": str(SNAPSHOT_430.resolve()), "sequence": 819, "method": "SHAPE_KEYS", "action": False}


@needs_cache
def test_a_recorded_cache_clip_bakes_again(dump):
    collection = player(dump)
    record = {"cache": str(SNAPSHOT_430), "sequence": 808, "method": "BONES", "action": False}
    assert appearance_clip.bake_recorded(collection, json.dumps(record)) == 12


def test_baking_from_the_cache_without_a_cache_folder_says_so(dump, monkeypatch):
    monkeypatch.setattr(appearance_clip_cache.preferences, "cache_folder", lambda: None)
    collection = player(dump)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    with pytest.raises(RuntimeError, match="Set the cache folder"):
        bpy.ops.rsps.bake_clip(sequence=819)  # pyrefly: ignore[missing-attribute]


def test_a_player_with_clips_in_a_scene_at_another_frame_rate_is_flagged_until_one_click_sets_50(dump):
    scene = bpy.context.scene
    assert scene is not None
    collection = player(dump)
    scene.render.fps, scene.render.fps_base = 24, 1.0
    assert not appearance_clip.plays_at_another_rate(scene, collection)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    assert not appearance_clip.plays_at_another_rate(scene, collection)
    scene.render.fps = 24
    assert appearance_clip.plays_at_another_rate(scene, collection)
    assert bpy.ops.rsps.set_clip_fps() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert (scene.render.fps, scene.render.fps_base) == (50, 1.0)
    assert not appearance_clip.plays_at_another_rate(scene, collection)


def test_the_frame_rate_check_reads_the_rate_so_100_fps_on_base_2_is_50_and_set_50_fps_resets_the_base(dump):
    scene = bpy.context.scene
    assert scene is not None
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    scene.render.fps, scene.render.fps_base = 100, 2.0
    assert not appearance_clip.plays_at_another_rate(scene, collection)
    scene.render.fps, scene.render.fps_base = 60, 1.2
    assert not appearance_clip.plays_at_another_rate(scene, collection)
    scene.render.fps, scene.render.fps_base = 50, 1.001
    assert appearance_clip.plays_at_another_rate(scene, collection)
    assert bpy.ops.rsps.set_clip_fps() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert (scene.render.fps, scene.render.fps_base) == (50, 1.0)


def test_picking_a_clip_stores_its_sequence_and_the_panel_names_it(dump):
    assert bpy.ops.rsps.pick_clip(clip="808") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert bpy.context.scene.rs_appearance.clip_sequence == 808  # pyrefly: ignore[missing-attribute]
    assert appearance_clip_cache.clip_label(808) == "HUMAN_READY (808)"


def wielding(collection, item_id):
    """Store the item in the player's weapon slot, which is all the weapon clip buttons read, and make it active."""
    preset = loads_preset(collection[appearance_preview.PRESET_KEY])
    equipment = list(preset.equipment)
    equipment[appearance_collection.WEAPON_SLOT] = 0 if item_id is None else item_id + ITEM_OFFSET
    collection[appearance_preview.PRESET_KEY] = dumps_preset(dataclasses.replace(preset, equipment=tuple(equipment)))
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]


def test_the_weapon_clip_buttons_choose_the_worn_weapons_clips_and_how_they_play(dump):
    wielding(player(dump), 4151)
    props = bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    for choice, clip, play_as in (
        ("WALK", 1660, "POSE"),
        ("RUN", 1661, "POSE"),
        ("STAND", 808, "POSE"),
        ("ATTACK_1", 1658, "ACTION"),
        ("BLOCK", 1659, "ACTION"),
    ):
        assert bpy.ops.rsps.pick_weapon_clip(choice=choice) == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
        assert (props.clip_sequence, props.clip_play_as) == (clip, play_as)
    with pytest.raises(RuntimeError, match="no clip for this button"):
        bpy.ops.rsps.pick_weapon_clip(choice="ATTACK_3")  # pyrefly: ignore[missing-attribute]
    assert props.clip_sequence == 1659


def test_a_weapon_no_table_lists_gives_the_unarmed_clips_and_is_named_for_the_note(dump):
    collection = player(dump)
    wielding(collection, 4162)
    assert appearance_clip.unlisted_weapon(collection) == 4162
    assert bpy.ops.rsps.pick_weapon_clip(choice="WALK") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert bpy.context.scene.rs_appearance.clip_sequence == 819  # pyrefly: ignore[missing-attribute]
    wielding(collection, 4151)
    assert appearance_clip.unlisted_weapon(collection) is None
    wielding(collection, None)
    assert appearance_clip.unlisted_weapon(collection) is None
    assert appearance_clip.worn_weapon_clips(collection) == appearance_clip.weapon_clip_table().unarmed


def test_the_weapon_clip_buttons_need_an_active_player(dump):
    player(dump)
    bpy.context.view_layer.objects.active = None  # pyrefly: ignore[missing-attribute]
    assert not bpy.ops.rsps.pick_weapon_clip.poll()  # pyrefly: ignore[missing-attribute]


FADE_CLIP = CLIPS / "alpha-1994"
FADE_POSE = json.loads((FADE_CLIP / "pose-male.json").read_text())


def kept_faces(dump, pose):
    """The model face behind each polygon: build_mesh leaves out faces that repeat a vertex or that another hides."""
    from rsps_toolkit.formats.face_order import visible_faces

    preset = AppearancePreset(149, 430, pose["female"], tuple(pose["equipment"]), tuple(pose["colours"]))
    model, _ = appearance_preview.assemble_lit(preset, dump)
    visible = set(visible_faces(model))
    return [i for i, face in enumerate(model.faces) if len(set(face)) == 3 and i in visible]


def client_alphas(frame_index, kept):
    """The client's alphas of the kept faces on a clip frame, unsigned; zeros where it left every face opaque."""
    recorded = FADE_POSE["frames"][frame_index]["o"]
    return [0 if recorded is None else recorded[i] & 255 for i in kept]


def shown_frames(clip, action=False):
    """The clip frame index shown on each Blender frame from 1, from the bake's schedule."""
    from rsps_toolkit.animation.clip import read_sequence
    from rsps_toolkit.animation.frames import frame_schedule

    return [index for index, ticks in frame_schedule(read_sequence(clip), action=action) for _ in range(ticks)]


def all_fade_materials():
    return [m for m in bpy.data.materials if appearance_fades.FADE_KEY in m]


def fade_materials(collection):
    mesh = appearance_collection.mesh_data(collection)
    return [m for m in mesh.materials if m is not None and appearance_fades.FADE_KEY in m]


def polygon_alphas(collection, owner):
    """Each polygon's alpha as its material reads it: the owner's group property, or 0 on the lit material."""
    mesh = appearance_collection.mesh_data(collection)
    alphas = []
    for polygon in mesh.polygons:
        material = mesh.materials[polygon.material_index]
        assert material is not None
        alphas.append(owner[material[appearance_fades.FADE_KEY]] if appearance_fades.FADE_KEY in material else 0)
    return alphas


def test_a_shape_key_bake_fades_faces_as_the_client_does(dump):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip(collection, FADE_CLIP)
    kept = kept_faces(dump, FADE_POSE)
    materials = fade_materials(collection)
    assert len(materials) == len({m[appearance_fades.FADE_KEY] for m in materials}) > 0
    key = appearance_collection.mesh_data(collection).shape_keys
    shown = shown_frames(FADE_CLIP)
    for frame in (1, len(shown) - 30, len(shown) - 1, len(shown)):
        bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
        assert polygon_alphas(collection, key) == client_alphas(shown[frame - 1], kept)
        for material in materials:
            alpha = key[material[appearance_fades.FADE_KEY]]  # pyrefly: ignore[unsupported-operation]
            opacity = material.node_tree.nodes["Fade"].inputs["Fac"].default_value  # pyrefly: ignore[missing-attribute]
            assert opacity == pytest.approx((256 - alpha) / 256)
    assert not appearance_collection.is_edited(collection)


@pytest.mark.parametrize("bake", [appearance_clip.bake_clip, appearance_clip.bake_clip_to_rig])
def test_a_clips_fade_materials_show_only_the_front_of_faces(dump, bake):
    # The user chose that players cull back faces as the client does, fade materials included (issue 28, decision 1,
    # 2026-11-10).
    collection = player(dump, FADE_POSE)
    bake(collection, FADE_CLIP)
    materials = fade_materials(collection)
    assert materials and all(material.use_backface_culling for material in materials)


def test_a_bone_bake_turns_culling_on_for_the_fade_materials_it_reuses(dump):
    # The user chose that a bake also makes a fade material it reuses cull, so one made before players culled gets it
    # at the next bake (issue 28, decision 4, 2026-11-10).
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    materials = fade_materials(collection)
    for material in materials:
        material.use_backface_culling = False
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    assert fade_materials(collection) == materials
    assert all(material.use_backface_culling for material in materials)


def test_a_bone_clip_keys_its_fades_in_the_strip_and_holds_the_last_after_it(dump):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    rig = appearance_collection.armature_of(collection)
    shown = shown_frames(FADE_CLIP)
    last = len(shown) - 1
    bpy.context.scene.frame_set(10 + last)  # pyrefly: ignore[missing-attribute]
    assert polygon_alphas(collection, rig) == client_alphas(shown[last], kept_faces(dump, FADE_POSE))
    bpy.context.scene.frame_set(10 + last + 5)  # pyrefly: ignore[missing-attribute]
    assert polygon_alphas(collection, rig) == client_alphas(shown[last], kept_faces(dump, FADE_POSE))
    bpy.context.scene.frame_set(5)  # pyrefly: ignore[missing-attribute]
    assert set(polygon_alphas(collection, rig)) == {0}
    assert not appearance_collection.is_edited(collection)


def test_a_duplicated_player_fades_with_its_own_materials_driven_by_its_own_rig(dump):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    copy = appearance_collection.duplicate_player(collection, str(dump))
    rig, copy_rig = appearance_collection.armature_of(collection), appearance_collection.armature_of(copy)
    ours = {material for obj in appearance_collection.parts(copy) for material in obj.data.materials}  # pyrefly: ignore[missing-attribute]
    theirs = {material for obj in appearance_collection.parts(collection) for material in obj.data.materials}  # pyrefly: ignore[missing-attribute]
    fades = {material for material in ours if appearance_fades.FADE_KEY in material}
    assert fades and not fades & theirs
    targets = {curve.driver.variables[0].targets[0].id for m in fades for curve in m.node_tree.animation_data.drivers}  # pyrefly: ignore[missing-attribute]
    assert targets == {copy_rig}
    last = len(shown_frames(FADE_CLIP)) - 1
    bpy.context.scene.frame_set(10 + last)  # pyrefly: ignore[missing-attribute]
    assert polygon_alphas(copy, copy_rig) == polygon_alphas(collection, rig)


def test_a_saved_player_appends_into_a_file_with_players_as_an_unedited_player_that_plays_its_clips(dump, tmp_path):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    path = tmp_path / "saved.blend"
    appearance_files.save_player(collection, path)
    with bpy.data.libraries.load(str(path)) as (source, target):  # pyrefly: ignore[bad-context-manager]
        target.collections = [collection.name]
    (appended,) = target.collections
    assert isinstance(appended, bpy.types.Collection)
    bpy.context.scene.collection.children.link(appended)  # pyrefly: ignore[missing-attribute]
    assert appended is not collection and appearance_preview.PRESET_KEY in appended
    assert not appearance_collection.is_edited(appended)
    rig = appearance_collection.armature_of(appended)
    clips = rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore[missing-attribute]
    assert [strip.frame_start for strip in clips] == [10]
    materials = [m for obj in appearance_collection.parts(appended) for m in obj.data.materials]  # pyrefly: ignore[missing-attribute]
    fades = {m for m in materials if appearance_fades.FADE_KEY in m}
    targets = {curve.driver.variables[0].targets[0].id for m in fades for curve in m.node_tree.animation_data.drivers}  # pyrefly: ignore[missing-attribute]
    assert fades and targets == {rig}
    last = len(shown_frames(FADE_CLIP)) - 1
    bpy.context.scene.frame_set(10 + last)  # pyrefly: ignore[missing-attribute]
    original = appearance_collection.armature_of(collection)
    assert polygon_alphas(appended, rig) == polygon_alphas(collection, original)


def append_player(path, name):
    with bpy.data.libraries.load(str(path)) as (_, target):  # pyrefly: ignore[bad-context-manager]
        target.collections = [name]
    (appended,) = target.collections
    assert isinstance(appended, bpy.types.Collection)
    bpy.context.scene.collection.children.link(appended)  # pyrefly: ignore[missing-attribute]
    return appended


def test_a_saved_player_appended_twice_gives_two_unedited_players(dump, tmp_path):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    path = tmp_path / "saved.blend"
    appearance_files.save_player(collection, path)
    first, second = append_player(path, collection.name), append_player(path, collection.name)
    assert first is not second
    assert not appearance_collection.is_edited(first) and not appearance_collection.is_edited(second)


def test_a_saved_player_appended_into_a_file_without_players_is_an_unedited_player_that_plays_its_clips(dump, tmp_path):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP, start=10)
    name = collection.name
    path = tmp_path / "saved.blend"
    appearance_files.save_player(collection, path)
    appearance_collection.remove_collection(collection)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    appended = append_player(path, name)
    assert appended.name == name and appearance_preview.MATERIAL_NAME in bpy.data.materials
    assert not appearance_collection.is_edited(appended)
    rig = appearance_collection.armature_of(appended)
    clips = rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips  # pyrefly: ignore[missing-attribute]
    assert [strip.frame_start for strip in clips] == [10]


def test_a_numbered_fade_material_reads_as_its_original_even_when_its_nodes_differ(dump):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP)
    mesh, index, fade = next(
        (obj.data, index, material)
        for obj in appearance_collection.parts(collection)
        for index, material in enumerate(obj.data.materials)  # pyrefly: ignore[missing-attribute]
        if material is not None and appearance_fades.FADE_KEY in material
    )
    copy = fade.copy()
    socket = next(
        s for node in copy.node_tree.nodes for s in node.inputs if isinstance(getattr(s, "default_value", None), float)
    )
    socket.default_value += 1.0
    mesh.materials[index] = copy  # pyrefly: ignore[missing-attribute]
    assert copy.name != fade.name
    assert not appearance_collection.is_edited(collection)


def test_a_clip_without_fades_and_a_player_built_without_face_attributes_get_no_fade_material(dump):
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip(collection, CLIP)
    assert fade_materials(collection) == []
    mesh = appearance_collection.mesh_data(collection)
    mesh.attributes.remove(mesh.attributes[appearance_preview.FACE_LABEL_ATTRIBUTE])
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    appearance_clip.bake_clip(collection, FADE_CLIP)
    assert fade_materials(collection) == []


def test_baking_a_clip_without_fades_over_one_with_them_drops_the_fade_material(dump):
    collection = player(dump, FADE_POSE)
    before = all_fade_materials()
    appearance_clip.bake_clip(collection, FADE_CLIP)
    appearance_clip.bake_clip(collection, CLIP)
    assert fade_materials(collection) == []
    assert all_fade_materials() == before


def test_removing_a_player_removes_its_fade_materials(dump):
    before = all_fade_materials()
    collection = player(dump, FADE_POSE)
    appearance_clip.bake_clip_to_rig(collection, FADE_CLIP)
    assert len(all_fade_materials()) > len(before)
    appearance_collection.remove_collection(collection)
    assert all_fade_materials() == before


def test_a_later_clip_extends_the_scene_range_but_never_shortens_it(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    bpy.context.scene.frame_end = 400  # pyrefly: ignore[missing-attribute]
    appearance_clip.bake_clip_to_rig(collection, CLIPS / "run", start=60)
    assert bpy.context.scene.frame_end == 400  # pyrefly: ignore[missing-attribute]
    appearance_clip.bake_clip_to_rig(collection, CLIPS / "idle", start=300)
    assert bpy.context.scene.frame_end == 552  # pyrefly: ignore[missing-attribute]


def test_a_smooth_bone_clip_meets_each_game_frame_on_its_first_tick_and_blends_between(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP, smooth=True)
    fitted = fitted_clip(collection, POSE, CLIP)
    shown = shown_frames(CLIP)
    starts = [frame for frame in range(1, len(shown) + 1) if frame == 1 or shown[frame - 1] != shown[frame - 2]]
    for frame in starts:
        assert largest_distance(posed_mesh(collection, frame), fitted[shown[frame - 1]]) <= RIG_ROUNDING
    first, second = starts[0], starts[1]
    middle = posed_mesh(collection, (first + second) // 2)
    a, b = fitted[shown[first - 1]], fitted[shown[second - 1]]
    assert largest_distance(middle, a) > RIG_ROUNDING and largest_distance(middle, b) > RIG_ROUNDING
    assert largest_distance(middle, a) < largest_distance(a, b) and largest_distance(middle, b) < largest_distance(a, b)
    record = json.loads(clip_action(collection)[appearance_collection.CLIP_KEY])
    assert record["smooth"] is True
    assert not appearance_collection.is_edited(collection)


def test_the_joints_carry_the_walk_and_label_bones_keep_only_a_small_leftover(dump):
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    rig = appearance_collection.armature_of(collection)
    joint_turns, leftovers = [], []
    for frame in range(1, 49, 4):
        bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
        for pose_bone in rig.pose.bones:  # pyrefly: ignore[missing-attribute]
            angle = math.degrees(pose_bone.rotation_quaternion.angle)
            angle = min(angle, 360 - angle)
            (leftovers if pose_bone.name.startswith("label_") else joint_turns).append(angle)
    # Measured 2026-11-07: joints up to 63.3 degrees, label leftovers at most 9.3 (mean 1.4).
    assert max(joint_turns) > 45
    assert max(leftovers) < 12 and sum(leftovers) / len(leftovers) < 2


def test_the_bone_bake_refuses_a_player_built_before_joint_bones(dump):
    collection = player(dump)
    del appearance_collection.armature_of(collection)[appearance_collection.JOINT_RIG_KEY]
    with pytest.raises(ValueError, match="before players had joint bones"):
        appearance_clip.bake_clip_to_rig(collection, CLIP)


ARMED = (0, 0, 0, 512 + 1333, 274, 512 + 1201, 282, 292, 256, 289, 298, 266)


def armed_player(dump):
    preset = AppearancePreset(149, 430, False, ARMED, (0,) * 5)
    body, shading, slots = appearance_preview.assemble_parts(preset, dump)
    return body, appearance_collection.build_collection(body, shading, preset, "Player", slots=slots)


def test_a_shape_key_bake_poses_the_weapon_and_shield_with_the_body_as_one_model(armed_dump):
    body, collection = armed_player(armed_dump)
    assert body.vertex_skins is not None
    appearance_clip.bake_clip(collection, CLIP)
    posed = pose_vertices(tuple(body.vertices), tuple(body.vertex_skins), CLIP)
    parts = appearance_collection.parts(collection)
    assert len(parts) == 3
    for obj in parts:
        keys = obj.data.shape_keys.key_blocks  # pyrefly: ignore[missing-attribute]
        model_vertex = appearance_preview.vertex_indices(obj.data)  # pyrefly: ignore[bad-argument-type]
        for index, frame in enumerate(posed):
            for vertex, point in enumerate(keys[f"clip_{index}"].data):  # pyrefly: ignore[missing-attribute]
                x, y, z = frame.vertices[model_vertex[vertex]]
                assert tuple(point.co) == pytest.approx((x, z, -y), abs=1e-4)
    assert not appearance_collection.is_edited(collection)


@pytest.mark.parametrize("moved", [False, True])
def test_a_bone_bake_moves_the_weapon_and_shield_with_the_body_as_one_model(armed_dump, moved):
    body, collection = armed_player(armed_dump)
    if moved:
        move_whole(collection)
    assert body.vertex_skins is not None
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    rest, labels = tuple(body.vertices), tuple(body.vertex_skins)
    fitted = [
        fitted_vertices(rest, labels, fit_frame(rest, labels, f.vertices)) for f in pose_vertices(rest, labels, CLIP)
    ]
    for frame, index in ((1, 0), (20, TIMING[819, "pose"][19])):
        bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
        for obj in appearance_collection.parts(collection):
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                moved = [(v.co.x, -v.co.z, v.co.y) for v in mesh.vertices]
            finally:
                evaluated.to_mesh_clear()
            model_vertex = appearance_preview.vertex_indices(obj.data)  # pyrefly: ignore[bad-argument-type]
            assert largest_distance(moved, [fitted[index][v] for v in model_vertex]) <= RIG_ROUNDING


def held_model(dump, clip):
    """The client's held variant for the armed player while the recorded clip plays, assembled as the bake does."""
    sequence = read_sequence(CLIPS / clip)
    preset = AppearancePreset(149, 430, False, ARMED, (0,) * 5)
    equipment = held_equipment(ARMED, sequence.left_hand_item, sequence.right_hand_item)
    return CacheProfile(dump).assemble_slots(preset, equipment)[0]


def shown(obj, frame):
    bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
    assert obj.hide_viewport == obj.hide_render
    return not obj.hide_viewport


def by_name(collection):
    return {obj.name.removeprefix("Player").strip() or "Body": obj for obj in appearance_collection.parts(collection)}


@pytest.mark.parametrize("clip", ["held-717", "held-1365", "held-909"])
def test_a_shape_key_action_bake_shows_the_held_items_posed_as_the_client_does(armed_dump, clip):
    _, collection = armed_player(armed_dump)
    client = json.loads((CLIPS / clip / "pose-male.json").read_text())
    model = held_model(armed_dump, clip)
    assert appearance_clip.bake_clip(collection, CLIPS / clip, action=True, dump_folder=str(armed_dump)) > 0
    objects = by_name(collection)
    held = {"held-717": [], "held-1365": ["Steel axe"], "held-909": ["Charcoal", "Papyrus"]}[clip]
    assert sorted(objects) == sorted(["Body", "Weapon", "Shield", *held])
    by_position = {position: index for index, position in enumerate(model.vertices)}
    for name in ["Body", *held]:
        obj = objects[name]
        keys = obj.data.shape_keys.key_blocks  # pyrefly: ignore[missing-attribute]
        basis = keys["Basis"].data  # pyrefly: ignore[missing-attribute]
        for index, frame in enumerate(client["frames"]):
            for vertex, point in enumerate(keys[f"clip_{index}"].data):  # pyrefly: ignore[missing-attribute]
                x, y, z = basis[vertex].co
                target = by_position.get((round(x), round(-z), round(y)))
                if target is None:
                    continue
                gx, gy, gz = frame["e"][target], frame["l"][target], frame["s"][target]
                assert tuple(point.co) == pytest.approx((gx, gz, -gy), abs=1e-4)
        assert shown(obj, 1) and shown(obj, 0) == (name == "Body")
    for name in ["Weapon", "Shield"]:
        assert objects[name].data.shape_keys is None  # pyrefly: ignore[missing-attribute]
        assert shown(objects[name], 0) and not shown(objects[name], 1)
    assert not appearance_collection.is_edited(collection)


def bone_names(collection):
    return sorted(bone.name for bone in appearance_collection.armature_data(collection).bones)


def test_posing_a_held_clip_gives_the_clients_frames_and_adds_its_objects_only_with_the_parts(armed_dump):
    _, collection = armed_player(armed_dump)
    client = json.loads((CLIPS / "held-1365" / "pose-male.json").read_text())
    before = (set(bpy.data.objects), set(bpy.data.meshes), bone_names(collection))
    posed = appearance_pose.pose_player(collection, CLIPS / "held-1365", action=True, dump_folder=str(armed_dump))
    assert [list(frame.vertices) for frame in posed.frames] == [
        list(zip(frame["e"], frame["l"], frame["s"], strict=True)) for frame in client["frames"]
    ]
    assert (set(bpy.data.objects), set(bpy.data.meshes), bone_names(collection)) == before
    assert sorted(part.obj.name for part in posed.ensure_parts()) == ["Player", "Player Steel axe"]
    assert sorted(by_name(collection)) == ["Body", "Shield", "Steel axe", "Weapon"]


LONE_LABEL = 250


def axe_with_a_lone_label(dump):
    """Give the Steel axe's model a label the armed player lacks, so a bake that holds it also adds a label bone."""
    axe = dump / "dump_index/models/510.dat"
    model = decode(axe.read_bytes(), profile="osrs-149")
    model.vertex_skins = [LONE_LABEL] * len(model.vertices)
    axe.write_bytes(encode(model))


@pytest.mark.parametrize(
    ("bake", "module", "step"),
    [
        (appearance_clip.bake_clip_to_rig, appearance_bone_action, "write"),
        (appearance_clip.bake_clip_to_rig, appearance_clip, "_add_clip_strip"),
        (appearance_clip.bake_clip, appearance_shape_keys, "write"),
    ],
)
def test_a_held_bake_that_fails_after_making_the_held_items_leaves_the_file_as_it_was(
    armed_dump, monkeypatch, bake, module, step
):
    # The user chose that a bake failing after it made the held items leaves the file's objects, meshes, bones and
    # actions as they were, and that the test forces the failure at the step after them, since no real input is known
    # to fail there (issue 13, decisions 1, 2, 4 and 6, 2026-11-10).
    axe_with_a_lone_label(armed_dump)
    _, collection = armed_player(armed_dump)

    def state():
        return set(bpy.data.objects), set(bpy.data.meshes), bone_names(collection), set(bpy.data.actions)

    def fail(*_args, **_kwargs):
        assert "Player Steel axe" in bpy.data.objects and f"label_{LONE_LABEL}" in bone_names(collection)
        assert (set(bpy.data.actions) != before[3]) == (step == "_add_clip_strip")
        raise ValueError("forced failure")

    before = state()
    monkeypatch.setattr(module, step, fail)
    with pytest.raises(ValueError, match="forced failure"):
        bake(collection, CLIPS / "held-1365", action=True, dump_folder=str(armed_dump))
    assert state() == before


def test_a_clip_that_ends_where_the_next_strip_starts_bakes_beside_it(dump):
    # The user chose that a clip baked to end exactly where another strip on RS clips starts bakes fine (issue 13,
    # decision 3, 2026-11-10).
    collection = player(dump)
    appearance_clip.bake_clip_to_rig(collection, CLIP, start=500)
    idle = CLIPS / "idle"
    before = 500 - len(shown_frames(idle))
    appearance_clip.bake_clip_to_rig(collection, idle, start=before)
    track = appearance_collection.armature_of(collection).animation_data.nla_tracks[appearance_clip.CLIP_TRACK]  # pyrefly: ignore[missing-attribute]
    assert [(strip.frame_start, strip.frame_end) for strip in track.strips] == [
        (before, 500),
        (500, 500 + len(shown_frames(CLIP))),
    ]


def test_a_clip_played_as_a_pose_never_changes_the_hands(armed_dump):
    _, collection = armed_player(armed_dump)
    appearance_clip.bake_clip(collection, CLIPS / "held-1365", dump_folder=str(armed_dump))
    objects = by_name(collection)
    assert sorted(objects) == ["Body", "Shield", "Weapon"]
    assert shown(objects["Weapon"], 1) and shown(objects["Shield"], 1)


@pytest.mark.parametrize("moved", [False, True])
def test_a_bone_action_bake_moves_the_held_items_with_the_body_from_its_strip_on(armed_dump, moved):
    _, collection = armed_player(armed_dump)
    if moved:
        move_whole(collection)
    appearance_clip.bake_clip_to_rig(collection, CLIP)
    start = 60
    appearance_clip.bake_clip_to_rig(
        collection, CLIPS / "held-909", action=True, start=start, dump_folder=str(armed_dump)
    )
    objects = by_name(collection)
    assert sorted(objects) == ["Body", "Charcoal", "Papyrus", "Shield", "Weapon"]
    for frame, held_shown in ((start - 1, False), (start, True), (start + 400, True)):
        assert shown(objects["Weapon"], frame) == shown(objects["Shield"], frame) == (not held_shown)
        assert shown(objects["Charcoal"], frame) == shown(objects["Papyrus"], frame) == held_shown
    model = held_model(armed_dump, "held-909")
    assert model.vertex_skins is not None
    rest, labels = tuple(model.vertices), tuple(model.vertex_skins)
    fitted = [
        fitted_vertices(rest, labels, fit_frame(rest, labels, f.vertices))
        for f in pose_vertices(rest, labels, CLIPS / "held-909")
    ]
    by_position = {position: index for index, position in enumerate(model.vertices)}
    bpy.context.scene.frame_set(start)  # pyrefly: ignore[missing-attribute]
    for name in ("Body", "Charcoal", "Papyrus"):
        obj = objects[name]
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            moved = [(v.co.x, -v.co.z, v.co.y) for v in mesh.vertices]
        finally:
            evaluated.to_mesh_clear()
        for vertex, point in zip(obj.data.vertices, moved, strict=True):  # pyrefly: ignore[missing-attribute]
            target = by_position.get((round(vertex.co.x), round(-vertex.co.z), round(vertex.co.y)))
            if target is not None:
                assert math.dist(point, fitted[0][target]) <= RIG_ROUNDING
    assert not appearance_collection.is_edited(collection)


@needs_cache
def test_the_panel_knows_which_cache_clips_hold_items(monkeypatch):
    monkeypatch.setattr(appearance_clip_cache.preferences, "cache_folder", lambda: SNAPSHOT_430)
    assert appearance_clip_cache.holds_items(1365) and appearance_clip_cache.holds_items(717)
    assert not appearance_clip_cache.holds_items(819)
    monkeypatch.setattr(appearance_clip_cache.preferences, "cache_folder", lambda: None)
    assert not appearance_clip_cache.holds_items(909)
