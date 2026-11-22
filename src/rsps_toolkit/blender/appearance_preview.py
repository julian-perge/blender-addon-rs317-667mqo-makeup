"""Builds the lit player mesh from an appearance preset. The operators that use it are in appearance_collection."""

from collections.abc import Collection, Mapping
from pathlib import Path

import bpy

from ..formats import texture_uvs
from ..formats.appearance_preset import AppearancePreset
from ..formats.cache_profile import MissingResourceError, shared_profile
from ..formats.colour import face_colour_to_rgb
from ..formats.face_order import visible_faces
from ..formats.js5 import Js5Store
from ..formats.lighting import PLAYER_LIGHTING, Shading, light
from ..formats.model import Model
from ..formats.texture import read_textures
from ..formats.texture import texture_pixels as decoded_pixels
from . import preferences, rs_layers
from .axes import game_to_blender
from .face_materials import DEFAULT_BRIGHTNESS, MISSING_TEXTURE, srgb_to_linear, texture_image

type TexturePixels = tuple[tuple[int, ...], bool]
"""The pixels of one texture at one brightness, as `formats.texture.texture_pixels` gives them, and whether it is
opaque."""

PRESET_KEY = "rs_appearance_preset"
LIT_ATTRIBUTE = "rs_lit"
# Face attributes the clip bake reads to fade faces: the face's skin label and its alpha at rest. A model with no face
# skins has no label attribute.
FACE_LABEL_ATTRIBUTE = "rs_face_label"
FACE_ALPHA_ATTRIBUTE = "rs_face_alpha"
# A face attribute: each polygon's face colour. The RS Scene export reads it with the face alpha (issue 143).
FACE_COLOUR_ATTRIBUTE = "rs_face_colour"
# A point attribute: each vertex's index in the merged model, so the parts of a player can be posed together.
VERTEX_ATTRIBUTE = "rs_vertex"
# A face attribute: each polygon's face index in the merged model.
FACE_ATTRIBUTE = "rs_face"
MATERIAL_NAME = "RS Appearance Preview"
# A face attribute: the material slot that `build_mesh` gave each polygon. A fade puts a polygon back on it.
LIT_SLOT_ATTRIBUTE = "rs_lit_slot"
# On a texture material of `build_mesh`: the texture id that it shows.
TEXTURE_KEY = "rs_preview_texture"
# On an alpha material of `build_mesh`: the face alpha of its faces.
ALPHA_KEY = "rs_preview_alpha"
# The third lit value of a face that the client never draws (`ej.ae`, docs/research/textured-light.md, section 2).
_NOT_DRAWN = -2


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
    textures: Mapping[int, TexturePixels] | None = None,
) -> bpy.types.Mesh:
    """Create a mesh whose face corners show the client's lit colours, from the model's faces or only `faces`.

    Game y points down, so a game vertex (x, y, z) becomes Blender (x, z, -y). Faces that repeat a vertex are not
    drawn, and neither is a face that the client never draws, whose third lit value is -2 (`ej.ae`, ADR 0036). A face
    whose third lit value is -1, a flat face or an untextured face of render type 3, uses its first lit value at all
    three corners. The mesh holds the vertices its faces use and, when `loose` is set, the vertices no drawn face of
    the model uses, in model order. Each vertex's index in the model is stored in the VERTEX_ATTRIBUTE point attribute
    and each polygon's in the FACE_ATTRIBUTE face attribute, with its face colour in FACE_COLOUR_ATTRIBUTE (-1 for a
    textured face with no colour), its face alpha in FACE_ALPHA_ATTRIBUTE and its material slot in LIT_SLOT_ATTRIBUTE.

    A textured face shows the image of its texture from `textures` times its light value, through a material of
    `_texture_material`, and magenta times its light value when `textures` lacks it. A plain face with a face alpha
    covers (256 - alpha) / 256 of its pixels, through a material of `_alpha_material`. Every other face uses the one
    shared material of players in slot 0.
    """
    visible = set(visible_faces(model))
    drawn = [
        i
        for i, face in enumerate(model.faces)
        if len(set(face)) == 3 and i in visible and shading.corner_c[i] != _NOT_DRAWN
    ]
    kept = drawn if faces is None else [i for i in drawn if i in faces]
    used = {v for i in kept for v in model.faces[i]}
    if loose:
        used |= set(range(len(model.vertices))) - {v for i in drawn for v in model.faces[i]}
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    try:
        _fill_mesh(mesh, model, shading, kept, sorted(used), brightness, textures or {})
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
    mesh: bpy.types.Mesh,
    model: Model,
    shading: Shading,
    kept: list[int],
    vertices: list[int],
    brightness: float,
    textures: Mapping[int, TexturePixels],
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
        third = shading.corner_c[i]
        corners = (shading.corner_a[i],) * 3 if third == -1 else (shading.corner_a[i], shading.corner_b[i], third)
        for shade in corners:
            if shading.light_values[i]:
                # The client multiplies each texel by the light value over 128 (`ep.c`, textured-light.md section 2),
                # and the texture image already has the brightness, as for the scenery (`region_scenery._write_lit`).
                grey = srgb_to_linear(shade / 128)
                values += [grey, grey, grey, 1.0]
            else:
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
    face_colours = [model.face_colours[i] for i in kept]
    mesh.attributes.new(FACE_COLOUR_ATTRIBUTE, "INT", "FACE").data.foreach_set(
        "value", [-1 if colour is None else colour for colour in face_colours]
    )
    mesh.materials.append(_material())
    slots: list[int] = []
    shown: dict[tuple[str, int], int] = {}
    for i in kept:
        texture = model.face_textures[i]
        key = ("alpha", alphas[i]) if texture is None else ("texture", texture)
        if key == ("alpha", 0):
            slots.append(0)
            continue
        if key not in shown:
            shown[key] = len(mesh.materials)
            mesh.materials.append(
                _alpha_material(alphas[i])
                if texture is None
                else _texture_material(texture, textures.get(texture), brightness)
            )
        slots.append(shown[key])
    mesh.polygons.foreach_set("material_index", slots)
    mesh.attributes.new(LIT_SLOT_ATTRIBUTE, "INT", "FACE").data.foreach_set("value", slots)
    if any(kind == "texture" for kind, _ in shown):
        _write_uvs(mesh, model, kept)


