import json
from dataclasses import replace
from pathlib import Path

import bmesh
import bpy
import pytest
from mathutils import Vector

from rsps_toolkit.blender import animation, export_model, texture_triangles
from rsps_toolkit.blender.face_materials import face_material
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, decode

FIXTURES = Path(__file__).parent.parent / "fixtures"
MODELS = FIXTURES / "models"
WORN = sorted((MODELS / "worn").glob("*.dat"))


@pytest.fixture(autouse=True)
def operator_registered(tmp_path: Path):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for cls in export_model.classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.exporter_output_dir = bpy.props.StringProperty(subtype="DIR_PATH")
    scene = bpy.context.scene
    assert scene is not None
    # The stubs do not know properties that add-ons register on Scene.
    scene.exporter_output_dir = str(tmp_path)  # pyrefly: ignore[missing-attribute]
    yield
    for cls in reversed(export_model.classes):
        bpy.utils.unregister_class(cls)


def run_export(obj: bpy.types.Object, preset: str) -> set[str]:
    for other in bpy.data.objects:
        other.select_set(other == obj)
    # The stubs only list Blender's own operators.
    return bpy.ops.export.rsps_model(export_preset=preset, auto_detect=True)  # pyrefly: ignore[missing-attribute]


def written(tmp_path: Path, name: str) -> Model:
    return decode((tmp_path / name).read_bytes())


def imported(dat: Path) -> tuple[Model, bpy.types.Object]:
    model = decode(dat.read_bytes())
    return model, model_to_object(model, dat.stem)


@pytest.mark.parametrize("dat", WORN, ids=lambda p: p.stem)
@pytest.mark.timeout(10, method="thread")
def test_weight_based_export_matches_the_original_exporter(dat: Path, tmp_path: Path):
    # tests/fixtures/drops and presets record what the original exporter wrote for these models.
    drop = json.loads((FIXTURES / "drops" / f"{dat.stem}.json").read_text())
    preset = drop["preset"]
    expected = json.loads((FIXTURES / "presets" / f"{dat.stem}.json").read_text())[preset]
    model, obj = imported(dat)

    assert run_export(obj, "DEFAULT") == {"FINISHED"}

    normal = written(tmp_path, f"{dat.stem}.dat")
    assert normal.vertices == model.vertices
    assert normal.render_priorities == expected["render_priorities"]
    assert normal.face_skins == expected["face_skins"]
    assert normal.vertex_skins == model.vertex_skins
    dropped = written(tmp_path, f"{dat.stem}_drop.dat")
    # The original exporter truncated rotated positions towards zero, where export now rounds.
    for got, want in zip(dropped.vertices, drop["vertices"], strict=True):
        assert all(abs(g - w) <= 1 for g, w in zip(got, want, strict=True)), (got, want)
    assert dropped.render_priorities == drop["render_priorities"]
    assert dropped.face_skins == drop["face_skins"]
    assert dropped.vertex_skins == drop["vertex_skins"]


def test_weight_based_export_of_an_unknown_type_writes_one_model_at_priority_1(tmp_path: Path):
    # The original exporter's DEFAULT preset gives every face priority 1 and writes no drop model.
    model, obj = imported(MODELS / "osrs" / "5412.dat")

    assert run_export(obj, "DEFAULT") == {"FINISHED"}

    assert sorted(p.name for p in tmp_path.iterdir()) == ["5412.dat"]
    assert written(tmp_path, "5412.dat").render_priorities == [1] * len(model.faces)


@pytest.mark.parametrize("name", ["49", "5409", "147"])
@pytest.mark.timeout(10, method="thread")
def test_custom_colour_export_writes_the_model_as_imported(name: str, tmp_path: Path):
    # 49 and 5409 mix opaque and see-through faces, which the original exporter wrongly wrote as alpha 255.
    model, obj = imported(MODELS / "osrs" / f"{name}.dat")

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert written(tmp_path, f"{name}.dat") == model


