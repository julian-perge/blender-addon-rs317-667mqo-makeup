"""The RS Scene export, read back from the JSON and binary chunks of the `.glb` file that it writes.

The rows named in the tests are the rows of the test table of spec 140 (`spec/140-campfire-glb-export.md`)."""

import json
import math
import struct
from pathlib import Path

import bmesh
import bpy
import pytest
from js5_builder import build_cache
from mathutils import Quaternion

from rsps_toolkit.animation.frames import decode_frame_map
from rsps_toolkit.blender import (
    appearance_clip,
    appearance_collection,
    appearance_preview,
    export_gltf,
    face_materials,
    npc_collection,
)
from rsps_toolkit.blender.face_materials import DEFAULT_BRIGHTNESS
from rsps_toolkit.formats.appearance_preset import AppearancePreset
from rsps_toolkit.formats.lighting import light_hsl
from rsps_toolkit.formats.model import Model
from rsps_toolkit.formats.texture import SIZE as TEXTURE_SIZE

# glTF 2.0 specification, sections 3.6.2 (accessor component types) and 4.4 (binary glTF layout).
COMPONENTS = {5121: ("B", 255), 5123: ("H", 65535), 5126: ("f", 1)}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
FIXTURES = Path(__file__).parent.parent / "fixtures"
REFERENCE = json.loads((FIXTURES / "appearance" / "reference.json").read_text())
NPC_FIXTURES = FIXTURES / "npc"
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

# The corner colours of the test triangle. Each attribute has its own three colours, so a test can tell which
# attribute the file holds.
COLOURS = {
    "rs_lit": ((0.1, 0.2, 0.3), (0.2, 0.3, 0.4), (0.3, 0.4, 0.5)),
    "scene_lit": ((0.6, 0.1, 0.1), (0.7, 0.1, 0.1), (0.8, 0.1, 0.1)),
    "fire_strength": ((0.25, 0.25, 0.25), (0.5, 0.5, 0.5), (0.75, 0.75, 0.75)),
    "wind": ((0.0, 0.9, 0.0), (0.0, 0.8, 0.0), (0.0, 0.7, 0.0)),
}


@pytest.fixture(autouse=True)
def operator_registered(clean):
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    for cls in export_gltf.classes:
        bpy.utils.register_class(cls)
    yield
    for cls in reversed(export_gltf.classes):
        bpy.utils.unregister_class(cls)


