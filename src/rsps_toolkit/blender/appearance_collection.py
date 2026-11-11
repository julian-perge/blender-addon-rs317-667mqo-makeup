"""A collection holding the lit player mesh, its skin-label armature and the preset it was built from."""

import hashlib
import re

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector

from ..formats.appearance import SHIELD_SLOT, WEAPON_SLOT
from ..formats.appearance_preset import AppearancePreset, dumps_preset, loads_preset
from ..formats.appearance_rig import Rig, derive_rig
from ..formats.lighting import Shading
from ..formats.model import Model
from . import appearance_fades, appearance_preview, appearance_props, preferences
from .axes import game_to_blender
from .face_materials import DEFAULT_BRIGHTNESS

# Fingerprint of the player as built or last baked, so a later rebuild or bake can tell whether the user edited it.
HASH_KEY = "rs_rig_hash"
# The clip last baked onto the player (folder, method and play mode, as JSON), which Update bakes again.
CLIP_KEY = "rs_clip"
# On an action made by the bone bake: the hash of its keys as baked. The fingerprint reads its keys only once they
# differ from this; actions without it are the user's own, which Update carries over.
RIG_ACTION_KEY = "rs_bone_clip"
BONE_PREFIX = "label_"
# Marks a rig built with joint bones from the player frame map (plan 11).
JOINT_RIG_KEY = "rs_joint_rig"
JOINT_COLLECTION, LABEL_COLLECTION = "Joints", "Labels"
# Coordinates are compared to this many decimals, which is finer than one game unit and coarser than float noise
# (the owner's choice, issue 20).
HASH_DECIMALS = 3
# A pose bone's matrix_basis at rest, as _rounded rows. Players without a posed bone hash as they did before poses
# were part of the fingerprint.
REST_ROWS = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
# Game units between a newly created player, or Update's copy of an edited player, and the player meshes already there.
PLAYER_GAP = 32.0
# On each mesh object of a player: which part of the player it is. A player built before parts has one mesh without it.
PART_KEY = "rs_part"
BODY = "Body"
# The worn slots that get their own object, since a clip's held items replace them (formats.appearance.held_equipment).
HAND_PARTS = ((WEAPON_SLOT, "Weapon"), (SHIELD_SLOT, "Shield"))
# An object a clip's held item adds (appearance_held). It also stores the slot, item id and item name below.
HELD = "Held"
HELD_SLOT_KEY, HELD_ITEM_KEY, HELD_NAME_KEY = "rs_held_slot", "rs_held_item", "rs_held_name"


def build_collection(
    body: Model,
    shading: Shading,
    preset: AppearancePreset,
    name: str,
    brightness: float = DEFAULT_BRIGHTNESS,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    slots: dict[int, range] | None = None,
) -> bpy.types.Collection:
    """Create the collection, with the rig at `location`, and link it to the scene.

    With `slots`, the faces each equipment slot supplied, a worn weapon and shield each get their own mesh object
    beside the body's; all of them are bound to the one rig. Everything that can fail runs before any Blender data
    exists.
    """
    rig = derive_rig(body)
    hands = {part: slots[slot] for slot, part in HAND_PARTS if slots is not None and slot in slots}
    held = {face for faces in hands.values() for face in faces}
    collection = bpy.data.collections.new(name)
    try:
        bpy.context.scene.collection.children.link(collection)
        body_faces = None if not held else [face for face in range(len(body.faces)) if face not in held]
        objects = [mesh_object(body, shading, name, brightness, collection, BODY, body_faces)]
        for part, faces in hands.items():
            objects.append(mesh_object(body, shading, f"{name} {part}", brightness, collection, part, faces, False))
        armature_obj = _armature_object(rig, name, collection)
        for obj in objects:
            bind(obj, armature_obj, rig)
        armature_obj.location = location
        bpy.context.view_layer.update()
        collection[appearance_preview.PRESET_KEY] = dumps_preset(preset)
        collection[HASH_KEY] = fingerprint(collection)
    except Exception:
        remove_collection(collection)
        raise
    return collection