def test_output_folder_starting_with_a_tilde_means_the_home_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # A leading ~ names the home folder in the shell and in Python's os.path.expanduser, and users type paths that way.
    monkeypatch.setenv("HOME", str(tmp_path))
    bpy.context.scene.exporter_output_dir = "~/exports"  # pyrefly: ignore[missing-attribute]
    model, obj = imported(MODELS / "osrs" / "147.dat")

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert written(tmp_path / "exports", "147.dat") == model


def test_export_applies_the_object_transform(tmp_path: Path):
    model, obj = imported(MODELS / "osrs" / "5412.dat")
    obj.location = (10.0, 0.0, 20.0)

    run_export(obj, "CUSTOM_PRIORITY")

    # Blender (x, y, z) is game (x, -z, y), as model_to_object maps it.
    moved = [(x + 10, y - 20, z) for x, y, z in model.vertices]
    assert written(tmp_path, "5412.dat").vertices == moved


def test_export_applies_modifiers_and_splits_quads(tmp_path: Path):
    mesh = bpy.data.meshes.new("quad")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(face_material(1000, None, 0))
    obj = bpy.data.objects.new("quad", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    obj.modifiers.new("mirror", "MIRROR")

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    result = written(tmp_path, "quad.dat")
    # The mirror modifier merges the two vertices on the mirror plane, so 4 + 4 - 2 remain.
    assert len(result.faces) == 4
    assert len(result.vertices) == 6
    assert result.face_colours == [1000] * 4


def test_a_dented_face_exports_as_triangles_that_cover_it_once(tmp_path: Path):
    # The user chose that export splits a face with more than 3 corners into triangles that all face its way and cover
    # it exactly once, and that the triangles' areas adding up to the face's area is the check (issue 05, decision 1,
    # 2026-11-10). The second corner is the dent, where the old split cut off a triangle outside the face.
    corners = [(0, 0), (10, 6), (20, 0), (20, 20), (0, 20)]
    mesh = bpy.data.meshes.new("dent")
    mesh.from_pydata([(x, y, 0) for x, y in corners], [], [tuple(range(len(corners)))])
    mesh.materials.append(face_material(1000, None, 0))
    obj = bpy.data.objects.new("dent", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    result = written(tmp_path, "dent.dat")
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(corners, corners[1:] + corners[:1])) / 2
    normals = []
    for a, b, c in result.faces:
        first, second, third = (Vector(result.vertices[i]) for i in (a, b, c))
        normals.append((second - first).cross(third - first))
    assert len(normals) == len(corners) - 2
    assert all(normal.dot(normals[0]) > 0 for normal in normals)  # pyrefly: ignore[missing-attribute]
    assert sum(normal.length for normal in normals) / 2 == pytest.approx(area)  # pyrefly: ignore[missing-attribute]


def test_a_face_with_no_clean_corner_to_cut_exports_with_a_warning(tmp_path: Path, capfd: pytest.CaptureFixture):
    # The user chose that a face with no corner whose triangle lies inside it still exports, split in corner order, and
    # that export warns how many cuts may overlap (issue 05, decision 3, 2026-11-10). Corners on one line have no area,
    # so no corner is clean, and a quad needs one cut.
    mesh = bpy.data.meshes.new("line")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(face_material(1000, None, 0))
    obj = bpy.data.objects.new("line", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)
    capfd.readouterr()

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert "line: 1 cuts of faces with more than 3 corners found no corner" in capfd.readouterr().out
    assert len(written(tmp_path, "line.dat").faces) == 2


def test_material_without_game_values_cancels_with_a_message(tmp_path: Path):
    model, obj = imported(MODELS / "osrs" / "5412.dat")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh.materials[0] = bpy.data.materials.new("hand made")

    # An operator that reports an error raises RuntimeError when called from Python.
    with pytest.raises(RuntimeError, match="no RuneScape face colour"):
        run_export(obj, "CUSTOM_PRIORITY")
    assert list(tmp_path.iterdir()) == []


def test_drop_model_of_an_object_with_no_drop_transform_keeps_its_vertices(tmp_path: Path):
    # BOOTS has no drop transform in the original exporter (DROP_PARAMS), so only the skins are left out.
    model, obj = imported(MODELS / "worn" / "16010.dat")

    run_export(obj, "DEFAULT")

    dropped = written(tmp_path, "16010_drop.dat")
    assert replace(dropped, render_priorities=model.render_priorities, face_skins=None) == replace(
        model, face_skins=None, vertex_skins=None
    )


def test_mesh_without_material_slots_cancels_with_a_message(tmp_path: Path):
    mesh = bpy.data.meshes.new("plain")
    mesh.from_pydata([(0, 0, 0), (10, 0, 0), (0, 10, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("plain", mesh)
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(obj)

    with pytest.raises(RuntimeError, match="empty material slot"):
        run_export(obj, "CUSTOM_PRIORITY")
    assert list(tmp_path.iterdir()) == []


def test_mirrored_object_keeps_its_faces_facing_out(tmp_path: Path):
    model, obj = imported(MODELS / "osrs" / "5412.dat")
    obj.scale = (-1.0, 1.0, 1.0)

    run_export(obj, "CUSTOM_PRIORITY")

    result = written(tmp_path, "5412.dat")
    assert result.vertices == [(-x, y, z) for x, y, z in model.vertices]
    # Mirroring reverses which way each face winds, so the corner order must be reversed to match.
    for got, original in zip(result.faces, model.faces, strict=True):
        a, b, c = original
        assert got in [(a, c, b), (c, b, a), (b, a, c)], (got, original)


def test_modifier_that_changes_vertices_under_texture_triangles_cancels(tmp_path: Path):
    model, obj = imported(MODELS / "osrs" / "135.dat")
    obj.modifiers.new("mirror", "MIRROR")

    with pytest.raises(RuntimeError, match="texture triangles"):
        run_export(obj, "CUSTOM_PRIORITY")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.timeout(10, method="thread")
def test_model_with_repeated_vertex_faces_and_a_quad_exports(tmp_path: Path):
    # Model 6658 has faces that repeat a vertex, on which bmesh.ops.triangulate never returns.
    model, obj = imported(MODELS / "worn" / "6658.dat")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    corners = [bm.verts.new((500 + x, y, 0)) for x, y in ((0, 0), (10, 0), (10, 10), (0, 10))]
    bm.faces.new(corners)
    bm.to_mesh(mesh)
    bm.free()

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert len(written(tmp_path, "6658.dat").faces) == len(model.faces) + 2


@pytest.mark.timeout(10, method="thread")
def test_modifier_that_changes_vertices_under_set_aside_faces_cancels(tmp_path: Path):
    # Model 6658's faces that repeat a vertex are kept beside the mesh and name vertices by index.
    model, obj = imported(MODELS / "worn" / "6658.dat")
    obj.modifiers.new("mirror", "MIRROR")

    with pytest.raises(RuntimeError, match="repeat a vertex"):
        run_export(obj, "CUSTOM_PRIORITY")
    assert list(tmp_path.iterdir()) == []


def test_modifier_on_a_model_without_texture_triangles_or_set_aside_faces_exports(tmp_path: Path):
    model, obj = imported(MODELS / "osrs" / "5412.dat")
    obj.modifiers.new("mirror", "MIRROR")

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert len(written(tmp_path, "5412.dat").faces) > len(model.faces)


@pytest.mark.timeout(10, method="thread")
def test_faces_kept_beside_the_mesh_are_left_out_once_their_vertices_are_renumbered(tmp_path: Path):
    # Deleting a vertex in Blender renumbers every later vertex, so the stored faces would name other vertices.
    model, obj = imported(MODELS / "worn" / "6658.dat")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bm.to_mesh(mesh)
    bm.free()

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    result = written(tmp_path, "6658.dat")
    original = {tuple(model.vertices[i] for i in face) for face in model.faces}
    assert all(tuple(result.vertices[i] for i in face) in original for face in result.faces)


@pytest.mark.timeout(10, method="thread")
def test_mirrored_export_reverses_the_faces_kept_beside_the_mesh_too(tmp_path: Path):
    model, obj = imported(MODELS / "worn" / "6658.dat")
    obj.scale = (-1.0, 1.0, 1.0)

    run_export(obj, "CUSTOM_PRIORITY")

    result = written(tmp_path, "6658.dat")
    for got, original in zip(result.faces, model.faces, strict=True):
        a, b, c = original
        if len({a, b, c}) < 3:
            # Any rotation of a reversed (a, a, b) includes (a, a, b) itself, so these are checked exactly.
            assert got == (c, b, a), (got, original)
        else:
            assert got in [(a, c, b), (c, b, a), (b, a, c)], (got, original)


def test_texture_triangles_no_face_uses_are_left_out(tmp_path: Path):
    # None of the 27,612 Old School models has such a triangle, so leaving them out never changes an imported model.
    model, obj = imported(MODELS / "osrs" / "147.dat")
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh["rs_texture_triangles"] = [0, 1, 2, *mesh["rs_texture_triangles"]]
    attribute = mesh.attributes["rs_face_texture_triangle"]
    assert isinstance(attribute, bpy.types.IntAttribute)
    values = [0] * len(mesh.polygons)
    attribute.data.foreach_get("value", values)
    attribute.data.foreach_set("value", [v + 1 if v else 0 for v in values])

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert written(tmp_path, "147.dat") == model


def model_with_a_texture_triangle() -> bpy.types.Object:
    return model_to_object(
        Model(
            vertices=[(0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0), (20, 0, 10), (30, 0, 10)],
            faces=[(0, 1, 2), (2, 3, 4)],
            face_colours=[100, None],
            face_textures=[None, 1],
            render_priorities=[0, 0],
            face_alphas=[0, 0],
            texture_triangles=[(2, 3, 4)],
            face_texture_triangles=[None, 0],
            flat_shaded=[False, False],
        ),
        "triangle",
    )


MOVED_WARNING = "1 texture triangles are no longer where they were"


def test_export_warns_about_a_texture_triangle_a_deleted_vertex_moved(tmp_path: Path, capfd: pytest.CaptureFixture):
    # The user chose a warning over keeping the triangle right (ADR 0009), so the file is
    # still written.
    obj = model_with_a_texture_triangle()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bm.to_mesh(mesh)
    bm.free()

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert MOVED_WARNING in capfd.readouterr().out
    assert (tmp_path / "triangle.dat").exists()


def test_export_says_nothing_about_texture_triangles_of_an_unedited_model(capfd: pytest.CaptureFixture):
    obj = model_with_a_texture_triangle()

    assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}

    assert "texture triangles" not in capfd.readouterr().out


def test_export_includes_a_vertex_deleted_in_edit_mode(tmp_path: Path, capfd: pytest.CaptureFixture):
    # The user chose to include current Edit Mode edits (ADR 0010).
    obj = model_with_a_texture_triangle()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bmesh.update_edit_mesh(mesh)

    try:
        assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}
        assert obj.mode == "EDIT"
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    assert MOVED_WARNING in capfd.readouterr().out
    assert len(written(tmp_path, "triangle.dat").vertices) == 5


def test_export_includes_a_vertex_moved_in_edit_mode(tmp_path: Path):
    obj = model_with_a_texture_triangle()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.verts[3].co.x = 35
    bmesh.update_edit_mesh(mesh)

    try:
        assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    assert written(tmp_path, "triangle.dat").vertices[3] == (35, 0, 0)


def test_export_after_fitting_in_edit_mode_uses_the_current_face_indices(tmp_path: Path, capfd: pytest.CaptureFixture):
    obj = model_with_a_texture_triangle()
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context="VERTS")
    bm.faces.ensure_lookup_table()
    texture_triangles.fit(mesh, bm, [bm.faces[0]])
    bmesh.update_edit_mesh(mesh)

    try:
        assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    assert MOVED_WARNING not in capfd.readouterr().out
    assert written(tmp_path, "triangle.dat") == object_to_model(obj)


@pytest.mark.parametrize("dat", WORN, ids=lambda p: p.stem)
@pytest.mark.timeout(10, method="thread")
def test_edit_mode_exports_match_leaving_edit_mode_including_drop_models(dat: Path, tmp_path: Path):
    _, obj = imported(dat)
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    for vertex in bm.verts:
        vertex.co.x += 5
    bmesh.update_edit_mesh(mesh)

    try:
        assert run_export(obj, "DEFAULT") == {"FINISHED"}
        in_edit_mode = {path.name: path.read_bytes() for path in tmp_path.glob("*.dat")}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    assert run_export(obj, "DEFAULT") == {"FINISHED"}
    assert {path.name: path.read_bytes() for path in tmp_path.glob("*.dat")} == in_edit_mode


def test_export_includes_edits_to_each_object_in_multi_object_edit_mode(tmp_path: Path):
    first = model_with_a_texture_triangle()
    second = model_with_a_texture_triangle()
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    for obj in bpy.data.objects:
        obj.select_set(obj in (first, second))
    view_layer.objects.active = first
    bpy.ops.object.mode_set(mode="EDIT")
    for obj in (first, second):
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.verts[3].co.x = 35
        bmesh.update_edit_mesh(mesh)

    try:
        assert bpy.ops.export.rsps_model(export_preset="CUSTOM_PRIORITY") == {"FINISHED"}  # pyrefly: ignore[missing-attribute]
        assert first.mode == second.mode == "EDIT"
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    assert written(tmp_path, f"{first.name}.dat").vertices[3] == (35, 0, 0)
    assert written(tmp_path, f"{second.name}.dat").vertices[3] == (35, 0, 0)


@pytest.mark.parametrize("mode", ["OBJECT", "EDIT"])
def test_export_after_undoing_a_move_and_fit(mode: str, tmp_path: Path, capfd: pytest.CaptureFixture):
    # The user accepted a visible notice for Edit Mode Undo until texture triangle storage is repaired (ADR 0009).
    # Object Mode Undo restores the records with the mesh.
    obj = model_with_a_texture_triangle()
    name = obj.name
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    view_layer = bpy.context.view_layer
    assert view_layer is not None
    view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode=mode)
    bpy.ops.ed.undo_push(message="Imported")
    bm = bmesh.from_edit_mesh(mesh) if mode == "EDIT" else bmesh.new()
    if mode == "OBJECT":
        bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.verts[3].co.x += 5
    if mode == "EDIT":
        bmesh.update_edit_mesh(mesh)
    else:
        bm.to_mesh(mesh)
        bm.free()
    bpy.ops.ed.undo_push(message="Moved")
    bm = bmesh.from_edit_mesh(mesh) if mode == "EDIT" else bmesh.new()
    if mode == "OBJECT":
        bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    texture_triangles.fit(mesh, bm, [bm.faces[1]])
    if mode == "EDIT":
        bmesh.update_edit_mesh(mesh)
    else:
        bm.to_mesh(mesh)
        bm.free()
    bpy.ops.ed.undo_push(message="Fitted")
    bpy.ops.ed.undo()
    bpy.ops.ed.undo()
    obj = bpy.data.objects[name]

    try:
        assert run_export(obj, "CUSTOM_PRIORITY") == {"FINISHED"}
    finally:
        if obj.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")

    assert written(tmp_path, f"{name}.dat").vertices[3] == (30, 0, 0)
    output = capfd.readouterr().out
    assert (MOVED_WARNING in output) == (mode == "EDIT")


