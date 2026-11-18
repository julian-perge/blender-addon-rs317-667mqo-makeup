"""Create NPC by id, from snapshot 430 (spec 13, issue 92)."""

import dataclasses
import json
import math
import os
import re
import types
from pathlib import Path

import bmesh
import bpy
import pytest
from mathutils import Matrix, Vector

from rsps_toolkit.animation.clip import CacheClip, pose_vertices, read_sequence
from rsps_toolkit.animation.frames import decode_frame_map, decode_sequence, frame_schedule
from rsps_toolkit.animation.label_fit import fit_frame, fitted_vertices
from rsps_toolkit.blender import (
    appearance_clip,
    appearance_collection,
    appearance_preview,
    appearance_props,
    npc_collection,
    npc_panel,
    rs_layers,
)
from rsps_toolkit.blender import mesh as blender_mesh
from rsps_toolkit.blender.face_materials import DEFAULT_BRIGHTNESS, srgb_to_linear
from rsps_toolkit.formats.appearance_preset import AppearancePreset
from rsps_toolkit.formats.appearance_rig import derive_rig, frame_map_joint_specs, load_joint_specs
from rsps_toolkit.formats.cache_profile import shared_profile
from rsps_toolkit.formats.colour import face_colour_to_rgb
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.npc_definition import npc_model, read_npc

SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
pytestmark = [
    pytest.mark.skipif(
        not ("RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()),
        reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
    ),
    pytest.mark.usefixtures("registered"),
]
FIXTURES = Path(__file__).parent.parent / "fixtures"
LIT = json.loads((FIXTURES / "npc" / "lit.json").read_text())["npcs"]
APPEARANCE = json.loads((FIXTURES / "appearance" / "reference.json").read_text())
# The unchanged revision 149 client posing each test NPC with every frame of its stand and walk clips, recorded by
# tests/fixtures/record_npc.py from the clip folders in tests/fixtures/npc/clips.
POSES = json.loads((FIXTURES / "npc" / "poses.json").read_text())
NPC_CLIPS = FIXTURES / "npc" / "clips"
# The five test NPCs of spec 13: the gnome, the ent, the cow, the green dragon and the giant spider.
TEST_NPCS = (4233, 6594, 2805, 260, 2477)
MAN = 3078


@pytest.fixture
def registered(clean):
    classes = (
        *appearance_props.classes,
        *appearance_collection.classes,
        *npc_collection.classes,
        *npc_panel.classes,
    )
    for cls in classes:
        bpy.utils.register_class(cls)
    appearance_props.register_properties()
    npc_collection.register_properties()
    yield
    npc_collection.unregister_properties()
    appearance_props.unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def create(npc_id: int):
    return bpy.ops.rsps.create_npc(npc_id=npc_id, cache_folder=str(SNAPSHOT_430))  # pyrefly: ignore[missing-attribute]


def active() -> bpy.types.Object:
    obj = bpy.context.view_layer.objects.active  # pyrefly: ignore[missing-attribute]
    assert obj is not None
    return obj


def created(npc_id: int) -> bpy.types.Collection:
    assert create(npc_id) == {"FINISHED"}
    collection = npc_collection.npc_of(active())
    assert collection is not None
    return collection


def mesh(collection: bpy.types.Collection) -> bpy.types.Mesh:
    data = appearance_collection.mesh_of(collection).data
    assert isinstance(data, bpy.types.Mesh)
    return data


def blender_data() -> dict[str, list[str]]:
    return {
        kind: sorted(item.name for item in getattr(bpy.data, kind))
        for kind in ("collections", "objects", "meshes", "armatures", "materials")
    }


@pytest.mark.parametrize("npc_id", (*TEST_NPCS, MAN))
def test_each_test_npc_shows_the_lit_colours_of_the_revision_149_client(npc_id):
    client = LIT[str(npc_id)]
    data = mesh(created(npc_id))
    assert_client_lit_colours(data, client)
    faces = appearance_preview.face_indices(data)
    assert faces is not None
    if npc_id in TEST_NPCS:
        # None of the five has a face that repeats a vertex or lies exactly on another, so the mesh holds every face.
        assert sorted(faces) == list(range(client["face_count"]))
    else:
        assert len(set(faces)) == len(faces) <= client["face_count"]


def assert_client_lit_colours(data: bpy.types.Mesh, client: dict) -> None:
    # tests/fixtures/npc/lit.json: the unchanged revision 149 client's getModel. The client marks a flat-shaded face
    # with a third colour of -1 and shows its first colour at every corner.
    faces = appearance_preview.face_indices(data)
    assert faces is not None
    colours = data.color_attributes[appearance_preview.LIT_ATTRIBUTE].data  # pyrefly: ignore[missing-attribute]
    for polygon, face in zip(data.polygons, faces, strict=True):
        shades = [client["g"][face]] * 3 if client["t"][face] == -1 else [client[k][face] for k in "gkt"]
        expected = [tuple(srgb_to_linear(c / 255) for c in face_colour_to_rgb(s, DEFAULT_BRIGHTNESS)) for s in shades]
        for corner, want in zip(polygon.loop_indices, expected, strict=True):
            assert tuple(colours[corner].color[:3]) == pytest.approx(want, abs=1e-6)


@pytest.mark.parametrize("npc_id", TEST_NPCS)
def test_each_test_npc_stands_where_the_client_puts_its_scaled_vertices(npc_id):
    # The client scales after the pose with whole game units, so a vertex may differ from the client's by less than
    # 1. Game (x, y, z) is Blender (x, z, -y), and the rig's placement is left out.
    client = LIT[str(npc_id)]
    collection = created(npc_id)
    rig = appearance_collection.armature_of(collection)
    mesh_obj = appearance_collection.mesh_of(collection)
    vertices = appearance_preview.vertex_indices(mesh(collection))
    to_rig = rig.matrix_world.inverted() @ mesh_obj.matrix_world
    scale = rig.matrix_world.to_scale()
    for vertex, model_vertex in zip(mesh(collection).vertices, vertices, strict=True):
        local = to_rig @ vertex.co
        placed = (local.x * scale.x, local.y * scale.y, local.z * scale.z)
        x, y, z = (client[k][model_vertex] for k in "els")
        assert placed == pytest.approx((x, z, -y), abs=1)


def test_the_green_dragons_rig_carries_its_scale():
    # docs/research/13-npc-rigs.md: the green dragon has width and height scale 110. Width scales game x and z, which
    # are Blender x and y, and height scales Blender z.
    rig = appearance_collection.armature_of(created(260))
    assert (rig.scale.x, rig.scale.y, rig.scale.z) == pytest.approx((110 / 128, 110 / 128, 110 / 128))


def test_the_width_scale_goes_on_blender_x_and_y_and_the_height_scale_on_blender_z(monkeypatch):
    # NPCComposition.getModel lines 436 to 437 scale game x and z by the width and game height by the height. Game
    # (x, y, z) is Blender (x, z, -y).
    read = npc_collection.read_npc
    monkeypatch.setattr(
        npc_collection,
        "read_npc",
        lambda store, npc_id: dataclasses.replace(read(store, npc_id), width_scale=64, height_scale=256),
    )
    rig = appearance_collection.armature_of(created(2805))
    assert (rig.scale.x, rig.scale.y, rig.scale.z) == pytest.approx((0.5, 0.5, 2.0))


def joint_names(collection: bpy.types.Collection) -> list[str]:
    data = appearance_collection.armature_data(collection)
    return [bone.name for bone in data.bones if not bone.name.startswith(appearance_collection.BONE_PREFIX)]


def stand_frame_map(npc_id: int):
    store = Js5Store(SNAPSHOT_430)
    clip = CacheClip(store, read_npc(store, npc_id).stand)
    group, file = decode_sequence(clip.sequence_bytes()).frames[0]
    map_id = int.from_bytes(clip.frame_bytes(group, file)[:2], "big")
    return map_id, decode_frame_map(clip.frame_map_bytes(map_id))


@pytest.mark.parametrize(
    ("npc_id", "frame_map_id", "count"),
    # docs/research/13-npc-rigs.md: the frame map of each stand sequence, and the joint count of the second probe, which
    # applies the rule of ADR 0025 with the pivot check of issue 91.
    [(4233, 319, 14), (6594, 1615, 69), (2805, 1338, 31), (260, 1080, 58), (2477, 1248, 41)],
)
def test_each_test_npc_has_generic_joints_from_the_frame_map_of_its_stand_sequence(npc_id, frame_map_id, count):
    collection = created(npc_id)
    names = joint_names(collection)
    assert all(re.fullmatch(r"joint_\d+(\.[LR])?(_\d+)?", name) for name in names)
    map_id, frame_map = stand_frame_map(npc_id)
    assert map_id == frame_map_id
    store = Js5Store(SNAPSHOT_430)
    model = npc_model(read_npc(store, npc_id), shared_profile(SNAPSHOT_430).load_model)
    assert model.vertex_skins is not None
    specs = frame_map_joint_specs(map_id, frame_map, model.vertex_skins)
    assert sorted(names) == sorted(joint.name for joint in derive_rig(model, specs).joints)
    assert len(names) == count


def test_man_gets_the_15_player_joints():
    # NPC 3078 stands on frame map 0, the player's (docs/research/13-npc-rigs.md), which uses data/player_joints.json.
    names = joint_names(created(MAN))
    assert {re.sub(r"\.[LR]$", "", name) for name in names} == {spec.name for spec in load_joint_specs()}
    assert len(names) == 15


def test_the_npc_collection_stores_the_npc_its_frame_map_and_its_sequences_and_no_preset():
    # docs/research/13-npc-rigs.md: the gnome stands with sequence 195 and walks with 189 on frame map 319. Its
    # definition names no other sequence (tests/fixtures/npc/npcs.json).
    collection = created(4233)
    assert json.loads(collection[npc_collection.NPC_KEY]) == {
        "npc": 4233,
        "name": "Gnome",
        "frame_map": 319,
        "sequences": {"stand": 195, "walk": 189},
    }
    assert appearance_preview.PRESET_KEY not in collection
    assert appearance_preview.collection_of(appearance_collection.mesh_of(collection)) is None
    assert not appearance_collection.is_edited(collection)


def test_moving_a_vertex_of_an_npc_counts_as_an_edit():
    collection = created(4233)
    mesh(collection).vertices[0].co.x += 5
    assert appearance_collection.is_edited(collection)


def test_removing_a_vertex_group_of_an_npc_counts_as_an_edit():
    collection = created(4233)
    mesh_obj = appearance_collection.mesh_of(collection)
    mesh_obj.vertex_groups.remove(mesh_obj.vertex_groups[0])
    assert appearance_collection.is_edited(collection)


def test_a_new_npc_starts_a_player_gap_right_of_every_player_and_npc_mesh():
    case = APPEARANCE["cases"][0]
    preset = AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))
    body, shading, slots = appearance_preview.assemble_parts(preset, SNAPSHOT_430)
    appearance_collection.build_collection(body, shading, preset, "Player", slots=slots)
    first = created(260)
    second = created(4233)

    def edges(collection, pick):
        obj = appearance_collection.mesh_of(collection)
        return pick((obj.matrix_world @ Vector(corner)).x for corner in obj.bound_box)

    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]
    player = bpy.data.collections["Player"]
    assert edges(first, min) == pytest.approx(edges(player, max) + appearance_collection.PLAYER_GAP, abs=1e-3)
    assert edges(second, min) == pytest.approx(edges(first, max) + appearance_collection.PLAYER_GAP, abs=1e-3)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda npc: dataclasses.replace(npc, models=()), "has no models"),
        (lambda npc: dataclasses.replace(npc, stand=-1), "has no stand sequence"),
        (lambda npc: dataclasses.replace(npc, models=(*npc.models, 146)), "without vertex skins.*: 146$"),
    ],
    ids=["no models", "no stand sequence", "model without vertex skins"],
)
def test_create_npc_refuses_an_npc_it_cannot_rig_and_changes_nothing(monkeypatch, change, message):
    # Model 146 of snapshot 430 has no vertex skins, as the add-on's decoder read it on 2026-11-16 (a scratch scan of
    # models 1 to 3000). The test fails if that is wrong, because the refusal would then not name it.
    read = npc_collection.read_npc
    monkeypatch.setattr(npc_collection, "read_npc", lambda store, npc_id: change(read(store, npc_id)))
    before = blender_data()
    with pytest.raises(RuntimeError, match=message):
        create(4233)
    assert blender_data() == before


def textured_first_face(model):
    data = model.new_data
    if data is not None:
        data = dataclasses.replace(data, textured_face_colours=(model.face_colours[0], *data.textured_face_colours[1:]))
    return dataclasses.replace(
        model,
        face_textures=[5, *model.face_textures[1:]],
        face_colours=[None, *model.face_colours[1:]],
        new_data=data,
    )


def alpha_on_first_face(alpha):
    return lambda model: dataclasses.replace(model, face_alphas=[alpha, *model.face_alphas[1:]])