def triangle(name: str, attributes: tuple[str, ...]) -> bpy.types.Object:
    """A selected one-triangle mesh with a Principled BSDF material and the corner colour attributes `attributes`,
    made in that order."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    for attribute in attributes:
        colours = mesh.color_attributes.new(attribute, "FLOAT_COLOR", "CORNER")
        assert isinstance(colours, bpy.types.FloatColorAttribute)
        colours.data.foreach_set("color", [v for rgb in COLOURS[attribute] for v in (*rgb, 1.0)])
    mesh.materials.append(bpy.data.materials.new(f"{name} source"))
    obj = bpy.data.objects.new(name, mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    return obj


def export(path: Path, **options) -> set[str]:
    # The stubs only list Blender's own operators.
    return bpy.ops.export_scene.rs_scene(filepath=str(path), **options)  # pyrefly: ignore[missing-attribute]


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    chunks: dict[int, bytes] = {}
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        chunks[kind] = data[offset + 8 : offset + 8 + length]
        offset += 8 + length
    return json.loads(chunks[JSON_CHUNK]), chunks.get(BIN_CHUNK, b"")


def accessor_values(gltf: dict, binary: bytes, index: int) -> list[tuple[float, ...]]:
    accessor = gltf["accessors"][index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    code, scale = COMPONENTS[accessor["componentType"]]
    if not accessor.get("normalized"):
        scale = 1
    width = WIDTHS[accessor["type"]]
    size = struct.calcsize(code)
    stride = view.get("byteStride", size * width)
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return [
        tuple(v / scale for v in struct.unpack_from(f"<{width}{code}", binary, start + i * stride))
        for i in range(accessor["count"])
    ]


def colours(gltf: dict, binary: bytes, attribute: str) -> list[tuple[float, ...]]:
    """The RGB values of `attribute` of the one primitive of the file, sorted, rounded to 2 places."""
    (mesh,) = gltf["meshes"]
    (primitive,) = mesh["primitives"]
    values = accessor_values(gltf, binary, primitive["attributes"][attribute])
    return sorted(tuple(round(v, 2) for v in value[:3]) for value in values)


def expected(attribute: str) -> list[tuple[float, ...]]:
    return sorted(COLOURS[attribute])


def test_the_operator_writes_one_glb_with_unlit_materials_that_draw_rs_lit(tmp_path: Path):
    # Rows "Menu" and "Unlit materials". The default colour attribute is `rs_lit` (ADR 0028), and a Color Attribute
    # node that feeds the Material Output exports as KHR_materials_unlit with COLOR_0 (ADR 0026).
    triangle("Ground", ("rs_lit",))
    path = tmp_path / "scene.glb"
    assert export(path) == {"FINISHED"}
    gltf, binary = read_glb(path)
    assert [list(m.get("extensions", {})) for m in gltf["materials"]] == [["KHR_materials_unlit"]]
    assert colours(gltf, binary, "COLOR_0") == expected("rs_lit")


def test_the_named_colour_attribute_is_color_0_and_the_plain_mesh_has_one_material_with_no_extras(tmp_path: Path):
    # Rows "Named attribute" and "Own mesh" (ADR 0028, spec decision 3).
    triangle("Ground", ("rs_lit", "scene_lit"))
    path = tmp_path / "scene.glb"
    export(path, colour_attribute="scene_lit")
    gltf, binary = read_glb(path)
    assert colours(gltf, binary, "COLOR_0") == expected("scene_lit")
    (material,) = gltf["materials"]
    assert "extras" not in material
    (primitive,) = gltf["meshes"][0]["primitives"]
    assert "COLOR_1" not in primitive["attributes"]


def test_one_extra_attribute_is_color_1(tmp_path: Path):
    # Row "Extra attributes" (spec decision 7).
    triangle("Ground", ("scene_lit", "fire_strength"))
    path = tmp_path / "scene.glb"
    export(path, colour_attribute="scene_lit", extra_attributes="fire_strength")
    gltf, binary = read_glb(path)
    assert colours(gltf, binary, "COLOR_1") == expected("fire_strength")


def test_two_extra_attributes_follow_the_order_of_the_list_and_not_of_the_mesh(tmp_path: Path):
    # Row "Extra attributes": the list order is the order of COLOR_1 and up (spec decision 7, guess 2). The mesh makes
    # the two attributes in the other order.
    triangle("Ground", ("scene_lit", "wind", "fire_strength"))
    path = tmp_path / "scene.glb"
    export(path, colour_attribute="scene_lit", extra_attributes="fire_strength, wind")
    gltf, binary = read_glb(path)
    assert colours(gltf, binary, "COLOR_1") == expected("fire_strength")
    assert colours(gltf, binary, "COLOR_2") == expected("wind")


@pytest.mark.parametrize(
    ("options", "missing"),
    [({"colour_attribute": "scene_lit"}, "scene_lit"), ({"extra_attributes": "fire_strength"}, "fire_strength")],
    ids=["colour", "extra"],
)
def test_a_mesh_without_an_attribute_stops_the_export_and_the_message_names_it(tmp_path: Path, options, missing):
    # Row "Refusal" (spec decision 5). The owner chose the wording of the message in the build of issue 141 on
    # 2026-11-17.
    triangle("Ground", ("rs_lit",))
    triangle("Rock", ("rs_lit", "scene_lit", "fire_strength"))
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError) as refusal:
        export(path, **options)
    assert f"Ground has no colour attribute {missing}." in str(refusal.value)
    assert "Rock" not in str(refusal.value)
    assert not path.exists()


def test_an_attribute_that_is_not_a_colour_attribute_stops_the_export(tmp_path: Path):
    # Spec rule 4: the named attribute must be a colour attribute. The owner chose the wording of the message in the
    # build of issue 141 on 2026-11-17.
    obj = triangle("Ground", ("rs_lit",))
    assert isinstance(obj.data, bpy.types.Mesh)
    obj.data.attributes.new("fire_strength", "FLOAT", "CORNER")
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError) as refusal:
        export(path, extra_attributes="fire_strength")
    assert "Ground: fire_strength is not a colour attribute." in str(refusal.value)
    assert not path.exists()


def test_nothing_selected_stops_the_export(tmp_path: Path):
    # Spec rule 2, a guess from ADR 0010 that the owner approved with the spec.
    triangle("Ground", ("rs_lit",)).select_set(False)
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError):
        export(path)
    assert not path.exists()


def test_the_file_has_the_names_of_the_scene_and_the_scene_is_unchanged(tmp_path: Path):
    # Spec Boundaries "Always": the export works on copies and leaves the scene as it was.
    ground = triangle("Ground", ("rs_lit", "scene_lit", "fire_strength"))
    ground.keyframe_insert("location", frame=1)
    triangle("Other", ("rs_lit",)).select_set(False)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = ground
    before = scene_state()
    path = tmp_path / "scene.glb"
    export(path, colour_attribute="scene_lit")
    assert scene_state() == before
    gltf, _ = read_glb(path)
    assert [node["name"] for node in gltf["nodes"]] == ["Ground"]
    assert [mesh["name"] for mesh in gltf["meshes"]] == ["Ground"]


def test_a_failed_export_leaves_the_scene_unchanged(tmp_path: Path, monkeypatch):
    # Spec Boundaries "Always": also when the export fails.
    ground = triangle("Ground", ("rs_lit",))
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = ground
    before = scene_state()

    def fail(path: Path) -> None:
        # The stock exporter goes to frame 0 and goes back only when it does not fail (exp/export.py, `save`).
        scene = bpy.context.scene
        assert scene is not None
        scene.frame_set(0)
        raise RuntimeError("the stock exporter failed")

    monkeypatch.setattr(export_gltf, "write_glb", fail)
    with pytest.raises(RuntimeError):
        export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_the_fixed_settings_write_extras_and_no_draco(tmp_path: Path):
    # Spec rule 11: `export_extras` on and Draco off.
    ground = triangle("Ground", ("rs_lit",))
    ground["rs_note"] = 7
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert gltf["nodes"][0]["extras"] == {"rs_note": 7}
    assert "KHR_draco_mesh_compression" not in gltf.get("extensionsUsed", [])


def scene_state() -> dict:
    view_layer = bpy.context.view_layer
    scene = bpy.context.scene
    assert view_layer is not None and scene is not None
    return {
        "objects": sorted(obj.name for obj in bpy.data.objects),
        "meshes": {
            mesh.name: (
                len(mesh.polygons),
                len(mesh.vertices),
                [m.name for m in mesh.materials if m is not None],
                [(a.name, a.domain, a.data_type) for a in mesh.attributes],
            )
            for mesh in bpy.data.meshes
        },
        "materials": sorted(m.name for m in bpy.data.materials),
        "actions": sorted(action.name for action in bpy.data.actions),
        "animation data": {obj.name: animation_state(obj.animation_data) for obj in bpy.data.objects},
        "selected": sorted(obj.name for obj in bpy.data.objects if obj.select_get()),
        "active": view_layer.objects.active.name if view_layer.objects.active else None,
        "frame": scene.frame_current,
    }


def animation_state(animation: bpy.types.AnimData | None) -> tuple | None:
    """The active action and slot of `animation`, and its tracks with their strips."""
    if animation is None:
        return None
    return (
        animation.action.name if animation.action else None,
        animation.action_slot.identifier if animation.action_slot else None,
        animation.use_nla,
        animation.use_tweak_mode,
        [
            (
                track.name,
                track.mute,
                track.is_solo,
                [
                    (
                        strip.name,
                        strip.action.name if strip.action else None,
                        strip.action_slot.identifier if strip.action_slot else None,
                        strip.frame_start,
                        strip.frame_end,
                        strip.mute,
                    )
                    for strip in track.strips
                ],
            )
            for track in animation.nla_tracks
        ],
    )


def raw_files(folder: Path) -> dict[int, bytes]:
    return {int(path.stem): path.read_bytes() for path in folder.glob("*.dat")}


def test_a_material_linked_to_the_object_is_replaced_too(tmp_path: Path):
    # Spec rule 7: the copy of a mesh with no `rs_face` draws the colour attribute through one unlit material, also when
    # the object, not the mesh, holds the material of its slot.
    ground = triangle("Ground", ("rs_lit",))
    ground.material_slots[0].link = "OBJECT"
    ground.material_slots[0].material = bpy.data.materials.new("Ground object")
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert [list(m.get("extensions", {})) for m in gltf["materials"]] == [["KHR_materials_unlit"]]


def test_a_repeated_extra_attribute_stops_the_export(tmp_path: Path):
    # The owner chose in the build of issue 141 on 2026-11-17 that a repeated name stops the export, because each extra
    # is its own COLOR_n.
    triangle("Ground", ("rs_lit", "wind", "fire_strength"))
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError, match="Extra attributes name wind twice."):
        export(path, extra_attributes="wind, fire_strength, wind")
    assert not path.exists()


def test_the_spaces_around_the_colour_attribute_are_not_part_of_it(tmp_path: Path):
    # The owner chose in the build of issue 141 on 2026-11-17 that both fields drop the spaces around a name.
    triangle("Ground", ("rs_lit", "scene_lit"))
    path = tmp_path / "scene.glb"
    export(path, colour_attribute=" scene_lit ")
    gltf, binary = read_glb(path)
    assert colours(gltf, binary, "COLOR_0") == expected("scene_lit")


def test_objects_of_another_scene_are_not_exported(tmp_path: Path):
    # Spec rule 2: the file holds the selected objects of the scene that the user exports from.
    ground = triangle("Ground", ("rs_lit",))
    other = bpy.data.scenes.new("Other scene")
    other.collection.objects.link(ground)
    elsewhere = bpy.data.objects.new("Elsewhere", bpy.data.meshes.new("Elsewhere"))
    other.collection.objects.link(elsewhere)
    for obj in (ground, elsewhere):
        obj.select_set(True, view_layer=other.view_layers[0])
    try:
        path = tmp_path / "scene.glb"
        export(path)
        gltf, _ = read_glb(path)
        assert [node["name"] for node in gltf["nodes"]] == ["Ground"]
    finally:
        bpy.data.scenes.remove(other)


def test_the_file_has_the_edit_mode_edits_and_the_mesh_stays_in_edit_mode(tmp_path: Path):
    # The owner chose in the build of issue 141 on 2026-11-17 that the export includes the Edit Mode edits and gives
    # back the mode, as ADR 0010 does for the model export.
    ground = triangle("Ground", ("rs_lit",))
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = ground
    bpy.ops.object.mode_set(mode="EDIT")
    mesh = ground.data
    assert isinstance(mesh, bpy.types.Mesh)
    edit = bmesh.from_edit_mesh(mesh)
    edit.verts.ensure_lookup_table()
    b, c = edit.verts[1], edit.verts[2]
    edit.faces.new((b, edit.verts.new((1, 1, 0)), c))
    bmesh.update_edit_mesh(mesh)
    path = tmp_path / "scene.glb"
    export(path)
    assert ground.mode == "EDIT"
    gltf, _ = read_glb(path)
    (primitive,) = gltf["meshes"][0]["primitives"]
    assert gltf["accessors"][primitive["indices"]]["count"] == 6


def test_objects_that_are_not_meshes_or_rigs_are_left_out_with_a_warning(tmp_path: Path, capfd):
    # The owner chose in the build of issue 141 on 2026-11-17 that the export leaves out the selected objects that are
    # not meshes, and says which. Since the build of issue 145 the export also writes rigs, and the owner chose there on
    # 2026-11-17 that the warning names them.
    triangle("Ground", ("rs_lit",))
    marker = bpy.data.objects.new("Marker", None)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(marker)
    marker.select_set(True)
    path = tmp_path / "scene.glb"
    capfd.readouterr()
    export(path)
    assert "Warning: Left out Marker: only meshes and rigs are exported." in capfd.readouterr().out.splitlines()
    gltf, _ = read_glb(path)
    assert [node["name"] for node in gltf["nodes"]] == ["Ground"]


def test_two_objects_on_one_mesh_share_one_mesh_in_the_file(tmp_path: Path):
    # The glTF note, row 9: the stock export writes a mesh that two objects use once.
    ground = triangle("Ground", ("rs_lit",))
    twin = bpy.data.objects.new("Twin", ground.data)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(twin)
    twin.select_set(True)
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(node["name"] for node in gltf["nodes"]) == ["Ground", "Twin"]
    assert [mesh["name"] for mesh in gltf["meshes"]] == ["Ground"]


def test_a_failure_while_the_copies_are_made_leaves_the_scene_unchanged(tmp_path: Path, monkeypatch):
    # Spec Boundaries "Always": also when the export fails.
    triangle("Ground", ("rs_lit",))
    before = scene_state()

    def fail(*args) -> None:
        raise RuntimeError("the copy failed")

    monkeypatch.setattr(export_gltf, "_keep_colour_attributes", fail)
    with pytest.raises(RuntimeError):
        export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_a_failure_while_a_material_is_drawn_leaves_the_scene_unchanged(tmp_path: Path, monkeypatch):
    # Spec Boundaries "Always": also when the export fails after it made a material.
    triangle("Ground", ("rs_lit",))
    before = scene_state()

    def fail(*args) -> None:
        raise RuntimeError("the drawing failed")

    monkeypatch.setattr(export_gltf, "_draw_unlit", fail)
    with pytest.raises(RuntimeError):
        export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_faces_on_the_same_three_vertices_are_all_in_the_file_in_mesh_order(tmp_path: Path):
    # Row "Shared vertices" (issue 121). Faces 2 and 3 use the vertices of faces 0 and 1, and Blender's mesh validation,
    # which the stock exporter runs, removes such a face. Each face has its own three corner colours, so a triangle of
    # the file tells which face it is.
    faces = [(0, 1, 2), (1, 3, 2), (2, 1, 0), (1, 3, 2)]
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [], faces)
    face_colours = [
        [(round(0.1 * (face + 1), 2), 0.2 * corner, 0.5) for corner in range(3)] for face in range(len(faces))
    ]
    lit = mesh.color_attributes.new("rs_lit", "FLOAT_COLOR", "CORNER")
    assert isinstance(lit, bpy.types.FloatColorAttribute)
    lit.data.foreach_set("color", [v for corners in face_colours for rgb in corners for v in (*rgb, 1.0)])
    obj = bpy.data.objects.new("Ground", mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    path = tmp_path / "scene.glb"
    export(path)
    assert len(mesh.polygons) == 4
    gltf, binary = read_glb(path)
    (primitive,) = gltf["meshes"][0]["primitives"]
    indices = [int(i) for (i,) in accessor_values(gltf, binary, primitive["indices"])]
    corner_colours = accessor_values(gltf, binary, primitive["attributes"]["COLOR_0"])
    triangles = [
        sorted(tuple(round(v, 2) for v in corner_colours[i][:3]) for i in indices[start : start + 3])
        for start in range(0, len(indices), 3)
    ]
    assert triangles == [sorted(corners) for corners in face_colours]


def test_a_refused_export_leaves_the_scene_unchanged(tmp_path: Path):
    # Row "Scene unchanged" (issue 121): a refused export also leaves the scene as it was.
    ground = triangle("Ground", ("rs_lit",))
    ground.keyframe_insert("location", frame=1)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = ground
    before = scene_state()
    with pytest.raises(RuntimeError):
        export(tmp_path / "scene.glb", colour_attribute="scene_lit")
    assert scene_state() == before


def test_the_export_of_faces_on_the_same_three_vertices_leaves_the_scene_unchanged(tmp_path: Path):
    # Rows "Shared vertices" and "Scene unchanged" (issue 121): the vertices of their own are made on the copy only.
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2), (2, 1, 0)])
    mesh.color_attributes.new("rs_lit", "FLOAT_COLOR", "CORNER")
    obj = bpy.data.objects.new("Ground", mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    before = scene_state()
    export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_the_vertices_of_their_own_keep_the_vertex_group_weights(tmp_path: Path, monkeypatch):
    # Issue 121: a player mesh is skinned through its vertex groups, so a face that gets vertices of its own keeps the
    # weights of the vertices that it used.
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2), (2, 1, 0)])
    mesh.color_attributes.new("rs_lit", "FLOAT_COLOR", "CORNER")
    obj = bpy.data.objects.new("Ground", mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    group = obj.vertex_groups.new(name="joint")
    for vertex, weight in enumerate((0.25, 0.5, 0.75)):
        group.add([vertex], weight, "REPLACE")
    seen: list[list[float]] = []
    vertex_counts: list[int] = []

    def record(path: Path) -> None:
        selected = bpy.context.selected_objects
        assert selected is not None and len(selected) == 1
        copy = selected[0]
        copy_mesh = copy.data
        assert isinstance(copy_mesh, bpy.types.Mesh)
        vertex_counts.append(len(copy_mesh.vertices))
        group = copy.vertex_groups["joint"]
        for face in copy_mesh.polygons:
            corners = copy_mesh.loops[face.loop_start : face.loop_start + face.loop_total]
            seen.append(sorted(group.weight(corner.vertex_index) for corner in corners))

    monkeypatch.setattr(export_gltf, "write_glb", record)
    export(tmp_path / "scene.glb")
    assert vertex_counts == [6]
    assert seen == [[0.25, 0.5, 0.75], [0.25, 0.5, 0.75]]


@pytest.mark.parametrize("extras", [("fire_strength", "wind"), ("wind", "fire_strength")])
def test_extra_attributes_keep_the_order_of_the_list_on_a_mesh_with_faces_on_the_same_three_vertices(
    tmp_path: Path, extras: tuple[str, str]
):
    # Rows "Extra attributes" and "Shared vertices": the vertices of their own do not change the order of COLOR_1 and
    # up (spec decision 7). The two extras differ in data type and domain, because Blender orders the attributes by
    # domain and data type when a mesh is written back from bmesh.
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2), (2, 1, 0)])
    mesh.color_attributes.new("rs_lit", "FLOAT_COLOR", "CORNER")
    values = {"fire_strength": 0.4, "wind": 0.8}
    for name, data_type, domain in (("fire_strength", "FLOAT_COLOR", "CORNER"), ("wind", "BYTE_COLOR", "POINT")):
        attribute = mesh.color_attributes.new(name, data_type, domain)
        assert isinstance(attribute, (bpy.types.FloatColorAttribute, bpy.types.ByteColorAttribute))
        attribute.data.foreach_set("color", [values[name], values[name], values[name], 1.0] * len(attribute.data))
    obj = bpy.data.objects.new("Ground", mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    path = tmp_path / "scene.glb"
    export(path, extra_attributes=", ".join(extras))
    gltf, binary = read_glb(path)
    (primitive,) = gltf["meshes"][0]["primitives"]
    for index, name in enumerate(extras, start=1):
        written = accessor_values(gltf, binary, primitive["attributes"][f"COLOR_{index}"])
        assert len(written) == 6
        assert {round(value[0], 1) for value in written} == {values[name]}


def player(cache: Path) -> tuple[bpy.types.Object, dict]:
    """A selected player mesh from Create Player's build, and the client's model of it before lighting
    (tests/fixtures/appearance/reference.json)."""
    case = next(c for c in REFERENCE["cases"] if not c.get("outfit") and not c["female"] and c["colours"] == [0] * 5)
    preset = AppearancePreset(149, 430, False, tuple(case["equipment"]), tuple(case["colours"]))
    body, shading, slots = appearance_preview.assemble_parts(preset, cache)
    collection = appearance_collection.build_collection(body, shading, preset, "Player", slots=slots)
    obj = appearance_collection.mesh_of(collection)
    obj.select_set(True)
    return obj, case["before_lighting"]


def model_mesh(name: str, alphas: list[int]) -> bpy.types.Object:
    """A selected mesh built as Create NPC and Make Rig build theirs, from a model of two faces with these face alphas
    and the face colours 8741 and 960. The model has no face skins, as a Make Rig model can have none."""
    model = Model(
        vertices=[(0, 0, 0), (100, 0, 0), (0, -100, 0), (100, -100, 0)],
        faces=[(0, 1, 2), (1, 3, 2)],
        face_colours=[8741, 960],
        face_textures=[None, None],
        render_priorities=[0, 0],
        face_alphas=alphas,
        face_texture_triangles=[None, None],
        flat_shaded=[True, True],
    )
    obj = bpy.data.objects.new(name, appearance_preview.build_mesh(model, light_hsl(model), name))
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    return obj


def test_the_player_has_one_unlit_material_for_each_pair_of_face_colour_and_face_alpha(cache: Path, tmp_path: Path):
    # Row "Split" (issue 116, ADR 0026): the pairs are the client's face colours and face alphas of the faces that the
    # mesh holds.
    obj, before = player(cache)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    faces = appearance_preview.face_indices(mesh)
    assert faces is not None
    alphas = before["face_alphas"] or [0] * before["face_count"]
    pairs = {(before["face_colours"][face], alphas[face]) for face in faces}
    path = tmp_path / "scene.glb"
    assert export(path) == {"FINISHED"}
    gltf, _ = read_glb(path)
    assert sorted((m["extras"]["rs_face_colour"], m["extras"]["rs_alpha"]) for m in gltf["materials"]) == sorted(pairs)
    assert all(list(m["extensions"]) == ["KHR_materials_unlit"] for m in gltf["materials"])
    (gltf_mesh,) = gltf["meshes"]
    assert all("COLOR_0" in primitive["attributes"] for primitive in gltf_mesh["primitives"])
    triangles = sum(gltf["accessors"][primitive["indices"]]["count"] for primitive in gltf_mesh["primitives"]) // 3
    assert triangles == len(mesh.polygons)


def test_each_face_draws_with_the_material_of_its_face_colour_and_face_alpha(tmp_path: Path):
    # Row "Split": each face of the file uses the material whose extras hold its own game values.
    model_mesh("Fire", [0, 0])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    (gltf_mesh,) = gltf["meshes"]
    drawn = []
    for primitive in gltf_mesh["primitives"]:
        extras = gltf["materials"][primitive["material"]]["extras"]
        count = gltf["accessors"][primitive["indices"]]["count"] // 3
        drawn += [(extras["rs_face_colour"], extras["rs_alpha"])] * count
    assert sorted(drawn) == [(960, 0), (8741, 0)]


def test_a_face_with_an_alpha_draws_blended_with_the_clients_opacity(tmp_path: Path):
    # Row "Face alpha" (spec decision 8). The client blends a face at (256 - alpha) / 256, the rule that
    # face_materials._show_alpha cites.
    model_mesh("Fire", [0, 100])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    by_alpha = {m["extras"]["rs_alpha"]: m for m in gltf["materials"]}
    assert sorted(by_alpha) == [0, 100]
    assert by_alpha[100]["alphaMode"] == "BLEND"
    assert by_alpha[100]["pbrMetallicRoughness"]["baseColorFactor"][3] == pytest.approx(156 / 256)
    assert "alphaMode" not in by_alpha[0]
    assert list(by_alpha[100]["extensions"]) == ["KHR_materials_unlit"]


def test_two_meshes_share_the_material_of_a_pair(tmp_path: Path):
    # The owner chose in the build of issue 143 on 2026-11-17 that the file has one material for each pair, also when
    # several meshes use it, and that it has the name that face_materials gives a model import's material.
    model_mesh("Fire", [0, 0])
    model_mesh("Embers", [0, 0])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(m["name"] for m in gltf["materials"]) == ["RS_Colour_8741_0", "RS_Colour_960_0"]


@pytest.mark.parametrize("attribute", ["rs_face_colour", "rs_face_alpha"])
def test_a_mesh_built_before_meshes_stored_their_face_colours_stops_the_export(tmp_path: Path, attribute: str):
    # Issue 143. The owner chose the wording of the message in the build of issue 143 on 2026-11-17.
    obj = model_mesh("Fire", [0, 0])
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh.attributes.remove(mesh.attributes[attribute])
    model_mesh("Embers", [0, 0])
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError) as refusal:
        export(path)
    assert (
        "Fire was built before meshes stored their face colours. Run Update Player on a player, or Create NPC or Make "
        "Rig again on an NPC." in str(refusal.value)
    )
    assert "Embers" not in str(refusal.value)
    assert not path.exists()


def test_the_export_of_a_player_leaves_the_scene_unchanged(cache: Path, tmp_path: Path):
    # Row "Scene unchanged": the materials of the pairs are made for the copies only.
    obj, _ = player(cache)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    model_mesh("Fire", [0, 100])
    before = scene_state()
    export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_each_primitive_of_a_split_mesh_has_its_faces_in_mesh_order(tmp_path: Path):
    # Row "Shared vertices". The owner chose in the build of issue 143 on 2026-11-17 that each primitive keeps the
    # mesh order of its faces, and that the order across primitives is left to the page. The four faces lie apart, and
    # their face colours take turns, so each primitive holds two faces that are not next to each other in the mesh.
    model = Model(
        vertices=[(x, y, 0) for i in range(4) for x, y in ((200 * i, 0), (200 * i + 100, 0), (200 * i, -100))],
        faces=[(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11)],
        face_colours=[8741, 960, 8741, 960],
        face_textures=[None] * 4,
        render_priorities=[0] * 4,
        face_alphas=[0] * 4,
        face_texture_triangles=[None] * 4,
        flat_shaded=[True] * 4,
    )
    obj = bpy.data.objects.new("Fire", appearance_preview.build_mesh(model, light_hsl(model), "Fire"))
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    # The glTF x is the Blender x, and the faces start at different x.
    face_at = {
        round(
            min(mesh.vertices[corner.vertex_index].co.x for corner in mesh.loops[f.loop_start : f.loop_start + 3]), 3
        ): f.index
        for f in mesh.polygons
    }
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    by_colour = {}
    for primitive in gltf["meshes"][0]["primitives"]:
        indices = [int(i) for (i,) in accessor_values(gltf, binary, primitive["indices"])]
        positions = accessor_values(gltf, binary, primitive["attributes"]["POSITION"])
        by_colour[gltf["materials"][primitive["material"]]["extras"]["rs_face_colour"]] = [
            face_at[round(min(positions[i][0] for i in indices[start : start + 3]), 3)]
            for start in range(0, len(indices), 3)
        ]
    assert by_colour == {8741: [0, 2], 960: [1, 3]}


# Texture 5 has a texel that the client does not draw, texture 7 has none, and texture 9 has no image, as when model
# import finds no PNG for it.
TEXTURES = {5: False, 7: True}


def imported_mesh(
    name: str,
    faces: list[tuple[int | None, int | None, int] | None],
    attributes: tuple[tuple[str, float], ...] = (("rs_lit", 0.5),),
    textures: dict[int, bool] = TEXTURES,
) -> bpy.types.Object:
    """A selected mesh with no `rs_face`, with one triangle apart from the others for each item of `faces`, a UV map
    and the corner colour attributes `attributes`, made in that order with one grey each. An item is the face colour,
    texture id and face alpha of a material that face_materials makes, as model import does, or None for a material
    with no game values, such as the owner's ground has. Each call makes its own image for each texture of `textures`,
    as the region import does for each region, and `textures` tells whether the texture is opaque."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(
        [(x, y, 0) for i in range(len(faces)) for x, y in ((2 * i, 0), (2 * i + 1, 0), (2 * i, 1))],
        [],
        [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(faces))],
    )
    mesh.uv_layers.new(name="UVMap")
    for attribute, grey in attributes:
        greys = mesh.color_attributes.new(attribute, "FLOAT_COLOR", "CORNER")
        assert isinstance(greys, bpy.types.FloatColorAttribute)
        greys.data.foreach_set("color", [grey] * 4 * len(mesh.loops))
    images = {
        texture: face_materials.texture_image(texture, [0] + [0x804020] * (TEXTURE_SIZE * TEXTURE_SIZE - 1), opaque)
        for texture, opaque in textures.items()
    }
    made: dict[tuple[int | None, int | None, int] | None, bpy.types.Material] = {}
    for face, values in zip(mesh.polygons, faces, strict=True):
        if values not in made:
            made[values] = (
                bpy.data.materials.new(f"{name} ground")
                if values is None
                else face_materials.face_material(*values, find_texture=images.get)
            )
            mesh.materials.append(made[values])
        face.material_index = list(made).index(values)
    obj = bpy.data.objects.new(name, mesh)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(obj)
    obj.select_set(True)
    return obj


