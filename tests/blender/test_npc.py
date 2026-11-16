"""Create NPC by id, from snapshot 430 (spec 13, issue 92)."""

import dataclasses
import json
import os
import re
from pathlib import Path

import bpy
import pytest
from mathutils import Vector

from rsps_toolkit.animation.clip import CacheClip
from rsps_toolkit.animation.frames import decode_frame_map, decode_sequence
from rsps_toolkit.blender import appearance_collection, appearance_preview, appearance_props, npc_collection, npc_panel
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
# The five test NPCs of spec 13: the gnome, the ent, the cow, the green dragon and the giant spider.
TEST_NPCS = (4233, 6594, 2805, 260, 2477)
MAN = 3078


@pytest.fixture
def registered(clean):
    classes = (*appearance_props.classes, *appearance_collection.classes, *npc_collection.classes)
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
