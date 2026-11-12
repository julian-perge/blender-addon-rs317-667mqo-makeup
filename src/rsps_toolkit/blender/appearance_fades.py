"""Face fades of a baked clip: materials whose opacity follows a keyed property, one per group of faces that fade alike.

A clip's alpha transforms (type 5) add to the alpha of every face with a given skin label, starting from the face's
rest alpha, so faces that share a label and a rest alpha always fade alike. Label groups with the same rest alpha and
the same alpha on every frame join into one fade group. Each fade group that a clip changes gets a property on the
clip's owner (the rig for a bone clip, the shape keys for a shape-key clip), keyed with the clip, and a material whose
driver turns the property into opacity as the client blends: (256 - alpha) / 256. Solid mode draws the lit vertex
colours without alpha, so the fades show in Material Preview and Rendered modes.
"""

from dataclasses import dataclass

import bpy

from ..animation.clip import PosedFrame
from .appearance_preview import FACE_ALPHA_ATTRIBUTE, FACE_LABEL_ATTRIBUTE, LIT_ATTRIBUTE

# Names a fade material's group property; the property sits on the clip's owner.
FADE_KEY = "rs_fade"
PROPERTY_PREFIX = "rs_fade_"


@dataclass(frozen=True)
class FadeGroup:
    # The skin labels of the group, lowest first. A group of one label keeps the names it had before groups joined.
    labels: tuple[int, ...]
    rest: int
    polygons: tuple[int, ...]
    # The group's alpha on each frame of the clip, in clip frame order.
    values: tuple[int, ...]

    @property
    def label(self) -> int:
        return self.labels[0]

    @property
    def prop(self) -> str:
        return f"{PROPERTY_PREFIX}{self.label}_{self.rest}"


def face_inputs(mesh: bpy.types.Mesh) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Each polygon's skin label and rest alpha, or None for a mesh built before players stored them."""
    labels, alphas = mesh.attributes.get(FACE_LABEL_ATTRIBUTE), mesh.attributes.get(FACE_ALPHA_ATTRIBUTE)
    if labels is None or alphas is None:
        return None
    return _values(labels, len(mesh.polygons)), _values(alphas, len(mesh.polygons))


def _values(attribute, count: int) -> tuple[int, ...]:
    out = [0] * count
    attribute.data.foreach_get("value", out)
    return tuple(out)


@dataclass(frozen=True)
class EarlierFades:
    """What the clips already baked on a rig do to each label group: its alpha on every key of each earlier action.

    A label group that no earlier clip fades is absent, and `of` gives it rest alpha on every key.
    """

    # The number of keys of each earlier action.
    lengths: tuple[int, ...]
    series: dict[tuple[int, int], tuple[tuple[float, ...], ...]]

    def of(self, label: int, rest: int) -> tuple[tuple[float, ...], ...]:
        known = self.series.get((label, rest))
        return known if known is not None else tuple((float(rest),) * length for length in self.lengths)


def fade_groups(
    inputs: list[tuple[tuple[int, ...], tuple[int, ...], tuple[PosedFrame, ...]]],
    earlier: EarlierFades | None = None,
) -> list[list[FadeGroup]]:
    """The fade groups of a player's mesh objects, one list per input: its polygons' labels, rest alphas and frames.

    Faces of one label and rest alpha always fade alike. Those label groups join into one fade group when their rest
    alpha, their alpha on every frame of the new clip and their alpha under every earlier clip are equal. The join
    runs over all objects, so a label group is in the same fade group on each of them, and a group fades only when
    the new clip or an earlier one changes it. Each list holds the groups that have polygons on that object.
    """
    earlier = earlier or EarlierFades((), {})
    values: dict[tuple[int, int], tuple[int, ...]] = {}
    members: list[dict[tuple[int, int], list[int]]] = []
    for labels, rests, posed in inputs:
        part: dict[tuple[int, int], list[int]] = {}
        for polygon, key in enumerate(zip(labels, rests, strict=True)):
            part.setdefault(key, []).append(polygon)
        for key, polygons in part.items():
            if key not in values:
                values[key] = tuple(
                    frame.alphas[polygons[0]] if frame.alphas is not None else key[1] for frame in posed
                )
        members.append(part)
    joined: dict[tuple[int, tuple[int, ...], tuple[tuple[float, ...], ...]], list[int]] = {}
    for (label, rest), series in sorted(values.items()):
        before = earlier.of(label, rest)
        if all(value == rest for value in series) and all(value == rest for run in before for value in run):
            continue
        joined.setdefault((rest, series, before), []).append(label)
    out = []
    for part in members:
        groups = []
        for (rest, series, _), labels in joined.items():
            polygons = sorted(polygon for label in labels for polygon in part.get((label, rest), ()))
            if polygons:
                groups.append(FadeGroup(tuple(labels), rest, tuple(polygons), series))
        out.append(groups)
    return out


