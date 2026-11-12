"""Writes a posed clip into an action that keys a player rig's joint and label bones."""

import bpy
from mathutils import Matrix, Quaternion, Vector

from ..animation.label_fit import LabelTransform, fit_frame, fit_label
from . import appearance_collection
from .appearance_fades import FADE_KEY, PROPERTY_PREFIX, EarlierFades, FadeGroup, face_inputs
from .appearance_pose import PosedPlayer
from .axes import GAME_TO_BLENDER

# The pose bone channels the bone bake keys, with their number of components, in the order `_basis` returns them.
CHANNELS = (("location", 3), ("rotation_quaternion", 4), ("scale", 3))
REST_CHANNELS = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)


def write(
    name: str, rig: bpy.types.Object, posed: PosedPlayer, fades: list[FadeGroup], *, smooth: bool
) -> tuple[bpy.types.Action, bpy.types.ActionSlot]:
    """A new action that moves the rig's bones through the posed clip, marked as a bake's with the hash of its keys,
    and the action's slot for the rig.

    Each joint bone is keyed with the fit of the labels it owns and each label bone with what its joint leaves
    (`_bone_rows`), on the ticks of the clip's schedule, with one curve per fade (`_fill_action`). A failure removes
    the half-made action.
    """
    armature = rig.data
    assert isinstance(armature, bpy.types.Armature)
    rows = _bone_rows(armature, rig.name, posed.vertices, posed.labels, posed.frames)
    new = bpy.data.actions.new(name)
    try:
        new[appearance_collection.RIG_ACTION_KEY] = ""
        slot = _fill_action(new, rig.name, rows, posed.schedule, fades, smooth)
        new[appearance_collection.RIG_ACTION_KEY] = appearance_collection.keys_hash(new)
    except Exception:
        bpy.data.actions.remove(new)
        raise
    return new, slot


def earlier_fades(actions: list[bpy.types.Action], objects: list[bpy.types.Object]) -> EarlierFades:
    """What the earlier bake actions do to each label group of the player's meshes, read from their fade curves.

    A polygon's alpha under an earlier clip is the curve of the property of its fade material, or its rest alpha when
    it has none. Every earlier action holds a curve for each property in use, which `rekey_fades` keeps true.
    """
    curves = [_fade_curves(action) for action in actions]
    lengths = tuple(len(_frames(action)) for action in actions)
    series: dict[tuple[int, int], tuple[tuple[float, ...], ...]] = {}
    for obj in objects:
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        faces = face_inputs(mesh)
        if faces is None:
            continue
        for polygon, (label, rest) in zip(mesh.polygons, zip(*faces, strict=True), strict=True):
            slot = polygon.material_index
            material = mesh.materials[slot] if slot < len(mesh.materials) else None
            if material is not None and FADE_KEY in material and (label, rest) not in series:
                prop = material[FADE_KEY]
                series[(label, rest)] = tuple(
                    found.get(prop, (float(rest),) * length) for found, length in zip(curves, lengths, strict=True)
                )
    return EarlierFades(lengths, series)


def rekey_fades(action: bpy.types.Action, fades: dict[str, tuple[float, ...]], keep: set[str]) -> None:
    """Replace the fade curves of an earlier bake action with one per property in `fades`, on the frames of its bone
    curves, and store the new hash of its keys, so the player stays unedited and the clip is not baked again.

    The curves of the properties in `keep` stay as they are, unless `fades` names them.
    """
    bag = action.layers[0].strips[0].channelbags[0]  # pyrefly: ignore[missing-attribute]
    frames = _frames(action)
    for curve in [c for c in bag.fcurves if _is_fade(c) and _prop(c) not in keep or _prop(c) in fades]:
        bag.fcurves.remove(curve)
    for prop, values in fades.items():
        _write_channel(bag, f'["{prop}"]', 0, "Fades", frames, list(values), ["CONSTANT"] * len(frames))
    action[appearance_collection.RIG_ACTION_KEY] = appearance_collection.keys_hash(action)