def test_a_textured_face_draws_its_texture_times_color_0_unlit(tmp_path: Path):
    # Row "Textured face" (spec decision 9, the glTF note "The lit scenery"). The texture is read one texel per pixel,
    # as model import reads it. The material must use rs_lit, or the stock exporter writes the colour attributes in
    # the order of the mesh, and fire_strength comes first.
    imported_mesh("Fire", [(None, 7, 0)], (("fire_strength", 0.25), ("rs_lit", 0.5)))
    path = tmp_path / "scene.glb"
    assert export(path, extra_attributes="fire_strength") == {"FINISHED"}
    gltf, binary = read_glb(path)
    assert {value[:3] for value in colours(gltf, binary, "COLOR_0")} == {(0.5, 0.5, 0.5)}
    assert {value[:3] for value in colours(gltf, binary, "COLOR_1")} == {(0.25, 0.25, 0.25)}
    (material,) = gltf["materials"]
    assert list(material["extensions"]) == ["KHR_materials_unlit"]
    texture = gltf["textures"][material["pbrMetallicRoughness"]["baseColorTexture"]["index"]]
    assert gltf["images"][texture["source"]]["name"] == "RS_Texture_7"
    assert gltf["samplers"][texture["sampler"]]["magFilter"] == 9728  # NEAREST, glTF 2.0 section 5.26.
    (primitive,) = gltf["meshes"][0]["primitives"]
    assert {"COLOR_0", "TEXCOORD_0"} <= set(primitive["attributes"])


