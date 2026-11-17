"""The RS Scene export, read back from the JSON and binary chunks of the `.glb` file that it writes.

The rows named in the tests are the rows of the test table of spec 140 (`spec/140-campfire-glb-export.md`)."""

import json
import struct
from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import export_gltf

# glTF 2.0 specification, sections 3.6.2 (accessor component types) and 4.4 (binary glTF layout).
COMPONENTS = {5121: ("B", 255), 5123: ("H", 65535), 5126: ("f", 1)}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
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
        "object actions": {
            obj.name: obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None
            for obj in bpy.data.objects
        },
        "selected": sorted(obj.name for obj in bpy.data.objects if obj.select_get()),
        "active": view_layer.objects.active.name if view_layer.objects.active else None,
        "frame": scene.frame_current,
    }


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


def test_objects_that_are_not_meshes_are_left_out_with_a_warning(tmp_path: Path, capfd):
    # The owner chose in the build of issue 141 on 2026-11-17 that the export leaves out the selected objects that are
    # not meshes, and says which.
    triangle("Ground", ("rs_lit",))
    marker = bpy.data.objects.new("Marker", None)
    scene = bpy.context.scene
    assert scene is not None
    scene.collection.objects.link(marker)
    marker.select_set(True)
    path = tmp_path / "scene.glb"
    capfd.readouterr()
    export(path)
    assert "Warning: Left out Marker: only meshes are exported." in capfd.readouterr().out.splitlines()
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