def _alpha_material(alpha: int) -> bpy.types.Material:
    """The material of every player mesh of the file for a plain face of this alpha: it emits the lit corner colours
    and covers (256 - alpha) / 256 of each pixel, as `ep.g` and `ep.m` blend such a face (ADR 0036,
    docs/research/textured-light.md, section 2). It draws blended, and culls back faces as the plain material does."""
    name = f"{MATERIAL_NAME} alpha {alpha}"
    material = bpy.data.materials.get(name)
    if material is not None:
        return material
    material = bpy.data.materials.new(name)
    material[ALPHA_KEY] = alpha
    material.use_nodes = True
    material.use_backface_culling = True
    material.surface_render_method = "BLENDED"
    nodes, links = material.node_tree.nodes, material.node_tree.links  # pyrefly: ignore[missing-attribute]
    nodes.remove(nodes["Principled BSDF"])
    light_node = nodes.new("ShaderNodeVertexColor")
    light_node.layer_name = LIT_ATTRIBUTE
    emission = nodes.new("ShaderNodeEmission")
    links.new(light_node.outputs["Color"], emission.inputs["Color"])
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = (256 - alpha) / 256
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    return material


def _write_uvs(mesh: bpy.types.Mesh, model: Model, kept: list[int]) -> None:
    """The texture coordinates of each textured polygon, as model import writes them (`mesh._write_uvs`), and (0, 0)
    for every other polygon."""
    uvs: list[float] = []
    for i in kept:
        corners = (texture_uvs(model, i) if model.face_textures[i] is not None else None) or ((0.0, 0.0),) * 3
        uvs += [c for u, v in corners for c in (u, 1 - v)]
    mesh.uv_layers.new(name=rs_layers.PREVIEW_UVS).data.foreach_set("uv", uvs)


def _texture_material(texture: int, pixels: TexturePixels | None, brightness: float) -> bpy.types.Material:
    """The material that shows a texture at a brightness on every player mesh of the file: it emits the image times
    the grey light value in `rs_lit`, read one texel per pixel, and the texel alpha is its cover (ADR 0036). A face
    alpha does not count, because `ep.k` does not read it (docs/research/textured-light.md, section 2). With no
    pixels it emits magenta times the light value, as the scenery does (issue 130). Back faces are culled, as for the
    plain material."""
    name = f"{MATERIAL_NAME} texture {texture} at {brightness:g}"
    material = bpy.data.materials.get(name)
    if material is not None:
        return material
    material = bpy.data.materials.new(name)
    material[TEXTURE_KEY] = texture
    material.use_nodes = True
    material.use_backface_culling = True
    nodes, links = material.node_tree.nodes, material.node_tree.links  # pyrefly: ignore[missing-attribute]
    nodes.remove(nodes["Principled BSDF"])
    light_node = nodes.new("ShaderNodeVertexColor")
    light_node.layer_name = LIT_ATTRIBUTE
    multiply = nodes.new("ShaderNodeMix")
    multiply.data_type = "RGBA"
    multiply.blend_type = "MULTIPLY"
    multiply.inputs["Factor"].default_value = 1.0
    links.new(light_node.outputs["Color"], multiply.inputs["B"])
    emission = nodes.new("ShaderNodeEmission")
    links.new(multiply.outputs["Result"], emission.inputs["Color"])
    output = nodes["Material Output"]
    if pixels is None:
        multiply.inputs["A"].default_value = MISSING_TEXTURE
        links.new(emission.outputs["Emission"], output.inputs["Surface"])
        return material
    image_name = f"RS Appearance Texture {texture} at {brightness:g}"
    image = bpy.data.images.get(image_name)
    if image is None:
        image = texture_image(texture, *pixels)
        image.name = image_name
    texels = nodes.new("ShaderNodeTexImage")
    texels.image = image
    texels.interpolation = "Closest"
    links.new(texels.outputs["Color"], multiply.inputs["A"])
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(texels.outputs["Alpha"], mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])
    return material


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
    return body, light(body, PLAYER_LIGHTING)


def assemble_parts(preset: AppearancePreset, folder: Path) -> tuple[Model, Shading, dict[int, range]]:
    """`assemble_lit`, with the faces each equipment slot supplied."""
    body, slots = shared_profile(folder).assemble_slots(preset)
    return body, light(body, PLAYER_LIGHTING), slots


def texture_pixels(folder: Path, model: Model, brightness: float) -> dict[int, TexturePixels]:
    """The pixels of each texture that a face of the model shows, at the brightness, read before any Blender data
    exists. A texture that the cache lacks is refused with a MissingResourceError, an OSError that the operators report,
    as the region import refuses it (issue 47)."""
    used = sorted({texture for texture in model.face_textures if texture is not None})
    if not used:
        return {}
    try:
        textures = read_textures(Js5Store(folder), used)
    except (LookupError, FileNotFoundError) as error:
        listed = ", ".join(map(str, used))
        raise MissingResourceError(
            f"The model shows texture {listed}, and the cache at {folder} lacks it: {error}"
        ) from error
    return {
        texture_id: (decoded_pixels(texture, sprites, brightness), texture.opaque)
        for texture_id, (texture, sprites) in textures.items()
    }