UNDRAWN_FACES = pytest.mark.parametrize(
    ("change", "message"),
    [
        (textured_first_face, "Lighting of textured faces is not verified against the client"),
        (alpha_on_first_face(254), "Lighting of faces with alpha 254 or 255 is not verified against the client"),
        (alpha_on_first_face(255), "Lighting of faces with alpha 254 or 255 is not verified against the client"),
    ],
    ids=["textured face", "alpha 254", "alpha 255"],
)


@UNDRAWN_FACES
def test_create_npc_refuses_a_face_it_cannot_draw_and_changes_nothing(monkeypatch, change, message):
    # The owner's decision of 2026-11-17 on issue 105: NPC import keeps refusing these faces until issue 103. The
    # gnome has none, so the test gives its model one.
    build = npc_collection.npc_model
    monkeypatch.setattr(npc_collection, "npc_model", lambda npc, load: change(build(npc, load)))
    before = blender_data()
    with pytest.raises(RuntimeError, match=message):
        create(4233)
    assert blender_data() == before


def test_create_npc_refuses_an_npc_id_that_the_cache_lacks_and_changes_nothing():
    before = blender_data()
    with pytest.raises(RuntimeError, match="no NPC 99999"):
        create(99999)
    assert blender_data() == before


def test_selecting_an_npc_leaves_the_player_appearance_panel_as_it_is():
    props = bpy.context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    props.source_player = ""
    before = (appearance_props.to_preset(props), props.source_player, props.last_error)
    created(4233)
    appearance_collection.follow_selection(bpy.context)
    assert (appearance_props.to_preset(props), props.source_player, props.last_error) == before


def test_the_npc_panel_draws_below_player_appearance_and_reads_the_npc_id_field():
    import rsps_toolkit.blender as addon

    order = [cls.__name__ for cls in addon.classes]
    assert order.index("VIEW3D_PT_rsps_npc") > order.index("VIEW3D_PT_rsps_appearance")
    assert npc_panel.VIEW3D_PT_rsps_npc.bl_category == "RSPS ADDON"
    assert npc_panel.VIEW3D_PT_rsps_npc.bl_label == "NPC"


# The largest distance, in game units, between an NPC baked on its rig and the client's posed vertices, measured on
# 2026-11-16 over every frame of each clip (docs/research/13-npc-rigs.md, "Bone bake"). The add-on's pose of each
# clip equals the client's, after the client's own scale, so the distance is the fit's: the similarity that a bone
# can carry against the client's integer vertices. The ent's clips and the green dragon's walk scale labels on one or
# two axes only, which no similarity follows. For the rest, even the best affine fit of each label is 2.3 to 3.1 away,
# which is the client's integer truncation.
CLIENT_BOUND = {
    (4233, "stand"): 0.0,
    (4233, "walk"): 1.36,
    (6594, "stand"): 2.58,
    (6594, "walk"): 5.72,
    (2805, "stand"): 1.46,
    (2805, "walk"): 1.37,
    (260, "stand"): 3.17,
    (260, "walk"): 3.51,
    (2477, "stand"): 1.43,
    (2477, "walk"): 1.60,
}
# Blender stores bones, keys and evaluated vertices in 32-bit floats (tests/blender/test_appearance_clip.py,
# RIG_ROUNDING). The NPCs are larger than a player, so this allows ten times the player's margin.
RIG_ROUNDING = 1e-3


def evaluated_vertices(collection: bpy.types.Collection, frame: int) -> dict[int, tuple[float, float, float]]:
    """Each model vertex of the NPC after the rig on a Blender frame, in game coordinates from the rig's location, so
    the rig's scale applies and its placement beside the other actors does not."""
    bpy.context.scene.frame_set(frame)  # pyrefly: ignore[missing-attribute]
    mesh_obj = appearance_collection.mesh_of(collection)
    origin = appearance_collection.armature_of(collection).matrix_world.translation
    evaluated = mesh_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh()
    try:
        out = {}
        for vertex, model_vertex in zip(data.vertices, vertices_of(collection), strict=True):
            x, y, z = mesh_obj.matrix_world @ vertex.co - origin
            out[model_vertex] = (x, -z, y)
        return out
    finally:
        evaluated.to_mesh_clear()


def vertices_of(collection: bpy.types.Collection) -> list[int]:
    return appearance_preview.vertex_indices(mesh(collection))


def fitted_clip(npc_id: int, sequence: int) -> list[tuple[tuple[float, float, float], ...]]:
    """The pure fit of every frame of the clip on the NPC's model before the client's scale."""
    model = npc_model(read_npc(Js5Store(SNAPSHOT_430), npc_id), shared_profile(SNAPSHOT_430).load_model)
    rest = tuple(model.vertices)
    assert model.vertex_skins is not None
    labels = tuple(model.vertex_skins)
    return [
        fitted_vertices(rest, labels, fit_frame(rest, labels, frame.vertices))
        for frame in pose_vertices(rest, labels, NPC_CLIPS / str(sequence))
    ]


def first_frames(sequence: int) -> list[tuple[int, int]]:
    """Each frame index of a pose clip with the Blender frame it starts on, for a strip that starts on frame 1."""
    out, frame = [], 1
    for index, ticks in frame_schedule(read_sequence(NPC_CLIPS / str(sequence)), action=False):
        out.append((index, frame))
        frame += ticks
    return out


@pytest.mark.parametrize("npc_id", TEST_NPCS)
@pytest.mark.parametrize("clip", ["stand", "walk"])
def test_each_frame_of_a_baked_stand_and_walk_clip_gives_the_clients_posed_vertices(npc_id, clip):
    sequence = POSES["clips"][str(npc_id)][clip]
    client = POSES["npcs"][str(npc_id)][str(sequence)]
    collection = created(npc_id)
    assert appearance_clip.bake_npc_clip(collection, NPC_CLIPS / str(sequence)) == len(client)
    fitted = fitted_clip(npc_id, sequence)
    scale = appearance_collection.armature_of(collection).scale
    for index, frame in first_frames(sequence):
        evaluated = evaluated_vertices(collection, frame)
        expected = client[index]
        for vertex, at in evaluated.items():
            x, y, z = fitted[index][vertex]
            assert math.dist(at, (x * scale.x, y * scale.z, z * scale.y)) <= RIG_ROUNDING
            assert math.dist(at, (expected["e"][vertex], expected["l"][vertex], expected["s"][vertex])) <= (
                CLIENT_BOUND[npc_id, clip] + RIG_ROUNDING
            )


