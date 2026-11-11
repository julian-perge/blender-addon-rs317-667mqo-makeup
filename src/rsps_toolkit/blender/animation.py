"""Presentation provenance and static export protection."""

import hashlib
import json
import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass

import bpy

from ..animation.bundle import TextureMotion
from ..animation.poses import AnimationAsset, Pose, sample_pose
from ..formats import Model
from . import face_materials
from .appearance_preview import collection_of
from .mesh import model_to_object


def is_presentation(obj: bpy.types.Object) -> bool:
    """Keep refusing presentation copies when their metadata is incomplete or from a newer version."""
    return "rs_presentation" in obj or (isinstance(obj.data, bpy.types.Mesh) and "rs_presentation" in obj.data)


def is_player(obj: bpy.types.Object) -> bool:
    """True for the mesh and rig of a player collection, which is built for Blender work and has no game export."""
    return collection_of(obj) is not None


def assert_static_exportable(objects: Sequence[bpy.types.Object]) -> None:
    """Refuse the complete selection before a caller writes any model files."""
    names = [obj.name for obj in objects if is_presentation(obj)]
    if names:
        raise ValueError(
            f"{', '.join(names)}: presentation-only copies cannot be exported as .dat. Export their original source models."
        )
    players = [obj.name for obj in objects if is_player(obj)]
    if players:
        raise ValueError(f"{', '.join(players)}: player appearance objects cannot be exported as .dat.")


@dataclass(frozen=True)
class Presentation:
    objects: tuple[bpy.types.Object, ...]
    duration_ns: int | None
    source_recipe: str


def _mesh_signatures(mesh: bpy.types.Mesh) -> tuple[str, str]:
    topology = hashlib.sha256()
    topology.update(struct.pack("<III", len(mesh.vertices), len(mesh.polygons), len(mesh.loops)))
    indices = [0] * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", indices)
    topology.update(struct.pack(f"<{len(indices)}I", *indices))
    counts = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("loop_total", counts)
    topology.update(struct.pack(f"<{len(counts)}I", *counts))
    geometry = hashlib.sha256()
    values = [0.0] * (3 * len(mesh.vertices))
    mesh.vertices.foreach_get("co", values)
    geometry.update(struct.pack(f"<{len(values)}f", *values))
    keys = mesh.shape_keys
    if keys is not None:
        for key in keys.key_blocks:
            geometry.update(key.name.encode())
            values = [0.0] * (3 * len(key.data))
            key.data.foreach_get("co", values)
            geometry.update(struct.pack(f"<{len(values)}f", *values))
    return topology.hexdigest(), geometry.hexdigest()


def binding_warning(obj: bpy.types.Object) -> str | None:
    """Explain when mesh edits invalidated a baked presentation's stored correspondence."""
    if not is_presentation(obj):
        return None
    try:
        record = json.loads(obj["rs_presentation"])
        if record["version"] != 1 or not isinstance(obj.data, bpy.types.Mesh):
            raise ValueError("Unsupported presentation binding")
        if obj.mode == "EDIT":
            obj.update_from_editmode()
        topology, geometry = _mesh_signatures(obj.data)
        if topology != record["topology"]:
            return "Mesh topology changed. Recreate playback from the source bundle."
        if geometry != record["geometry"]:
            return "Mesh or baked pose positions changed. Recreate playback from the source bundle."
    except (TypeError, ValueError, KeyError):
        return "Presentation binding metadata is missing or unsupported. Recreate playback from the source bundle."
    return None


def _driver(
    target, path: str, expression: str, scene: bpy.types.Scene, controller: bpy.types.Object, index: int = -1
) -> None:
    curve = target.driver_add(path, index) if index >= 0 else target.driver_add(path)
    driver = curve.driver
    driver.type = "SCRIPTED"
    for name, owner, owner_type, data_path in (
        ("fps", scene, "SCENE", "render.fps"),
        ("base", scene, "SCENE", "render.fps_base"),
        ("start", controller, "OBJECT", '["rs_animation_start"]'),
        ("loop", controller, "OBJECT", '["rs_animation_loop"]'),
    ):
        variable = driver.variables.new()
        variable.name = name
        variable.type = "SINGLE_PROP"
        variable.targets[0].id_type = owner_type
        variable.targets[0].id = owner
        variable.targets[0].data_path = data_path
    driver.expression = expression
    if not driver.is_simple_expression:
        raise ValueError("Playback driver is not a self-contained simple expression")


