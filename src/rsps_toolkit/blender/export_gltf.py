"""File > Export > RS Scene (.glb): the selected meshes and rigs as one binary glTF file that the profile page draws
with no lights, with one clip for each action of a rig (spec 140, ADR 0028).

The operator exports copies of the meshes, because the stock exporter validates the meshes that it exports and so
removes faces from them (`docs/research/82-gltf-export.md`, "Form of the exporter"). On the copy, each face that uses
the vertices of an earlier face gets vertices of its own, so that the validation keeps it (issue 121). Each copy draws
one colour attribute through unlit materials, and the stock exporter writes the file with fixed settings. A copy of a
player or NPC mesh gets one material for each pair of face colour and face alpha, with the pair as extras (issue 143).
The rigs are exported as copies too, so that each action gets an NLA track of its own (issue 145)."""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
from bpy_extras.io_utils import ExportHelper

from ..formats.attribute_list import attribute_names, naming_problems
from ..formats.repeated_faces import repeated_faces
from .appearance_preview import FACE_ALPHA_ATTRIBUTE, FACE_ATTRIBUTE, FACE_COLOUR_ATTRIBUTE
from .face_materials import ALPHA, FACE_COLOUR

# An original keeps this suffix on its name while its copy holds the name, so that the file has the names of the scene.
SET_ASIDE_SUFFIX = ".rs_scene_original"

# A pair of face colour and face alpha, or None for the one material of a mesh with no game values on its faces.
type MaterialKey = tuple[int, int] | None


class RS_OT_export_scene(bpy.types.Operator, ExportHelper):
    """Export the selected meshes and rigs as one binary glTF file whose unlit materials draw a colour attribute, with
    one clip for each action of a rig"""

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
        rigs = [obj for obj in selected if obj.type == "ARMATURE"]
        if not meshes:
            problems = ["Select the meshes to export."]
        else:
            problems = naming_problems(colour, extras)
            if not problems:
                problems = attribute_problems(meshes, (colour, *extras)) + face_value_problems(meshes)
        if problems:
            self.report({"ERROR"}, " ".join(problems))
            return {"CANCELLED"}
        left_out = [obj.name for obj in selected if obj.type not in ("MESH", "ARMATURE")]
        if left_out:
            self.report({"WARNING"}, f"Left out {', '.join(left_out)}: only meshes and rigs are exported.")
        with _copies(context.scene.collection, meshes, rigs, colour, extras) as copies:
            for obj in selected:
                obj.select_set(False)
            for copy in copies:
                copy.select_set(True)
            try:
                write_glb(Path(self.filepath))
            finally:
                for obj in selected:
                    obj.select_set(True)
        counted = f"{len(meshes)} {'mesh' if len(meshes) == 1 else 'meshes'}"
        if rigs:
            counted += f" and {len(rigs)} {'rig' if len(rigs) == 1 else 'rigs'}"
        self.report({"INFO"}, f"Exported {counted} to {self.filepath}.")
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


def face_value_problems(objects: Sequence[bpy.types.Object]) -> list[str]:
    """One sentence for each mesh object that Create Player, Create NPC or Make Rig built before meshes stored the face
    colour and face alpha of each face. The owner chose the wording in the build of issue 143 on 2026-11-17."""
    problems = []
    names = (FACE_COLOUR_ATTRIBUTE, FACE_ALPHA_ATTRIBUTE)
    for obj in objects:
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        if FACE_ATTRIBUTE in mesh.attributes and any(name not in mesh.attributes for name in names):
            problems.append(
                f"{obj.name} was built before meshes stored their face colours. Run Update Player on a player, or "
                "Create NPC or Make Rig again on an NPC."
            )
    return problems


def write_glb(path: Path) -> None:
    """Write the selected objects to `path` with the stock exporter. The settings are fixed (spec 140, rule 11): a
    binary file, the custom properties as extras and no Draco. The file holds the active scene only. The colour settings
    are the defaults, and they are given here because the copies need them: a material's colour attribute is `COLOR_0`,
    and every other colour attribute of the mesh follows in the order of the mesh.

    The animation settings write one clip for each action of a rig copy (spec 140, rule 10). The animation mode
    `ACTIONS` is the default, and it writes `STEP` for a channel whose keys are constant (`docs/research/82-gltf-export.md`,
    row 6). The fallback `STEP` also makes a channel of other keys `STEP`, because the client does not blend between
    frames. With one rig in the file, the default `export_anim_single_armature` adds every action of the file that keys a
    bone, so it is off. Each clip starts at 0 seconds, so that the page plays it at once. The owner chose this in the
    build of issue 145 on 2026-11-17."""
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
        export_animation_mode="ACTIONS",
        export_sampling_interpolation_fallback="STEP",
        export_anim_single_armature=False,
        export_anim_slide_to_zero=True,
    )