def test_an_npc_bake_keeps_the_tracks_frame_rate_and_scene_range_of_the_player_bake():
    # docs/research/13-npc-rigs.md: the gnome stands with sequence 195, two frames of 21 ticks, and walks with 189,
    # eight frames of 5 ticks (tests/fixtures/npc/clips/<sequence>/manifest.json). The first frame of a pose clip shows
    # one tick longer than its duration (`frames._frames_per_tick`), so the clips are 43 and 41 Blender frames long.
    collection = created(4233)
    scene = bpy.context.scene
    scene.render.fps = 24  # pyrefly: ignore[missing-attribute]
    appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "195")
    appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "189", start=44)
    animation = appearance_collection.armature_of(collection).animation_data
    assert animation is not None
    assert [track.name for track in animation.nla_tracks] == [appearance_clip.CLIP_TRACK, appearance_clip.USER_TRACK]
    strips = animation.nla_tracks[appearance_clip.CLIP_TRACK].strips
    assert [(s.frame_start, s.frame_end, s.extrapolation) for s in strips] == [
        (1, 44, "HOLD_FORWARD"),
        (44, 85, "HOLD_FORWARD"),
    ]
    assert (scene.render.fps, scene.frame_start, scene.frame_end) == (50, 1, 84)  # pyrefly: ignore[missing-attribute]
    assert not appearance_collection.is_edited(collection)


def test_a_key_on_a_joint_on_your_motion_moves_the_mesh_on_top_of_the_baked_clip():
    collection = created(4233)
    appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "189")
    rig = appearance_collection.armature_of(collection)
    clip_only = evaluated_vertices(collection, 12)
    clip_basis = {bone.name: bone.matrix_basis.copy() for bone in rig.pose.bones}  # pyrefly: ignore[missing-attribute]
    joint = next(name for name in joint_names(collection) if not rig.data.bones[name].parent)  # pyrefly: ignore[missing-attribute]
    turn = bpy.data.actions.new("turn")
    animation = rig.animation_data
    assert animation is not None
    animation.action = turn
    path = f'pose.bones["{joint}"].rotation_quaternion'
    for index, value in enumerate((math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4))):
        turn.fcurve_ensure_for_datablock(rig, path, index=index).keyframe_points.insert(1, value)
    slot = animation.action_slot
    animation.action = None
    strip = animation.nla_tracks[appearance_clip.USER_TRACK].strips.new("turn", 1, turn)
    strip.action_slot = slot
    strip.blend_type = animation.action_blend_type
    keyed = evaluated_vertices(collection, 12)
    # Combine blending multiplies the clip's rotation by the user's, so the joint turns a quarter turn from where the
    # clip puts it, and every other bone keeps the clip's pose.
    pose_bones = rig.pose.bones  # pyrefly: ignore[missing-attribute]
    expected = clip_basis[joint] @ Matrix.Rotation(math.pi / 2, 4, "Z")
    assert [v for row in pose_bones[joint].matrix_basis for v in row] == pytest.approx(
        [v for row in expected for v in row], abs=1e-5
    )
    for bone in pose_bones:
        if bone.name != joint:
            assert [v for row in bone.matrix_basis for v in row] == pytest.approx(
                [v for row in clip_basis[bone.name] for v in row], abs=1e-5
            )
    assert any(math.dist(keyed[v], clip_only[v]) > 1 for v in keyed)


def file_state() -> dict[str, object]:
    """What a refused bake must leave alone: the data of `blender_data`, the actions, each rig's strips and the
    scene's rate and range."""
    scene = bpy.context.scene
    return {
        **blender_data(),
        "actions": sorted(action.name for action in bpy.data.actions),
        "strips": sorted(
            (obj.name, track.name, strip.name, strip.frame_start, strip.frame_end)
            for obj in bpy.data.objects
            if obj.animation_data is not None
            for track in obj.animation_data.nla_tracks
            for strip in track.strips
        ),
        "scene": (scene.render.fps, scene.frame_start, scene.frame_end),  # pyrefly: ignore[missing-attribute]
    }


def test_a_sequence_on_another_frame_map_is_refused_with_no_change():
    # docs/research/13-npc-rigs.md: the gnome is rigged for frame map 319 and the green dragon's stand sequence 90
    # uses frame map 1080.
    collection = created(4233)
    before = file_state()
    with pytest.raises(ValueError, match="uses frame map 1080.*frame map 319"):
        appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "90")
    assert file_state() == before


def test_an_edited_npc_is_refused_with_no_change():
    collection = created(4233)
    mesh(collection).vertices[0].co.x += 5
    before = file_state()
    with pytest.raises(ValueError, match="has edits"):
        appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "195")
    assert file_state() == before


def test_a_strip_that_would_overlap_another_is_refused_with_no_change():
    collection = created(4233)
    appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "195")
    before = file_state()
    with pytest.raises(ValueError, match="over the strip"):
        appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "189", start=30)
    assert file_state() == before


def test_an_npc_in_edit_mode_is_refused_with_no_change():
    collection = created(4233)
    bpy.context.view_layer.objects.active = appearance_collection.mesh_of(collection)  # pyrefly: ignore[missing-attribute]
    bpy.ops.object.mode_set(mode="EDIT")
    before = file_state()
    with pytest.raises(ValueError, match="Edit Mode"):
        appearance_clip.bake_npc_clip(collection, NPC_CLIPS / "195")
    assert file_state() == before


def test_a_player_is_refused_by_the_npc_bake():
    case = APPEARANCE["cases"][0]
    preset = AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))
    body, shading, slots = appearance_preview.assemble_parts(preset, SNAPSHOT_430)
    player = appearance_collection.build_collection(body, shading, preset, "Player", slots=slots)
    with pytest.raises(ValueError, match="Player is not an NPC"):
        appearance_clip.bake_npc_clip(player, NPC_CLIPS / "195")


class Drawn:
    """Stands in for a Blender layout and records the labels, fields and buttons that the NPC panel draws on it."""

    def __init__(self, calls: list | None = None):
        self.calls = [] if calls is None else calls

    def row(self, **_):
        return Drawn(self.calls)

    split = box = column = grid_flow = row

    def label(self, text="", **_):
        self.calls.append(("label", text))

    def prop(self, data, name, **_):
        self.calls.append(("prop", name))

    def operator(self, idname, text="", **_):
        button = types.SimpleNamespace(idname=idname, text=text)
        self.calls.append(("operator", button))
        return button


def drawn_panel() -> list:
    drawn = Drawn()
    npc_panel.VIEW3D_PT_rsps_npc.draw(types.SimpleNamespace(layout=drawn), bpy.context)  # pyrefly: ignore[bad-argument-type]
    return drawn.calls


def bake_buttons() -> list[types.SimpleNamespace]:
    return [
        item
        for kind, item in drawn_panel()
        if kind == "operator" and item.idname == npc_panel.RSPS_OT_bake_npc_clip.bl_idname
    ]


