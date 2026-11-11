import json
from pathlib import Path
from types import SimpleNamespace

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import appearance_collection, appearance_preview
from rsps_toolkit.blender.animation import assert_static_exportable
from rsps_toolkit.formats.appearance_preset import AppearancePreset, loads_preset
from rsps_toolkit.formats.appearance_rig import BONE_LENGTH, derive_rig

FIXTURES = Path(__file__).parent.parent / "fixtures" / "appearance"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())
pytestmark = pytest.mark.usefixtures("clean")


def preset():
    case = next(c for c in REFERENCE["cases"] if not c.get("outfit") and not c["female"] and c["colours"] == [0] * 5)
    return AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))


def build(dump):
    source = preset()
    body, shading, slots = appearance_preview.assemble_parts(source, dump)
    return source, body, appearance_collection.build_collection(body, shading, source, "Player", slots=slots)


def test_collection_holds_a_mesh_and_an_armature_and_the_recipe(dump):
    source, body, collection = build(dump)
    kinds = sorted(obj.type for obj in collection.objects)
    assert kinds == ["ARMATURE", "MESH"]
    assert loads_preset(collection[appearance_preview.PRESET_KEY]) == source
    assert collection.name in bpy.context.scene.collection.children  # pyrefly: ignore[missing-attribute]


def test_bones_are_one_per_label_in_blender_axes(dump):
    _, body, collection = build(dump)
    bones = sorted(
        (b for b in appearance_collection.armature_data(collection).bones if b.name.startswith("label_")),
        key=lambda b: int(b.name.removeprefix("label_")),
    )
    rig = derive_rig(body)
    assert [bone.name for bone in bones] == [f"label_{b.label}" for b in rig.bones]
    first, bone = rig.bones[0], bones[0]
    x, y, z = first.head
    assert tuple(bone.head_local) == pytest.approx((x, z, -y), abs=1e-3)  # pyrefly: ignore[bad-argument-type]
    assert bone.length == pytest.approx(BONE_LENGTH, abs=1e-3)
    assert bone.tail_local.z > bone.head_local.z


def test_every_vertex_has_weight_one_on_exactly_its_label(dump):
    _, body, collection = build(dump)
    mesh_obj = appearance_collection.mesh_of(collection)
    assert body.vertex_skins is not None
    for vertex, label in zip(appearance_collection.mesh_data(collection).vertices, body.vertex_skins, strict=True):
        weights = {mesh_obj.vertex_groups[g.group].name: g.weight for g in vertex.groups}
        assert weights == {f"label_{label}": 1.0}


def test_mesh_is_bound_to_the_armature(dump):
    _, _, collection = build(dump)
    mesh_obj = appearance_collection.mesh_of(collection)
    armature_obj = appearance_collection.armature_of(collection)
    assert mesh_obj.parent == armature_obj
    modifiers = [m for m in mesh_obj.modifiers if m.type == "ARMATURE"]
    assert len(modifiers) == 1 and modifiers[0].object == armature_obj  # pyrefly: ignore[missing-attribute]


def test_a_fresh_build_is_not_edited(dump):
    _, _, collection = build(dump)
    assert not appearance_collection.is_edited(collection)


def test_moving_a_vertex_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).vertices[0].co.x += 5
    assert appearance_collection.is_edited(collection)


def test_moving_a_bone_counts_as_edited(dump):
    _, _, collection = build(dump)
    armature_obj = appearance_collection.armature_of(collection)
    layer = bpy.context.view_layer
    assert layer is not None
    layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")
    appearance_collection.armature_data(collection).edit_bones[0].head.x += 3
    bpy.ops.object.mode_set(mode="OBJECT")
    assert appearance_collection.is_edited(collection)


def test_changing_a_weight_counts_as_edited(dump):
    _, _, collection = build(dump)
    mesh_obj = appearance_collection.mesh_of(collection)
    group = mesh_obj.vertex_groups[0]
    group.add([0], 0.5, "REPLACE")
    assert appearance_collection.is_edited(collection)