def remove_collection(collection: bpy.types.Collection) -> None:
    """Delete the collection with its mesh and armature. Refuses, before any change, a collection holding anything else."""
    check_removable(collection)
    actions = []
    materials = []
    for obj in list(collection.objects):
        data = obj.data
        if isinstance(data, bpy.types.Mesh):
            materials += list(data.materials)
        actions += _actions(obj) + _actions(getattr(data, "shape_keys", None))
        bpy.data.objects.remove(obj)
        if isinstance(data, bpy.types.Mesh) and data.users == 0:
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Armature) and data.users == 0:
            bpy.data.armatures.remove(data)
    for action in actions:
        if action is not None and action.users == 0:
            bpy.data.actions.remove(action)
    appearance_fades.remove_unused(materials)
    bpy.data.collections.remove(collection)


def _actions(owner) -> list[bpy.types.Action | None]:
    """The owner's active action and the actions of its NLA strips."""
    animation = None if owner is None else owner.animation_data
    if animation is None:
        return []
    return [animation.action] + [strip.action for track in animation.nla_tracks for strip in track.strips]


def check_removable(collection: bpy.types.Collection) -> None:
    """Raise when the collection holds objects or collections the add-on did not make, which removal would delete."""
    others = [obj.name for obj in collection.objects if obj.type not in ("MESH", "ARMATURE")]
    others += [child.name for child in collection.children]
    if others:
        raise ValueError(
            f"{collection.name} holds {', '.join(others)}, which the add-on did not make. "
            "Move them to another collection first"
        )


def check_object_mode(collection: bpy.types.Collection, action: str) -> None:
    """Raise when an object of the player is in Edit Mode, whose edits Blender has not yet written to the object."""
    names = [obj.name for obj in collection.objects if obj.mode == "EDIT"]
    if names:
        raise ValueError(f"Leave Edit Mode on {', '.join(names)} before {action}")


def check_no_edit_mode(action: str) -> None:
    """Raise when any mesh or armature object is in Edit Mode, because building the armature switches modes."""
    names = [obj.name for obj in bpy.data.objects if obj.type in ("MESH", "ARMATURE") and obj.mode == "EDIT"]
    if names:
        raise ValueError(f"Leave Edit Mode on {', '.join(names)} before {action}")


def baked_clip(collection: bpy.types.Collection) -> str | None:
    """The method of the clip baked onto the player, "shape keys" or "bones", or None when it has none."""
    shape_keys = mesh_data(collection).shape_keys
    if shape_keys is not None and len(shape_keys.key_blocks) > 0:
        return "shape keys"
    return "bones" if _bake_actions(armature_of(collection)) else None


def _bake_actions(rig: bpy.types.Object) -> list[bpy.types.Action]:
    """The actions the bone bake made that the rig plays: its clip strips and, from older bakes, its active action."""
    return [action for action in _actions(rig) if action is not None and RIG_ACTION_KEY in action]


def notice(collection: bpy.types.Collection) -> str | None:
    """A warning for the panel about the player, or None. It never raises, because the panel calls it on every redraw."""
    try:
        check_object_mode(collection, "updating or baking")
        if is_edited(collection):
            return f"{collection.name} has edits. Update keeps it and builds a copy."
    except ValueError as error:
        return str(error)
    return None


def mesh_of(collection: bpy.types.Collection) -> bpy.types.Object:
    """The player's body mesh."""
    found = [obj for obj in collection.objects if obj.type == "MESH" and obj.get(PART_KEY, BODY) == BODY]
    if len(found) != 1:
        raise ValueError(
            f"Collection {collection.name!r} should hold one body mesh object, it holds {len(found)}{_shift_d_hint(found)}"
        )
    return found[0]