def press(button: types.SimpleNamespace):
    return bpy.ops.rsps.bake_npc_clip(  # pyrefly: ignore[missing-attribute]
        sequence=button.sequence, play_as=button.play_as, smooth=button.smooth, cache_folder=str(SNAPSHOT_430)
    )


def clip_strips(collection: bpy.types.Collection) -> list[bpy.types.NlaStrip]:
    animation = appearance_collection.armature_of(collection).animation_data
    assert animation is not None
    return list(animation.nla_tracks[appearance_clip.CLIP_TRACK].strips)


def strip_record(strip: bpy.types.NlaStrip) -> dict:
    assert strip.action is not None
    return json.loads(strip.action[appearance_collection.CLIP_KEY])


@pytest.mark.parametrize("npc_id", TEST_NPCS)
@pytest.mark.parametrize("clip", ["stand", "walk"])
def test_each_test_npc_plays_its_stand_and_walk_clips_from_its_stance_buttons(npc_id, clip):
    # tests/fixtures/npc/poses.json names the stand and walk sequence of each test NPC and holds the client's pose of
    # every frame. A Stance button bakes as Pose (spec 13, Panel).
    sequence = POSES["clips"][str(npc_id)][clip]
    client = POSES["npcs"][str(npc_id)][str(sequence)]
    collection = created(npc_id)
    bpy.context.scene.frame_set(1)  # pyrefly: ignore[missing-attribute]
    button = next(b for b in bake_buttons() if b.text == clip.capitalize())
    assert (button.sequence, button.play_as) == (sequence, "POSE")
    assert press(button) == {"FINISHED"}
    for index, frame in first_frames(sequence):
        expected = client[index]
        for vertex, at in evaluated_vertices(collection, frame).items():
            assert math.dist(at, (expected["e"][vertex], expected["l"][vertex], expected["s"][vertex])) <= (
                CLIENT_BOUND[npc_id, clip] + RIG_ROUNDING
            )


def test_the_bake_rows_show_the_active_npcs_name_its_stance_buttons_the_fields_and_the_bake_button():
    # Spec 13, Panel item 4. The gnome's definition names a stand and a walk sequence only
    # (tests/fixtures/npc/npcs.json).
    created(4233)
    calls = drawn_panel()
    assert ("label", "Gnome") in calls
    assert [button.text for button in bake_buttons()] == ["Stand", "Walk", "Bake at the current frame"]
    props = [name for kind, name in calls if kind == "prop"]
    assert props[-2:] == ["rs_npc_sequence", "rs_npc_smooth"]


def test_man_has_a_stance_button_for_each_sequence_that_his_definition_names():
    # tests/fixtures/npc/npcs.json, RuneLite's decode of NPC 3078: stand 808, walk 819, and 820, 821 and 822 in the
    # rotate180, rotateLeft and rotateRight fields, which are the walk back, walk left and walk right sequences
    # (spec 13, NPC definition). It names no turn sequence.
    created(MAN)
    assert [(button.text, button.sequence, button.play_as) for button in bake_buttons()[:-1]] == [
        ("Stand", 808, "POSE"),
        ("Walk", 819, "POSE"),
        ("Walk back", 820, "POSE"),
        ("Walk left", 821, "POSE"),
        ("Walk right", 822, "POSE"),
    ]


def test_smooth_applies_to_the_stance_buttons_and_to_the_typed_sequence():
    # The owner's decision of 2026-11-16 (the decision comment of issue 94): Smooth applies to every bake of the panel.
    collection = created(4233)
    bpy.context.scene.frame_set(1)  # pyrefly: ignore[missing-attribute]
    assert [button.smooth for button in bake_buttons()] == [False, False, False]
    bpy.context.scene.rs_npc_smooth = True  # pyrefly: ignore[missing-attribute]
    buttons = bake_buttons()
    assert [button.smooth for button in buttons] == [True, True, True]
    assert press(buttons[0]) == {"FINISHED"}
    assert strip_record(clip_strips(collection)[0])["smooth"] is True


def test_the_sequence_id_field_bakes_a_typed_sequence_as_an_action_at_the_current_frame():
    # docs/research/13-npc-rigs.md: the gnome's walk sequence 189 is on its frame map 319. The sequence id field bakes
    # as Action (spec 13, Panel).
    collection = created(4233)
    scene = bpy.context.scene
    scene.rs_npc_sequence = 189  # pyrefly: ignore[missing-attribute]
    scene.rs_npc_smooth = True  # pyrefly: ignore[missing-attribute]
    scene.frame_set(10)  # pyrefly: ignore[missing-attribute]
    button = bake_buttons()[-1]
    assert (button.sequence, button.play_as, button.smooth) == (189, "ACTION", True)
    assert press(button) == {"FINISHED"}
    (strip,) = clip_strips(collection)
    assert strip.frame_start == 10
    record = strip_record(strip)
    assert (record["sequence"], record["action"], record["smooth"]) == (189, True, True)


def test_the_sequence_id_field_refuses_a_sequence_on_another_frame_map_with_no_change():
    # docs/research/13-npc-rigs.md: the green dragon's stand sequence 90 uses frame map 1080, and the gnome is rigged
    # for frame map 319.
    created(4233)
    bpy.context.scene.rs_npc_sequence = 90  # pyrefly: ignore[missing-attribute]
    button = bake_buttons()[-1]
    before = file_state()
    with pytest.raises(RuntimeError, match="uses frame map 1080.*frame map 319"):
        press(button)
    assert file_state() == before


def test_a_sequence_that_the_cache_lacks_is_refused_with_no_change():
    created(4233)
    before = file_state()
    with pytest.raises(RuntimeError, match="no sequence 99999"):
        bpy.ops.rsps.bake_npc_clip(sequence=99999, play_as="ACTION", cache_folder=str(SNAPSHOT_430))  # pyrefly: ignore[missing-attribute]
    assert file_state() == before


def test_a_player_a_plain_model_and_no_active_object_show_no_bake_rows():
    case = APPEARANCE["cases"][0]
    preset = AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))
    body, shading, slots = appearance_preview.assemble_parts(preset, SNAPSHOT_430)
    player = appearance_collection.build_collection(body, shading, preset, "Player", slots=slots)
    plain = bpy.data.objects.new("plain", bpy.data.meshes.new("plain"))
    bpy.context.scene.collection.objects.link(plain)  # pyrefly: ignore[missing-attribute]
    created(4233)
    assert bake_buttons()
    for obj in (appearance_collection.mesh_of(player), plain, None):
        bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
        assert bake_buttons() == []
        assert not bpy.ops.rsps.bake_npc_clip.poll()  # pyrefly: ignore[missing-attribute]