@contextmanager
def _copies(
    collection: bpy.types.Collection,
    objects: Sequence[bpy.types.Object],
    rigs: Sequence[bpy.types.Object],
    colour: str,
    extras: Sequence[str],
) -> Iterator[list[bpy.types.Object]]:
    """Copies of the mesh objects `objects` and their meshes, and of the armature objects `rigs`, in `collection`, with
    the names of the originals. Each mesh copy has only the colour attributes `colour` and `extras`, and unlit materials
    that draw `colour`. The meshes share one material for each key. A mesh copy that a rig of `rigs` moves through its
    parent or an Armature modifier is moved by the copy of that rig. Each rig copy plays a copy of each of its actions
    with no custom properties, on a track of its own (`_one_track_per_action`).
    On leaving, the copies and the materials are removed and the originals get their names back."""
    materials: dict[MaterialKey, bpy.types.Material] = {}
    mesh_copies: dict[bpy.types.Mesh, bpy.types.Mesh] = {}
    action_copies: dict[bpy.types.Action, bpy.types.Action] = {}
    copies: list[bpy.types.Object] = []
    pairs: list[tuple[bpy.types.ID, bpy.types.ID]] = []
    renamed: list[tuple[bpy.types.ID, str]] = []

    def material_of(key: MaterialKey) -> bpy.types.Material:
        if key not in materials:
            # The material goes into the dict before it is drawn, so the clean-up removes it if the drawing fails.
            materials[key] = _new_material(key, colour)
            _draw_unlit(materials[key], colour, 0 if key is None else key[1])
        return materials[key]

    def action_copy(action: bpy.types.Action) -> bpy.types.Action:
        # A baked clip's action holds its clip record, with the local path of the cache, as a custom property, and the
        # stock exporter writes the custom properties of an action as extras. The owner chose in the build of issue
        # 145 on 2026-11-17 that the clips have no extras.
        if action not in action_copies:
            action_copies[action] = action.copy()
            pairs.append((action, action_copies[action]))
            for key in list(action_copies[action].keys()):
                del action_copies[action][key]
        return action_copies[action]

    try:
        rig_copies: dict[bpy.types.Object, bpy.types.Object] = {}
        for rig in rigs:
            rig_copies[rig] = rig.copy()
            copies.append(rig_copies[rig])
            collection.objects.link(rig_copies[rig])
            pairs.append((rig, rig_copies[rig]))
            _one_track_per_action(rig, rig_copies[rig], action_copy)
        for obj in objects:
            mesh = obj.data
            assert isinstance(mesh, bpy.types.Mesh)
            if mesh not in mesh_copies:
                mesh_copies[mesh] = mesh.copy()
                pairs.append((mesh, mesh_copies[mesh]))
                _prepare_mesh(mesh_copies[mesh], material_of, colour, extras)
            copy = obj.copy()
            copies.append(copy)
            copy.data = mesh_copies[mesh]
            for slot in copy.material_slots:
                slot.link = "DATA"
            if copy.parent in rig_copies:
                copy.parent = rig_copies[copy.parent]
            for modifier in copy.modifiers:
                if isinstance(modifier, bpy.types.ArmatureModifier) and modifier.object in rig_copies:
                    modifier.object = rig_copies[modifier.object]
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
        for action in action_copies.values():
            bpy.data.actions.remove(action)
        for mesh in mesh_copies.values():
            bpy.data.meshes.remove(mesh)
        for material in materials.values():
            bpy.data.materials.remove(material)
        for original, name in renamed:
            original.name = name


def _played_actions(rig: bpy.types.Object) -> list[tuple[bpy.types.Action, bpy.types.ActionSlot | None]]:
    """Each action of `rig` once, with the slot that it first plays: the active action, then the action of each strip of
    the tracks, also of a muted strip or track. The owner chose in the build of issue 145 on 2026-11-17 that a muted
    strip is a clip too, and spec decision 6 gives one clip for each action. In tweak mode, Blender holds the active
    action aside and has no slot for it, so it plays its only slot for objects, if it has one (a guess of that build)."""
    animation = rig.animation_data
    if animation is None:
        return []
    if animation.use_tweak_mode:
        active = animation.action_tweak_storage
        slots = [] if active is None else [slot for slot in active.slots if slot.target_id_type == "OBJECT"]
        played = [(active, slots[0] if len(slots) == 1 else None)]
    else:
        played = [(animation.action, animation.action_slot)]
    played += [(strip.action, strip.action_slot) for track in animation.nla_tracks for strip in track.strips]
    first: dict[bpy.types.Action, bpy.types.ActionSlot | None] = {}
    for action, slot in played:
        if action is not None and action not in first:
            first[action] = slot
    return list(first.items())


def _one_track_per_action(
    rig: bpy.types.Object, copy: bpy.types.Object, action_copy: Callable[[bpy.types.Action], bpy.types.Action]
) -> None:
    """Give `copy` no active action and one NLA track for each action of `rig`, with the copy of that action that
    `action_copy` gives. The stock exporter writes the action of a track with one strip as a clip, and leaves out a
    track with more strips and a muted strip (`io_scene_gltf2/blender/exp/animation/action.py`, `__track_extract`). A
    strip plays the slot of the copy that has the identifier of the rig's slot, which tells the exporter which channels
    of the action are the rig's."""
    copy.animation_data_clear()
    played = _played_actions(rig)
    if not played:
        return
    copied = copy.animation_data_create()
    for action, slot in played:
        new = action_copy(action)
        track = copied.nla_tracks.new()
        strip = track.strips.new(new.name, round(new.frame_range[0]), new)
        if slot is not None:
            strip.action_slot = next(s for s in new.slots if s.identifier == slot.identifier)