def parts(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    """The player's mesh objects: the body, then its worn weapon and shield, then the items its clips hold."""
    order = [BODY] + [part for _, part in HAND_PARTS] + [HELD]
    others = [obj for obj in collection.objects if obj.type == "MESH" and obj.get(PART_KEY, BODY) != BODY]
    return [mesh_of(collection)] + sorted(
        others, key=lambda obj: (order.index(obj[PART_KEY]) if obj[PART_KEY] in order else len(order), obj.name)
    )


def armature_of(collection: bpy.types.Collection) -> bpy.types.Object:
    return _single(collection, "ARMATURE")


def mesh_data(collection: bpy.types.Collection) -> bpy.types.Mesh:
    mesh = mesh_of(collection).data
    assert isinstance(mesh, bpy.types.Mesh)
    return mesh


def armature_data(collection: bpy.types.Collection) -> bpy.types.Armature:
    armature = armature_of(collection).data
    assert isinstance(armature, bpy.types.Armature)
    return armature


def worn_parts(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    """The mesh objects built from the player's worn equipment, which together hold every vertex of its model."""
    return [obj for obj in parts(collection) if obj.get(PART_KEY) != HELD]


def is_edited(collection: bpy.types.Collection) -> bool:
    """True when the fingerprint differs from the one recorded at the build or last bake, or the record is missing."""
    recorded = collection.get(HASH_KEY)
    return recorded is None or recorded != fingerprint(collection)


def fingerprint(collection: bpy.types.Collection) -> str:
    """A hash of the mesh, weights, material slot and colour attribute names, shape keys, bones, where each mesh object
    sits against the rig, and the rig's pose.

    Where the rig itself stands, turns and scales is not read, so moving the whole player is not an edit: the bake
    tests give the same result on a moved rig, and Update carries the rig's placement to the rebuilt rig.

    An object in Edit Mode is read with its edits, which this writes to the object first. A bone bake's action
    counts once its keys differ from the hash the bake stored on it. The user's own actions and strips do not count,
    because Update carries them to the rebuilt rig. A rig without any animation is read by its posed bones; with
    animation its pose follows the current frame, so it is not read.
    """
    meshes, armature_obj = parts(collection), armature_of(collection)
    for obj in (*meshes, armature_obj):
        if obj.mode == "EDIT":
            obj.update_from_editmode()
    assert isinstance(armature_obj.data, bpy.types.Armature)
    mesh_obj = meshes[0]
    # The body is read first and on its own, so a player without a weapon or shield hashes as before players had parts.
    parts_read = _mesh_parts(mesh_obj)
    for bone in armature_obj.data.bones:
        parts_read.append(
            (
                bone.name,
                bone.parent.name if bone.parent is not None else None,
                _rounded(bone.head_local),
                _rounded(bone.tail_local),
                [_rounded(row) for row in bone.matrix_local],
            )
        )
    parts_read.append(_placement(mesh_obj, armature_obj))
    for obj in meshes[1:]:
        parts_read.append((obj[PART_KEY], _mesh_parts(obj), _placement(obj, armature_obj)))
    for action in _bake_actions(armature_obj):
        if action[RIG_ACTION_KEY] != keys_hash(action):
            parts_read.append(_keyframes(action))
    animation = armature_obj.animation_data
    if animation is None or (animation.action is None and not any(t.strips for t in animation.nla_tracks)):
        posed = [
            (bone.name, rows)
            for bone in armature_obj.pose.bones  # pyrefly: ignore[missing-attribute]
            if (rows := [_rounded(row) for row in bone.matrix_basis]) != REST_ROWS
        ]
        if posed:
            parts_read.append(posed)
    return hashlib.sha256(repr(parts_read).encode()).hexdigest()


def _placement(mesh_obj: bpy.types.Object, armature_obj: bpy.types.Object) -> tuple[bool, list[list[float]]]:
    """What the fingerprint reads of where a mesh object sits: whether the rig is its parent, and its transform
    against its parent.

    The transform comes from the object's stored values. Its world matrix holds the placement only once Blender has
    evaluated the scene, which a held item object made during a bake has not been when the bake records the
    fingerprint.
    """
    return (
        mesh_obj.parent == armature_obj,
        [_rounded(row) for row in mesh_obj.matrix_parent_inverse @ mesh_obj.matrix_basis],
    )


def _mesh_parts(mesh_obj: bpy.types.Object) -> list[object]:
    """What the fingerprint reads of one mesh object: weights, vertices, polygons, material slots, colour attribute
    names and shape keys."""
    mesh = mesh_obj.data
    assert isinstance(mesh, bpy.types.Mesh)
    names = [group.name for group in mesh_obj.vertex_groups]
    read: list[object] = [names]
    for vertex in mesh.vertices:
        read.append(_rounded(vertex.co))
        read.append(sorted((names[g.group], _rounded([g.weight])) for g in vertex.groups))
    read.append([tuple(polygon.vertices) for polygon in mesh.polygons])  # pyrefly: ignore[bad-argument-type]
    read.append([_material_name(slot.material) for slot in mesh_obj.material_slots])
    read.append([attribute.name for attribute in mesh.color_attributes])
    if mesh.shape_keys is not None:
        for key in mesh.shape_keys.key_blocks:
            read.append((key.name, [_rounded(point.co) for point in key.data]))  # pyrefly: ignore[missing-attribute]
    return read


def keys_hash(action: bpy.types.Action) -> str:
    return hashlib.sha256(repr(_keyframes(action)).encode()).hexdigest()


def _keyframes(action: bpy.types.Action) -> list[object]:
    return [
        (curve.data_path, curve.array_index, [(*_rounded(p.co), p.interpolation) for p in curve.keyframe_points])
        for layer in action.layers
        for strip in layer.strips
        for bag in strip.channelbags  # pyrefly: ignore[missing-attribute]
        for curve in bag.fcurves
    ]


def _material_name(material: bpy.types.Material | None) -> str | None:
    """The name the fingerprint reads for a slot's material.

    Blender adds a number to a material whose name is taken. Append does when a saved player comes into a file whose
    players use the same lit material, and New Material does for the copy it makes. The user chose that a numbered
    copy reads as the material it is named after while its nodes, links and input values match that material, so an
    appended player stays unedited and an edited copy is an edit. The user also chose that a numbered material with
    no material of its base name reads as numbered, so it counts as an edit, because Update then keeps the player
    rather than replace an edit on a guess. A fade material belongs to one player, so its number is always dropped.
    """
    if material is None:
        return None
    base = re.sub(r"\.\d{3,}$", "", material.name)
    if base == material.name or appearance_fades.FADE_KEY in material:
        return base
    original = bpy.data.materials.get(base)
    return base if original is not None and _node_setup(original) == _node_setup(material) else material.name


def _node_setup(material: bpy.types.Material) -> list[object]:
    """The material's nodes, each with its type, name, mute state, settings and input values, and the links between
    them. Settings that only change how the node editor draws a node, such as its location, label, size and colour,
    are left out, as the user chose, because they do not change the material."""
    tree = material.node_tree
    if tree is None:
        return []
    drawn = {prop.identifier for prop in bpy.types.Node.bl_rna.properties}
    nodes = [
        (
            node.bl_idname,
            node.name,
            node.mute,
            _settings(node, drawn),
            [(s.identifier, _comparable(s.default_value)) for s in node.inputs if hasattr(s, "default_value")],
        )
        for node in sorted(tree.nodes, key=lambda each: each.name)
    ]
    links = sorted(
        (link.from_node.name, link.from_socket.identifier, link.to_node.name, link.to_socket.identifier, link.is_muted)
        for link in tree.links
    )
    return [nodes, links]


def _settings(node: bpy.types.Node, drawn: set[str]) -> list[tuple[str, object]]:
    """The settings of the node's own type, such as a Mix node's blend mode or an Image node's image. The properties
    every node has, named in `drawn`, are read by `_node_setup` or left out there."""
    settings = []
    for prop in node.bl_rna.properties:
        if prop.identifier in drawn:
            continue
        value = getattr(node, prop.identifier)
        if prop.type in {"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"} or isinstance(value, bpy.types.ID):
            settings.append((prop.identifier, _comparable(value)))
    return settings


def _comparable(value: object) -> object:
    """A node setting or input value in a form that `==` compares, with floats rounded as the fingerprint rounds."""
    if isinstance(value, float):
        return _rounded([value])[0]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, bpy.types.ID):
        return value.name
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, bpy.types.bpy_prop_array):
        items = [0.0] * len(value)  # pyrefly: ignore[bad-argument-type]
        value.foreach_get(items)
        return _rounded(items)
    return repr(value)


