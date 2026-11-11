"""Baked playback is checked against the matching client's poses and approved presentation choices."""

import hashlib
import json
import math
import os
import subprocess
from collections.abc import Sized
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

import bmesh
import bpy
import pytest

from rsps_toolkit.animation.bundle import Frame, FrameMap, ModelResource, PartRecipe, Recipe, load_bundle
from rsps_toolkit.animation.poses import compile_asset
from rsps_toolkit.blender.animation import binding_warning, create_playback, is_presentation
from rsps_toolkit.blender.mesh import model_to_object, object_to_model
from rsps_toolkit.formats import Model, decode, encode

FIXTURE = Path(__file__).parents[1] / "fixtures/animations/2013"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def current_scene() -> bpy.types.Scene:
    scene = bpy.context.scene
    assert scene is not None
    return scene


def current_layer() -> bpy.types.ViewLayer:
    layer = bpy.context.view_layer
    assert layer is not None
    return layer


def selected_objects() -> tuple[bpy.types.Object, ...]:
    objects = bpy.context.selected_objects
    assert objects is not None
    return tuple(objects)


def mesh_data(obj: bpy.types.Object) -> bpy.types.Mesh:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    return mesh


def object_materials(obj):
    return [material for material in mesh_data(obj).materials if material is not None]


@pytest.fixture(autouse=True)
def clean_animation_scene():
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = current_scene()
    assert scene is not None
    scene.render.fps = 50
    scene.render.fps_base = 1.0
    scene.frame_set(1)
    yield
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def set_frame(scene, frame):
    integer = math.floor(frame)
    scene.frame_set(integer, subframe=frame - integer)
    current_layer().update()