def test_a_mesh_with_no_rs_face_has_one_material_for_each_texture_and_face_alpha_with_no_extras(tmp_path: Path):
    # The plan decision comment of issue 140: one material for each pair of texture id and face alpha, and the faces
    # with no texture and alpha 0 share one, also a face whose material has no game values. The owner chose the names
    # in the build of issue 144 on 2026-11-17.
    imported_mesh("Fire", [(None, 5, 0), (None, 7, 0), (8741, None, 100), (8741, None, 0), (960, None, 0), None])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(m["name"] for m in gltf["materials"]) == ["RS_Texture_5", "RS_Texture_7", "rs_lit", "rs_lit_100"]
    assert not any("extras" in m for m in gltf["materials"])
    assert all(list(m["extensions"]) == ["KHR_materials_unlit"] for m in gltf["materials"])


def test_a_face_alpha_on_a_mesh_with_no_rs_face_draws_blended_with_the_clients_opacity(tmp_path: Path):
    # Spec rule 8 for a mesh with no rs_face.
    imported_mesh("Fire", [(8741, None, 100), (8741, None, 0)])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    by_name = {m["name"]: m for m in gltf["materials"]}
    assert by_name["rs_lit_100"]["alphaMode"] == "BLEND"
    assert by_name["rs_lit_100"]["pbrMetallicRoughness"]["baseColorFactor"][3] == pytest.approx(156 / 256)
    assert "alphaMode" not in by_name["rs_lit"]