def test_the_rig_of_an_npc_shows_the_bake_rows_too():
    # The active NPC is the NPC of the active object (spec 13, Panel item 4), and the rig is in the NPC collection.
    collection = created(4233)
    bpy.context.view_layer.objects.active = appearance_collection.armature_of(collection)  # pyrefly: ignore[missing-attribute]
    assert len(bake_buttons()) == 3


def test_the_stance_buttons_cover_every_sequence_field_of_an_npc_in_order():
    # A field that npc_collection stores and the panel has no text for would get no button.
    assert tuple(npc_panel.STANCE_LABELS) == npc_collection.SEQUENCE_FIELDS


def test_the_tooltip_of_a_bake_button_names_its_sequence_and_how_it_plays():
    pose = types.SimpleNamespace(sequence=808, play_as="POSE", runelite_name="")
    action = types.SimpleNamespace(sequence=189, play_as="ACTION", runelite_name="")
    describe = npc_panel.RSPS_OT_bake_npc_clip.description
    assert describe(bpy.context, pose) == (
        "Bake sequence 808 onto the active NPC as a Pose, starting at the current frame"
    )
    assert describe(bpy.context, action) == (
        "Bake sequence 189 onto the active NPC as an Action, starting at the current frame"
    )


def imported_gnome() -> bpy.types.Object:
    """The gnome's merged and recoloured model as a plain import: a mesh object with vertex skins and no rig. The
    gnome has the default ambient, contrast and scale of an NPC (tests/fixtures/npc/npcs.json)."""
    model = npc_model(read_npc(Js5Store(SNAPSHOT_430), 4233), shared_profile(SNAPSHOT_430).load_model)
    # model_to_object links to the context's collection. The `clean` fixture removes every collection, which can leave
    # the active layer collection on a removed one, so the scene's own collection is made active first.
    layer = bpy.context.view_layer
    assert layer is not None
    layer.active_layer_collection = layer.layer_collection
    obj = blender_mesh.model_to_object(model, "Gnome model")
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    obj.select_set(True)
    return obj


def make_rig(sequence: int):
    return bpy.ops.rsps.make_rig(sequence=sequence, cache_folder=str(SNAPSHOT_430))  # pyrefly: ignore[missing-attribute]


def object_state(obj: bpy.types.Object) -> dict[str, object]:
    """What Make rig must leave alone on the selected object: its name, transform, collections, mesh, face corners,
    vertex groups, modifiers and custom properties."""
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    return {
        "name": obj.name,
        "matrix": [row[:] for row in obj.matrix_world],
        "collections": sorted(c.name for c in obj.users_collection),
        "mesh": data.name,
        "vertices": [v.co[:] for v in data.vertices],
        "groups": [(g.name, g.index) for g in obj.vertex_groups],
        "weights": [[(g.group, g.weight) for g in v.groups] for v in data.vertices],
        "materials": [m.name for m in data.materials if m is not None],
        "properties": sorted(obj.keys()),
        "mesh properties": sorted(data.keys()),
        "corners": [loop.vertex_index for loop in data.loops],
        "modifiers": [(m.name, m.type) for m in obj.modifiers],
    }


def test_make_rig_builds_an_npc_collection_that_bakes_the_typed_sequence():
    # docs/research/13-npc-rigs.md: the gnome's stand sequence 195 is on frame map 319. The rig's clip is the fit of
    # the client's pose of the model, as for an NPC made by id.
    imported_gnome()
    assert make_rig(195) == {"FINISHED"}
    collection = npc_collection.npc_of(active())
    assert collection is not None
    assert json.loads(collection[npc_collection.NPC_KEY]) == {
        "npc": None,
        "name": "Gnome model",
        "frame_map": 319,
        "sequences": {},
        "sequence": 195,
    }
    assert collection.name == "Gnome model"
    assert appearance_preview.PRESET_KEY not in collection
    assert not appearance_collection.is_edited(collection)
    assert appearance_collection.armature_of(collection).scale == Vector((1, 1, 1))
    bpy.context.scene.frame_set(1)  # pyrefly: ignore[missing-attribute]
    (stance, typed) = bake_buttons()
    assert (stance.text, stance.sequence, stance.play_as) == ("Sequence 195", 195, "POSE")
    assert typed.play_as == "ACTION"
    assert press(stance) == {"FINISHED"}
    fitted = fitted_clip(4233, 195)
    for index, frame in first_frames(195):
        for vertex, at in evaluated_vertices(collection, frame).items():
            assert math.dist(at, fitted[index][vertex]) <= RIG_ROUNDING


def test_make_rig_gives_the_joints_and_the_lit_colours_of_the_npc_with_that_model():
    # The gnome's definition has the constructor's ambient and contrast of 0 (NPCComposition.java lines 192 to 217),
    # so the client lights its model as Make rig lights any model: with the NPC lighting of npc_lighting.
    imported_gnome()
    assert make_rig(195) == {"FINISHED"}
    collection = npc_collection.npc_of(active())
    assert collection is not None
    assert_client_lit_colours(mesh(collection), LIT["4233"])
    # The gnome's own count from the second probe of docs/research/13-npc-rigs.md.
    assert len(joint_names(collection)) == 14


def test_make_rig_leaves_the_selected_object_as_it_is():
    obj = imported_gnome()
    obj.location = (3.0, -2.0, 1.0)
    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]
    before = object_state(obj)
    assert make_rig(195) == {"FINISHED"}
    assert object_state(obj) == before
    assert npc_collection.npc_of(obj) is None


def test_make_rig_places_the_new_npc_a_player_gap_right_of_the_other_npcs():
    first = created(4233)
    imported_gnome()
    assert make_rig(195) == {"FINISHED"}
    second = npc_collection.npc_of(active())
    assert second is not None

    def edge(collection, pick):
        obj = appearance_collection.mesh_of(collection)
        return pick((obj.matrix_world @ Vector(corner)).x for corner in obj.bound_box)

    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]
    assert edge(second, min) == pytest.approx(edge(first, max) + appearance_collection.PLAYER_GAP, abs=1e-3)


def armature_object() -> bpy.types.Object:
    obj = bpy.data.objects.new("rig", bpy.data.armatures.new("rig"))
    bpy.context.scene.collection.objects.link(obj)  # pyrefly: ignore[missing-attribute]
    return obj


def unskinned_gnome() -> bpy.types.Object:
    obj = imported_gnome()
    for name in [group.name for group in obj.vertex_groups]:
        obj.vertex_groups.remove(obj.vertex_groups[name])
    return obj