def _is_fade(curve: bpy.types.FCurve) -> bool:
    return curve.data_path.startswith(f'["{PROPERTY_PREFIX}')


def _prop(curve: bpy.types.FCurve) -> str:
    return curve.data_path.removeprefix('["').removesuffix('"]')


def _fade_curves(action: bpy.types.Action) -> dict[str, tuple[float, ...]]:
    bag = action.layers[0].strips[0].channelbags[0]  # pyrefly: ignore[missing-attribute]
    return {_prop(curve): tuple(p.co[1] for p in curve.keyframe_points) for curve in bag.fcurves if _is_fade(curve)}


def _frames(action: bpy.types.Action) -> list[int]:
    """The frames every curve of a bake action is keyed on, read from its first bone curve."""
    bag = action.layers[0].strips[0].channelbags[0]  # pyrefly: ignore[missing-attribute]
    curve = next((c for c in bag.fcurves if not _is_fade(c)), None)
    if curve is None:
        raise ValueError(f"The action {action.name!r} has no bone curve to read its frames from")
    return [round(p.co[0]) for p in curve.keyframe_points]


def _bone_rows(armature: bpy.types.Armature, rig_name: str, vertices, labels, posed) -> list[tuple[str, list]]:
    """Every joint and label bone with its channels on each frame of the clip, joints first, parents before children.

    A joint's world transform is the fit of the vertices of the labels it owns, or its parent's when it owns none on
    this body or the frame collapses them to a point. A label bone keeps only what its joint leaves: its label is
    fitted to the posed vertices taken back through its joint, so its own turn is the smallest that places them.
    Each bone is keyed with its world transform seen from its parent's (`_basis`).
    """
    prefix = appearance_collection.BONE_PREFIX
    joints = [bone for bone in armature.bones if not bone.name.startswith(prefix)]
    index = {bone.name: number for number, bone in enumerate(joints)}
    owner = {}
    for label in set(labels):
        bone = armature.bones.get(f"{prefix}{label}")
        if bone is None:
            raise ValueError(f"{rig_name} has no bone {prefix}{label} for its vertices")
        owner[label] = bone.parent.name if bone.parent is not None else None
    joint_of = tuple(index.get(owner[label] or "", -1) for label in labels)
    members: dict[int, list[int]] = {}
    for vertex, label in enumerate(labels):
        members.setdefault(label, []).append(vertex)
    rows: dict[str, list] = {bone.name: [] for bone in joints}
    rows.update({f"{prefix}{label}": [] for label in sorted(members)})
    for frame in posed:
        joint_fits = fit_frame(vertices, joint_of, frame.vertices)
        fits: dict[str | None, LabelTransform | None] = {None: None}
        world: dict[str | None, Matrix] = {None: Matrix.Identity(4)}
        for number, bone in enumerate(joints):
            parent = bone.parent.name if bone.parent is not None else None
            fit = joint_fits.get(number)
            if fit is None or fit.scale < 1e-9:
                fits[bone.name], world[bone.name] = fits[parent], world[parent]
            else:
                fits[bone.name], world[bone.name] = fit, _world(fit)
            rows[bone.name].append(_basis(world[bone.name], world[parent], bone))
        for label, vertex_ids in sorted(members.items()):
            joint = fits[owner[label]]
            targets = [frame.vertices[i] for i in vertex_ids]
            local = targets if joint is None else [joint.unapply(point) for point in targets]
            leftover = fit_label([vertices[i] for i in vertex_ids], local)
            bone = armature.bones[f"{prefix}{label}"]
            rows[bone.name].append(_basis(world[owner[label]] @ _world(leftover), world[owner[label]], bone))
    return list(rows.items())


def _world(fit: LabelTransform) -> Matrix:
    """The fitted transform in Blender axes, as a matrix that moves rest points."""
    turn = GAME_TO_BLENDER @ Quaternion(fit.rotation).to_matrix() @ GAME_TO_BLENDER.transposed()
    move = GAME_TO_BLENDER @ Vector(fit.translation)
    return Matrix.Translation((move.x, move.y, move.z)) @ (turn * fit.scale).to_4x4()


