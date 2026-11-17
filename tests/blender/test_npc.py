"""Create NPC by id, from snapshot 430 (spec 13, issue 92)."""

import dataclasses
import json
import math
import os
import re
import types
from pathlib import Path

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
)
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
    # tests/fixtures/npc/lit.json: the unchanged revision 149 client's getModel. The client marks a flat-shaded face
    # with a third colour of -1 and shows its first colour at every corner.
    client = LIT[str(npc_id)]
    data = mesh(created(npc_id))
    faces = appearance_preview.face_indices(data)
    assert faces is not None
    colours = data.color_attributes[appearance_preview.LIT_ATTRIBUTE].data  # pyrefly: ignore[missing-attribute]
    for polygon, face in zip(data.polygons, faces, strict=True):
        shades = [client["g"][face]] * 3 if client["t"][face] == -1 else [client[k][face] for k in "gkt"]
        expected = [tuple(srgb_to_linear(c / 255) for c in face_colour_to_rgb(s, DEFAULT_BRIGHTNESS)) for s in shades]
        for corner, want in zip(polygon.loop_indices, expected, strict=True):
            assert tuple(colours[corner].color[:3]) == pytest.approx(want, abs=1e-6)
    if npc_id in TEST_NPCS:
        # None of the five has a face that repeats a vertex or lies exactly on another, so the mesh holds every face.
        assert sorted(faces) == list(range(client["face_count"]))
    else:
        assert len(set(faces)) == len(faces) <= client["face_count"]


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
    pose = types.SimpleNamespace(sequence=808, play_as="POSE")
    action = types.SimpleNamespace(sequence=189, play_as="ACTION")
    describe = npc_panel.RSPS_OT_bake_npc_clip.description
    assert describe(bpy.context, pose) == (
        "Bake sequence 808 onto the active NPC as a Pose, starting at the current frame"
    )
    assert describe(bpy.context, action) == (
        "Bake sequence 189 onto the active NPC as an Action, starting at the current frame"
    )