def positions(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.data
    assert isinstance(mesh, bpy.types.Mesh)
    values = [0.0] * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", values)
    return tuple(tuple(values[i : i + 3]) for i in range(0, len(values), 3))


def expected_positions(frame_index):
    pose = REFERENCE["poses"][frame_index]
    result = []
    for part in REFERENCE["parts"]:
        points = [pose["vertices"][index] for index in part["assembled_vertex_indices"]]
        result.append(tuple((x, z, -y) for x, y, z in points))
    return tuple(result)


def actual_positions(presentation):
    return tuple(positions(obj) for obj in presentation.objects)


def tree_uv_offsets(presentation):
    offsets = {}
    for obj in presentation.objects:
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        for material in mesh.materials:
            if material is None or "rs_texture_id" not in material:
                continue
            tree = material.node_tree
            assert tree is not None
            node = tree.nodes.get("RS Animation UV")
            if node is not None:
                value = getattr(node.inputs[1], "default_value")
                offsets[int(material["rs_texture_id"])] = tuple(value)
    return offsets


def test_playback_matches_every_client_pose(bundle_root):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    initial = deepcopy(tuple(part.models for part in asset.parts))
    scene = current_scene()
    presentation = create_playback(asset, scene, start_frame=1.0, loop=True)
    assert presentation.duration_ns == asset.duration_ns
    assert presentation.source_recipe == "default-male-whip"
    assert len(presentation.objects) == len(REFERENCE["parts"])
    for row in REFERENCE["rendered_actor_clock"][:-1]:
        set_frame(scene, 1 + row["elapsed_tick"])
        assert actual_positions(presentation) == expected_positions(row["frame_index"])
    assert tuple(part.models for part in asset.parts) == initial
    for obj in presentation.objects:
        assert is_presentation(obj)
        assert binding_warning(obj) is None
        assert "source" in obj["rs_animation_notice"].lower()
        assert isinstance(obj.data, bpy.types.Mesh)
        assert obj.data.shape_keys is not None
        animation = obj.data.shape_keys.animation_data
        assert animation is not None
        for curve in animation.drivers:
            driver = curve.driver
            assert driver is not None
            assert driver.is_simple_expression


@pytest.mark.parametrize("fps,base", [(50, 1.0), (24, 1.001)])
def test_fps_and_scrubbing_preserve_elapsed_time(bundle_root, fps, base):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    scene = current_scene()
    presentation = create_playback(asset, scene, start_frame=3.5, loop=True)
    scene.render.fps = fps
    scene.render.fps_base = base
    scene.frame_end = 10000
    for row in reversed(REFERENCE["rendered_actor_clock"][:-1]):
        ticks = row["elapsed_tick"] + 0.5
        set_frame(scene, 3.5 + ticks * fps / (base * 50))
        assert actual_positions(presentation) == expected_positions(row["frame_index"])
    set_frame(scene, 3.5 + 39.5 * fps / (base * 50))
    assert actual_positions(presentation) == expected_positions(0)
    set_frame(scene, 1)
    assert actual_positions(presentation) == expected_positions(0)


def test_nonlooping_last_pose_and_continuing_texture_motion(bundle_root):
    bundle = load_bundle(bundle_root)
    scene = current_scene()
    player = create_playback(
        compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"]), scene, start_frame=10.0, loop=False
    )
    tree = create_playback(compile_asset(bundle, "magic-tree", None), scene, start_frame=10.0, loop=False)
    set_frame(scene, 1)
    assert actual_positions(player) == expected_positions(0)
    assert tree_uv_offsets(tree)[34][:2] == pytest.approx((0, 0))
    set_frame(scene, 10 + 39)
    assert actual_positions(player) == expected_positions(14)
    set_frame(scene, 10 + 65)
    assert actual_positions(player) == expected_positions(14)
    assert tree_uv_offsets(tree)[34][:2] == pytest.approx((0, 2 / 128))


def test_source_and_other_instances_do_not_animate(bundle_root):
    bundle = load_bundle(bundle_root)
    asset = compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"])
    source_model = decode(bundle.models[5409].data)
    source = model_to_object(source_model, "source-whip")
    before = object_to_model(source)
    source_mesh = source.data
    assert isinstance(source_mesh, bpy.types.Mesh)
    source_materials = object_materials(source)
    scene = current_scene()
    first = create_playback(asset, scene, start_frame=1.0, loop=True)
    second = create_playback(asset, scene, start_frame=20.0, loop=True)
    set_frame(scene, 20)
    assert actual_positions(first) == expected_positions(REFERENCE["rendered_actor_clock"][19]["frame_index"])
    assert actual_positions(second) == expected_positions(0)
    assert object_to_model(source) == before
    assert not is_presentation(source)
    meshes = [mesh_data(obj) for obj in (*first.objects, *second.objects)]
    assert len(set(meshes)) == len(meshes)
    materials = [material for mesh in meshes for material in mesh.materials if material is not None]
    assert not set(source_materials).intersection(materials)
    assert all(material.animation_data is None for material in source_materials)
    trees = [
        create_playback(compile_asset(bundle, "magic-tree", None), scene, start_frame=start, loop=True)
        for start in (1.0, 20.0)
    ]
    set_frame(scene, 20)
    assert tree_uv_offsets(trees[0])[34][:2] != tree_uv_offsets(trees[1])[34][:2]
    first_materials = {material for obj in trees[0].objects for material in object_materials(obj)}
    second_materials = {material for obj in trees[1].objects for material in object_materials(obj)}
    assert not first_materials.intersection(second_materials)


def test_reopened_file_plays_without_extension(bundle_root, tmp_path):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    scene = current_scene()
    presentation = create_playback(asset, scene, start_frame=1.0, loop=True)
    names = [obj.name for obj in presentation.objects]
    tree = create_playback(compile_asset(asset.bundle, "magic-tree", None), scene, start_frame=1.0, loop=True)
    tree_names = [obj.name for obj in tree.objects]
    saved = tmp_path / "playback.blend"
    result = tmp_path / "reopened.json"
    bpy.ops.wm.save_as_mainfile(filepath=str(saved))
    for path in (bundle_root / "textures").glob("*.png"):
        path.unlink()
    script = tmp_path / "reopen.py"
    script.write_text(
        "import bpy,json,sys\nassert 'rsps_toolkit' not in sys.modules\n"
        "bpy.context.scene.frame_set(20)\nresult={}\n"
        f"for name in {names!r}:\n"
        " obj=bpy.data.objects[name]\n obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())\n"
        " flat=[0.0]*(3*len(obj.data.vertices))\n obj.data.vertices.foreach_get('co',flat)\n result[name]=flat\n"
        "offsets={}\n"
        f"for name in {tree_names!r}:\n"
        " for material in bpy.data.objects[name].data.materials:\n"
        "  node=material.node_tree.nodes.get('RS Animation UV')\n"
        "  if node: offsets[str(material['rs_texture_id'])]=list(node.inputs[1].default_value)\n"
        "  for image_node in material.node_tree.nodes:\n"
        "   if image_node.type=='TEX_IMAGE': assert image_node.image.packed_file and len(image_node.image.pixels)>0\n"
        f"open({str(result)!r},'w').write(json.dumps({{'positions':result,'texture_offsets':offsets}}))\n"
    )
    environment = dict(os.environ)
    environment["BLENDER_USER_RESOURCES"] = str(tmp_path / "clean-profile")
    log = tmp_path / "reopen.log"
    with log.open("w") as output:
        run = subprocess.run(
            [
                bpy.app.binary_path,
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                str(saved),
                "--python-exit-code",
                "1",
                "--python",
                str(script),
            ],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    assert run.returncode == 0, log.read_text()
    recorded = json.loads(result.read_text())
    for name, expected in zip(
        names, expected_positions(REFERENCE["rendered_actor_clock"][19]["frame_index"]), strict=True
    ):
        assert recorded["positions"][name] == [coordinate for point in expected for coordinate in point]
    assert recorded["texture_offsets"]["34"][:2] == pytest.approx((0, 38 / 128))


def edit_mesh(obj, operation, *, leave=True):
    for other in selected_objects():
        other.select_set(False)
    obj.select_set(True)
    current_layer().objects.active = obj
    obj.active_shape_key_index = 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    if operation == "move":
        bm.verts[0].co.x += 1
    elif operation in ("delete", "merge"):
        bm.verts[0].select_set(True)
        if operation == "merge":
            bm.verts[1].select_set(True)
    elif operation == "add-face":
        import itertools

        existing = {frozenset(face.verts) for face in bm.faces}
        corners = next(c for c in itertools.combinations(list(bm.verts)[:6], 3) if frozenset(c) not in existing)
        bm.faces.new(corners)
    bmesh.update_edit_mesh(obj.data)
    if operation == "delete":
        bpy.ops.mesh.delete(type="VERT")
    elif operation == "merge":
        bpy.ops.mesh.merge(type="CENTER")
    if leave:
        bpy.ops.object.mode_set(mode="OBJECT")


@pytest.mark.parametrize("operation", ["move", "delete", "merge", "add-face"])
@pytest.mark.timeout(15, method="thread")
def test_presentation_bindings_are_not_silent_after_edits(bundle_root, operation):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    scene = current_scene()
    result = create_playback(asset, scene, start_frame=1.0, loop=True)
    obj = result.objects[0]
    assert binding_warning(obj) is None
    edit_mesh(obj, operation, leave=False)
    warning = binding_warning(obj)
    assert warning is not None
    assert "changed" in warning.lower()
    bpy.ops.object.mode_set(mode="OBJECT")
    warning = binding_warning(obj)
    assert warning is not None
    assert "source" in warning.lower()
    assert "changed" in warning.lower()
    rebuilt = create_playback(asset, scene, start_frame=1.0, loop=True)
    assert binding_warning(obj) == warning
    assert all(binding_warning(new) is None for new in rebuilt.objects)


def test_real_undo_keeps_or_warns_about_presentation_bindings(bundle_root):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    result = create_playback(asset, current_scene(), start_frame=1.0, loop=True)
    name = result.objects[0].name
    bpy.ops.ed.undo_push(message="Playback created")
    edit_mesh(result.objects[0], "move")
    bpy.ops.ed.undo_push(message="Playback moved")
    bpy.ops.ed.undo()
    obj = bpy.data.objects[name]
    warning = binding_warning(obj)
    if warning is None:
        set_frame(current_scene(), 1)
        assert positions(obj) == expected_positions(0)[0]
    else:
        assert "source" in warning.lower()
    assert is_presentation(obj)


def test_weighter_mirror_refuses_presentation_before_mutating_it(bundle_root):
    from rsps_toolkit.blender.weighter import EPIC_OT_create_and_apply_mirror

    result = create_playback(
        compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"]),
        current_scene(),
        start_frame=1.0,
        loop=True,
    )
    obj = result.objects[0]
    for other in selected_objects():
        other.select_set(False)
    obj.select_set(True)
    current_layer().objects.active = obj
    before = positions(obj)
    bpy.utils.register_class(EPIC_OT_create_and_apply_mirror)
    try:
        assert bpy.ops.epic.create_and_apply_mirror() == {"CANCELLED"}  # pyrefly: ignore[missing-attribute]
    finally:
        bpy.utils.unregister_class(EPIC_OT_create_and_apply_mirror)
    assert positions(obj) == before
    assert binding_warning(obj) is None


def test_object_transforms_and_material_edits_preserve_bindings(bundle_root):
    result = create_playback(
        compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"]),
        current_scene(),
        start_frame=1.0,
        loop=True,
    )
    for obj in result.objects:
        obj.location.x += 5
        obj.scale = (0.5, 0.5, 0.5)
        obj.rotation_euler.z = 0.3
        object_materials(obj)[0].roughness = 0.3
        assert binding_warning(obj) is None


def test_face_groups_with_equal_static_materials_can_animate_alpha_independently(bundle_root):
    case = next(
        row
        for row in json.loads((FIXTURE / "transform-cases.json").read_text())
        if row["name"] == "alpha-distinct-groups"
    )
    model = Model(
        vertices=[tuple(v) for v in case["vertices"]],
        faces=[(0, 1, 2)] * 3,
        face_colours=[1000] * 3,
        face_textures=[None] * 3,
        face_alphas=case["face_alphas"],
        face_skins=case["face_skins"],
        vertex_skins=case["vertex_skins"],
        render_priorities=[0] * 3,
        face_texture_triangles=[None] * 3,
        flat_shaded=[False] * 3,
    )
    data = encode(model)
    bundle = load_bundle(bundle_root)
    sequence_id = REFERENCE["sequence_id"]
    sequence = replace(bundle.sequences[sequence_id], frame_ids=(0, 1), durations=(2, 2))
    frame_map = FrameMap(tuple(case["types"]), tuple(tuple(v) for v in case["labels"]))
    bundle = replace(
        bundle,
        models={0: ModelResource(bundle_root / "probe.dat", hashlib.sha256(data).hexdigest(), data)},
        frames={0: Frame(0, (0,), (0,), (0,), (0,)), 1: Frame(0, (0,), (8,), (0,), (0,))},
        frame_maps={0: frame_map},
        sequences={sequence_id: sequence},
        recipes={"alpha": Recipe((PartRecipe("probe", (0,), (0, 0, 0), (), ()),), (), (sequence_id,))},
    )
    result = create_playback(compile_asset(bundle, "alpha", sequence_id), current_scene(), start_frame=1.0, loop=False)
    mesh = mesh_data(result.objects[0])
    set_frame(current_scene(), 3)
    slots = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", slots)
    assert slots[0] == slots[2]
    assert slots[0] != slots[1]
    for polygon, alpha in zip(mesh.polygons, case["expected_face_alphas"], strict=True):
        material = mesh.materials[polygon.material_index]
        assert material is not None
        tree = material.node_tree
        assert tree is not None
        node = next(node for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeBsdfPrincipled))
        inputs = node.inputs
        assert inputs is not None
        assert getattr(inputs["Alpha"], "default_value") == pytest.approx((256 - alpha) / 256)


@pytest.mark.parametrize("start", [float("nan"), float("inf"), float("-inf"), True])
def test_invalid_start_frame_creates_no_partial_objects(bundle_root, start):
    asset = compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"])
    before = set(bpy.data.objects)
    with pytest.raises(ValueError, match="start"):
        create_playback(asset, current_scene(), start_frame=start, loop=True)
    assert set(bpy.data.objects) == before


def test_presentation_images_are_private_and_packed(bundle_root):
    bundle = load_bundle(bundle_root)
    source = model_to_object(
        decode(bundle.models[7978].data), "source-tree", lambda texture: bundle.textures[texture].path
    )
    source_images = []
    for material in object_materials(source):
        tree = material.node_tree
        assert tree is not None
        source_images.extend(
            node.image
            for node in tree.nodes
            if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None
        )
    packing = [image.packed_file for image in source_images]
    result = create_playback(compile_asset(bundle, "magic-tree", None), current_scene(), start_frame=1.0, loop=True)
    for obj in result.objects:
        for material in object_materials(obj):
            tree = material.node_tree
            assert tree is not None
            for node in tree.nodes:
                if isinstance(node, bpy.types.ShaderNodeTexImage):
                    image = node.image
                    assert image is not None
                    assert image not in source_images
                    assert image.packed_file is not None
    assert [image.packed_file for image in source_images] == packing


def image_pixels(image):
    values = [0.0] * len(cast(Sized, image.pixels))
    image.pixels.foreach_get(values)
    return values


def test_cached_source_image_edits_do_not_replace_verified_texture_pixels(bundle_root):
    bundle = load_bundle(bundle_root)
    source = model_to_object(
        decode(bundle.models[7978].data), "edited-source-tree", lambda texture: bundle.textures[texture].path
    )
    original_pixels = {}
    source_images = []
    for material in object_materials(source):
        tree = material.node_tree
        assert tree is not None
        for node in tree.nodes:
            if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None:
                image = node.image
                values = image_pixels(image)
                original_pixels[int(material["rs_texture_id"])] = values[0]
                values[0] = 0.271
                image.pixels.foreach_set(values)
                image.update()
                edited = image_pixels(image)
                source_images.append((image, edited[0]))
    result = create_playback(compile_asset(bundle, "magic-tree", None), current_scene(), start_frame=1.0, loop=True)
    for obj in result.objects:
        for material in object_materials(obj):
            tree = material.node_tree
            assert tree is not None
            for node in tree.nodes:
                if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None:
                    values = image_pixels(node.image)
                    assert values[0] == original_pixels[int(material["rs_texture_id"])]
    for image, edited in source_images:
        values = image_pixels(image)
        assert values[0] == edited


def test_changed_texture_resource_is_refused_before_partial_creation(bundle_root):
    asset = compile_asset(load_bundle(bundle_root), "magic-tree", None)
    path = bundle_root / "textures/34.png"
    data = bytearray(path.read_bytes())
    data[0] ^= 1
    path.write_bytes(data)
    before = set(bpy.data.objects)
    with pytest.raises(ValueError, match="texture 34"):
        create_playback(asset, current_scene(), start_frame=1.0, loop=True)
    assert set(bpy.data.objects) == before


def test_static_playback_keeps_unreferenced_vertices_and_item_offsets(bundle_root):
    bundle = load_bundle(bundle_root)
    model = decode(bundle.models[7978].data)
    model.vertices.append((12, 34, 56))
    if model.vertex_skins is not None:
        model.vertex_skins.append(0)
    data = encode(model)
    models = dict(bundle.models)
    models[7978] = replace(models[7978], data=data, sha256=hashlib.sha256(data).hexdigest())
    recipe = bundle.recipes["magic-tree"]
    recipe = replace(recipe, parts=(replace(recipe.parts[0], offset=(7, -11, 13)),))
    bundle = replace(bundle, models=models, recipes={"magic-tree": recipe})
    result = create_playback(compile_asset(bundle, "magic-tree", None), current_scene(), start_frame=1.0, loop=True)
    # Class104_Sub18_Sub16_Sub5.java:321-328 translates every raw vertex, including one unused by any face.
    assert positions(result.objects[0]) == tuple((x + 7, z + 13, -y + 11) for x, y, z in model.vertices)


@pytest.mark.parametrize("active_key", [0, 1, 15])
def test_entering_edit_mode_without_editing_keeps_the_binding_valid(bundle_root, active_key):
    result = create_playback(
        compile_asset(load_bundle(bundle_root), "default-male-whip", REFERENCE["sequence_id"]),
        current_scene(),
        start_frame=1.0,
        loop=True,
    )
    obj = result.objects[0]
    for other in selected_objects():
        other.select_set(False)
    obj.select_set(True)
    current_layer().objects.active = obj
    obj.active_shape_key_index = active_key
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        assert binding_warning(obj) is None
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    assert binding_warning(obj) is None


def test_private_presentation_materials_cull_back_faces_without_changing_sources(bundle_root):
    bundle = load_bundle(bundle_root)
    source = model_to_object(decode(bundle.models[5409].data), "source-whip")
    source_materials = object_materials(source)
    before = [material.use_backface_culling for material in source_materials]
    result = create_playback(
        compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"]),
        current_scene(),
        start_frame=1.0,
        loop=True,
    )
    # The pinned client's Class104_Sub18_Sub16_Sub4.java:810-812 draws only faces passing its winding test.
    assert all(material.use_backface_culling for obj in result.objects for material in object_materials(obj))
    assert [material.use_backface_culling for material in source_materials] == before