def _rounded(values) -> list[float]:
    """Round to HASH_DECIMALS. Adding 0.0 turns a negative zero into zero, so float noise around zero hashes alike."""
    return [round(value, HASH_DECIMALS) + 0.0 for value in values]


def _single(collection: bpy.types.Collection, kind: str) -> bpy.types.Object:
    found = [obj for obj in collection.objects if obj.type == kind]
    if len(found) != 1:
        raise ValueError(
            f"Collection {collection.name!r} should hold one {kind.lower()} object, it holds {len(found)}{_shift_d_hint(found)}"
        )
    return found[0]


def _shift_d_hint(found: list[bpy.types.Object]) -> str:
    """The text that ends the error for a player holding more than one rig or body mesh. It says that Shift+D puts
    copies of a player's objects into the same player and that Duplicate Player makes a working copy instead. It is
    empty when the player holds at most one."""
    if len(found) < 2:
        return ""
    return ". Shift+D copies a player's objects into the same player; Duplicate Player makes a working copy instead"


def mesh_object(
    body: Model,
    shading: Shading,
    name: str,
    brightness: float,
    collection: bpy.types.Collection,
    part: str,
    faces: list[int] | range | None = None,
    loose: bool = True,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, appearance_preview.build_mesh(body, shading, name, brightness, faces, loose))
    obj[PART_KEY] = part
    collection.objects.link(obj)
    return obj