def test_a_textured_face_ignores_its_face_alpha_as_the_client_does(tmp_path: Path):
    # The client reads the face alpha only for a face with no texture (`Graphics3D.java` lines 794 to 859 and 1348 to
    # 1372 of the 2018 client, as region_scenery.show_loc_light cites). The owner chose in the build of issue 144 on
    # 2026-11-17 that the export does the same.
    imported_mesh("Fire", [(None, 7, 0), (None, 7, 100)])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (material,) = gltf["materials"]
    assert "alphaMode" not in material
    assert "baseColorFactor" not in material["pbrMetallicRoughness"]


def test_the_texels_that_the_client_does_not_draw_are_masked(tmp_path: Path):
    # face_materials.texture_image gives such a texel the alpha 0. The owner chose in the build of issue 144 on
    # 2026-11-17 that the page leaves them out with alphaMode MASK.
    imported_mesh("Fire", [(None, 5, 0)])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (material,) = gltf["materials"]
    assert material["alphaMode"] == "MASK"
    assert material.get("alphaCutoff", 0.5) == 0.5


def test_a_textured_face_with_no_image_draws_magenta_times_color_0(tmp_path: Path):
    # The owner chose in the build of issue 144 on 2026-11-17 that the file draws it as region_scenery.show_loc_light
    # draws it in Blender.
    imported_mesh("Fire", [(None, 9, 0)])
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (material,) = gltf["materials"]
    assert material["name"] == "RS_Texture_9"
    assert material["pbrMetallicRoughness"]["baseColorFactor"] == [1.0, 0.0, 1.0, 1.0]
    assert "baseColorTexture" not in material["pbrMetallicRoughness"]
    (primitive,) = gltf["meshes"][0]["primitives"]
    assert "COLOR_0" in primitive["attributes"]