def _ticks(tick_ns: int) -> str:
    return f"floor(max(0,(frame-start)*base*{1_000_000_000 // tick_ns}/fps))"


def _conditions(asset: AnimationAsset) -> tuple[str, ...]:
    if asset.sequence is None or asset.duration_ns is None:
        return ("True",)
    tick_ns = asset.sequence.tick_ns
    raw = _ticks(tick_ns)
    period = asset.duration_ns // tick_ns
    tick = f"(fmod(({raw}),{period}) if loop else ({raw}))"
    starts = [time // tick_ns for time in asset.pose_starts_ns]
    result = []
    for index, start in enumerate(starts):
        if index == len(starts) - 1:
            result.append(f"({tick})>={start}")
        elif index == 0:
            result.append(f"({tick})<{starts[index + 1]}")
        else:
            result.append(f"{start}<=({tick})<{starts[index + 1]}")
    return tuple(result)


def _linked_source(socket: bpy.types.NodeSocket) -> bpy.types.NodeSocket:
    links = socket.links
    assert links is not None and len(links) > 0
    source = links[0].from_socket
    assert source is not None
    return source


def _texture_motion(
    material: bpy.types.Material, motion: TextureMotion, scene: bpy.types.Scene, controller: bpy.types.Object
) -> None:
    if motion.direction == 0 or motion.speed == 0:
        return
    tree = material.node_tree
    assert tree is not None
    images = [node for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeTexImage)]
    for image in images:
        offset = tree.nodes.new("ShaderNodeVectorMath")
        offset.name = "RS Animation UV"
        offset.operation = "ADD"
        inputs = image.inputs
        assert inputs is not None
        if inputs["Vector"].is_linked:
            source = _linked_source(inputs["Vector"])
        else:
            coordinates = tree.nodes.new("ShaderNodeTexCoord")
            source = coordinates.outputs["UV"]
        tree.links.new(source, offset.inputs[0])
        tree.links.new(offset.outputs["Vector"], inputs["Vector"])
        vector = offset.inputs[1]
        vector.default_value = (0.0, 0.0, 0.0)
        axis = 1 if motion.direction in (1, 3) else 0
        sign = -1 if motion.direction in (2, 3) else 1
        step = f"fmod(({_ticks(motion.tick_ns)})*{motion.speed},{motion.sampling_size})"
        wrapped = step if sign > 0 else f"fmod({motion.sampling_size}-({step}),{motion.sampling_size})"
        expression = f"({wrapped})/{motion.sampling_size}"
        _driver(vector, "default_value", expression, scene, controller, axis)


def _face_alpha(
    material: bpy.types.Material,
    trace: tuple[int, ...],
    conditions: tuple[str, ...],
    scene: bpy.types.Scene,
    controller: bpy.types.Object,
) -> None:
    if not any(trace):
        return
    tree = material.node_tree
    assert tree is not None
    principled = next(node for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeBsdfPrincipled))
    inputs = principled.inputs
    assert inputs is not None
    alpha = inputs["Alpha"]
    if alpha.is_linked:
        multiply = tree.nodes.new("ShaderNodeMath")
        multiply.operation = "MULTIPLY"
        source = _linked_source(alpha)
        tree.links.new(source, multiply.inputs[0])
        tree.links.new(multiply.outputs[0], alpha)
        alpha = multiply.inputs[1]
    weights = [(256 - value) / 256 for value in trace]
    alpha.default_value = weights[0]
    material.surface_render_method = "BLENDED"
    if len(set(trace)) > 1:
        expression = "".join(
            f"{weight!r} if ({condition}) else "
            for weight, condition in zip(weights[:-1], conditions[:-1], strict=True)
        ) + repr(weights[-1])
        _driver(alpha, "default_value", expression, scene, controller)