def _armature_object(rig: Rig, name: str, collection: bpy.types.Collection) -> bpy.types.Object:
    """The armature: joint bones in their hierarchy, and under them the label bones that deform the mesh.

    The joints and the label bones are in two bone collections, and the label bones are hidden: the user animates
    the joints, and clips key what is left of each label under its joint.
    """
    armature = bpy.data.armatures.new(f"{name}_armature")
    joint_collection = armature.collections.new(JOINT_COLLECTION)
    label_collection = armature.collections.new(LABEL_COLLECTION)
    label_collection.is_visible = False
    obj = bpy.data.objects.new(f"{name}_rig", armature)
    obj[JOINT_RIG_KEY] = True
    collection.objects.link(obj)
    layer = bpy.context.view_layer
    previous = layer.objects.active
    layer.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            joints = {}
            for joint in rig.joints:
                edit = armature.edit_bones.new(joint.name)
                edit.head = game_to_blender(joint.head)
                edit.tail = game_to_blender(joint.tail)
                edit.use_deform = False
                edit.parent = None if joint.parent is None else joints[joint.parent]
                joint_collection.assign(edit)
                joints[joint.name] = edit
            for bone in rig.bones:
                edit = armature.edit_bones.new(f"{BONE_PREFIX}{bone.label}")
                edit.head = game_to_blender(bone.head)
                edit.tail = game_to_blender(bone.tail)
                owner = rig.owner(bone.label)
                edit.parent = None if owner is None else joints[owner]
                label_collection.assign(edit)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        layer.objects.active = previous
    return obj


def is_joint_rig(rig: bpy.types.Object) -> bool:
    """False for a player built before rigs had joint bones."""
    return bool(rig.get(JOINT_RIG_KEY))


def bind(mesh_obj: bpy.types.Object, armature_obj: bpy.types.Object, rig: Rig) -> None:
    """Weight each vertex fully to its label's bone, with one vertex group per label the mesh's vertices carry."""
    assert isinstance(mesh_obj.data, bpy.types.Mesh)
    by_label: dict[int, list[int]] = {}
    for vertex, model_vertex in enumerate(appearance_preview.vertex_indices(mesh_obj.data)):
        by_label.setdefault(rig.vertex_labels[model_vertex], []).append(vertex)
    for bone in rig.bones:
        if bone.label in by_label:
            mesh_obj.vertex_groups.new(name=f"{BONE_PREFIX}{bone.label}").add(by_label[bone.label], 1.0, "REPLACE")
    mesh_obj.parent = armature_obj
    modifier = mesh_obj.modifiers.new("Armature", "ARMATURE")
    assert isinstance(modifier, bpy.types.ArmatureModifier)
    modifier.object = armature_obj


def beside_players(body: Model) -> tuple[float, float, float]:
    """Where to put a new player's rig so its mesh starts PLAYER_GAP to the right of every player mesh in the file."""
    right = max(
        (
            (obj.matrix_world @ Vector(corner)).x
            for obj in bpy.data.objects
            if obj.type == "MESH" and appearance_preview.collection_of(obj) is not None
            for corner in obj.bound_box
        ),
        default=None,
    )
    if right is None:
        return (0.0, 0.0, 0.0)
    left = min(x for x, _, _ in body.vertices)
    return (right + PLAYER_GAP - left, 0.0, 0.0)


def _carry_placement(old_rig: bpy.types.Object, new_rig: bpy.types.Object) -> None:
    """Give the rebuilt rig the old rig's parent, constraints, location, rotation and scale.

    `fingerprint` does not read where the rig stands, so a player that was moved, parented or constrained counts as
    unedited and is rebuilt in place, and Update must not undo that placement.
    """
    new_rig.parent = old_rig.parent
    new_rig.parent_type = old_rig.parent_type
    new_rig.parent_bone = old_rig.parent_bone
    new_rig.matrix_parent_inverse = old_rig.matrix_parent_inverse.copy()
    for constraint in old_rig.constraints:
        new_rig.constraints.copy(constraint)
    new_rig.rotation_mode = old_rig.rotation_mode
    for name in (
        "location",
        "rotation_euler",
        "rotation_quaternion",
        "rotation_axis_angle",
        "scale",
        "delta_location",
        "delta_rotation_euler",
        "delta_rotation_quaternion",
        "delta_scale",
    ):
        setattr(new_rig, name, getattr(old_rig, name))


