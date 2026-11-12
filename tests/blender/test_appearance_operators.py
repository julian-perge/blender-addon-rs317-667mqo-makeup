import dataclasses
import json
import shutil
from pathlib import Path

import bmesh
import bpy
import pytest
from js5_builder import rewrite_cache
from mathutils import Matrix

from rsps_toolkit.animation.clip import read_sequence
from rsps_toolkit.animation.frames import frame_schedule
from rsps_toolkit.blender import (
    appearance_clip,
    appearance_collection,
    appearance_fades,
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
def test_preview_has_the_clients_geometry_and_lit_colours(cache, outfit, female):
    reference = case(outfit, female, [1, 2, 3, 4, 5])
    show(reference)
    assert create(cache_folder=str(cache)) == {"FINISHED"}
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


def test_preview_stores_the_source_preset(cache):
    preset = show(case("dragon_plate", True, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    obj = active()
    assert loads_preset(appearance_preview.collection_of(obj)[appearance_preview.PRESET_KEY]) == preset  # pyrefly: ignore[unsupported-operation]


def test_a_missing_model_cancels_and_creates_nothing(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    rewrite_cache(cache, lambda parts: parts["models"].pop(230))
    with pytest.raises(RuntimeError, match="Model 230"):
        create(cache_folder=str(cache))
    assert not bpy.data.objects


def test_no_cache_folder_is_an_error(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    with pytest.raises(RuntimeError, match="Set the Cache folder"):
        create()


def update(**options):
    return bpy.ops.rsps.update_appearance_preview(**options)  # pyrefly: ignore[missing-attribute]


def players():
    return [c for c in bpy.data.collections if appearance_preview.PRESET_KEY in c]


def stored(collection):
    return loads_preset(collection[appearance_preview.PRESET_KEY])


def test_update_replaces_the_players_contents_and_the_stored_preset(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    old_name = players()[0].name
    preset = show(case("dragon_plate", True, [1, 2, 3, 4, 5]))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    (collection,) = players()
    assert collection.name == old_name == "Player"
    assert stored(collection) == preset
    expected = case("dragon_plate", True, [1, 2, 3, 4, 5])["before_lighting"]["vertex_count"]
    assert len(appearance_collection.mesh_data(collection).vertices) == expected
    assert active() is appearance_collection.mesh_of(collection)
    assert appearance_collection.mesh_of(collection).name == "Player"


def test_update_turns_culling_on_again_for_the_shared_lit_material(cache):
    # The user chose that Update turns culling on again for a lit material made before players culled (issue 28,
    # decision 3, 2026-11-10).
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    material = bpy.data.materials[appearance_preview.MATERIAL_NAME]
    material.use_backface_culling = False
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert material.use_backface_culling


WALK = Path(__file__).parent.parent / "fixtures" / "animation149" / "walk"


def baked_player(cache, method, clip=WALK):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, clip)
    return collection


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_update_bakes_the_players_clip_again_and_leaves_no_old_action(cache, capfd, method):
    baked_player(cache, method)
    capfd.readouterr()
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert "baked clip" not in capfd.readouterr().out
    (rebuilt,) = players()
    assert appearance_collection.baked_clip(rebuilt) == method
    assert not appearance_collection.is_edited(rebuilt)
    users = [action for action in bpy.data.actions if action.users == 0]
    assert users == []


def test_update_of_a_player_with_split_fade_groups_ends_with_the_same_groups_and_alphas(cache):
    # Sequence 1994 fades every label alike and 3364 fades two sets of labels differently (spec shared-fade-groups).
    folders = WALK.parent
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    first, second = (
        sum(ticks for _, ticks in frame_schedule(read_sequence(folders / name), action=False))
        for name in ("alpha-1994", "alpha-3364")
    )
    second_start = 1 + first + 5
    appearance_clip.bake_clip_to_rig(collection, folders / "alpha-1994", start=1)
    appearance_clip.bake_clip_to_rig(collection, folders / "alpha-3364", start=second_start)
    frames = [1, first, second_start, second_start + second // 2, second_start + second - 1]

    def seen(player):
        rig = appearance_collection.armature_of(player)
        mesh = appearance_collection.mesh_data(player)
        props = [
            m[appearance_fades.FADE_KEY] for m in mesh.materials if m is not None and appearance_fades.FADE_KEY in m
        ]
        keyed = []
        for strip in rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK].strips:  # pyrefly: ignore[missing-attribute]
            curves = strip.action.layers[0].strips[0].channelbags[0].fcurves
            keyed.append(sorted(c.data_path for c in curves if c.data_path.startswith('["rs_fade_')))
        alphas = []
        for frame in frames:
            bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
            slots = [mesh.materials[p.material_index] for p in mesh.polygons]
            alphas.append(
                [rig[m[appearance_fades.FADE_KEY]] if m and appearance_fades.FADE_KEY in m else 0 for m in slots]
            )
        return sorted(props), keyed, alphas

    # This checks that Update keeps what the player showed. The clip tests check the alphas against the client.
    before = seen(collection)
    assert before[0] == ["rs_fade_0_0", "rs_fade_18_0"]
    assert before[1] == [['["rs_fade_0_0"]', '["rs_fade_18_0"]']] * 2
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    (rebuilt,) = players()
    assert seen(rebuilt) == before
    assert not appearance_collection.is_edited(rebuilt)


def test_update_keeps_the_clip_strips_frames_and_the_users_own_animation(cache):
    collection = baked_player(cache, "bones")
    appearance_clip.bake_clip_to_rig(collection, WALK.parent / "idle", start=60)
    rig = appearance_collection.armature_of(collection)
    wave, step = bpy.data.actions.new("wave"), bpy.data.actions.new("step")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    track = rig.animation_data.nla_tracks.new()  # pyrefly: ignore[missing-attribute]
    track.name = "mine"
    placed = track.strips.new("step", 5, step)
    placed.influence = 0.5
    assert update(cache_folder=str(cache)) == {"FINISHED"}
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


def test_duplicate_builds_a_copy_beside_the_players_with_its_own_clips_and_animation(cache):
    collection = baked_player(cache, "bones")
    appearance_clip.bake_clip_to_rig(collection, WALK.parent / "idle", start=60)
    rig = appearance_collection.armature_of(collection)
    wave, step = bpy.data.actions.new("wave"), bpy.data.actions.new("step")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    track = rig.animation_data.nla_tracks.new()  # pyrefly: ignore[missing-attribute]
    track.name = "mine"
    track.strips.new("step", 5, step)
    originals = {strip.action for track in rig.animation_data.nla_tracks for strip in track.strips}  # pyrefly: ignore[missing-attribute]
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
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


def test_duplicating_an_edited_player_is_refused_and_adds_nothing(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    appearance_collection.mesh_data(collection).vertices[0].co.z += 7
    objects = set(bpy.data.objects)
    with pytest.raises(RuntimeError, match="has edits"):
        duplicate(cache_folder=str(cache))
    assert players() == [collection] and set(bpy.data.objects) == objects


def test_duplicating_a_player_in_edit_mode_is_refused_and_adds_nothing(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    obj = appearance_collection.mesh_of(collection)
    bpy.ops.object.mode_set(mode="EDIT")
    with pytest.raises(RuntimeError, match="Leave Edit Mode"):
        duplicate(cache_folder=str(cache))
    assert players() == [collection] and obj.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")


def test_duplicating_a_player_whose_clip_cannot_be_baked_again_adds_nothing(cache, tmp_path):
    clip = tmp_path / "walk"
    shutil.copytree(WALK, clip)
    collection = baked_player(cache, "bones", clip)
    shutil.rmtree(clip)
    objects = set(bpy.data.objects)
    with pytest.raises(RuntimeError, match="The clip folder lacks"):
        duplicate(cache_folder=str(cache))
    assert players() == [collection] and set(bpy.data.objects) == objects


def location_curve(action, bone):
    (bag,) = action.layers[0].strips[0].channelbags
    return bag.fcurves.find(f'pose.bones["{bone}"].location', index=2)


def test_strips_sharing_one_action_on_the_original_share_one_copied_action_on_the_duplicate(cache):
    collection = baked_player(cache, "bones")
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
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    strips = appearance_collection.armature_of(copy).animation_data.nla_tracks["mine"].strips  # pyrefly: ignore[missing-attribute]
    actions = {strip.action for strip in strips}
    assert len(actions) == 1 and wave not in actions
    assert [strip.action_slot.identifier for strip in strips] == [slot.identifier] * 2


def test_keys_changed_on_a_duplicate_leave_the_originals_keys_alone(cache):
    collection = baked_player(cache, "bones")
    rig = appearance_collection.armature_of(collection)
    bone = next(b for b in rig.pose.bones if not b.name.startswith(appearance_collection.BONE_PREFIX))  # pyrefly: ignore[missing-attribute]
    bone.location = (0.0, 0.0, 1.0)
    bone.keyframe_insert("location", frame=1)
    animation = rig.animation_data
    assert animation is not None and animation.action is not None and animation.action_slot is not None
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
    copy = next(c for c in players() if c is not collection)
    copied = appearance_collection.armature_of(copy).animation_data
    assert copied is not None and copied.action is not None and copied.action is not animation.action
    assert copied.action_slot is not None and copied.action_slot.identifier == animation.action_slot.identifier
    location_curve(copied.action, bone.name).keyframe_points[0].co.y = 5.0
    assert location_curve(animation.action, bone.name).keyframe_points[0].co.y == 1.0


def test_duplicating_a_player_with_a_shape_key_clip_bakes_the_copy_its_own_keys(cache):
    collection = baked_player(cache, "shape keys")
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
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


def test_duplicate_leaves_the_panel_on_the_original_while_it_holds_changes_not_yet_applied(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    changed = show(case("dragon_plate", True, [1, 2, 3, 4, 5]))
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
    assert len(players()) == 2
    assert panel().source_player == collection.name
    assert appearance_props.to_preset(panel()) == changed


def test_duplicating_an_old_label_only_player_gives_the_copy_joints_and_says_its_own_keys_stayed_behind(cache, capfd):
    collection = baked_player(cache, "bones")
    rig = appearance_collection.armature_of(collection)
    del rig[appearance_collection.JOINT_RIG_KEY]
    wave = bpy.data.actions.new("wave")
    rig.animation_data.action = wave  # pyrefly: ignore[missing-attribute]
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    capfd.readouterr()
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
    assert "were not copied" in capfd.readouterr().out
    copy = next(c for c in players() if c is not collection)
    copy_rig = appearance_collection.armature_of(copy)
    assert appearance_collection.is_joint_rig(copy_rig)
    assert copy_rig.animation_data.action is None  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.baked_clip(copy) == "bones"
    assert rig.animation_data.action == wave  # pyrefly: ignore[missing-attribute]


@pytest.mark.parametrize("method", ["shape keys", "bones"])
@pytest.mark.parametrize("rebuild", [duplicate, update], ids=["duplicate", "update"])
def test_duplicate_and_update_bake_the_clips_again_without_changing_the_scenes_rate_or_range(cache, method, rebuild):
    baked_player(cache, method)
    scene = bpy.context.scene
    assert scene is not None
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.frame_start, scene.frame_end = 3, 500
    assert rebuild(cache_folder=str(cache)) == {"FINISHED"}
    assert (scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end) == (24, 1.0, 3, 500)
    if active().mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def test_update_moves_a_users_strip_from_the_clip_track_to_the_users_track(cache):
    collection = baked_player(cache, "bones")
    rig = appearance_collection.armature_of(collection)
    turn = bpy.data.actions.new("turn")
    clips = rig.animation_data.nla_tracks[appearance_clip.CLIP_TRACK]  # pyrefly: ignore[missing-attribute]
    clips.strips.new("turn", 270, turn)
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    (rebuilt,) = players()
    tracks = appearance_collection.armature_of(rebuilt).animation_data.nla_tracks  # pyrefly: ignore[missing-attribute]
    assert [s.frame_start for s in tracks[appearance_clip.CLIP_TRACK].strips] == [1]
    assert [(s.frame_start, s.action) for s in tracks[appearance_clip.USER_TRACK].strips] == [(270, turn)]
    assert [track.name for track in tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    assert turn.users > 0


def test_update_keeps_the_users_track_above_the_clips(cache):
    collection = baked_player(cache, "bones")
    rig = appearance_collection.armature_of(collection)
    turn = bpy.data.actions.new("turn")
    rig.animation_data.nla_tracks[appearance_clip.USER_TRACK].strips.new("turn", 270, turn)  # pyrefly: ignore[missing-attribute]
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    (rebuilt,) = players()
    tracks = appearance_collection.armature_of(rebuilt).animation_data.nla_tracks  # pyrefly: ignore[missing-attribute]
    assert [track.name for track in tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    assert [s.action for s in tracks[appearance_clip.USER_TRACK].strips] == [turn]
    assert appearance_collection.armature_of(rebuilt).animation_data.action_blend_type == "COMBINE"  # pyrefly: ignore[missing-attribute]


def test_update_from_pose_mode_leaves_the_rebuilt_rig_active_in_pose_mode(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    rig = appearance_collection.armature_of(collection)
    bpy.context.view_layer.objects.active = rig  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="POSE")
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    (rebuilt,) = players()
    assert active() is appearance_collection.armature_of(rebuilt)
    assert active().mode == "POSE"
    bpy.ops.object.mode_set(mode="OBJECT")


def test_update_gives_an_old_label_only_player_joints_and_says_its_own_keys_stayed_behind(cache, capfd):
    collection = baked_player(cache, "bones")
    rig = appearance_collection.armature_of(collection)
    del rig[appearance_collection.JOINT_RIG_KEY]
    rig.animation_data.action = bpy.data.actions.new("wave")  # pyrefly: ignore[missing-attribute]
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    capfd.readouterr()
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert "were not carried over" in capfd.readouterr().out
    (rebuilt,) = players()
    new_rig = appearance_collection.armature_of(rebuilt)
    assert appearance_collection.is_joint_rig(new_rig)
    assert new_rig.animation_data.action is None  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.baked_clip(rebuilt) == "bones"


def test_update_warns_when_the_clip_folder_is_gone(cache, capfd, tmp_path):
    clip = tmp_path / "walk"
    shutil.copytree(WALK, clip)
    baked_player(cache, "bones", clip)
    shutil.rmtree(clip)
    capfd.readouterr()
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert "the baked clip could not be baked again" in capfd.readouterr().out
    (rebuilt,) = players()
    assert appearance_collection.baked_clip(rebuilt) is None


def test_update_of_a_player_baked_without_a_record_warns_that_the_clip_was_removed(cache, capfd):
    collection = baked_player(cache, "shape keys")
    del collection[appearance_collection.CLIP_KEY]
    capfd.readouterr()
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert "the baked clip (shape keys) was removed; bake it again" in capfd.readouterr().out


def test_update_of_a_player_without_a_clip_does_not_warn_about_one(cache, capfd):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    capfd.readouterr()
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert "baked clip" not in capfd.readouterr().out


def test_a_failed_update_keeps_the_old_player_and_preset(cache):
    first = show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    mesh = appearance_collection.mesh_data(collection)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    rewrite_cache(cache, lambda parts: parts["models"].pop(3379))
    with pytest.raises(RuntimeError, match="Model 3379"):
        update(cache_folder=str(cache))
    assert players() == [collection]
    assert appearance_collection.mesh_data(collection) is mesh
    assert stored(collection) == first
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1


def test_repeated_updates_do_not_leak_data(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    materials = len(bpy.data.materials)
    for outfit in ("dragon_plate", "excalibur", None, "dragon_chain"):
        show(case(outfit, False, [0, 0, 0, 0, 0]))
        assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert len(players()) == 1
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1 and len(bpy.data.materials) == materials
    assert len(bpy.data.objects) == 2


def test_update_needs_a_player(cache):
    with pytest.raises(RuntimeError, match="poll"):
        update(cache_folder=str(cache))


def test_an_edited_player_is_kept_and_the_update_is_a_separate_copy(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (old,) = players()
    appearance_collection.mesh_data(old).vertices[0].co.x += 7
    edited_x = appearance_collection.mesh_data(old).vertices[0].co.x
    preset = show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
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


def test_the_copy_of_an_edited_player_stands_to_the_right_of_it(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (old,) = players()
    appearance_collection.mesh_data(old).vertices[0].co.z += 7
    update(cache_folder=str(cache))
    new = next(c for c in players() if c is not old)
    assert x_extent(new)[0] == pytest.approx(x_extent(old)[1] + appearance_collection.PLAYER_GAP, abs=1e-3)
    assert not appearance_collection.is_edited(new)


def test_a_second_player_is_created_to_the_right_of_the_first(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (first,) = players()
    assert rig_location(first) == (0, 0, 0)
    create(cache_folder=str(cache))
    second = next(c for c in players() if c is not first)
    assert x_extent(second)[0] == pytest.approx(x_extent(first)[1] + appearance_collection.PLAYER_GAP, abs=1e-3)
    assert not appearance_collection.is_edited(second)


def test_two_players_keep_their_own_mesh_and_rig_data(cache):
    # Issue 12 asks that two players built in one file use their own mesh and armature data, and its decisions 1 and 2
    # (2026-11-10) set this check: every part's mesh, the Excalibur player's Weapon included, and the rig, and that
    # moving a vertex of one player leaves the other unedited.
    show(case("excalibur", False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    create(cache_folder=str(cache))
    first, second = players()
    first_parts, second_parts = appearance_collection.parts(first), appearance_collection.parts(second)
    assert len(first_parts) == len(second_parts) == 2
    assert not {obj.data for obj in first_parts} & {obj.data for obj in second_parts}
    assert appearance_collection.armature_data(first) != appearance_collection.armature_data(second)
    appearance_collection.mesh_data(first).vertices[0].co.x += 1
    assert appearance_collection.is_edited(first) and not appearance_collection.is_edited(second)


def test_updating_a_player_that_stands_aside_keeps_it_there(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    create(cache_folder=str(cache))
    location = rig_location()
    assert location[0] > 0
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    assert rig_location() == location


def test_updating_a_moved_turned_and_scaled_player_keeps_it_so(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (old,) = players()
    rig = appearance_collection.armature_of(old)
    rig.location = (40.0, -12.0, 3.0)
    rig.rotation_euler.z = 1.2
    rig.scale = (2.0, 2.0, 2.0)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    (player,) = players()
    rig = appearance_collection.armature_of(player)
    assert rig_location(player) == (40.0, -12.0, 3.0)
    assert rig.rotation_euler.z == pytest.approx(1.2)
    assert (rig.scale.x, rig.scale.y, rig.scale.z) == (2.0, 2.0, 2.0)
    assert not appearance_collection.is_edited(player)


def test_updating_a_player_keeps_its_rigs_parent_and_constraints(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (old,) = players()
    anchor = bpy.data.objects.new("Anchor", None)
    bpy.context.scene.collection.objects.link(anchor)  # pyrefly: ignore[missing-attribute]
    anchor.location = (5.0, 0.0, 0.0)
    rig = appearance_collection.armature_of(old)
    rig.parent = anchor
    rig.constraints.new("LIMIT_ROTATION")
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    (player,) = players()
    rig = appearance_collection.armature_of(player)
    assert rig.parent == anchor
    assert [constraint.type for constraint in rig.constraints] == ["LIMIT_ROTATION"]


def test_one_undo_restores_the_previous_player(cache):
    first = show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    vertices = len(appearance_collection.mesh_data(players()[0]).vertices)
    # Background Blender pushes undo states only when asked, so the test pushes one after each operator.
    bpy.ops.ed.undo_push(message="Player created")
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    bpy.ops.ed.undo_push(message="Player updated")
    assert len(appearance_collection.mesh_data(players()[0]).vertices) != vertices
    bpy.ops.ed.undo()
    (collection,) = players()
    assert len(appearance_collection.mesh_data(collection).vertices) == vertices
    assert stored(collection) == first


def test_empty_equipment_cancels_with_a_message_and_creates_nothing(cache):
    appearance_props.from_preset(
        bpy.context.scene.rs_appearance,  # pyrefly: ignore[missing-attribute]
        AppearancePreset(149, 430, False, (0,) * 12, (0,) * 5),
    )
    with pytest.raises(RuntimeError, match="nothing to assemble"):
        create(cache_folder=str(cache))
    assert not bpy.data.objects and not bpy.data.collections


def outer_with_extras(cache):
    """An unedited player holding a nested player, a collection of the user's, an empty and a camera, as File >
    Append and the user's own set-up leave one. Returns the names, since Update replaces the outer collection."""
    seen.clear()
    outer = make_player(cache, None)
    inner = make_player(cache, "dragon_plate")
    # Issue 27 found that File > Append links an appended player into the active collection, which this simulates.
    scene_collection().children.unlink(inner)
    outer.children.link(inner)
    own = bpy.data.collections.new("MyCollection")
    outer.children.link(own)
    outer.objects.link(bpy.data.objects.new("MyEmpty", None))
    outer.objects.link(bpy.data.objects.new("MyCamera", bpy.data.cameras.new("MyCamera")))
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(outer)  # pyrefly: ignore[missing-attribute]
    panel().source_player = outer.name
    return outer.name, inner.name


def scene_collection():
    scene = bpy.context.scene
    assert scene is not None
    return scene.collection


def held_by(name):
    """The sorted names of what the player's collection links that the add-on did not make."""
    collection = bpy.data.collections[name]
    return sorted(
        [child.name for child in collection.children]
        + [obj.name for obj in collection.objects if obj.type not in ("MESH", "ARMATURE")]
    )


EXTRAS = ["MyCamera", "MyCollection", "MyEmpty"]


def test_update_carries_what_the_add_on_did_not_make_into_the_rebuilt_player(cache):
    # Issue 27, decisions 1 and 2: Update no longer refuses a player holding them, and links them into the rebuilt one.
    outer, inner = outer_with_extras(cache)
    cameras, meshes = len(bpy.data.cameras), len(bpy.data.meshes)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert held_by(outer) == sorted([inner, *EXTRAS])
    assert len(bpy.data.cameras) == cameras and len(bpy.data.meshes) == meshes
    # ADR 0015: the rebuilt player stores the settings it was built from.
    assert stored(bpy.data.collections[outer]) == show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    assert not appearance_collection.is_edited(bpy.data.collections[outer])


def test_the_nested_player_stays_a_working_unedited_player_after_update(cache):
    # Issue 27, decision 2 (story 3): the nested player is neither rebuilt nor changed.
    outer, inner = outer_with_extras(cache)
    nested_mesh = appearance_collection.mesh_data(bpy.data.collections[inner])
    nested_preset = stored(bpy.data.collections[inner])
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    nested = bpy.data.collections[inner]
    assert appearance_collection.mesh_data(nested) is nested_mesh
    assert stored(nested) == nested_preset
    assert not appearance_collection.is_edited(nested)
    assert [c.name for c in bpy.data.collections[outer].children if c.name == inner] == [inner]
    assert inner not in [c.name for c in scene_collection().children]


def test_a_carried_object_keeps_its_transform_parent_and_other_collections(cache):
    # Issue 27, decisions 1 and 3 (story 6): objects are linked, not copied.
    outer, _ = outer_with_extras(cache)
    empty = bpy.data.objects["MyEmpty"]
    empty.location = (1.0, 2.0, 3.0)
    child = bpy.data.objects.new("MyChild", None)
    child.parent = empty
    bpy.data.collections[outer].objects.link(child)
    elsewhere = bpy.data.collections.new("Elsewhere")
    scene_collection().children.link(elsewhere)
    elsewhere.objects.link(empty)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    assert bpy.data.objects["MyEmpty"] is empty and empty.location.to_tuple() == (1.0, 2.0, 3.0)
    assert child.parent is empty
    assert {c.name for c in empty.users_collection} == {outer, "Elsewhere"}


def test_update_of_an_edited_player_keeps_it_with_its_extras_and_builds_the_copy_without_them(cache):
    # Issue 27, decision 4 (story 9).
    outer, inner = outer_with_extras(cache)
    appearance_collection.mesh_data(bpy.data.collections[outer]).vertices[0].co.x += 7
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert held_by(outer) == sorted([inner, *EXTRAS])
    (copy,) = [c for c in players() if c.name not in (outer, inner)]
    assert held_by(copy.name) == []


def test_duplicate_copies_only_the_player(cache):
    # Issue 27, decision 4 (story 10).
    outer, inner = outer_with_extras(cache)
    assert duplicate(cache_folder=str(cache)) == {"FINISHED"}
    assert held_by(outer) == sorted([inner, *EXTRAS])
    (copy,) = [c for c in players() if c.name not in (outer, inner)]
    assert held_by(copy.name) == []


def test_removing_a_player_still_refuses_while_it_holds_what_the_add_on_did_not_make(cache):
    # Issue 27, decision 1 (story 11): removal, unlike Update, would take them away.
    outer, inner = outer_with_extras(cache)
    collection = bpy.data.collections[outer]
    meshes, armatures = len(bpy.data.meshes), len(bpy.data.armatures)
    with pytest.raises(ValueError, match="MyCollection.*MyCamera|MyCamera.*MyCollection"):
        appearance_collection.remove_collection(collection)
    assert held_by(outer) == sorted([inner, *EXTRAS])
    assert len(bpy.data.meshes) == meshes and len(bpy.data.armatures) == armatures


def test_a_failed_update_leaves_the_extras_in_the_old_player(cache):
    # Issue 27, decision 4 (story 12).
    outer, inner = outer_with_extras(cache)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    rewrite_cache(cache, lambda parts: parts["models"].pop(3379))
    with pytest.raises(RuntimeError, match="Model 3379"):
        update(cache_folder=str(cache))
    assert held_by(outer) == sorted([inner, *EXTRAS])


def test_one_undo_after_update_brings_the_extras_back_in_the_old_player(cache):
    # The update-carries-extras spec, story 13: Undo brings the player back with its extras, as it does today.
    outer, inner = outer_with_extras(cache)
    before = stored(bpy.data.collections[outer])
    vertices = len(appearance_collection.mesh_data(bpy.data.collections[outer]).vertices)
    bpy.ops.ed.undo_push(message="Player set up")
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    bpy.ops.ed.undo_push(message="Player updated")
    # Update changed the player, so the checks below can only hold for the player as it was.
    assert len(appearance_collection.mesh_data(bpy.data.collections[outer]).vertices) != vertices
    bpy.ops.ed.undo()
    collection = bpy.data.collections[outer]
    assert stored(collection) == before
    assert len(appearance_collection.mesh_data(collection).vertices) == vertices
    assert held_by(outer) == sorted([inner, *EXTRAS])


def view_layer():
    layer = bpy.context.view_layer
    assert layer is not None
    return layer


def layer_collection(name):
    """The view layer's entry for the collection of that name; the test fails when there is none."""
    found = _find_layer_collection(name, view_layer().layer_collection)
    assert found is not None, f"No layer collection named {name}"
    return found


def _find_layer_collection(name, parent):
    if parent.name == name:
        return parent
    return next((found for child in parent.children if (found := _find_layer_collection(name, child))), None)


def world_difference(first, second):
    return max(abs(first[row][column] - second[row][column]) for row in range(4) for column in range(4))


def test_an_extra_parented_or_constrained_to_the_old_player_follows_to_the_rebuilt_one(cache):
    # Spec story 6: the carried objects keep their parents, so ones parented to the old player's own objects move
    # to the rebuilt ones and stay where they were.
    outer, _ = outer_with_extras(cache)
    collection = bpy.data.collections[outer]
    on_rig, on_body, constrained = (
        bpy.data.objects["MyEmpty"],
        bpy.data.objects["MyCamera"],
        bpy.data.objects.new("Follower", None),
    )
    collection.objects.link(constrained)
    appearance_collection.armature_of(collection).location = (5.0, 0.0, 0.0)
    on_rig.parent = appearance_collection.armature_of(collection)
    on_rig.location = (0.0, 2.0, 1.0)
    on_body.parent = appearance_collection.mesh_of(collection)
    on_body.location = (1.0, 0.0, 3.0)
    constrained.constraints.new("COPY_LOCATION").target = appearance_collection.armature_of(collection)  # pyrefly: ignore[missing-attribute]
    view_layer().update()
    rig_world, body_world = on_rig.matrix_world.copy(), on_body.matrix_world.copy()
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    rebuilt = bpy.data.collections[outer]
    view_layer().update()
    assert on_rig.parent is appearance_collection.armature_of(rebuilt)
    assert on_body.parent is appearance_collection.mesh_of(rebuilt)
    assert constrained.constraints[0].target is appearance_collection.armature_of(rebuilt)  # pyrefly: ignore[missing-attribute]
    assert world_difference(on_rig.matrix_world, rig_world) < 1e-4
    assert world_difference(on_body.matrix_world, body_world) < 1e-4


def armed_player(armed_cache):
    seen.clear()
    appearance_props.from_preset(panel(), AppearancePreset(149, 430, False, ARMED, (0,) * 5))
    create(cache_folder=str(armed_cache))
    (collection,) = players()
    empty = bpy.data.objects.new("OnWeapon", None)
    collection.objects.link(empty)
    (weapon,) = (obj for obj in collection.objects if obj.get(appearance_collection.PART_KEY) == "Weapon")
    empty.parent = weapon
    # Moving the weapon would be an edit, so the empty carries the offset in its parent inverse instead.
    empty.matrix_parent_inverse = Matrix.Translation((4.0, 0.0, 0.0))
    empty.location = (0.0, 1.0, 2.0)
    view_layer().update()
    return collection.name, empty, empty.matrix_world.copy()


def test_an_extra_parented_to_a_weapon_the_rebuilt_player_still_wears_follows_the_new_weapon(armed_cache):
    name, empty, world = armed_player(armed_cache)
    assert update(cache_folder=str(armed_cache)) == {"FINISHED"}
    (weapon,) = (
        obj for obj in bpy.data.collections[name].objects if obj.get(appearance_collection.PART_KEY) == "Weapon"
    )
    view_layer().update()
    assert empty.parent is weapon and world_difference(empty.matrix_world, world) < 1e-4


def test_an_extra_parented_to_a_weapon_the_rebuilt_player_no_longer_wears_loses_its_parent_and_stays_put(armed_cache):
    name, empty, world = armed_player(armed_cache)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert update(cache_folder=str(armed_cache)) == {"FINISHED"}
    view_layer().update()
    assert empty.parent is None and world_difference(empty.matrix_world, world) < 1e-4
    assert "OnWeapon" in held_by(name)


def test_update_keeps_the_view_layer_state_of_the_player_its_collections_and_its_objects(cache):
    # Spec story 2: the Outliner looks as the user left it, so Update restores what linking again resets.
    outer, inner = outer_with_extras(cache)
    layer_collection(inner).hide_viewport = True
    layer_collection("MyCollection").exclude = True
    layer_collection(outer).holdout = True
    bpy.data.objects["MyEmpty"].hide_set(True)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    assert layer_collection(inner).hide_viewport
    assert layer_collection("MyCollection").exclude
    assert layer_collection(outer).holdout
    assert bpy.data.objects["MyEmpty"].hide_get()
    assert not layer_collection(inner).exclude and not bpy.data.objects["MyCamera"].hide_get()


def test_updating_a_nested_player_keeps_it_inside_the_outer_player(cache):
    # Spec story 3: the nested player stays a player the user can update, and stays nested.
    outer, inner = outer_with_extras(cache)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(bpy.data.collections[inner])  # pyrefly: ignore[missing-attribute]
    panel().source_player = inner
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert inner in [child.name for child in bpy.data.collections[outer].children]
    assert inner not in [child.name for child in scene_collection().children]
    assert held_by(outer) == sorted([inner, *EXTRAS])


def test_a_removal_that_fails_puts_the_extras_back_in_the_old_player(cache, monkeypatch):
    # Spec story 12, past the point where Update has lifted the extras out.
    outer, inner = outer_with_extras(cache)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))

    def fail(collection):
        raise RuntimeError("removal failed")

    monkeypatch.setattr(appearance_collection, "remove_collection", fail)
    with pytest.raises(RuntimeError, match="removal failed"):
        update(cache_folder=str(cache))
    assert held_by(outer) == sorted([inner, *EXTRAS])


def test_a_second_update_still_carries_the_extras_and_leaves_the_player_unedited(cache):
    # Spec stories 7 and 8: the rebuilt player is a player like any other, so Update works on it again.
    outer, inner = outer_with_extras(cache)
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    show(case(None, False, [0, 0, 0, 0, 0]))
    update(cache_folder=str(cache))
    assert held_by(outer) == sorted([inner, *EXTRAS])
    assert not appearance_collection.is_edited(bpy.data.collections[outer])
    assert len(players()) == 2


def test_update_refuses_a_player_in_edit_mode_and_keeps_the_edit(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = players()
    obj = appearance_collection.mesh_of(collection)
    bpy.ops.object.mode_set(mode="EDIT")
    edited = bmesh.from_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    edited.verts.ensure_lookup_table()
    edited.verts[0].co.x += 50
    moved = edited.verts[0].co.x
    bmesh.update_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    with pytest.raises(RuntimeError, match="Edit Mode"):
        update(cache_folder=str(cache))
    assert players() == [collection] and obj.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")
    assert appearance_collection.mesh_data(collection).vertices[0].co.x == pytest.approx(moved)


@pytest.mark.parametrize("kind", ["mesh", "armature"])
def test_create_refuses_while_any_mesh_or_armature_is_in_edit_mode_and_changes_nothing(cache, kind):
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
        create(cache_folder=str(cache))
    assert players() == [] and other.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")


def panel():
    return bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]


def make_player(cache, outfit):
    show(case(outfit, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    (collection,) = [c for c in players() if c.name not in seen]
    seen.add(collection.name)
    return collection


seen: set[str] = set()


def test_create_ties_the_panel_to_the_new_player(cache):
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    assert panel().source_player == players()[0].name


def test_updating_a_player_the_panel_is_not_tied_to_is_refused_and_changes_nothing(cache):
    seen.clear()
    first = make_player(cache, None)
    second = make_player(cache, "dragon_plate")
    stored_second = stored(second)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    assert panel().source_player == second.name
    with pytest.raises(RuntimeError, match="Load Player Settings"):
        update(cache_folder=str(cache))
    assert stored(second) == stored_second and len(players()) == 2


def test_load_player_settings_fills_the_panel_from_the_players_stored_preset(cache):
    seen.clear()
    first = make_player(cache, None)
    make_player(cache, "dragon_plate")
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    assert bpy.ops.rsps.load_player_settings() == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
    assert appearance_props.to_preset(panel()) == stored(first)
    assert panel().source_player == first.name
    assert update(cache_folder=str(cache)) == {"FINISHED"}


def select(obj):
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    appearance_collection.follow_selection(bpy.context)


def test_selecting_another_player_loads_its_settings_into_the_panel(cache):
    seen.clear()
    first = make_player(cache, None)
    make_player(cache, "dragon_plate")
    select(appearance_collection.armature_of(first))
    assert appearance_props.to_preset(panel()) == stored(first)
    assert panel().source_player == first.name
    assert not appearance_collection.holds_unapplied_settings(panel())


def test_selecting_a_players_weapon_loads_its_settings(armed_cache):
    seen.clear()
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(armed_cache))
    (plain,) = players()
    appearance_props.from_preset(panel(), AppearancePreset(149, 430, False, ARMED, (0,) * 5))
    create(cache_folder=str(armed_cache))
    armed = next(c for c in players() if c is not plain)
    select(appearance_collection.mesh_of(plain))
    (weapon,) = (obj for obj in armed.objects if obj.get(appearance_collection.PART_KEY) == "Weapon")
    select(weapon)
    assert panel().source_player == armed.name
    assert appearance_props.to_preset(panel()) == stored(armed)


def test_selecting_another_player_keeps_changes_not_yet_applied_with_update(cache):
    seen.clear()
    first = make_player(cache, None)
    second = make_player(cache, "dragon_plate")
    panel().colours[0] = 1
    changed = appearance_props.to_preset(panel())
    select(appearance_collection.mesh_of(first))
    assert appearance_props.to_preset(panel()) == changed
    assert panel().source_player == second.name
    assert appearance_collection.holds_unapplied_settings(panel())


def test_selecting_a_player_keeps_the_settings_of_a_preset_file(cache):
    seen.clear()
    first = make_player(cache, None)
    from_file = show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = ""
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == ""
    assert appearance_props.to_preset(panel()) == from_file


def test_selecting_an_object_of_no_player_leaves_the_panel_as_it_is(cache):
    seen.clear()
    first = make_player(cache, None)
    lamp = bpy.data.objects.new("Lamp", bpy.data.lights.new("Lamp", "POINT"))
    bpy.context.scene.collection.objects.link(lamp)  # pyrefly: ignore[missing-attribute]
    select(lamp)
    assert panel().source_player == first.name
    assert appearance_props.to_preset(panel()) == stored(first)


def test_selecting_a_renamed_player_whose_settings_the_panel_holds_ties_the_panel_to_it(cache):
    seen.clear()
    first = make_player(cache, None)
    first.name = "Guard"
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == "Guard"


def test_a_panel_tied_to_a_deleted_player_keeps_its_settings_and_may_update_another(cache):
    seen.clear()
    first = make_player(cache, None)
    second = make_player(cache, "dragon_plate")
    held = appearance_props.to_preset(panel())
    appearance_collection.remove_collection(second)
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == ""
    assert appearance_props.to_preset(panel()) == held
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert stored(players()[0]) == held


def test_a_player_whose_settings_the_panel_refuses_leaves_the_panel_and_says_why(cache):
    seen.clear()
    first = make_player(cache, None)
    second = make_player(cache, "dragon_plate")
    first[appearance_preview.PRESET_KEY] = dumps_preset(dataclasses.replace(stored(first), client_revision=170))
    select(appearance_collection.mesh_of(first))
    assert panel().source_player == second.name
    assert "client revision 170" in panel().last_error


def test_the_panel_follows_the_active_player_after_an_undo(cache):
    seen.clear()
    first = make_player(cache, None)
    make_player(cache, "dragon_plate")
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(first)  # pyrefly: ignore[missing-attribute]
    appearance_collection.follow_active_player()
    assert panel().source_player == first.name


def test_a_panel_loaded_from_a_preset_file_may_update_any_player(cache):
    seen.clear()
    make_player(cache, None)
    panel().source_player = ""
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = ""
    assert update(cache_folder=str(cache)) == {"FINISHED"}


def test_an_edited_players_copy_becomes_the_tied_player(cache):
    seen.clear()
    first = make_player(cache, None)
    appearance_collection.mesh_data(first).vertices[0].co.x += 7
    show(case("dragon_plate", False, [0, 0, 0, 0, 0]))
    panel().source_player = first.name
    update(cache_folder=str(cache))
    copy = next(c for c in players() if c is not first)
    assert panel().source_player == copy.name


ARMED = (0, 0, 0, 512 + 1333, 274, 512 + 1201, 282, 292, 256, 289, 298, 266)


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_update_bakes_a_clip_with_held_items_again_with_them(armed_cache, method):
    appearance_props.from_preset(bpy.context.scene.rs_appearance, AppearancePreset(149, 430, False, ARMED, (0,) * 5))  # pyrefly: ignore[missing-attribute]
    create(cache_folder=str(armed_cache))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, FIXTURES.parent / "animation149/held-1365", action=True, cache_folder=str(armed_cache))
    assert update(cache_folder=str(armed_cache)) == {"FINISHED"}
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


def test_create_twice_and_update_once_read_the_item_catalog_once(cache, monkeypatch):
    # The user chose that Create and Update share one parsed copy of the catalogs per cache folder (issue 29,
    # decision 2, 2026-11-10).
    loads = count_item_catalog_loads(monkeypatch)
    show(case(None, False, [0, 0, 0, 0, 0]))
    create(cache_folder=str(cache))
    create(cache_folder=str(cache))
    assert update(cache_folder=str(cache)) == {"FINISHED"}
    assert loads == [cache]


def test_create_reuses_the_item_catalog_the_panel_read(cache, monkeypatch):
    # The user chose that the panel and Create share one parsed copy of the catalogs per cache folder (issue 29,
    # decision 2, 2026-11-10). Item 35 is named Excalibur, as its row in the fixture ItemDefinitions.json says.
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    loads = count_item_catalog_loads(monkeypatch)
    assert appearance_items.item_name(35) == "Excalibur"
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert loads == [cache]


def test_changing_the_cache_folder_preference_uses_that_folders_item_catalog(cache, monkeypatch, tmp_path_factory):
    # The user asked that changing the cache folder preference uses that folder's catalog, as before (spec of the
    # shared catalog cache, user story 5).
    other = tmp_path_factory.mktemp("other_cache")
    shutil.copytree(cache, other, dirs_exist_ok=True)
    rewrite_cache(other, rename_item(35, "Excalibur", "Renamed sword"))
    loads = count_item_catalog_loads(monkeypatch)
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    assert appearance_items.item_name(35) == "Excalibur"
    monkeypatch.setattr(preferences, "cache_folder", lambda: other)
    assert appearance_items.item_name(35) == "Renamed sword"
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert loads == [cache, other]


def test_a_missing_item_group_names_the_preference_at_every_create(cache):
    # The user asked that a missing catalog gives the same message at every Create (spec of the shared catalog cache,
    # user story 6). The spec of 2026-11-11 in spec/ that made the Cache folder the only cache setting changed the
    # message to name that preference.
    rewrite_cache(cache, lambda parts: parts["items"].clear())
    show(case(None, False, [0, 0, 0, 0, 0]))
    for _ in range(2):
        with pytest.raises(RuntimeError, match=r"no group 10 .*Set the Cache folder in the add-on preferences"):
            create(cache_folder=str(cache))
    assert not players()


@pytest.mark.parametrize("method", ["shape keys", "bones"])
def test_a_held_item_bake_reuses_the_item_catalog_create_read(armed_cache, monkeypatch, method):
    # The user chose that held-item bakes share Create's parsed copy of the catalogs (issue 29, decision 2,
    # 2026-11-10).
    loads = count_item_catalog_loads(monkeypatch)
    appearance_props.from_preset(bpy.context.scene.rs_appearance, AppearancePreset(149, 430, False, ARMED, (0,) * 5))  # pyrefly: ignore[missing-attribute]
    create(cache_folder=str(armed_cache))
    (collection,) = players()
    bake = appearance_clip.bake_clip if method == "shape keys" else appearance_clip.bake_clip_to_rig
    bake(collection, FIXTURES.parent / "animation149/held-1365", action=True, cache_folder=str(armed_cache))
    assert "Player Steel axe" in [obj.name for obj in appearance_collection.parts(collection)]
    assert loads == [armed_cache]


def rename_item(item_id, old, new):
    """A cache change that renames an item, by replacing the zero-ended name text in its definition."""

    def change(parts):
        parts["items"][item_id] = parts["items"][item_id].replace(old.encode() + b"\0", new.encode() + b"\0")

    return change


def test_the_item_search_after_create_sees_a_renamed_item(cache, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Item 35 is named Excalibur, as its row in the fixture ItemDefinitions.json says.
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert appearance_items.item_name(35) == "Excalibur"
    rewrite_cache(cache, rename_item(35, "Excalibur", "Renamed sword"))
    assert appearance_items.item_name(35) == "Renamed sword"


def search_labels(slot):
    """The labels the item search popup of a slot lists, by item id. The popup reads only the operator's slot, so a
    stand-in is enough."""
    choices = appearance_items._slot_items(type("Operator", (), {"slot": slot})(), bpy.context)
    return {identifier: label for identifier, label, _ in choices}


def test_the_item_search_popup_after_create_lists_a_renamed_item(cache, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10). Item 2653 is the Zamorak platebody, a male body item, in the fixture
    # ItemDefinitions.json.
    monkeypatch.setattr(preferences, "cache_folder", lambda: cache)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create() == {"FINISHED"}
    assert "Zamorak platebody" in search_labels(4)["2653"]
    rewrite_cache(cache, rename_item(2653, "Zamorak platebody", "Renamed platebody"))
    label = search_labels(4)["2653"]
    assert "Renamed platebody" in label and "Zamorak platebody" not in label


def test_create_after_create_sees_an_item_a_changed_cache_added_and_reads_the_catalog_once_more(cache, monkeypatch):
    # The user chose that a catalog whose files' modified times change is parsed again at the next use, and that an
    # unchanged one is shared (issue 29, decisions 2 and 3, 2026-11-10). Item 9035 is a copy of Excalibur (item 35)
    # under an id the fixture cache lacks.
    def add_sword(parts):
        parts["items"][9035] = parts["items"][35]

    loads = count_item_catalog_loads(monkeypatch)
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create(cache_folder=str(cache)) == {"FINISHED"}
    equipment = list(case("excalibur", False, [0, 0, 0, 0, 0])["equipment"])
    equipment[3] = 512 + 9035
    bpy.context.scene.rs_appearance.equipment = equipment  # pyrefly: ignore[missing-attribute]
    rewrite_cache(cache, add_sword)
    assert create(cache_folder=str(cache)) == {"FINISHED"}
    assert create(cache_folder=str(cache)) == {"FINISHED"}
    assert loads == [cache] * 2


def test_create_after_create_sees_a_kit_a_changed_cache_removed(cache):
    # The user chose that each catalog whose files' modified times change is parsed again at the next use (issue 29,
    # decision 3, 2026-11-10), so Create refuses a look whose kit the changed cache lacks instead of building it from the
    # old catalog. The default male look wears torso kit 18 (equipment 274 in reference.json).
    show(case(None, False, [0, 0, 0, 0, 0]))
    assert create(cache_folder=str(cache)) == {"FINISHED"}
    rewrite_cache(cache, lambda parts: parts["kits"].pop(18))
    with pytest.raises(RuntimeError):
        create(cache_folder=str(cache))
    assert len(players()) == 1