def unlabelled_gnome() -> bpy.types.Object:
    # A vertex in no vertex skin group has no label (the decision comment of issue 95).
    obj = imported_gnome()
    for group in list(obj.vertex_groups):
        group.remove([0, 1])
    return obj


def weight_stripped_gnome() -> bpy.types.Object:
    # Every vertex of the mesh has a label, but Vertex Weight Edit modifiers take each vertex out of every vertex skin
    # group, so no vertex of the evaluated model has one.
    obj = imported_gnome()
    for name in rs_layers.VERTEX_SKIN_GROUPS:
        if name in obj.vertex_groups:
            modifier = obj.modifiers.new(f"Strip {name}", "VERTEX_WEIGHT_EDIT")
            assert isinstance(modifier, bpy.types.VertexWeightEditModifier)
            modifier.vertex_group = name
            modifier.use_remove = True
            modifier.remove_threshold = 1.0
    return obj


def mirrored(obj: bpy.types.Object) -> bpy.types.Object:
    # The Mirror modifier gives a second copy of every vertex, with the same vertex skin weights. The gnome is symmetric,
    # so it mirrors across an empty far to the right, where the copy touches nothing of the original.
    centre = bpy.data.objects.new("mirror centre", None)
    bpy.context.scene.collection.objects.link(centre)  # pyrefly: ignore[missing-attribute]
    centre.location = (10.0, 0.0, 0.0)
    modifier = obj.modifiers.new("Mirror", "MIRROR")
    assert isinstance(modifier, bpy.types.MirrorModifier)
    modifier.use_mirror_merge = False
    modifier.mirror_object = centre
    return obj


def mirrored_textured_gnome() -> bpy.types.Object:
    # Model export refuses a modifier that changes the vertices a texture triangle names (export_model._evaluated).
    obj = mirrored(imported_gnome())
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    data[rs_layers.TEXTURE_TRIANGLES] = [0, 1, 2]
    return obj


@pytest.mark.parametrize(
    ("make_active", "sequence", "message"),
    [
        (lambda: None, 195, "no active object"),
        (armature_object, 195, "'rig' is not a mesh"),
        (unskinned_gnome, 195, "'Gnome model' has no vertex skins"),
        (unlabelled_gnome, 195, "'Gnome model' cannot have a rig: 2 vertices have no vertex skin label"),
        (weight_stripped_gnome, 195, r"'Gnome model' cannot have a rig: \d+ vertices have no vertex skin label"),
        (mirrored_textured_gnome, 195, "'Gnome model' cannot have a rig: its modifiers change the vertices"),
        (imported_gnome, 99999, "no sequence 99999"),
    ],
    ids=[
        "no active object",
        "not a mesh",
        "no vertex skins",
        "vertices with no label",
        "modifiers that remove the labels",
        "modifiers that move texture triangles",
        "sequence the cache lacks",
    ],
)
def test_make_rig_refuses_and_changes_nothing(make_active, sequence, message):
    obj = make_active()
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    before = (blender_data(), None if obj is None or obj.type != "MESH" else object_state(obj))
    with pytest.raises(RuntimeError, match=message):
        make_rig(sequence)
    assert (blender_data(), None if obj is None or obj.type != "MESH" else object_state(obj)) == before


@UNDRAWN_FACES
def test_make_rig_refuses_a_face_it_cannot_draw_and_changes_nothing(monkeypatch, change, message):
    # The owner's decision of 2026-11-17 on issue 127: Make rig keeps refusing these faces until issue 103, as NPC
    # import does. The gnome has none, so the test gives the model that model export builds one.
    obj = imported_gnome()
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    evaluated = npc_collection.export_model.evaluated_model
    monkeypatch.setattr(
        npc_collection.export_model, "evaluated_model", lambda *args, **kwargs: change(evaluated(*args, **kwargs))
    )
    before = (blender_data(), object_state(obj))
    with pytest.raises(RuntimeError, match=message):
        make_rig(195)
    assert (blender_data(), object_state(obj)) == before


def test_the_npc_panel_draws_the_make_rig_field_and_button_after_create_npc():
    # Spec 13, Panel item 3: a sequence id field and Make rig, for the active mesh object, after the NPC id row. With no
    # active NPC the panel draws no bake rows, and in these tests the cache folder row is a label, because the add-on
    # is not enabled.
    bpy.context.scene.rs_make_rig_sequence = 195  # pyrefly: ignore[missing-attribute]
    calls = drawn_panel()
    names = [item if kind == "prop" else item.idname for kind, item in calls if kind in ("prop", "operator")]
    assert names == [
        "rs_npc_id",
        npc_collection.RSPS_OT_create_npc.bl_idname,
        "rs_make_rig_sequence",
        npc_collection.RSPS_OT_make_rig.bl_idname,
    ]
    (button,) = [item for kind, item in calls if kind == "operator" and item.idname == "rsps.make_rig"]
    assert button.sequence == 195


def test_make_rig_builds_from_the_mesh_as_the_user_edited_it():
    # The model is the one that model export would write, so a moved vertex goes into the NPC's mesh as it is now.
    obj = imported_gnome()
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    data.vertices[0].co.z += 7
    moved = blender_mesh.object_to_model(obj).vertices[0]
    assert make_rig(195) == {"FINISHED"}
    collection = npc_collection.npc_of(active())
    assert collection is not None
    rig = appearance_collection.armature_of(collection)
    mesh_obj = appearance_collection.mesh_of(collection)
    to_rig = rig.matrix_world.inverted() @ mesh_obj.matrix_world
    index = vertices_of(collection).index(0)
    x, y, z = to_rig @ mesh(collection).vertices[index].co
    assert (x, -z, y) == pytest.approx(moved, abs=1e-4)


def test_make_rig_splits_a_face_with_four_corners_into_triangles():
    # Make rig takes what model export takes (issue 113), and model export splits such a face into two triangles.
    obj = imported_gnome()
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    faces = len(data.polygons)
    bm = bmesh.new()
    bm.from_mesh(data)
    bm.edges.ensure_lookup_table()
    shared = next(edge for edge in bm.edges if len(edge.link_faces) == 2)
    bmesh.ops.dissolve_edges(bm, edges=[shared])
    bm.to_mesh(data)
    bm.free()
    assert max(p.loop_total for p in data.polygons) == 4
    before = object_state(obj)
    assert make_rig(195) == {"FINISHED"}
    assert object_state(obj) == before
    collection = npc_collection.npc_of(active())
    assert collection is not None
    assert {p.loop_total for p in mesh(collection).polygons} == {3}
    assert len(mesh(collection).polygons) == faces