def _rename(collection: bpy.types.Collection, name: str) -> None:
    collection.name = name
    for obj in parts(collection):
        part = obj.get(PART_KEY, BODY)
        obj.name = name if part == BODY else f"{name} {obj[HELD_NAME_KEY] if part == HELD else part}"
    armature_of(collection).name = f"{name}_rig"


def _activate(context: bpy.types.Context, collection: bpy.types.Collection, kind: str = "MESH", mode: str = "OBJECT"):
    """Select the player's object of `kind` alone and make it active, back in Pose Mode when the user was posing."""
    obj = armature_of(collection) if kind == "ARMATURE" else mesh_of(collection)
    for other in context.selected_objects or ():
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    if mode == "POSE" and obj.type == "ARMATURE":
        bpy.ops.object.mode_set(mode="POSE")


def _cache_folder_property():
    return bpy.props.StringProperty(
        name="Cache folder",
        description="Overrides the add-on preference; scripts and tests set it, the panel never shows it",
        subtype="DIR_PATH",
        options={"HIDDEN", "SKIP_SAVE"},
    )


class RSPS_OT_create_appearance_preview(bpy.types.Operator):
    bl_idname = "rsps.create_appearance_preview"
    bl_label = "Create Player"
    bl_description = "Assemble the player appearance from the cache into a collection with a lit mesh and a rig"
    bl_options = {"REGISTER", "UNDO"}

    cache_folder: _cache_folder_property()  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        try:
            check_no_edit_mode("creating a player")
            preset = appearance_props.to_preset(context.scene.rs_appearance)
            folder = appearance_preview.cache_folder(self.cache_folder)
            body, shading, slots = appearance_preview.assemble_parts(preset, folder)
            collection = build_collection(
                body, shading, preset, "Player", preferences.brightness(), beside_players(body), slots
            )
        except (OSError, ValueError, RuntimeError) as error:
            appearance_preview.fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        context.scene.rs_appearance.source_player = collection.name
        _activate(context, collection)
        appearance_preview.show_lit_colours(context)
        return {"FINISHED"}


class RSPS_OT_update_appearance_preview(bpy.types.Operator):
    bl_idname = "rsps.update_appearance_preview"
    bl_label = "Update Player"
    bl_description = (
        "Rebuild the active player from the current appearance. A player whose mesh or rig you edited is kept, "
        "and the update is built as a separate copy"
    )
    bl_options = {"REGISTER", "UNDO"}

    cache_folder: _cache_folder_property()  # pyrefly: ignore[bad-assignment]

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def execute(self, context):
        old = appearance_preview.collection_of(context.active_object)
        assert old is not None
        kind, mode = context.active_object.type, context.active_object.mode
        try:
            check_object_mode(old, "updating")
            tied = tied_player(context.scene.rs_appearance)
            if tied is not None and tied != old:
                raise ValueError(
                    f"The panel holds the settings of {tied.name}, not {old.name}. Click Load Player Settings first."
                )
            edited = is_edited(old)
            lost_clip = None if edited else baked_clip(old)
            if not edited:
                check_removable(old)
            preset = appearance_props.to_preset(context.scene.rs_appearance)
            folder = appearance_preview.cache_folder(self.cache_folder)
            body, shading, slots = appearance_preview.assemble_parts(preset, folder)
            name = old.name
            # An unedited player's rebuilt rig takes the old rig's placement in `_replace`, so it is built at the origin.
            location = beside_players(body) if edited else (0.0, 0.0, 0.0)
            new = build_collection(body, shading, preset, name, preferences.brightness(), location, slots)
        except (OSError, ValueError, RuntimeError) as error:
            appearance_preview.fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        if edited:
            self.report({"WARNING"}, f"{name} has edits, so it was kept and the update is a separate copy")
        else:
            _replace(self, old, new, name, lost_clip, self.cache_folder)
        context.scene.rs_appearance.source_player = new.name
        _activate(context, new, kind, mode)
        appearance_preview.show_lit_colours(context)
        return {"FINISHED"}