def test_the_export_of_textured_faces_leaves_the_scene_unchanged(tmp_path: Path):
    # Row "Scene unchanged".
    imported_mesh("Fire", [(None, 5, 0), (None, 9, 0), (8741, None, 100), None])
    before = scene_state()
    images = sorted(image.name for image in bpy.data.images)
    export(tmp_path / "scene.glb")
    assert scene_state() == before
    assert sorted(image.name for image in bpy.data.images) == images


def rigged_player(cache: Path) -> bpy.types.Object:
    """The rig of a player from Create Player's build, selected with the player's meshes."""
    obj, _ = player(cache)
    collection = obj.users_collection[0]
    rig = appearance_collection.armature_of(collection)
    rig.select_set(True)
    return rig


# The keyed joints of the test motions, as rotations of the joints from their rest frames.
SITTING = {
    "thigh.L": Quaternion((1, 0, 0), math.radians(-80)),
    "thigh.R": Quaternion((1, 0, 0), math.radians(-85)),
    "shin.L": Quaternion((1, 0, 0), math.radians(75)),
    "spine": Quaternion((0, 1, 0), math.radians(10)),
}
WAVE = {
    1: {"upper_arm.R": Quaternion((0, 0, 1), math.radians(120))},
    5: {"upper_arm.R": Quaternion((0, 0, 1), math.radians(140))},
    9: {"upper_arm.R": Quaternion((0, 0, 1), math.radians(120))},
}


def hand_keyed(
    rig: bpy.types.Object,
    name: str,
    keys: dict[int, dict[str, Quaternion]],
    start: int,
    interpolation: str,
    track_name: str = appearance_clip.USER_TRACK,
) -> bpy.types.Action:
    """An action of rotation keys on the joints, made as the hand-made motion runbook makes one, on a strip on the
    track `track_name`. The first key of `keys` is on frame 1, and the action and its strip start on frame `start`."""
    action = bpy.data.actions.new(name)
    slot = action.slots.new(id_type="OBJECT", name=rig.name)
    keyframes = action.layers.new("Layer").strips.new(type="KEYFRAME")
    assert isinstance(keyframes, bpy.types.ActionKeyframeStrip)
    bag = keyframes.channelbag(slot, ensure=True)
    for frame, rotations in keys.items():
        for joint, rotation in rotations.items():
            path = f'pose.bones["{joint}"].rotation_quaternion'
            for index in range(4):
                curve = bag.fcurves.find(path, index=index) or bag.fcurves.new(path, index=index, group_name=joint)
                point = curve.keyframe_points.insert(frame + start - 1, rotation[index], options={"FAST"})
                point.interpolation = interpolation
    animation = rig.animation_data or rig.animation_data_create()
    track = animation.nla_tracks.get(track_name)
    if track is None:
        track = animation.nla_tracks.new()
        track.name = track_name
    strip = track.strips.new(name, start, action)
    strip.action_slot = slot
    return action


def held_pose(rig: bpy.types.Object, start: int = 1) -> bpy.types.Action:
    """The sitting pose, held from frame `start` for 20 frames: each joint has the same key on both frames."""
    return hand_keyed(rig, "Sitting", {1: SITTING, 21: SITTING}, start, "CONSTANT")


def npc_with_clip(tmp_path: Path, monkeypatch) -> bpy.types.Object:
    """The rig of the gnome (NPC 4233) with its stand clip (sequence 195) baked by Bake NPC Clip, selected with its
    mesh. The test cache has no sequences or frames, so the frame map of the rig is read from the clip folder."""
    folder = tmp_path / "npc cache"
    build_cache(folder, npcs=raw_files(NPC_FIXTURES), models=raw_files(NPC_FIXTURES / "models"))
    stand = NPC_FIXTURES / "clips" / "195"
    frame_map = decode_frame_map((stand / "maps" / "319.dat").read_bytes())
    monkeypatch.setattr(npc_collection, "stand_frame_map", lambda store, npc: (319, frame_map))
    collection = npc_collection.create_npc(4233, folder, DEFAULT_BRIGHTNESS)
    appearance_clip.bake_npc_clip(collection, stand)
    for obj in collection.objects:
        obj.select_set(True)
    return appearance_collection.armature_of(collection)


def strip_actions(rig: bpy.types.Object) -> list[str]:
    animation = rig.animation_data
    assert animation is not None
    return [strip.action.name for track in animation.nla_tracks for strip in track.strips if strip.action is not None]


def moves(gltf: dict, binary: bytes, sampler: dict) -> bool:
    values = accessor_values(gltf, binary, sampler["output"])
    return any(not all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(value, values[0])) for value in values)


def test_each_action_of_a_player_and_an_npc_rig_is_one_animation_with_the_actions_name(
    cache: Path, tmp_path: Path, monkeypatch
):
    # Row "Clips" (spec decision 6). The held pose and the wave are on one track, as the hand-made motion runbook puts
    # them, and the NPC's baked clip is on the RS clips track.
    rig = rigged_player(cache)
    held_pose(rig)
    hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    npc = npc_with_clip(tmp_path, monkeypatch)
    path = tmp_path / "scene.glb"
    assert export(path) == {"FINISHED"}
    gltf, _ = read_glb(path)
    assert sorted(animation["name"] for animation in gltf["animations"]) == sorted(
        ["Sitting", "Wave", *strip_actions(npc)]
    )
    # The clips move the joints of the rigs, and each mesh is skinned to the joints of its rig.
    assert [("skin" in node) for node in gltf["nodes"] if "mesh" in node] == [True, True]


