"""Materials for a model's faces: one per distinct face colour or texture ID and face alpha.

Each material keeps the game values it stands for as custom properties, so exporting returns exactly the
imported values. Its visible colour is the client's palette colour, which Blender holds in linear space.
"""

from collections.abc import Callable
from pathlib import Path

import bpy

from ..formats import face_colour_to_rgb

# The 317 client starts at brightness 0.8 (client.java line 15624 of the decompile); its settings offer 0.9 to 0.6.
DEFAULT_BRIGHTNESS = 0.8
# A textured face whose PNG is missing shows this colour, so that it stands out.
MISSING_TEXTURE = (1.0, 0.0, 1.0, 1.0)

FACE_COLOUR = "rs_face_colour"
TEXTURE_ID = "rs_texture_id"
ALPHA = "rs_alpha"
STACKED = "rs_stacked"

type FindTexture = Callable[[int], Path | None]


def face_material(
    colour: int | None,
    texture: int | None,
    alpha: int,
    find_texture: FindTexture | None = None,
    brightness: float = DEFAULT_BRIGHTNESS,
) -> bpy.types.Material:
    if texture is not None:
        material = bpy.data.materials.new(f"RS_Texture_{texture}_{alpha}")
        material[TEXTURE_ID] = texture
        _show_texture(material, texture, find_texture)
    elif colour is not None:
        material = bpy.data.materials.new(f"RS_Colour_{colour}_{alpha}")
        material[FACE_COLOUR] = colour
        _show_colour(material, colour, brightness)
    else:
        raise ValueError("a face needs either a face colour or a texture ID")
    material[ALPHA] = alpha
    if alpha:
        _show_alpha(material, alpha)
    return material


def material_values(material: bpy.types.Material | None) -> tuple[int | None, int | None, int]:
    """Return the face colour, texture ID and alpha a material stands for."""
    if material is None:
        raise ValueError("a face uses an empty material slot")
    if FACE_COLOUR not in material and TEXTURE_ID not in material:
        raise ValueError(
            f"material {material.name!r} has no RuneScape face colour or texture ID; "
            "run Upgrade RS Materials on materials from older versions, or re-import the model"
        )
    colour = material[FACE_COLOUR] if FACE_COLOUR in material else None
    texture = material[TEXTURE_ID] if TEXTURE_ID in material else None
    return colour, texture, material.get(ALPHA, 0)


def show_stacked(material: bpy.types.Material) -> None:
    """Draw a material whose faces share their corners with another textured face.

    Such faces showed black with the Dithered method, which Blender issue 136453 says draws only the last of several
    coplanar faces correctly; that this is the whole cause is a guess. Blending shows them with no black, and culling
    hides the see-through back faces, as the client's own winding test does (ZKARKDQW.java line 4455 of the 317
    decompile).
    """
    material[STACKED] = True
    material.surface_render_method = "BLENDED"
    material.use_backface_culling = True


def stop_blending(material: bpy.types.Material) -> None:
    """Turn off a material's blending, unless its faces are stacked, which show black without it."""
    if STACKED not in material:
        material.blend_method = "OPAQUE"


def write_values(material: bpy.types.Material, colour: int | None, texture: int | None, alpha: int) -> None:
    """Store game values on an existing material without changing how it looks."""
    for key, value in ((FACE_COLOUR, colour), (TEXTURE_ID, texture)):
        if value is None:
            material.pop(key, None)
        else:
            material[key] = value
    material[ALPHA] = alpha


def _principled(material: bpy.types.Material) -> bpy.types.Node:
    if material.node_tree is None:
        material.use_nodes = True
    return next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _show_colour(material: bpy.types.Material, colour: int, brightness: float) -> None:
    linear = (*(srgb_to_linear(c / 255) for c in face_colour_to_rgb(colour, brightness)), 1.0)
    material.diffuse_color = linear  # pyrefly: ignore[bad-assignment]
    _principled(material).inputs["Base Color"].default_value = linear


def _show_texture(material: bpy.types.Material, texture: int, find_texture: FindTexture | None) -> None:
    path = find_texture(texture) if find_texture else None
    bsdf = _principled(material)
    if path is None:
        material.diffuse_color = MISSING_TEXTURE  # pyrefly: ignore[bad-assignment]
        bsdf.inputs["Base Color"].default_value = MISSING_TEXTURE
        return
    nodes = material.node_tree.nodes
    image = nodes.new("ShaderNodeTexImage")
    image.image = bpy.data.images.load(str(path), check_existing=True)
    # The client reads one texel per pixel without filtering (Graphics3D.rasterTextureAffineLine in the 2018 client).
    # The texture PNGs have an alpha channel, so it is linked too; which texels the client draws see-through is
    # unverified.
    image.interpolation = "Closest"
    material.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    material.node_tree.links.new(image.outputs["Alpha"], bsdf.inputs["Alpha"])


def _show_alpha(material: bpy.types.Material, alpha: int) -> None:
    # The client blends new pixel * (256 - alpha) / 256 over what is already drawn.
    _principled(material).inputs["Alpha"].default_value = (256 - alpha) / 256
    material.surface_render_method = "BLENDED"


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