def _replace(
    operator: bpy.types.Operator,
    old: bpy.types.Collection,
    new: bpy.types.Collection,
    name: str,
    lost_clip: str | None,
    cache_folder: str = "",
) -> None:
    """Swap the rebuilt player in for the old one: carry the user's animation over, then bake the old clips again.

    A player built before rigs had joint bones gets them; the user's keys on its label bones would fight the joints,
    so they are not carried, and that is reported. A clip whose bake fails, or one baked before bakes were recorded,
    is reported, and the rebuilt player goes on without it.
    """
    # appearance_clip imports this module, so it is imported here, when Update runs.
    from . import appearance_clip

    clips = appearance_clip.recorded_clips(old)
    if is_joint_rig(armature_of(old)):
        appearance_clip.carry_animation(armature_of(old), armature_of(new))
    elif appearance_clip.has_own_animation(armature_of(old)):
        operator.report(
            {"WARNING"},
            f"{name} now has joint bones. Your own keys were on its old label bones and were not carried over",
        )
    _carry_placement(armature_of(old), armature_of(new))
    remove_collection(old)
    _rename(new, name)
    for clip, start in clips:
        try:
            appearance_clip.bake_recorded(new, clip, start, cache_folder)
        except (OSError, LookupError, ValueError, RuntimeError) as error:
            operator.report({"WARNING"}, f"{name}: the baked clip could not be baked again ({error})")
    if lost_clip is not None and not clips:
        operator.report({"WARNING"}, f"{name}: the baked clip ({lost_clip}) was removed; bake it again")


def tied_player(props: "appearance_props.RsAppearanceProperties") -> bpy.types.Collection | None:
    """The player the panel is tied to, or None when it is tied to none or to a player since deleted or renamed."""
    tied = bpy.data.collections.get(props.source_player) if props.source_player else None
    return tied if tied is not None and appearance_preview.PRESET_KEY in tied else None


def holds_unapplied_settings(props: "appearance_props.RsAppearanceProperties") -> bool:
    """True when the panel holds settings that no existing player stores as they are.

    These are changes not yet applied with Update, and settings tied to no existing player: a preset file's, a new
    scene's, or those of a player since deleted or renamed. A tied player whose stored settings cannot be read counts
    too, so the panel's settings are never replaced on a guess. The user chose to keep all of them when a player is
    selected.
    """
    tied = tied_player(props)
    if tied is None:
        return True
    try:
        return appearance_props.to_preset(props) != loads_preset(tied[appearance_preview.PRESET_KEY])
    except ValueError:
        return True


def follow_selection(context: bpy.types.Context) -> None:
    """Tie the panel to the active player, loading the player's stored settings unless the panel holds unapplied
    settings, which the user chose that a click in the viewport must not throw away.

    A panel that already holds the active player's stored settings is tied to it either way. A panel tied to a player
    since deleted or renamed is untied first, so its settings count as a preset file's and Update can apply them. A
    player whose stored settings the panel refuses, such as those of another client revision, leaves the panel as it
    is and puts the reason in its error box, as Load Player Settings does.
    """
    player = appearance_preview.collection_of(context.view_layer.objects.active)
    props = context.scene.rs_appearance  # pyrefly: ignore[missing-attribute]
    if player is None or player.name == props.source_player:
        return
    if tied_player(props) is None:
        props.source_player = ""
    try:
        stored = loads_preset(player[appearance_preview.PRESET_KEY])
        if appearance_props.to_preset(props) == stored:
            props.source_player = player.name
        elif not holds_unapplied_settings(props):
            appearance_props.from_preset(props, stored)
            props.source_player = player.name
            props.last_error = ""
    except ValueError as error:
        props.last_error = str(error)


_SELECTION_OWNER = object()


@persistent
def watch_selection(*_args) -> None:
    """Run `follow_selection` whenever the active object changes, by a click in the viewport or the Outliner or by a
    script.

    The add-on calls this when it is enabled and after every file load, because loading a file drops message bus
    subscriptions (evidence: the `bpy.msgbus.subscribe_rna` documentation).
    """
    bpy.msgbus.clear_by_owner(_SELECTION_OWNER)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),  # pyrefly: ignore[bad-argument-type]
        owner=_SELECTION_OWNER,
        args=(),
        notify=follow_active_player,
    )