@pytest.mark.parametrize("model_id", [5409, 7978], ids=["whip", "tree"])
@pytest.mark.parametrize("owner", ["object", "mesh", "both"])
@pytest.mark.parametrize("version", [1, 999])
def test_presentation_model_files_are_refused(model_id: int, owner: str, version: int):
    path = FIXTURES / f"animations/2013/raw/7/{model_id}/0.dat"
    _, obj = imported(path)
    assert isinstance(obj.data, bpy.types.Mesh)
    obj.name = f"presentation-{model_id}"
    if owner in ("object", "both"):
        obj["rs_presentation"] = {"version": version, "source_recipe": "verified-example"}
    if owner in ("mesh", "both"):
        obj.data["rs_presentation"] = {"version": version, "source_recipe": "verified-example"}
    with pytest.raises(ValueError, match="presentation-only.*source model"):
        export_model.model_files(obj, "CUSTOM_PRIORITY", False)


@pytest.mark.parametrize("linked", [False, True])
def test_presentation_duplicates_keep_export_refusal(linked: bool):
    _, source = imported(FIXTURES / "animations/2013/raw/7/5409/0.dat")
    assert isinstance(source.data, bpy.types.Mesh)
    source["rs_presentation"] = {"version": 1}
    source.data["rs_presentation"] = {"version": 1}
    duplicate = source.copy()
    if not linked:
        duplicate.data = source.data.copy()
    collection = bpy.context.collection
    assert collection is not None
    collection.objects.link(duplicate)
    del duplicate["rs_presentation"]
    with pytest.raises(ValueError, match="presentation-only"):
        export_model.model_files(duplicate, "CUSTOM_PRIORITY", False)