def test_the_active_action_of_a_rig_is_one_animation_too(cache: Path, tmp_path: Path):
    # Row "Clips" (spec decision 6): the rig's active action and the actions of its strips.
    rig = rigged_player(cache)
    held_pose(rig)
    wave = hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    animation = rig.animation_data
    assert animation is not None
    track = animation.nla_tracks[appearance_clip.USER_TRACK]
    track.strips.remove(track.strips[-1])
    animation.action = wave
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(animation["name"] for animation in gltf["animations"]) == ["Sitting", "Wave"]


def test_an_action_that_no_selected_rig_plays_is_not_exported(cache: Path, tmp_path: Path):
    # Spec rule 10: the clips are the actions of the selected rigs, not every action of the file.
    rig = rigged_player(cache)
    held_pose(rig)
    other = hand_keyed(rig, "Elsewhere", WAVE, 30, "CONSTANT")
    animation = rig.animation_data
    assert animation is not None
    track = animation.nla_tracks[appearance_clip.USER_TRACK]
    track.strips.remove(track.strips[-1])
    other.use_fake_user = True
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert [animation["name"] for animation in gltf["animations"]] == ["Sitting"]


@pytest.mark.parametrize("interpolation", ["CONSTANT", "BEZIER"])
def test_every_channel_that_moves_is_step(cache: Path, tmp_path: Path, monkeypatch, interpolation: str):
    # Row "STEP" (issue 120, spec decision 10): the client shows one frame on each tick and does not blend between
    # frames. The hand-made motion runbook keys constant keys, and a key that the user adds by hand is a Bezier key.
    rig = rigged_player(cache)
    held_pose(rig)
    hand_keyed(rig, "Wave", WAVE, 30, interpolation)
    npc = npc_with_clip(tmp_path, monkeypatch)
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    moving = [
        (animation["name"], sampler["interpolation"])
        for animation in gltf["animations"]
        for sampler in animation["samplers"]
        if moves(gltf, binary, sampler)
    ]
    assert {name for name, _ in moving} == {"Wave", *strip_actions(npc)}
    assert [m for m in moving if m[1] != "STEP"] == []


def test_the_held_pose_has_a_channel_for_each_keyed_joint_with_the_keyed_value(cache: Path, tmp_path: Path):
    # Row "Held pose": no channel of the sitting pose moves, and the page still needs each keyed joint. A glTF joint
    # has no rest pose of its own, so its value is the rest rotation of its node turned by the keyed rotation.
    rig = rigged_player(cache)
    held_pose(rig)
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    (sitting,) = gltf["animations"]
    rotations = {}
    for channel in sitting["channels"]:
        if channel["target"]["path"] == "rotation":
            node = gltf["nodes"][channel["target"]["node"]]
            values = accessor_values(gltf, binary, sitting["samplers"][channel["sampler"]]["output"])
            rotations[node["name"]] = (node.get("rotation", [0, 0, 0, 1]), values)
    assert set(SITTING) <= set(rotations)
    for joint, keyed in SITTING.items():
        rest, values = rotations[joint]
        x, y, z, w = rest
        expected = Quaternion((w, x, y, z)) @ keyed
        for x, y, z, w in values:
            assert Quaternion((w, x, y, z)).rotation_difference(expected).angle == pytest.approx(0, abs=1e-4)


def test_no_animation_has_interleave_extras(cache: Path, tmp_path: Path, monkeypatch):
    # Row "No interleave" (spec decision 1): the first version writes no interleave list.
    rig = rigged_player(cache)
    held_pose(rig)
    npc_with_clip(tmp_path, monkeypatch)
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert gltf["animations"]
    assert ["interleave" in json.dumps(animation.get("extras", {})) for animation in gltf["animations"]] == [
        False
    ] * len(gltf["animations"])


def test_the_export_of_rigs_leaves_their_actions_tracks_and_active_actions_unchanged(
    cache: Path, tmp_path: Path, monkeypatch
):
    # Spec Boundaries "Always": the scene keeps its actions, NLA tracks and active actions.
    rig = rigged_player(cache)
    held_pose(rig)
    wave = hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    animation = rig.animation_data
    assert animation is not None
    animation.action = wave
    npc_with_clip(tmp_path, monkeypatch)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = rig
    before = scene_state()
    export(tmp_path / "scene.glb")
    assert scene_state() == before


def test_each_clip_starts_at_0_seconds(cache: Path, tmp_path: Path):
    # The owner chose in the build of issue 145 on 2026-11-17 that each clip starts at 0 seconds, so that the page plays
    # the wave at once. The wave starts on frame 30.
    rig = rigged_player(cache)
    hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (wave,) = gltf["animations"]
    assert {gltf["accessors"][sampler["input"]]["min"][0] for sampler in wave["samplers"]} == {0}


def test_a_muted_strip_and_a_strip_on_a_muted_track_are_clips_too(cache: Path, tmp_path: Path):
    # The owner chose in the build of issue 145 on 2026-11-17 that each action on a strip becomes a clip, also when the
    # strip or its track is muted (spec decision 6).
    rig = rigged_player(cache)
    held_pose(rig)
    hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    animation = rig.animation_data
    assert animation is not None
    animation.nla_tracks[appearance_clip.USER_TRACK].strips[1].mute = True
    hand_keyed(rig, "Nod", WAVE, 60, "CONSTANT", "Muted")
    animation.nla_tracks["Muted"].mute = True
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(animation["name"] for animation in gltf["animations"]) == ["Nod", "Sitting", "Wave"]


def test_a_rig_with_no_mesh_stops_the_export(cache: Path, tmp_path: Path):
    # The owner chose in the build of issue 145 on 2026-11-17 that a selection with a rig and no mesh stops the export,
    # because the page has nothing to draw.
    rig = rigged_player(cache)
    for obj in bpy.context.selected_objects or []:
        obj.select_set(obj == rig)
    path = tmp_path / "scene.glb"
    with pytest.raises(RuntimeError, match="Select the meshes to export."):
        export(path)
    assert not path.exists()


def test_the_message_names_the_meshes_and_the_rigs(cache: Path, tmp_path: Path, capfd):
    # The owner chose the wording in the build of issue 145 on 2026-11-17.
    rigged_player(cache)
    path = tmp_path / "scene.glb"
    capfd.readouterr()
    export(path)
    assert f"Info: Exported 1 mesh and 1 rig to {path}." in capfd.readouterr().out.splitlines()


def test_a_clip_has_no_extras_and_the_action_keeps_its_custom_properties(cache: Path, tmp_path: Path, monkeypatch):
    # The owner chose in the build of issue 145 on 2026-11-17 that the clips have no extras, because the clip record of
    # a baked clip holds the local path of its cache, and the page is public.
    rig = rigged_player(cache)
    held_pose(rig)["rs_note"] = 7
    npc = npc_with_clip(tmp_path, monkeypatch)
    records = {name: bpy.data.actions[name].get(appearance_collection.CLIP_KEY) for name in strip_actions(npc)}
    assert all(records.values())
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(animation["name"] for animation in gltf["animations"]) == sorted(["Sitting", *strip_actions(npc)])
    assert [animation.get("extras") for animation in gltf["animations"]] == [None] * len(gltf["animations"])
    assert bpy.data.actions["Sitting"]["rs_note"] == 7
    assert {name: bpy.data.actions[name].get(appearance_collection.CLIP_KEY) for name in records} == records