def _prepare_mesh(
    mesh: bpy.types.Mesh,
    material_of: Callable[[MaterialKey], bpy.types.Material],
    colour: str,
    extras: Sequence[str],
) -> None:
    keys = _face_keys(mesh)
    slots = list(dict.fromkeys(keys))
    mesh.materials.clear()
    for key in slots:
        mesh.materials.append(material_of(key))
    index = {key: i for i, key in enumerate(slots)}
    mesh.polygons.foreach_set("material_index", [index[key] for key in keys])
    # Blender writes a mesh back from bmesh with its attributes ordered by domain and data type, so the faces are
    # separated before the colour attributes are put in the order of the list.
    _separate_repeated_faces(mesh)
    _keep_colour_attributes(mesh, colour, extras)


def _face_keys(mesh: bpy.types.Mesh) -> list[MaterialKey]:
    """The material key of each face of `mesh`: its pair of face colour and face alpha when the mesh has `rs_face`, and
    None otherwise (spec rules 6 and 7)."""
    if FACE_ATTRIBUTE not in mesh.attributes:
        return [None] * len(mesh.polygons)
    colour_attribute = mesh.attributes.get(FACE_COLOUR_ATTRIBUTE)
    alpha_attribute = mesh.attributes.get(FACE_ALPHA_ATTRIBUTE)
    assert colour_attribute is not None and alpha_attribute is not None
    colours = [0] * len(mesh.polygons)
    alphas = [0] * len(mesh.polygons)
    colour_attribute.data.foreach_get("value", colours)
    alpha_attribute.data.foreach_get("value", alphas)
    return list(zip(colours, alphas, strict=True))


def _separate_repeated_faces(mesh: bpy.types.Mesh) -> None:
    """Give each face of `mesh` that uses the vertices of an earlier face vertices of its own, so that the stock
    exporter's mesh validation keeps it (issue 121). The faces keep their order, and a new vertex copies the attributes
    and the vertex group weights of the vertex that it replaces."""
    corners = [0] * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", corners)
    repeated = repeated_faces(corners[face.loop_start : face.loop_start + face.loop_total] for face in mesh.polygons)
    if not repeated:
        return
    edit = bmesh.new()
    try:
        edit.from_mesh(mesh)
        edit.faces.ensure_lookup_table()
        for index in repeated:
            face = edit.faces[index]
            for vertex in list(face.verts):
                bmesh.utils.face_vert_separate(face, vertex)
        edit.to_mesh(mesh)
    finally:
        edit.free()


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


def _new_material(key: MaterialKey, colour: str) -> bpy.types.Material:
    """A new material for `key`, with no nodes drawn yet. The material of no pair has the name `colour`. A material of
    a pair has the name that `face_materials` gives a model import's material, and holds the pair as custom
    properties, which the stock exporter writes as extras."""
    if key is None:
        return bpy.data.materials.new(colour)
    face_colour, alpha = key
    material = bpy.data.materials.new(f"RS_Colour_{face_colour}_{alpha}")
    material[FACE_COLOUR] = face_colour
    material[ALPHA] = alpha
    return material


def _draw_unlit(material: bpy.types.Material, colour: str, alpha: int) -> None:
    """Give `material` only a Color Attribute node of `colour` that feeds the Material Output. The stock exporter
    writes this shape as `KHR_materials_unlit` with the attribute as `COLOR_0` (ADR 0026). The nodes are made by type,
    because Blender can translate the names of the nodes that a new material starts with.

    With an alpha, a Mix Shader puts a Transparent BSDF under the colour, with the opacity `(256 - alpha) / 256` of
    `face_materials._show_alpha` as its factor. The stock exporter writes this shape as `alphaMode` `BLEND` with the
    opacity as the alpha of `baseColorFactor` (`io_scene_gltf2/blender/exp/material/unlit.py`, `detect_mix_alpha`)."""
    tree = material.node_tree
    assert tree is not None
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    attribute = tree.nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = colour
    if not alpha:
        tree.links.new(attribute.outputs["Color"], output.inputs["Surface"])
        return
    mix = tree.nodes.new("ShaderNodeMixShader")
    transparent = tree.nodes.new("ShaderNodeBsdfTransparent")
    mix.inputs[0].default_value = (256 - alpha) / 256  # pyrefly: ignore[missing-attribute]
    tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    tree.links.new(attribute.outputs["Color"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])


def menu_entry(self, context):
    self.layout.operator(RS_OT_export_scene.bl_idname, text="RS Scene (.glb)")


classes = (RS_OT_export_scene,)