def test_a_collection_without_a_build_record_counts_as_edited(dump):
    _, _, collection = build(dump)
    del collection[appearance_collection.HASH_KEY]
    assert appearance_collection.is_edited(collection)


def test_deleting_a_face_counts_as_edited(dump):
    _, _, collection = build(dump)
    mesh = appearance_collection.mesh_data(collection)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.remove(bm.faces[0])
    bm.to_mesh(mesh)
    bm.free()
    assert appearance_collection.is_edited(collection)


def edit(obj):
    layer = bpy.context.view_layer
    assert layer is not None
    layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")


def test_moving_a_vertex_in_edit_mode_counts_as_edited(dump):
    _, _, collection = build(dump)
    obj = appearance_collection.mesh_of(collection)
    edit(obj)
    mesh = bmesh.from_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    mesh.verts.ensure_lookup_table()
    mesh.verts[0].co.x += 50
    bmesh.update_edit_mesh(obj.data)  # pyrefly: ignore[bad-argument-type]
    assert appearance_collection.is_edited(collection)


def test_moving_a_bone_in_edit_mode_counts_as_edited(dump):
    _, _, collection = build(dump)
    edit(appearance_collection.armature_of(collection))
    appearance_collection.armature_data(collection).edit_bones[0].head.x += 3
    assert appearance_collection.is_edited(collection)


def edit_bones(collection):
    edit(appearance_collection.armature_of(collection))
    return appearance_collection.armature_data(collection).edit_bones


def test_parenting_a_bone_counts_as_edited(dump):
    _, _, collection = build(dump)
    bones = edit_bones(collection)
    bones["label_1"].parent = bones["label_0"]
    bpy.ops.object.mode_set(mode="OBJECT")
    assert appearance_collection.is_edited(collection)


def test_rolling_a_bone_counts_as_edited(dump):
    _, _, collection = build(dump)
    edit_bones(collection)[2].roll = 1.0
    bpy.ops.object.mode_set(mode="OBJECT")
    assert appearance_collection.is_edited(collection)


def update_layer():
    layer = bpy.context.view_layer
    assert layer is not None
    layer.update()


def test_moving_a_part_against_the_rig_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_of(collection).location.x += 10
    update_layer()
    assert appearance_collection.is_edited(collection)


def test_moving_turning_or_scaling_the_whole_player_is_not_an_edit(dump):
    _, _, collection = build(dump)
    rig = appearance_collection.armature_of(collection)
    rig.location = (40.0, -12.0, 3.0)
    rig.rotation_euler.z = 1.2
    rig.scale = (2.0, 2.0, 2.0)
    update_layer()
    assert not appearance_collection.is_edited(collection)


def test_unparenting_a_part_from_the_rig_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_of(collection).parent = None
    update_layer()
    assert appearance_collection.is_edited(collection)


def test_moving_the_weapon_against_the_rig_counts_as_edited(armed_dump):
    source = AppearancePreset(
        149, 430, False, (0, 0, 0, 512 + 1333, 274, 512 + 1201, 282, 292, 256, 289, 298, 266), (0,) * 5
    )
    body, shading, slots = appearance_preview.assemble_parts(source, armed_dump)
    collection = appearance_collection.build_collection(body, shading, source, "Player", slots=slots)
    (weapon,) = (obj for obj in appearance_collection.parts(collection) if obj.name == "Player Weapon")
    weapon.location.z += 5
    update_layer()
    assert appearance_collection.is_edited(collection)


def test_adding_a_shape_key_counts_as_edited(dump):
    _, _, collection = build(dump)
    obj = appearance_collection.mesh_of(collection)
    obj.shape_key_add(name="Basis")
    obj.shape_key_add(name="smile")
    assert appearance_collection.is_edited(collection)


def test_adding_a_material_slot_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).materials.append(bpy.data.materials.new("Skin"))
    assert appearance_collection.is_edited(collection)