def test_the_active_action_held_aside_in_tweak_mode_is_a_clip_too(cache: Path, tmp_path: Path):
    # Row "Clips" (spec decision 6): in tweak mode Blender holds the rig's active action aside.
    rig = rigged_player(cache)
    held_pose(rig)
    wave = hand_keyed(rig, "Wave", WAVE, 30, "CONSTANT")
    animation = rig.animation_data
    assert animation is not None
    track = animation.nla_tracks[appearance_clip.USER_TRACK]
    track.strips.remove(track.strips[-1])
    animation.action = wave
    for other in animation.nla_tracks:
        other.select = other == track
    track.strips[0].select = True
    animation.use_tweak_mode = True
    assert animation.action_tweak_storage == wave
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert sorted(animation["name"] for animation in gltf["animations"]) == ["Sitting", "Wave"]
    assert animation.use_tweak_mode


def test_a_mesh_that_only_an_armature_modifier_binds_to_the_rig_is_skinned_to_the_exported_rig(
    cache: Path, tmp_path: Path
):
    # Spec rule 10: the clips move the meshes of the rig. A mesh that the user unparents, and that the rig still moves
    # through its Armature modifier, is skinned to the joints of the exported rig.
    rig = rigged_player(cache)
    held_pose(rig)
    mesh = appearance_collection.mesh_of(rig.users_collection[0])
    world = mesh.matrix_world.copy()
    mesh.parent = None
    mesh.matrix_world = world
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (node,) = [node for node in gltf["nodes"] if "mesh" in node]
    joints = {gltf["nodes"][joint]["name"] for joint in gltf["skins"][node["skin"]]["joints"]}
    assert set(SITTING) <= joints


def test_a_clip_has_the_keys_of_the_slot_that_the_rig_plays(cache: Path, tmp_path: Path):
    # Row "Held pose" (spec rule 10): the clip has the keyed values of the rig's slot, also when the action has a slot
    # for another object before it.
    rig = rigged_player(cache)
    sitting = held_pose(rig)
    decoy = sitting.slots.new(id_type="OBJECT", name="Decoy")
    strip = sitting.layers[0].strips[0]
    assert isinstance(strip, bpy.types.ActionKeyframeStrip)
    bag = strip.channelbag(decoy, ensure=True)
    for joint in SITTING:
        path = f'pose.bones["{joint}"].rotation_quaternion'
        for index, value in enumerate(Quaternion((0, 0, 1), math.radians(90))):
            bag.fcurves.new(path, index=index).keyframe_points.insert(1, value)
    sitting.slots.active = decoy
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    (clip,) = gltf["animations"]
    for channel in clip["channels"]:
        node = gltf["nodes"][channel["target"]["node"]]
        if channel["target"]["path"] == "rotation" and node["name"] in SITTING:
            x, y, z, w = node.get("rotation", [0, 0, 0, 1])
            expected = Quaternion((w, x, y, z)) @ SITTING[node["name"]]
            for x, y, z, w in accessor_values(gltf, binary, clip["samplers"][channel["sampler"]]["output"]):
                assert Quaternion((w, x, y, z)).rotation_difference(expected).angle == pytest.approx(0, abs=1e-4)


def test_an_action_that_a_rig_plays_with_two_slots_is_one_clip_with_the_slot_that_it_plays_first(
    cache: Path, tmp_path: Path
):
    # The owner chose in the review of issue 145 on 2026-11-17 that such an action is one clip (spec decision 6) with
    # the slot of the active action, which comes before the slots of the strips.
    rig = rigged_player(cache)
    sitting = held_pose(rig)
    other = sitting.slots.new(id_type="OBJECT", name="Other")
    strip = sitting.layers[0].strips[0]
    assert isinstance(strip, bpy.types.ActionKeyframeStrip)
    bag = strip.channelbag(other, ensure=True)
    turned = Quaternion((0, 0, 1), math.radians(90))
    for joint in SITTING:
        path = f'pose.bones["{joint}"].rotation_quaternion'
        for index, value in enumerate(turned):
            bag.fcurves.new(path, index=index).keyframe_points.insert(1, value)
    animation = rig.animation_data
    assert animation is not None
    animation.action = sitting
    animation.action_slot = other
    path = tmp_path / "scene.glb"
    export(path)
    gltf, binary = read_glb(path)
    (clip,) = gltf["animations"]
    checked = set()
    for channel in clip["channels"]:
        node = gltf["nodes"][channel["target"]["node"]]
        if channel["target"]["path"] == "rotation" and node["name"] in SITTING:
            x, y, z, w = node.get("rotation", [0, 0, 0, 1])
            expected = Quaternion((w, x, y, z)) @ turned
            for x, y, z, w in accessor_values(gltf, binary, clip["samplers"][channel["sampler"]]["output"]):
                assert Quaternion((w, x, y, z)).rotation_difference(expected).angle == pytest.approx(0, abs=1e-4)
            checked.add(node["name"])
    assert checked == set(SITTING)


def test_one_texture_id_is_one_material_and_one_image_also_with_two_images_or_none(tmp_path: Path):
    # The owner chose in the build of issue 144 on 2026-11-17 that a texture id is one material, with the first image
    # found for it, also for a material that has no image. The images of two regions hold the same texels.
    imported_mesh("Lumbridge", [(None, 7, 0)])
    imported_mesh("Draynor", [(None, 7, 0)])
    imported_mesh("Missing", [(None, 7, 0)], textures={})
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    (material,) = gltf["materials"]
    assert material["name"] == "RS_Texture_7"
    assert "baseColorTexture" in material["pbrMetallicRoughness"]
    assert len(gltf["images"]) == 1


def test_a_textured_material_with_two_images_draws_the_first_image_node(tmp_path: Path):
    # The owner chose in the build of issue 144 on 2026-11-17 that the first Image Texture node of the node list wins.
    obj = imported_mesh("Fire", [(None, 7, 0)])
    material = obj.material_slots[0].material
    assert material is not None and material.node_tree is not None
    nodes = material.node_tree.nodes
    for node in [node for node in nodes if node.type == "TEX_IMAGE"]:
        nodes.remove(node)
    images = [bpy.data.images.new(name, 2, 2) for name in ("first", "second")]
    for image in images:
        texels = nodes.new("ShaderNodeTexImage")
        assert isinstance(texels, bpy.types.ShaderNodeTexImage)
        texels.image = image
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert [image["name"] for image in gltf["images"]] == [images[0].name]


def test_a_face_past_the_last_material_slot_draws_with_the_last_slot(tmp_path: Path):
    # Blender draws such a face with the last slot. The owner chose in the build of issue 144 on 2026-11-17 that the
    # export does the same.
    obj = imported_mesh("Fire", [(None, 7, 0), (8741, None, 100)])
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh.polygons[0].material_index = 9
    path = tmp_path / "scene.glb"
    export(path)
    gltf, _ = read_glb(path)
    assert [m["name"] for m in gltf["materials"]] == ["rs_lit_100"]