def _materials(
    obj: bpy.types.Object,
    model: Model,
    poses: tuple[Pose, ...],
    part_index: int,
    face_offset: int,
    asset: AnimationAsset,
    conditions: tuple[str, ...],
    scene: bpy.types.Scene,
    controller: bpy.types.Object,
) -> None:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    original = list(mesh.materials)
    slots = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", slots)
    mesh.materials.clear()
    materials: dict[tuple[int, tuple[int, ...]], int] = {}
    polygon_index = 0
    for face_index, face in enumerate(model.faces):
        if len(set(face)) < 3:
            continue
        trace = tuple(pose.parts[part_index].face_alphas[face_offset + face_index] for pose in poses)
        key = slots[polygon_index], trace
        if key not in materials:
            source = original[key[0]]
            assert source is not None
            material = source.copy()
            material.use_backface_culling = True
            tree = material.node_tree
            assert tree is not None
            for node in tree.nodes:
                if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image is not None:
                    node.image = node.image.copy()
                    node.image.pack()
            materials[key] = len(mesh.materials)
            mesh.materials.append(material)
            _face_alpha(material, trace, conditions, scene, controller)
            texture_id = material.get(face_materials.TEXTURE_ID)
            if texture_id is not None:
                _texture_motion(material, asset.bundle.textures[int(texture_id)], scene, controller)
        mesh.polygons[polygon_index].material_index = materials[key]
        polygon_index += 1
    for material in original:
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material)


def create_playback(asset: AnimationAsset, scene: bpy.types.Scene, *, start_frame: float, loop: bool) -> Presentation:
    """Bake private meshes and materials that play without Python handlers or the extension."""
    if isinstance(start_frame, bool) or not math.isfinite(start_frame) or type(loop) is not bool:
        raise ValueError("Playback requires a finite start frame and an explicit loop setting")
    texture_ids = {
        texture
        for part in asset.parts
        for model in part.models
        for texture in model.face_textures
        if texture is not None
    }
    for texture_id in texture_ids:
        motion = asset.bundle.textures[texture_id]
        if not motion.path.resolve().is_relative_to(asset.bundle.root):
            raise ValueError(f"Resource path changed for texture {texture_id}")
        try:
            data = motion.path.read_bytes()
        except OSError as error:
            raise ValueError(f"Missing resource for texture {texture_id}") from error
        if hashlib.sha256(data).hexdigest() != motion.sha256:
            raise ValueError(f"Resource changed for texture {texture_id}; load the source bundle again")
    times = asset.pose_starts_ns if asset.sequence is not None else (0,)
    poses = tuple(sample_pose(asset, time) for time in times)
    conditions = _conditions(asset)
    objects = []
    controller = None
    for part_index, part in enumerate(asset.parts):
        face_offset = 0
        for model_index, model in enumerate(part.models):
            obj = model_to_object(
                model,
                f"RS Animation {asset.recipe_id} {part.key} {model_index}",
                lambda texture_id: asset.bundle.textures[texture_id].path,
            )
            for collection in tuple(obj.users_collection):
                collection.objects.unlink(obj)
            scene.collection.objects.link(obj)
            objects.append(obj)
            mesh = obj.data
            assert isinstance(mesh, bpy.types.Mesh)
            mapping = part.model_vertex_indices[model_index]
            vertices = part.model_rest_vertices[model_index]
            mesh.vertices.foreach_set("co", [coordinate for x, y, z in vertices for coordinate in (x, z, -y)])
            if controller is None:
                controller = obj
                obj["rs_animation_start"] = float(start_frame)
                obj["rs_animation_loop"] = loop
            if asset.sequence is not None:
                obj.shape_key_add(name="Basis")
                for pose_index, pose in enumerate(poses):
                    key = obj.shape_key_add(name=f"Game pose {pose_index}")
                    points = [pose.parts[part_index].vertices[index] for index in mapping]
                    key.data.foreach_set("co", [coordinate for x, y, z in points for coordinate in (x, z, -y)])
                    _driver(key, "value", f"1 if ({conditions[pose_index]}) else 0", scene, controller)
            _materials(obj, model, poses, part_index, face_offset, asset, conditions, scene, controller)
            face_offset += len(model.faces)
            topology, geometry = _mesh_signatures(mesh)
            record = json.dumps(
                {
                    "version": 1,
                    "source_recipe": asset.recipe_id,
                    "sequence_id": asset.sequence_id,
                    "part": part.key,
                    "model_index": model_index,
                    "duration_ns": asset.duration_ns,
                    "topology": topology,
                    "geometry": geometry,
                }
            )
            obj["rs_presentation"] = record
            mesh["rs_presentation"] = record
            obj["rs_animation_notice"] = (
                "Mesh or topology edits require recreating playback from the source bundle. DAT export is refused."
            )
    if not objects:
        raise ValueError("The selected animation recipe has no renderable models")
    for layer in scene.view_layers:
        layer.update()
    return Presentation(tuple(objects), asset.duration_ns, asset.recipe_id)