def test_presentation_refusal_survives_reopening(tmp_path: Path):
    _, obj = imported(FIXTURES / "animations/2013/raw/7/5409/0.dat")
    assert isinstance(obj.data, bpy.types.Mesh)
    obj.name = "saved-presentation"
    obj["rs_presentation"] = {"version": 1}
    obj.data["rs_presentation"] = {"version": 1}
    saved = tmp_path / "presentation.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(saved))
    bpy.ops.wm.open_mainfile(filepath=str(saved))
    with pytest.raises(ValueError, match="presentation-only"):
        export_model.model_files(bpy.data.objects["saved-presentation"], "CUSTOM_PRIORITY", False)


def test_mixed_selection_writes_no_files(tmp_path: Path, capfd: pytest.CaptureFixture):
    _, source = imported(MODELS / "osrs/5412.dat")
    source.name = "first-source"
    _, presentation = imported(FIXTURES / "animations/2013/raw/7/5409/0.dat")
    assert isinstance(presentation.data, bpy.types.Mesh)
    presentation.name = "second-presentation"
    presentation["rs_presentation"] = {"version": 1}
    presentation.data["rs_presentation"] = {"version": 1}
    selected = bpy.context.selected_objects
    assert selected is not None
    for obj in selected:
        obj.select_set(False)
    source.select_set(True)
    presentation.select_set(True)
    keep = tmp_path / "existing.txt"
    keep.write_text("keep")
    with pytest.raises(RuntimeError, match="presentation-only"):
        bpy.ops.export.rsps_model(export_preset="CUSTOM_PRIORITY", auto_detect=False)  # pyrefly: ignore[missing-attribute]
    assert list(tmp_path.iterdir()) == [keep]
    assert keep.read_text() == "keep"
    assert "second-presentation" in capfd.readouterr().out


def test_presentation_marker_presence_is_conservative():
    from rsps_toolkit.blender.animation import is_presentation

    _, obj = imported(MODELS / "osrs/5412.dat")
    assert isinstance(obj.data, bpy.types.Mesh)
    assert not is_presentation(obj)
    obj["rs_presentation"] = {}
    assert is_presentation(obj)
    del obj["rs_presentation"]
    obj.data["rs_presentation"] = {"version": "unknown"}
    assert is_presentation(obj)


def test_player_collection_objects_are_refused_with_the_rest_of_the_selection(tmp_path: Path):
    _, source = imported(MODELS / "osrs/5412.dat")
    _, player = imported(MODELS / "osrs/5412.dat")
    player.name = "player-mesh"
    collection = bpy.data.collections.new("Player")
    collection["rs_appearance_preset"] = "{}"
    collection.objects.link(player)
    with pytest.raises(ValueError, match="player-mesh.*player appearance"):
        export_model.model_files(player, "CUSTOM_PRIORITY", False)
    with pytest.raises(ValueError, match="player appearance"):
        animation.assert_static_exportable([source, player])