def _basis(world: Matrix, parent_world: Matrix, bone: bpy.types.Bone) -> tuple[float, ...]:
    """The bone's location, rotation and scale channels that make it move its rest frame by `world`.

    Blender poses a bone at parent pose @ parent rest.inverted() @ rest @ basis, and a parent whose rest frame
    `parent_world` moves has the pose parent_world @ parent rest, so the basis is rest.inverted() @
    parent_world.inverted() @ world @ rest. The Armature modifier then moves the bone's vertices by `world`. A
    uniform scale is the same in any frame, so the three scale channels are equal.
    """
    rest = bone.matrix_local
    location, rotation, scale = (rest.inverted() @ parent_world.inverted() @ world @ rest).decompose()
    return (
        location.x,
        location.y,
        location.z,
        rotation.w,
        rotation.x,
        rotation.y,
        rotation.z,
        scale.x,
        scale.y,
        scale.z,
    )


def _fill_action(
    action: bpy.types.Action, rig_name: str, rows, schedule, fades, smooth: bool = False
) -> bpy.types.ActionSlot:
    """Write one curve per bone channel and per fade group: rest on Blender frame 0, then each frame from its first
    tick, the last one keyed again where the clip ends, so the strip's Hold Forward keeps the clip's last pose.

    Without `smooth` each frame holds for its run of ticks, as the client shows it. With `smooth` the bone channels
    blend linearly from each frame to the next and the last frame holds until the clip ends; fades still step.
    Blender frame 1 is the tick the sequence starts on, as in `appearance_shape_keys`.
    """
    slot = action.slots.new(id_type="OBJECT", name=rig_name)
    bag = action.layers.new("Layer").strips.new(type="KEYFRAME").channelbags.new(slot)
    frames = [0, 1]
    for _, ticks in schedule:
        frames.append(frames[-1] + ticks)
    for bone_name, per_frame in rows:
        shown = [per_frame[index] for index, _ in schedule]
        values = _same_hemisphere([REST_CHANNELS] + shown + [shown[-1]])
        modes = _modes(len(frames), smooth)
        column = 0
        for path, count in CHANNELS:
            for axis in range(count):
                curve_values = [row[column] for row in values]
                _write_channel(bag, f'pose.bones["{bone_name}"].{path}', axis, bone_name, frames, curve_values, modes)
                column += 1
    for fade in fades:
        shown = [float(fade.values[index]) for index, _ in schedule]
        values = [float(fade.rest)] + shown + [shown[-1]]
        _write_channel(bag, f'["{fade.prop}"]', 0, "Fades", frames, values, ["CONSTANT"] * len(frames))
    return slot


def _same_hemisphere(rows: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """Flip each rotation to the sign nearer the one before it. Both signs are the same rotation, but blending
    between opposite signs would turn the long way round."""
    out = [rows[0]]
    for row in rows[1:]:
        previous, rotation = out[-1][3:7], row[3:7]
        if sum(a * b for a, b in zip(previous, rotation, strict=True)) < 0:
            row = (*row[:3], *(-value for value in rotation), *row[7:])
        out.append(row)
    return out


def _modes(count: int, smooth: bool) -> list[str]:
    """The interpolation of a bone curve's keys: rest, one key per frame, rest. A smooth clip blends each frame into
    the next and holds its last frame until the clip ends; otherwise every key holds."""
    if not smooth:
        return ["CONSTANT"] * count
    return ["CONSTANT"] + ["LINEAR"] * (count - 3) + ["CONSTANT", "CONSTANT"]


def _write_channel(
    bag, path: str, axis: int, group: str, frames: list[int], values: list[float], modes: list[str]
) -> None:
    curve = bag.fcurves.new(path, index=axis, group_name=group)
    points = curve.keyframe_points
    points.add(len(frames))
    points.foreach_set("co", [c for pair in zip(frames, values, strict=True) for c in pair])
    kinds = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items
    points.foreach_set("interpolation", [kinds[mode].value for mode in modes])
    curve.update()