def stop_watching_selection() -> None:
    bpy.msgbus.clear_by_owner(_SELECTION_OWNER)


@persistent
def follow_active_player(*_args) -> None:
    """Run `follow_selection` in the current context. The add-on also calls this after every undo and redo, which
    restore the active object without a message bus notification (from Blender's source, as the review read it)."""
    if bpy.context.scene is not None and bpy.context.view_layer is not None:
        follow_selection(bpy.context)


def duplicate_player(old: bpy.types.Collection, cache_folder: str = "") -> bpy.types.Collection:
    """Build a second player from the old one's stored settings, beside the players, with copies of the user's own
    actions and the old player's clips baked again at their start frames. The two share only the file's one lit
    material, which every player uses; the copy's rig, meshes, actions and fade materials are its own.

    The user chose to rebuild rather than copy the objects, so mesh edits cannot be carried, and an edited player is
    refused before any change, as is one in Edit Mode. A clip that fails to bake again removes the copy and raises.
    A player built before rigs had joint bones gets a copy with them. The user's keys on its old label bones would
    fight the joints, so they are not copied, as Update does not carry them (`_replace`).
    """
    # appearance_clip imports this module, so it is imported here, when a player is duplicated.
    from . import appearance_clip

    check_object_mode(old, "duplicating it")
    if is_edited(old):
        raise ValueError(
            f"{old.name} has edits, which Duplicate Player cannot copy, because it rebuilds the player from its stored "
            "settings"
        )
    preset = loads_preset(old[appearance_preview.PRESET_KEY])
    body, shading, slots = appearance_preview.assemble_parts(preset, appearance_preview.cache_folder(cache_folder))
    new = build_collection(body, shading, preset, old.name, preferences.brightness(), beside_players(body), slots)
    # The collection took the next free name, so the objects are named after it rather than after the original.
    _rename(new, new.name)
    try:
        if is_joint_rig(armature_of(old)):
            appearance_clip.carry_animation(armature_of(old), armature_of(new), copy_actions=True)
        for clip, start in appearance_clip.recorded_clips(old):
            appearance_clip.bake_recorded(new, clip, start, cache_folder)
    except Exception:
        remove_collection(new)
        raise
    return new


class RSPS_OT_duplicate_player(bpy.types.Operator):
    bl_idname = "rsps.duplicate_player"
    bl_label = "Duplicate Player"
    bl_description = (
        "Build a second player from the active player's stored settings beside the players, with its clips baked again "
        "and copies of your own animation. It shares only the lit material every player uses. A player with mesh or "
        "rig edits is refused"
    )
    bl_options = {"REGISTER", "UNDO"}

    cache_folder: _cache_folder_property()  # pyrefly: ignore[bad-assignment]

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def execute(self, context):
        # appearance_clip imports this module, so it is imported here, when a player is duplicated.
        from . import appearance_clip

        old = appearance_preview.collection_of(context.active_object)
        assert old is not None
        try:
            rig = armature_of(old)
            keys_left = not is_joint_rig(rig) and appearance_clip.has_own_animation(rig)
            new = duplicate_player(old, self.cache_folder)
        except (OSError, LookupError, ValueError, RuntimeError) as error:
            appearance_preview.fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        _activate(context, new)
        # The user chose that the panel treats the copy as a click on it does, so changes not yet applied stay with
        # the player they were made for.
        follow_selection(context)
        appearance_preview.show_lit_colours(context)
        if keys_left:
            self.report(
                {"WARNING"},
                f"{new.name} has joint bones. Your own keys were on the old label bones of {old.name} and were not "
                "copied",
            )
        self.report({"INFO"}, f"Duplicated {old.name} as {new.name}")
        return {"FINISHED"}


class RSPS_OT_load_player_settings(bpy.types.Operator):
    bl_idname = "rsps.load_player_settings"
    bl_label = "Load Player Settings"
    bl_description = "Set the panel's appearance from the active player's stored preset"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        try:
            appearance_props.from_preset(
                context.scene.rs_appearance, loads_preset(player[appearance_preview.PRESET_KEY])
            )
        except ValueError as error:
            appearance_preview.fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.source_player = player.name
        context.scene.rs_appearance.last_error = ""
        return {"FINISHED"}


classes = (
    RSPS_OT_create_appearance_preview,
    RSPS_OT_update_appearance_preview,
    RSPS_OT_duplicate_player,
    RSPS_OT_load_player_settings,
)
