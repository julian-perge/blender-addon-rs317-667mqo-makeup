from pathlib import Path

import bmesh
import bpy
import pytest

from rsps_toolkit.blender import painter, rs_layers
from rsps_toolkit.blender.mesh import model_to_object
from rsps_toolkit.formats import decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
KINDS = [painter.PRIORITY, painter.FACE_SKIN]


@pytest.fixture(autouse=True)
def painters_registered():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    painter.register_properties()
    for cls in painter.classes:
        bpy.utils.register_class(cls)
    yield
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for cls in reversed(painter.classes):
        bpy.utils.unregister_class(cls)


def editing(dat: Path) -> bpy.types.Object:
    obj = model_to_object(decode(dat.read_bytes()), dat.stem)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    return obj


def paint(obj: bpy.types.Object, kind: painter.Kind, faces: list[int], value: int) -> set[str]:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.from_edit_mesh(mesh)
    for face in bm.faces:
        face.select = face.index in faces
    bmesh.update_edit_mesh(mesh)
    setattr(bpy.context.scene, kind.value_property, value)
    # The stubs only list Blender's own operators.
    return getattr(bpy.ops.rsps, kind.operator)()  # pyrefly: ignore[missing-attribute]


@pytest.mark.parametrize("kind", KINDS, ids=lambda k: k.layer)
@pytest.mark.timeout(10, method="thread")
def test_every_painted_value_reads_back_exactly(kind: painter.Kind):
    # Values are stored as value / 255 in an 8-bit colour channel.
    obj = editing(MODELS / "osrs" / "49.dat")
    for value in range(256):
        assert paint(obj, kind, [value], value) == {"FINISHED"}
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    values = rs_layers.read_face_values(mesh, kind.layer)
    assert values is not None
    assert values[:256] == list(range(256))


@pytest.mark.parametrize("kind", KINDS, ids=lambda k: k.layer)
def test_painting_keeps_a_single_layer(kind: painter.Kind):
    obj = editing(MODELS / "osrs" / "5412.dat")
    paint(obj, kind, [0, 1], 4)
    paint(obj, kind, [2], 9)
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    names = [layer.name for layer in mesh.vertex_colors]
    assert [n for n in names if n.startswith(kind.layer)] == [kind.layer]


def test_writing_face_values_twice_overwrites_the_layer():
    obj = model_to_object(decode((MODELS / "osrs" / "5412.dat").read_bytes()), "5412")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)

    rs_layers.write_face_values(mesh, rs_layers.PRIORITY_LAYER, [3] * len(mesh.polygons))

    assert [layer.name for layer in mesh.vertex_colors].count(rs_layers.PRIORITY_LAYER) == 1
    assert [n for n in (layer.name for layer in mesh.vertex_colors) if n.startswith("RSPRI.")] == []
    assert rs_layers.read_face_values(mesh, rs_layers.PRIORITY_LAYER) == [3] * len(mesh.polygons)


def test_overlay_groups_faces_by_painted_value():
    obj = editing(MODELS / "osrs" / "5412.dat")
    paint(obj, painter.PRIORITY, [0, 1], 4)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.from_edit_mesh(mesh)

    groups = painter.faces_by_value(bm, painter.PRIORITY)

    assert sorted(groups) == [4, 10]
    assert len(groups[4]) == 2
    assert len(groups[10]) == len(bm.faces) - 2


@pytest.mark.parametrize("kind", KINDS, ids=lambda k: k.layer)
def test_painting_a_new_layer_leaves_other_faces_at_the_unpainted_value(kind: painter.Kind):
    # Without the layer, export gives every face priority 1 (mesh.DEFAULT_PRIORITY) and no face skins.
    obj = editing(MODELS / "osrs" / "5412.dat")
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    existing = mesh.vertex_colors.get(kind.layer)
    if existing is not None:
        mesh.vertex_colors.remove(existing)
    bpy.ops.object.mode_set(mode="EDIT")

    paint(obj, kind, [0], 7)
    bpy.ops.object.mode_set(mode="OBJECT")

    assert rs_layers.read_face_values(mesh, kind.layer) == [7] + [kind.unpainted] * (len(mesh.polygons) - 1)


def test_texture_triangles_saved_in_the_old_attribute_still_read():
    # Before the attribute stored index + 1, it stored the index itself with -1 for none.
    obj = model_to_object(decode((MODELS / "osrs" / "135.dat").read_bytes()), "135")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    triangles, per_face = rs_layers.read_texture_triangles(mesh)
    mesh.attributes.remove(mesh.attributes[rs_layers.FACE_TEXTURE_TRIANGLE])
    old = mesh.attributes.new(rs_layers.OLD_FACE_TEXTURE_TRIANGLE, "INT", "FACE")
    assert isinstance(old, bpy.types.IntAttribute)
    old.data.foreach_set("value", [-1 if t is None else t for t in per_face])

    assert rs_layers.read_texture_triangles(mesh) == (triangles, per_face)
