"""Upgrade RS Materials: store the game values of the materials the PMN tool made, which stored none on them.

The texture ID from the material's name and the alpha from its shader go on each material, as face_materials stores
them for imports. The material's faces also get the texture triangle the original exporter wrote for them (ADR 0008).
"""

import re

import bmesh
import bpy

from ..formats.colour import original_exporter_colour
from . import rs_layers, texture_triangles
from .face_materials import FACE_COLOUR, TEXTURE_ID, face_material, material_values, write_values
from .preferences import brightness

# The PMN tool named its materials PMN_<image name> and stored no game values on them. The original exporter took the
# first number after PMN_ as the texture ID. Blender appends .001 and so on to repeated names, and the Aether panel
# appends _unique to the copies it makes.
_PMN_NAME = re.compile(r"^PMN_.*?(\d+)")
_COPY_SUFFIXES = re.compile(r"(?:\.\d{3}|_unique)+$")


def _pmn_texture_id(name: str) -> int | None:
    """The texture ID in a PMN tool material name, or None if the name is not one."""
    match = _PMN_NAME.match(_COPY_SUFFIXES.sub("", name))
    if match and int(match[1]) <= 0xFFFF:
        return int(match[1])
    return None


def _material_alpha(material: bpy.types.Material) -> int | None:
    """The alpha of a blended material, read from its shader's Alpha input as (255 - alpha) / 255, or None if the
    material is not blended or has no Principled shader.

    Unverified: the formula comes from the removed importers, and no PMN tool export has confirmed it (issue 32).
    """
    if material.surface_render_method != "BLENDED" or material.node_tree is None:
        return None
    shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        return None
    return min(255, max(0, round(255 - shader.inputs["Alpha"].default_value * 255)))


class RSPS_OT_upgrade_materials(bpy.types.Operator):
    """Store the texture ID and alpha of PMN tool materials, read from their names and shaders"""

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
        self.no_triangle: set[str] = set()
        self.too_many: set[str] = set()
        self.shared = 0
        self.untextured = 0

    def needs_attention(self) -> bool:
        return bool(self.unreadable or self.no_triangle or self.too_many or self.shared or self.untextured)

    def message(self) -> str:
        # Blender shows only the last report in the status bar, so everything goes into one.
        message = f"Upgraded {len(self.upgraded)} materials."
        if self.unreadable:
            message += f" Could not read game values from: {', '.join(sorted(self.unreadable))}."
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
    pmn: list[tuple[bpy.types.Material, int]] = []
    for material in materials:
        if _pmn_texture_id(material.name) is None:
            if FACE_COLOUR not in material and TEXTURE_ID not in material:
                report.unreadable.add(material.name)
            continue
        # A PMN tool material also needs its faces' triangle, which a material shared with another object, or one
        # upgraded before triangles were fitted, has values but lacks.
        alpha = _material_alpha(material)
        pmn.append((material, 0 if alpha is None else alpha))
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
    texture = _pmn_texture_id(material.name)
    assert texture is not None
    write_values(material, None, texture, alpha)
    report.upgraded.add(material.name)


classes = (RSPS_OT_upgrade_materials,)