def apply_fades(mesh_obj: bpy.types.Object, owner: bpy.types.ID, groups: list[FadeGroup]) -> None:
    """Give each group's polygons its fade material, reading the group's property on `owner`, at rest alpha.

    Polygons that a group no longer holds go back to the lit material, and a fade material no polygon uses is removed.
    """
    mesh = mesh_obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    indices = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", indices)
    for polygon, slot in enumerate(indices):
        material = mesh.materials[slot] if slot < len(mesh.materials) else None
        if material is not None and FADE_KEY in material:
            indices[polygon] = 0
    for group in groups:
        owner[group.prop] = float(group.rest)
        slot = next((i for i, m in enumerate(mesh.materials) if m is not None and m.get(FADE_KEY) == group.prop), None)
        if slot is None:
            mesh.materials.append(_fade_material(f"{mesh_obj.name} fade {group.label}", owner, group.prop))
            slot = len(mesh.materials) - 1
        # Like the lit material, a fade material shows only the front of each face, as the client does
        # (docs/research/render-priority.md, "Skip and cull"). A reused one made before players culled gets it too
        # (issue 28, decisions 1 and 4).
        mesh.materials[slot].use_backface_culling = True  # pyrefly: ignore[missing-attribute]
        for polygon in group.polygons:
            indices[polygon] = slot
    mesh.polygons.foreach_set("material_index", indices)
    used = set(indices)
    for index in reversed(range(len(mesh.materials))):
        material = mesh.materials[index]
        if material is not None and FADE_KEY in material and index not in used:
            # Removing a slot moves the later polygons' indices down by one.
            mesh.materials.pop(index=index)
            if material.users == 0:
                bpy.data.materials.remove(material)


def clear_fades(mesh_obj: bpy.types.Object) -> None:
    """Put every polygon back on the lit material and drop the fade materials nothing else uses."""
    mesh = mesh_obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    for index in reversed(range(len(mesh.materials))):
        material = mesh.materials[index]
        if material is not None and FADE_KEY in material:
            mesh.materials.pop(index=index)
            if material.users == 0:
                bpy.data.materials.remove(material)


def remove_unused(materials: list[bpy.types.Material | None]) -> None:
    for material in materials:
        if material is not None and FADE_KEY in material and material.users == 0:
            bpy.data.materials.remove(material)


def _fade_material(name: str, owner: bpy.types.ID, prop: str) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material[FADE_KEY] = prop
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.remove(nodes["Principled BSDF"])
    colour = nodes.new("ShaderNodeVertexColor")
    colour.layer_name = LIT_ATTRIBUTE
    emission = nodes.new("ShaderNodeEmission")
    clear = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    mix.name = "Fade"
    links.new(colour.outputs["Color"], emission.inputs["Color"])
    links.new(clear.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    driver = mix.inputs["Fac"].driver_add("default_value").driver
    driver.type = "SCRIPTED"
    variable = driver.variables.new()
    variable.name = "alpha"
    target = variable.targets[0]
    target.id_type = "KEY" if isinstance(owner, bpy.types.Key) else "OBJECT"
    target.id = owner
    target.data_path = f'["{prop}"]'
    driver.expression = "(256 - alpha) / 256"
    return material