def test_replacing_the_material_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).materials[0] = bpy.data.materials.new("Skin")
    assert appearance_collection.is_edited(collection)


def test_a_numbered_copy_of_the_lit_material_counts_as_edited_only_once_its_nodes_differ(dump):
    _, _, collection = build(dump)
    mesh = appearance_collection.mesh_data(collection)
    copy = mesh.materials[0].copy()  # pyrefly: ignore[missing-attribute]
    assert copy.name.startswith(f"{appearance_preview.MATERIAL_NAME}.")
    mesh.materials[0] = copy
    assert not appearance_collection.is_edited(collection)
    copy.node_tree.nodes["Emission"].inputs["Strength"].default_value = 2.0  # pyrefly: ignore[missing-attribute]
    assert appearance_collection.is_edited(collection)


def test_a_numbered_copy_of_the_lit_material_whose_image_node_shows_another_image_counts_as_edited(dump):
    _, _, collection = build(dump)
    mesh = appearance_collection.mesh_data(collection)
    original = mesh.materials[0]
    assert original is not None
    copy = original.copy()
    mesh.materials[0] = copy
    for material, image in ((original, "first"), (copy, "second")):
        node = material.node_tree.nodes.new("ShaderNodeTexImage")  # pyrefly: ignore[missing-attribute]
        node.name = "Picture"
        node.image = bpy.data.images.new(image, 1, 1)
    assert appearance_collection.is_edited(collection)


@pytest.mark.parametrize("predates_culling", [False, True])
def test_building_a_player_makes_the_lit_material_show_only_the_front_of_faces(dump, predates_culling):
    # The user chose that players cull back faces as the client does, and that Create Player turns culling on again
    # for a lit material made before players culled (issue 28, decisions 1 and 3, 2026-11-10).
    old = bpy.data.materials.get(appearance_preview.MATERIAL_NAME)
    if old is not None:
        bpy.data.materials.remove(old)
    if predates_culling:
        build(dump)
        bpy.data.materials[appearance_preview.MATERIAL_NAME].use_backface_culling = False
    _, _, collection = build(dump)
    material = appearance_collection.mesh_data(collection).materials[0]
    assert material is not None and material.name == appearance_preview.MATERIAL_NAME
    assert material.use_backface_culling


def test_showing_the_lit_colours_makes_a_solid_view_draw_only_the_front_of_faces():
    # The user chose that building a player also turns on the Solid view's culling (issue 28, decision 1, 2026-11-10).
    space = next(area.spaces.active for screen in bpy.data.screens for area in screen.areas if area.type == "VIEW_3D")
    assert isinstance(space, bpy.types.SpaceView3D)
    space.shading.type = "SOLID"
    space.shading.show_backface_culling = False
    appearance_preview.show_lit_colours(SimpleNamespace(space_data=space))  # pyrefly: ignore[bad-argument-type]
    assert space.shading.show_backface_culling


def test_adding_a_colour_attribute_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).color_attributes.new("paint", "BYTE_COLOR", "CORNER")
    assert appearance_collection.is_edited(collection)


def test_renaming_the_lit_colour_attribute_counts_as_edited(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).color_attributes[appearance_preview.LIT_ATTRIBUTE].name = "renamed"
    assert appearance_collection.is_edited(collection)


def user_objects(collection):
    empty = bpy.data.objects.new("MyEmpty", None)
    camera = bpy.data.objects.new("MyCamera", bpy.data.cameras.new("MyCamera"))
    collection.objects.link(empty)
    collection.objects.link(camera)
    return empty, camera


def test_removing_a_collection_with_objects_the_add_on_did_not_make_is_refused_and_changes_nothing(dump):
    _, _, collection = build(dump)
    user_objects(collection)
    with pytest.raises(ValueError, match="MyEmpty, MyCamera"):
        appearance_collection.remove_collection(collection)
    assert sorted(obj.name for obj in collection.objects) == ["MyCamera", "MyEmpty", "Player", "Player_rig"]
    assert len(bpy.data.meshes) == 1 and len(bpy.data.armatures) == 1


