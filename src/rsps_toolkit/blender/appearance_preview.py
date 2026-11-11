"""Builds the lit player mesh from an appearance preset. The operators that use it are in appearance_collection."""

from collections.abc import Collection
from pathlib import Path

import bpy

from ..formats.appearance_preset import AppearancePreset
from ..formats.cache_profile import shared_profile
from ..formats.colour import face_colour_to_rgb
from ..formats.face_order import visible_faces
from ..formats.lighting import Shading, light
from ..formats.model import Model
from . import preferences
from .axes import game_to_blender
from .face_materials import DEFAULT_BRIGHTNESS, srgb_to_linear

PRESET_KEY = "rs_appearance_preset"
LIT_ATTRIBUTE = "rs_lit"
# Face attributes the clip bake reads to fade faces: the face's skin label and its alpha at rest.
FACE_LABEL_ATTRIBUTE = "rs_face_label"
FACE_ALPHA_ATTRIBUTE = "rs_face_alpha"
# A point attribute: each vertex's index in the merged model, so the parts of a player can be posed together.
VERTEX_ATTRIBUTE = "rs_vertex"
# A face attribute: each polygon's face index in the merged model.
FACE_ATTRIBUTE = "rs_face"
MATERIAL_NAME = "RS Appearance Preview"


def collection_of(obj: bpy.types.Object | None) -> bpy.types.Collection | None:
    """The player collection that holds the object, if it is part of one."""
    if obj is None:
        return None
    return next((c for c in obj.users_collection if PRESET_KEY in c), None)


def build_mesh(
    model: Model,
    shading: Shading,
    name: str,
    brightness: float = DEFAULT_BRIGHTNESS,
    faces: Collection[int] | None = None,
    loose: bool = True,
) -> bpy.types.Mesh:
    """Create a mesh whose face corners show the client's lit colours, from the model's faces or only `faces`.

    Game y points down, so a game vertex (x, y, z) becomes Blender (x, z, -y). Faces that repeat a vertex are not
    drawn. A flat-shaded face uses its one lit colour at all three corners. The mesh holds the vertices its faces use
    and, when `loose` is set, the vertices no drawn face of the model uses, in model order. Each vertex's index in the
    model is stored in the VERTEX_ATTRIBUTE point attribute and each polygon's in the FACE_ATTRIBUTE face attribute.
    """
    visible = set(visible_faces(model))
    drawn = [i for i, face in enumerate(model.faces) if len(set(face)) == 3 and i in visible]
    kept = drawn if faces is None else [i for i in drawn if i in faces]
    used = {v for i in kept for v in model.faces[i]}
    if loose:
        used |= set(range(len(model.vertices))) - {v for i in drawn for v in model.faces[i]}
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    try:
        _fill_mesh(mesh, model, shading, kept, sorted(used), brightness)
    except Exception:
        bpy.data.meshes.remove(mesh)
        raise
    return mesh


def vertex_indices(mesh: bpy.types.Mesh) -> list[int]:
    """Each mesh vertex's index in the model it was built from. A mesh built before meshes stored it holds every
    model vertex in order."""
    attribute = mesh.attributes.get(VERTEX_ATTRIBUTE)
    if attribute is None:
        return list(range(len(mesh.vertices)))
    out = [0] * len(mesh.vertices)
    attribute.data.foreach_get("value", out)
    return out


def face_indices(mesh: bpy.types.Mesh) -> list[int] | None:
    """Each polygon's face index in the model it was built from, or None for a mesh built before meshes stored it."""
    attribute = mesh.attributes.get(FACE_ATTRIBUTE)
    if attribute is None:
        return None
    out = [0] * len(mesh.polygons)
    attribute.data.foreach_get("value", out)
    return out


