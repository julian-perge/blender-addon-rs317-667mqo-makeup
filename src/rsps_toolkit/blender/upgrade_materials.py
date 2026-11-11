"""Upgrade RS Materials: store the game values that older add-on versions kept only in material names and nodes.

The face colour, texture ID and alpha go on each material, as face_materials stores them for imports. Materials the
PMN tool made also get the texture triangle the original exporter wrote for their faces (ADR 0008).
"""

import re

import bmesh
import bpy

from ..formats.colour import original_exporter_colour
from . import rs_layers, texture_triangles
from .face_materials import FACE_COLOUR, STACKED, TEXTURE_ID, face_material, material_values, write_values
from .preferences import brightness

# Materials made before the game values were stored on them: by the original 317 importer and the 667 importer
# (importer_667.py), which named them RS_Color_<colour> or Texture_<id>, and by the PMN tool, which named them
# PMN_<image name>. The 667 importer also appended _Alpha_<alpha>, which the alpha read from the material repeats.
# Blender appends .001 and so on to repeated names, and the Aether panel appends _unique to the copies it makes.
_LEGACY_COLOUR = re.compile(r"^RS_Color_(\d+)(?:_Alpha_\d+)?$")
_LEGACY_TEXTURE = re.compile(r"^Texture_(\d+)(?:_Alpha_\d+)?$")
# The original exporter took the first number after PMN_ as the texture ID.
_LEGACY_PMN = re.compile(r"^PMN_.*?(\d+)")
_COPY_SUFFIXES = re.compile(r"(?:\.\d{3}|_unique)+$")
IMPORTER, PMN_TOOL = "importer", "PMN tool"


def _legacy_identity(name: str) -> tuple[int | None, int | None, str] | None:
    """The face colour or texture ID in a legacy material name, and what made it: IMPORTER or PMN_TOOL."""
    name = _COPY_SUFFIXES.sub("", name)
    for pattern, is_texture in ((_LEGACY_COLOUR, False), (_LEGACY_TEXTURE, True)):
        match = pattern.match(name)
        if match and int(match[1]) <= 0xFFFF:
            return (None, int(match[1]), IMPORTER) if is_texture else (int(match[1]), None, IMPORTER)
    match = _LEGACY_PMN.match(name)
    if match and int(match[1]) <= 0xFFFF:
        return None, int(match[1]), PMN_TOOL
    return None


def _legacy_alpha(material: bpy.types.Material) -> int | None:
    """The alpha the original importers set up on a material, or None if they set up none.

    They switched the material to blending and set the shader's Alpha input to (255 - alpha) / 255 for every face
    of a model with face alphas, except faces at 255. A stacked material is blended without any face alpha.
    """
    if STACKED in material or material.surface_render_method != "BLENDED" or material.node_tree is None:
        return None
    shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        return None
    return min(255, max(0, round(255 - shader.inputs["Alpha"].default_value * 255)))


class RSPS_OT_upgrade_materials(bpy.types.Operator):
    """Store the face colour, texture ID and alpha that older add-on versions kept only in material names"""

    bl_idname = "rsps.upgrade_materials"
    bl_label = "Upgrade RS Materials"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not objects:
            self.report({"WARNING"}, "Select the mesh objects whose materials to upgrade.")
            return {"CANCELLED"}
        report = _Report()
        for obj in objects:
            _upgrade(obj, report)
        self.report({"WARNING"} if report.needs_attention() else {"INFO"}, report.message())
        return {"FINISHED"}


class _Report:
    def __init__(self) -> None:
        self.upgraded: set[str] = set()
        self.unreadable: set[str] = set()
        self.invisible: set[str] = set()
        self.no_triangle: set[str] = set()
        self.too_many: set[str] = set()
        self.shared = 0
        self.untextured = 0

    def needs_attention(self) -> bool:
        return bool(
            self.unreadable or self.invisible or self.no_triangle or self.too_many or self.shared or self.untextured
        )

    def message(self) -> str:
        # Blender shows only the last report in the status bar, so everything goes into one.
        message = f"Upgraded {len(self.upgraded)} materials."
        if self.unreadable:
            message += f" Could not read game values from: {', '.join(sorted(self.unreadable))}."
        if self.invisible:
            message += (
                " Set to alpha 255, which the game does not draw, because their model has face alphas and they had"
                f" none set up; check they should be invisible: {', '.join(sorted(self.invisible))}."
            )
        if self.no_triangle:
            message += (
                " Left without game values, since no face's UVs give a texture triangle; give their faces usable UVs"
                f" and upgrade again: {', '.join(sorted(self.no_triangle))}."
            )
        if self.too_many:
            message += (
                " Left without a texture triangle, since the model would need more than 64:"
                f" {', '.join(sorted(self.too_many))}."
            )
        if self.shared:
            message += (
                f" {self.shared} faces of PMN_ materials whose UVs gave no texture triangle now share their"
                " material's, where the original exporter wrote them untextured."
            )
        if self.untextured:
            message += (
                f" {self.untextured} faces of PMN_ materials shared with another object had no UVs giving a texture"
                " triangle, so they are untextured in the colour the original exporter gave them."
            )
        return message