def test_the_notice_of_a_fresh_player_is_empty(dump):
    _, _, collection = build(dump)
    assert appearance_collection.notice(collection) is None


def test_the_notice_names_edits(dump):
    _, _, collection = build(dump)
    appearance_collection.mesh_data(collection).vertices[0].co.x += 5
    assert "has edits" in (appearance_collection.notice(collection) or "")


def test_the_notice_names_edit_mode(dump):
    _, _, collection = build(dump)
    edit(appearance_collection.mesh_of(collection))
    assert "Edit Mode" in (appearance_collection.notice(collection) or "")


def test_the_notice_of_a_collection_with_two_meshes_is_a_warning_and_does_not_raise(dump):
    _, _, collection = build(dump)
    collection.objects.link(bpy.data.objects.new("Second", appearance_collection.mesh_data(collection).copy()))
    assert "holds 2" in (appearance_collection.notice(collection) or "")


def test_player_objects_are_refused_by_static_export_and_others_are_not(dump):
    _, _, collection = build(dump)
    with pytest.raises(ValueError, match="Player, Player_rig"):
        assert_static_exportable(
            [appearance_collection.mesh_of(collection), appearance_collection.armature_of(collection)]
        )
    assert_static_exportable([bpy.data.objects.new("Elsewhere", None)])


def test_joint_bones_form_the_frame_maps_hierarchy_with_label_bones_under_them(dump):
    _, body, collection = build(dump)
    rig = derive_rig(body)
    bones = appearance_collection.armature_data(collection).bones
    for joint in rig.joints:
        bone = bones[joint.name]
        assert (bone.parent.name if bone.parent else None) == joint.parent
        assert not bone.use_deform
    for label in {b.label for b in rig.bones}:
        parent = bones[f"label_{label}"].parent
        assert (parent.name if parent else None) == rig.owner(label)
    assert appearance_collection.is_joint_rig(appearance_collection.armature_of(collection))


