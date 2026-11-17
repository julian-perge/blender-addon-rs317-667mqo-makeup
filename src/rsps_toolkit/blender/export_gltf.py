"""File > Export > RS Scene (.glb): the selected meshes as one binary glTF file that the profile page draws with no
lights (spec 140, ADR 0028).

The operator exports copies of the meshes, because the stock exporter validates the meshes that it exports and so
removes faces from them (`docs/research/82-gltf-export.md`, "Form of the exporter"). Each copy draws one colour
attribute through an unlit material, and the stock exporter writes the file with fixed settings."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import bpy
from bpy_extras.io_utils import ExportHelper

from ..formats.attribute_list import attribute_names, naming_problems

# An original keeps this suffix on its name while its copy holds the name, so that the file has the names of the scene.
SET_ASIDE_SUFFIX = ".rs_scene_original"


class RS_OT_export_scene(bpy.types.Operator, ExportHelper):
    """Export the selected meshes as one binary glTF file whose unlit materials draw a colour attribute"""

    bl_idname = "export_scene.rs_scene"
    bl_label = "Export RS Scene"

    filename_ext = ".glb"
    filter_glob: bpy.props.StringProperty(default="*.glb", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    colour_attribute: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Colour attribute",
        description="The colour attribute that the page draws, written as COLOR_0",
        default="rs_lit",
    )
    extra_attributes: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Extra attributes",
        description="Comma-separated colour attributes, written as COLOR_1, COLOR_2 and up in this order",
        default="",
    )

    def execute(self, context):
        # The export reads the Edit Mode edits and gives back the mode, as the model export does (ADR 0010). The owner
        # chose this in the build of issue 141 on 2026-11-17. The stock exporter goes to frame 0 and goes back only when
        # it does not fail (`io_scene_gltf2/blender/exp/export.py`, `save`), so the frame is set back here too.
        scene = context.scene
        mode = context.object.mode if context.object is not None else "OBJECT"
        frame = scene.frame_current
        if mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            return self._export(context)
        finally:
            if scene.frame_current != frame:
                scene.frame_set(frame)
            if mode != "OBJECT":
                bpy.ops.object.mode_set(mode=mode)

    def _export(self, context) -> set[str]:
        colour = self.colour_attribute.strip()
        extras = attribute_names(self.extra_attributes)
        selected = list(context.selected_objects)
        meshes = [obj for obj in selected if obj.type == "MESH"]
        if not meshes:
            problems = ["Select the meshes to export."]
        else:
            problems = naming_problems(colour, extras) or attribute_problems(meshes, (colour, *extras))
        if problems:
            self.report({"ERROR"}, " ".join(problems))
            return {"CANCELLED"}
        left_out = [obj.name for obj in selected if obj.type != "MESH"]
        if left_out:
            self.report({"WARNING"}, f"Left out {', '.join(left_out)}: only meshes are exported.")
        with _copies(context.scene.collection, meshes, colour, extras) as copies:
            for obj in selected:
                obj.select_set(False)
            for copy in copies:
                copy.select_set(True)
            try:
                write_glb(Path(self.filepath))
            finally:
                for obj in selected:
                    obj.select_set(True)
        noun = "mesh" if len(meshes) == 1 else "meshes"
        self.report({"INFO"}, f"Exported {len(meshes)} {noun} to {self.filepath}.")
        return {"FINISHED"}


def attribute_problems(objects: Sequence[bpy.types.Object], names: Sequence[str]) -> list[str]:
    """One sentence for each mesh object and each name in `names` that is not a colour attribute of its mesh."""
    problems = []
    for obj in objects:
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        for name in names:
            if mesh.color_attributes.find(name) != -1:
                continue
            if mesh.attributes.find(name) != -1:
                problems.append(f"{obj.name}: {name} is not a colour attribute.")
            else:
                problems.append(f"{obj.name} has no colour attribute {name}.")
    return problems


def write_glb(path: Path) -> None:
    """Write the selected objects to `path` with the stock exporter. The settings are fixed (spec 140, rule 11): a
    binary file, the custom properties as extras and no Draco. The file holds the active scene only. The colour settings are the defaults, and they are given
    here because the copies need them: a material's colour attribute is `COLOR_0`, and every other colour attribute of
    the mesh follows in the order of the mesh."""
    # The stubs do not list the operators of add-ons, and the glTF exporter is one.
    bpy.ops.export_scene.gltf(  # pyrefly: ignore[missing-attribute]
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        use_active_scene=True,
        export_extras=True,
        export_draco_mesh_compression_enable=False,
        export_vertex_color="MATERIAL",
        export_all_vertex_colors=True,
    )


@contextmanager
def _copies(
    collection: bpy.types.Collection, objects: Sequence[bpy.types.Object], colour: str, extras: Sequence[str]
) -> Iterator[list[bpy.types.Object]]:
    """Copies of `objects` and their meshes in `collection`, with the names of the originals. Each mesh copy has only
    the colour attributes `colour` and `extras`, and the unlit material that draws `colour`. On leaving, the copies and
    the material are removed and the originals get their names back."""
    material: bpy.types.Material | None = None
    mesh_copies: dict[bpy.types.Mesh, bpy.types.Mesh] = {}
    copies: list[bpy.types.Object] = []
    pairs: list[tuple[bpy.types.ID, bpy.types.ID]] = []
    renamed: list[tuple[bpy.types.ID, str]] = []
    try:
        material = bpy.data.materials.new(colour)
        _draw_unlit(material, colour)
        for obj in objects:
            mesh = obj.data
            assert isinstance(mesh, bpy.types.Mesh)
            if mesh not in mesh_copies:
                mesh_copies[mesh] = mesh.copy()
                pairs.append((mesh, mesh_copies[mesh]))
                _prepare_mesh(mesh_copies[mesh], material, colour, extras)
            copy = obj.copy()
            copies.append(copy)
            copy.data = mesh_copies[mesh]
            for slot in copy.material_slots:
                slot.link = "DATA"
            collection.objects.link(copy)
            pairs.append((obj, copy))
        for original, copy in pairs:
            name = original.name
            original.name = name + SET_ASIDE_SUFFIX
            renamed.append((original, name))
            copy.name = name
        yield copies
    finally:
        for copy in copies:
            bpy.data.objects.remove(copy)
        for mesh in mesh_copies.values():
            bpy.data.meshes.remove(mesh)
        if material is not None:
            bpy.data.materials.remove(material)
        for original, name in renamed:
            original.name = name


def _prepare_mesh(mesh: bpy.types.Mesh, material: bpy.types.Material, colour: str, extras: Sequence[str]) -> None:
    mesh.materials.clear()
    mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    _keep_colour_attributes(mesh, colour, extras)


def _keep_colour_attributes(mesh: bpy.types.Mesh, colour: str, extras: Sequence[str]) -> None:
    """Remove every colour attribute of `mesh` but `colour` and `extras`, and make the extras again in the order of
    `extras`. The stock exporter writes the colour attributes that no material uses in the order of the mesh, so this
    makes `COLOR_1` and up follow the list."""
    for name in [attribute.name for attribute in mesh.color_attributes if attribute.name not in (colour, *extras)]:
        mesh.color_attributes.remove(mesh.color_attributes[name])
    for name in extras:
        old = mesh.color_attributes[name]
        domain, data_type = old.domain, old.data_type
        values = [0.0] * (len(old.data) * 4)
        old.data.foreach_get("color", values)
        mesh.color_attributes.remove(old)
        new = mesh.color_attributes.new(name, data_type, domain)
        new.data.foreach_set("color", values)


def _draw_unlit(material: bpy.types.Material, colour: str) -> None:
    """Give `material` only a Color Attribute node of `colour` that feeds the Material Output. The stock exporter
    writes this shape as `KHR_materials_unlit` with the attribute as `COLOR_0` (ADR 0026). The nodes are made by type,
    because Blender can translate the names of the nodes that a new material starts with."""
    tree = material.node_tree
    assert tree is not None
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    attribute = tree.nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = colour
    tree.links.new(attribute.outputs["Color"], output.inputs["Surface"])


def menu_entry(self, context):
    self.layout.operator(RS_OT_export_scene.bl_idname, text="RS Scene (.glb)")


classes = (RS_OT_export_scene,)