def test_make_rig_builds_the_model_with_the_modifiers_applied():
    obj = mirrored(imported_gnome())
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    vertices, faces = len(data.vertices), len(data.polygons)
    before = object_state(obj)
    assert make_rig(195) == {"FINISHED"}
    assert object_state(obj) == before
    collection = npc_collection.npc_of(active())
    assert collection is not None
    assert max(vertices_of(collection)) + 1 == 2 * vertices
    assert len(mesh(collection).polygons) == 2 * faces


def test_make_rig_checks_the_labels_of_the_model_with_the_modifiers_applied():
    # A Mask modifier that drops the two vertices with no label leaves a model in which every vertex has one.
    obj = unlabelled_gnome()
    keep = obj.vertex_groups.new(name="keep")
    data = obj.data
    assert isinstance(data, bpy.types.Mesh)
    keep.add(list(range(2, len(data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Mask", "MASK")
    assert isinstance(modifier, bpy.types.MaskModifier)
    modifier.vertex_group = "keep"
    before = object_state(obj)
    assert make_rig(195) == {"FINISHED"}
    assert object_state(obj) == before
    collection = npc_collection.npc_of(active())
    assert collection is not None
    assert max(vertices_of(collection)) + 1 == len(data.vertices) - 2


def test_make_rig_twice_on_one_object_builds_two_npcs():
    obj = imported_gnome()
    assert make_rig(195) == {"FINISHED"}
    first = npc_collection.npc_of(active())
    bpy.context.view_layer.objects.active = obj  # pyrefly: ignore[missing-attribute]
    assert make_rig(189) == {"FINISHED"}
    second = npc_collection.npc_of(active())
    assert first is not None and second is not None and first != second
    assert [json.loads(c[npc_collection.NPC_KEY])["sequence"] for c in (first, second)] == [195, 189]


# Spec 160, the Combat row. The clips of the green dragon and the giant spider are in "Sample NPCs" of
# docs/research/160-npc-clips.md, read by hand from the source.json files of the AnotherScape models mod.
DRAGON_COMBAT = [("Attack", 91), ("Flinch", 89), ("Death", 92)]
SPIDER_COMBAT = [("Attack", 5319), ("Mage", 5322), ("Flinch", 5320), ("Death", 5321)]
BAKE_TEXT = "Bake at the current frame"


def combat_buttons() -> list[types.SimpleNamespace]:
    buttons = bake_buttons()
    stance_texts = {*npc_panel.STANCE_LABELS.values(), BAKE_TEXT}
    return [button for button in buttons if button.text not in stance_texts]


def test_the_green_dragon_draws_a_combat_row_between_its_stance_buttons_and_the_sequence_id_field():
    # Design decisions 2, 5 and 6 of issue 160: the row "Combat:" under Stance, the mod's key as the button text, an
    # Action bake, and the button order.
    created(260)
    bpy.context.scene.rs_npc_smooth = True  # pyrefly: ignore[missing-attribute]
    calls = drawn_panel()
    combat = calls.index(("label", "Combat:"))
    texts = [item.text if kind == "operator" else item for kind, item in calls]
    assert calls.index(("label", "Stance:")) < combat < calls.index(("prop", "rs_npc_sequence"))
    assert texts[combat + 1 : combat + 4] == [text for text, _ in DRAGON_COMBAT]
    assert [(b.text, b.sequence, b.play_as, b.smooth) for b in combat_buttons()] == [
        (text, sequence, "ACTION", True) for text, sequence in DRAGON_COMBAT
    ]


@pytest.mark.parametrize(("npc_id", "expected"), [(260, DRAGON_COMBAT), (2477, SPIDER_COMBAT)])
def test_each_combat_button_bakes_its_sequence_as_an_action(npc_id, expected):
    # The AC of issue 160: each button bakes with no refusal. Each bake starts at a later frame, so no strip overlaps.
    collection = created(npc_id)
    buttons = combat_buttons()
    assert [(button.text, button.sequence) for button in buttons] == expected
    for index, button in enumerate(buttons):
        bpy.context.scene.frame_set(1 + 1000 * index)  # pyrefly: ignore[missing-attribute]
        assert press(button) == {"FINISHED"}
    records = [strip_record(strip) for strip in clip_strips(collection)]
    assert [(record["sequence"], record["action"]) for record in records] == [(seq, True) for _, seq in expected]


def test_the_cow_has_no_combat_row_and_the_bake_buttons_of_today():
    # No source.json of the mod has NPC 2805 (docs/research/160-npc-clips.md).
    collection = created(2805)
    sequences = json.loads(collection[npc_collection.NPC_KEY])["sequences"]
    calls = drawn_panel()
    assert ("label", "Combat:") not in calls
    assert [button.text for button in bake_buttons()] == [
        *(text for field, text in npc_panel.STANCE_LABELS.items() if field in sequences),
        BAKE_TEXT,
    ]


def test_an_npc_that_make_rig_built_has_no_combat_row():
    # Design decision 8 of issue 160: an NPC that Make rig built has no NPC id.
    imported_gnome()
    assert make_rig(195) == {"FINISHED"}
    assert ("label", "Combat:") not in drawn_panel()
    assert [button.text for button in bake_buttons()] == ["Sequence 195", BAKE_TEXT]


def tooltip(button: types.SimpleNamespace) -> str:
    properties = types.SimpleNamespace(
        sequence=button.sequence, play_as=button.play_as, runelite_name=getattr(button, "runelite_name", "")
    )
    return npc_panel.RSPS_OT_bake_npc_clip.description(bpy.context, properties)  # pyrefly: ignore[bad-argument-type]


def test_the_tooltip_of_a_combat_button_names_the_runelite_name_when_the_mod_gives_one():
    # Answer 5 of spec 160: the spider's attack label is SPIDER_UPDATE_ATTACK_LARGE, and the dragon's is the plain word
    # melee, which the table does not store.
    created(2477)
    assert tooltip(combat_buttons()[0]) == (
        "Bake sequence 5319 (SPIDER_UPDATE_ATTACK_LARGE) onto the active NPC as an Action, starting at the current frame"
    )
    bpy.context.scene.rs_npc_sequence = 5319  # pyrefly: ignore[missing-attribute]
    assert tooltip(bake_buttons()[-1]) == (
        "Bake sequence 5319 onto the active NPC as an Action, starting at the current frame"
    )
    created(260)
    assert tooltip(combat_buttons()[0]) == (
        "Bake sequence 91 onto the active NPC as an Action, starting at the current frame"
    )
    assert tooltip(bake_buttons()[0]) == "Bake sequence 90 onto the active NPC as a Pose, starting at the current frame"