def posed_points(collection):
    mesh_obj = appearance_collection.mesh_of(collection)
    evaluated = mesh_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return [v.co.copy() for v in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def test_turning_the_head_joint_moves_labels_1_and_3_about_the_neck_and_nothing_else(dump):
    from mathutils import Matrix, Quaternion

    _, body, collection = build(dump)
    rig = appearance_collection.armature_of(collection)
    rest = posed_points(collection)
    head = rig.pose.bones["head"]  # pyrefly: ignore[missing-attribute]
    head.rotation_quaternion = Quaternion((0.0, 1.0, 0.0), 0.7)
    bpy.context.view_layer.update()  # pyrefly: ignore[missing-attribute]
    posed = posed_points(collection)
    pivot = rig.data.bones["head"].head_local  # pyrefly: ignore[missing-attribute]
    turn = (
        Matrix.Translation(pivot) @ Quaternion((0.0, 0.0, 1.0), 0.7).to_matrix().to_4x4() @ Matrix.Translation(-pivot)
    )
    assert body.vertex_skins is not None
    for before, after, label in zip(rest, posed, body.vertex_skins, strict=True):
        expected = turn @ before if label in (1, 3) else before
        assert (after - expected).length < 1e-3


def test_joints_are_shown_and_label_bones_are_kept_in_a_hidden_bone_collection(dump):
    _, _, collection = build(dump)
    armature = appearance_collection.armature_data(collection)
    joints = armature.collections[appearance_collection.JOINT_COLLECTION]
    labels = armature.collections[appearance_collection.LABEL_COLLECTION]
    assert joints.is_visible and not labels.is_visible
    assert {b.name for b in joints.bones} == {b.name for b in armature.bones if not b.name.startswith("label_")}
    assert {b.name for b in labels.bones} == {b.name for b in armature.bones if b.name.startswith("label_")}


ARMED = (0, 0, 0, 512 + 1333, 274, 512 + 1201, 282, 292, 256, 289, 298, 266)


def build_armed(dump):
    source = AppearancePreset(149, 430, False, ARMED, (0,) * 5)
    body, shading, slots = appearance_preview.assemble_parts(source, dump)
    return source, body, shading, appearance_collection.build_collection(body, shading, source, "Player", slots=slots)


def corners(obj) -> list[tuple]:
    """Each polygon as its merged-model vertices, corner colours and face label, for comparing meshes."""
    mesh = obj.data
    model_vertex = appearance_preview.vertex_indices(mesh)
    colours = mesh.color_attributes[appearance_preview.LIT_ATTRIBUTE].data
    labels = mesh.attributes[appearance_preview.FACE_LABEL_ATTRIBUTE].data
    return [
        (
            tuple(model_vertex[v] for v in polygon.vertices),
            tuple(tuple(round(c, 6) for c in colours[i].color) for i in polygon.loop_indices),
            labels[polygon.index].value,
        )
        for polygon in mesh.polygons
    ]


def test_a_worn_weapon_and_shield_are_their_own_objects_moved_by_the_rig(armed_dump):
    _, _, _, collection = build_armed(armed_dump)
    rig = appearance_collection.armature_of(collection)
    parts = appearance_collection.parts(collection)
    assert [obj.name for obj in parts] == ["Player", "Player Weapon", "Player Shield"]
    assert appearance_collection.mesh_of(collection) is parts[0]
    for obj in parts:
        assert obj.parent == rig
        assert [m.object for m in obj.modifiers if m.type == "ARMATURE"] == [rig]  # pyrefly: ignore[missing-attribute]
    assert not appearance_collection.is_edited(collection)


def test_the_parts_together_hold_the_single_meshs_faces_colours_and_labels(armed_dump):
    _, body, shading, collection = build_armed(armed_dump)
    whole = bpy.data.objects.new("whole", appearance_preview.build_mesh(body, shading, "whole"))
    expected = sorted(corners(whole))
    assert sorted(face for obj in appearance_collection.parts(collection) for face in corners(obj)) == expected
    assert len(appearance_collection.parts(collection)[1].data.polygons) > 0  # pyrefly: ignore[missing-attribute, bad-argument-type]


def test_each_part_vertex_carries_its_merged_vertex_position_and_label(armed_dump):
    _, body, _, collection = build_armed(armed_dump)
    assert body.vertex_skins is not None
    for obj in appearance_collection.parts(collection):
        model_vertex = appearance_preview.vertex_indices(obj.data)  # pyrefly: ignore[missing-attribute, bad-argument-type]
        for vertex in obj.data.vertices:  # pyrefly: ignore[missing-attribute, bad-argument-type]
            x, y, z = body.vertices[model_vertex[vertex.index]]
            assert tuple(vertex.co) == pytest.approx((x, z, -y))
            assert [obj.vertex_groups[g.group].name for g in vertex.groups] == [
                f"label_{body.vertex_skins[model_vertex[vertex.index]]}"
            ]


def test_moving_a_weapon_vertex_counts_as_edited(armed_dump):
    _, _, _, collection = build_armed(armed_dump)
    appearance_collection.parts(collection)[1].data.vertices[0].co.x += 5  # pyrefly: ignore[missing-attribute, bad-argument-type]
    assert appearance_collection.is_edited(collection)


def test_a_player_without_a_weapon_or_shield_is_one_mesh_with_every_vertex_in_order(dump):
    _, body, collection = build(dump)
    assert len(appearance_collection.parts(collection)) == 1
    mesh = appearance_collection.mesh_data(collection)
    assert appearance_preview.vertex_indices(mesh) == list(range(len(body.vertices)))


def test_a_player_holding_two_rigs_says_to_use_duplicate_player(dump):
    _, _, collection = build(dump)
    rig = appearance_collection.armature_of(collection)
    copy = rig.copy()
    collection.objects.link(copy)
    message = appearance_collection.notice(collection)
    assert message is not None and "Duplicate Player" in message