def _fill_mesh(
    mesh: bpy.types.Mesh, model: Model, shading: Shading, kept: list[int], vertices: list[int], brightness: float
) -> None:
    index = {v: i for i, v in enumerate(vertices)}
    mesh.from_pydata(
        [game_to_blender(model.vertices[v]) for v in vertices],
        [],
        [tuple(index[v] for v in model.faces[i]) for i in kept],
    )
    mesh.update()
    mesh.attributes.new(VERTEX_ATTRIBUTE, "INT", "POINT").data.foreach_set("value", vertices)
    mesh.attributes.new(FACE_ATTRIBUTE, "INT", "FACE").data.foreach_set("value", kept)
    colours = mesh.color_attributes.new(LIT_ATTRIBUTE, "FLOAT_COLOR", "CORNER")
    values: list[float] = []
    for i in kept:
        corners = (
            (shading.corner_a[i],) * 3
            if model.flat_shaded[i]
            else (shading.corner_a[i], shading.corner_b[i], shading.corner_c[i])
        )
        for shade in corners:
            r, g, b = face_colour_to_rgb(shade, brightness)
            values += [srgb_to_linear(r / 255), srgb_to_linear(g / 255), srgb_to_linear(b / 255), 1.0]
    colours.data.foreach_set("color", values)
    mesh.color_attributes.active_color = colours
    mesh.color_attributes.render_color_index = mesh.color_attributes.find(LIT_ATTRIBUTE)
    if model.face_skins is not None:
        mesh.attributes.new(FACE_LABEL_ATTRIBUTE, "INT", "FACE").data.foreach_set(
            "value", [model.face_skins[i] for i in kept]
        )
        alphas = model.face_alphas or [0] * len(model.faces)
        mesh.attributes.new(FACE_ALPHA_ATTRIBUTE, "INT", "FACE").data.foreach_set("value", [alphas[i] for i in kept])
    mesh.materials.append(_material())


def _material() -> bpy.types.Material:
    """One shared material that emits the lit corner colours, so Blender's own lights do not shade them again.

    Its Backface Culling hides the back of each face in Material Preview and renders, as the client does
    (docs/research/render-priority.md, "Skip and cull"). Solid mode ignores it and culls through `show_lit_colours`.
    Every time the add-on builds player meshes (Create, Update and Duplicate Player, and a bake that adds a held item)
    it turns culling on again, so a file whose material was made before players culled gets it too (issue 28,
    decisions 1, 3 and 6).
    """
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        nodes.remove(nodes["Principled BSDF"])
        attribute = nodes.new("ShaderNodeVertexColor")
        attribute.layer_name = LIT_ATTRIBUTE
        emission = nodes.new("ShaderNodeEmission")
        links.new(attribute.outputs["Color"], emission.inputs["Color"])
        links.new(emission.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    material.use_backface_culling = True
    return material


def show_lit_colours(context: bpy.types.Context) -> None:
    """Make Solid mode draw the lit corner colours, unshaded, and only the front of each face, as the client does
    (docs/research/render-priority.md, "Skip and cull").

    The colours already contain the client's lighting. Culling is a setting of the whole view, so it hides the back of
    every object in that view, not only players (issue 28, decision 1).
    """
    space = context.space_data
    if isinstance(space, bpy.types.SpaceView3D) and space.shading.type == "SOLID":
        space.shading.color_type = "VERTEX"
        space.shading.light = "FLAT"
        space.shading.show_backface_culling = True


def fail(operator: bpy.types.Operator, context: bpy.types.Context, error: Exception) -> None:
    operator.report({"ERROR"}, str(error))
    context.scene.rs_appearance.last_error = str(error)


def cache_folder(setting: str) -> Path:
    folder = preferences.folder_in_setting(setting) if setting else preferences.cache_folder()
    if folder is None:
        raise ValueError("Set the Cache folder in the add-on preferences.")
    return folder


def assemble_lit(preset: AppearancePreset, folder: Path) -> tuple[Model, Shading]:
    """Assemble and light the preset's body. Everything that can fail runs here, before any Blender data changes."""
    body = shared_profile(folder).assemble(preset)
    return body, light(body)


def assemble_parts(preset: AppearancePreset, folder: Path) -> tuple[Model, Shading, dict[int, range]]:
    """`assemble_lit`, with the faces each equipment slot supplied."""
    body, slots = shared_profile(folder).assemble_slots(preset)
    return body, light(body), slots