def _upgrade(obj: bpy.types.Object, report: _Report) -> None:
    mesh = obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    materials = list(dict.fromkeys(m for m in mesh.materials if m))
    # In a model with face alphas, an importer material without alpha set up stands for alpha 255, which the game
    # does not draw; the user chose this reading on 2026-11-05.
    has_alphas = any(_legacy_alpha(m) is not None for m in materials)
    pmn: list[tuple[bpy.types.Material, int]] = []
    for material in materials:
        has_values = FACE_COLOUR in material or TEXTURE_ID in material
        identity = _legacy_identity(material.name)
        if identity is None:
            if not has_values:
                report.unreadable.add(material.name)
            continue
        colour, texture, source = identity
        alpha = _legacy_alpha(material)
        if source == PMN_TOOL:
            # A PMN tool material also needs its faces' triangle, which a material shared with another object, or
            # one upgraded before triangles were fitted, has values but lacks.
            pmn.append((material, 0 if alpha is None else alpha))
            continue
        if has_values:
            continue
        if alpha is None:
            alpha = 255 if has_alphas else 0
            if alpha == 255:
                report.invisible.add(material.name)
        write_values(material, colour, texture, alpha)
        report.upgraded.add(material.name)
    if pmn:
        _give_pmn_triangles(obj, mesh, pmn, report)


def _give_pmn_triangles(
    obj: bpy.types.Object, mesh: bpy.types.Mesh, pmn: list[tuple[bpy.types.Material, int]], report: _Report
) -> None:
    """Give each PMN tool material's faces the triangle the original exporter wrote, and the material its values."""
    editing = obj.mode == "EDIT"
    bm = bmesh.from_edit_mesh(mesh) if editing else bmesh.new()
    if not editing:
        bm.from_mesh(mesh)
    try:
        texture_triangles.ready(bm, [])
        layer = bm.faces.layers.int[rs_layers.FACE_TEXTURE_TRIANGLE]
        found = []
        for material, alpha in pmn:
            slots = {i for i, m in enumerate(mesh.materials) if m == material}
            faces = [f for f in bm.faces if f.material_index in slots]
            if not faces:
                # With no faces on this object there is no triangle to fit, only the values to store.
                _store_pmn_values(material, alpha, report)
                continue
            if any(rs_layers.bmesh_texture_triangle(f, layer) is not None for f in faces):
                continue
            result = texture_triangles.original_exporter_triangle(bm, faces)
            if result is None:
                if TEXTURE_ID not in material:
                    report.no_triangle.add(material.name)
                else:
                    # The material got its values from another object, so only these faces lack a triangle. The
                    # user chose on 2026-11-06 to write them untextured, as the original exporter did.
                    _make_untextured(mesh, faces, material, alpha)
                    report.untextured += len(faces)
                continue
            triangle, fitted_face, before = result
            found.append((fitted_face, material, alpha, triangle, before))
        # The original exporter added triangles in the order of the faces it fitted them to.
        for _, material, alpha, triangle, before in sorted(found, key=lambda f: f[0]):
            slots = {i for i, m in enumerate(mesh.materials) if m == material}
            faces = [f for f in bm.faces if f.material_index in slots]
            try:
                texture_triangles.give(mesh, bm, faces, triangle)
            except ValueError:
                report.too_many.add(material.name)
                continue
            report.shared += before
            _store_pmn_values(material, alpha, report)
        if editing:
            bmesh.update_edit_mesh(mesh)
        else:
            bm.to_mesh(mesh)
    finally:
        if not editing:
            bm.free()


def _make_untextured(
    mesh: bpy.types.Mesh, faces: list[bmesh.types.BMFace], material: bpy.types.Material, alpha: int
) -> None:
    """Give the faces the face colour the original exporter wrote for the material: its Base Color, converted."""
    shader = None
    if material.node_tree is not None:
        shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    # The original exporter wrote colour 0 for a material without a Principled shader.
    colour = 0
    if shader is not None:
        red, green, blue, _ = shader.inputs["Base Color"].default_value
        colour = original_exporter_colour(red, green, blue)
    slot = next((i for i, m in enumerate(mesh.materials) if _values(m) == (colour, None, alpha)), None)
    if slot is None:
        mesh.materials.append(face_material(colour, None, alpha, brightness=brightness()))
        slot = len(mesh.materials) - 1
    for face in faces:
        face.material_index = slot


def _values(material: bpy.types.Material | None) -> tuple[int | None, int | None, int] | None:
    try:
        return material_values(material)
    except ValueError:
        return None


def _store_pmn_values(material: bpy.types.Material, alpha: int, report: _Report) -> None:
    if TEXTURE_ID in material:
        return
    identity = _legacy_identity(material.name)
    assert identity is not None
    write_values(material, None, identity[1], alpha)
    report.upgraded.add(material.name)


classes = (RSPS_OT_upgrade_materials,)
