"""Held items: the objects a clip's held items add to a player, and which hand objects each frame shows.

While an action sequence plays, the client builds the player from its worn slots with the sequence's held items in
the weapon and shield slots (`formats.appearance.held_equipment`), lit and posed as one merged model. A bake of such
a clip therefore poses that model, the held variant, and the player shows the variant's held items in place of the
worn weapon and shield on the frames the clip covers. A clip played as a pose never changes the hands.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import bpy

from ..animation.clip import PosedFrame
from ..animation.frames import SequenceDefinition
from ..formats.appearance import ITEM_OFFSET, held_equipment
from ..formats.appearance_preset import loads_preset
from ..formats.appearance_rig import Rig, derive_rig
from ..formats.cache_profile import shared_profile
from ..formats.lighting import Shading, light
from ..formats.model import Model, Vertex
from . import appearance_collection, appearance_preview, preferences
from .axes import game_to_blender

VISIBILITY = ("hide_viewport", "hide_render")
# Marks the action that keys a hand object's visibility, which every bake writes again from the clips.
VISIBILITY_KEY = "rs_visibility"


def held_items(sequence: SequenceDefinition, action: bool) -> tuple[int, int] | None:
    """The sequence's shield-hand and weapon-hand values when it plays as an action and sets either, else None."""
    if not action or (sequence.left_hand_item < 0 and sequence.right_hand_item < 0):
        return None
    return sequence.left_hand_item, sequence.right_hand_item


@dataclass(frozen=True)
class Variant:
    """The merged model the client poses while a clip with held items plays, and the worn one it replaces."""

    equipment: tuple[int, ...]
    model: Model
    shading: Shading
    slots: dict[int, range]
    worn_model: Model
    worn_slots: dict[int, range]
    # The name of every item the variant holds, for its object's name.
    names: dict[int, str]


def variant(collection: bpy.types.Collection, held: tuple[int, int], dump_folder: str) -> Variant | None:
    """The player's held variant, or None when the held items leave every slot as worn."""
    preset = loads_preset(collection[appearance_preview.PRESET_KEY])
    equipment = held_equipment(preset.equipment, *held)
    if equipment == list(preset.equipment):
        return None
    profile = shared_profile(appearance_preview.dump_folder(dump_folder))
    model, slots = profile.assemble_slots(preset, equipment)
    worn_model, worn_slots = profile.assemble_slots(preset)
    names = {value - ITEM_OFFSET: profile.items[value - ITEM_OFFSET].name for value in held if value >= ITEM_OFFSET}
    return Variant(tuple(equipment), model, light(model), slots, worn_model, worn_slots, names)


def changed_slots(collection: bpy.types.Collection, equipment: Sequence[int]) -> list[int]:
    """The hand slots whose value `equipment` changes from the player's worn equipment."""
    worn = loads_preset(collection[appearance_preview.PRESET_KEY]).equipment
    return [slot for slot, _ in appearance_collection.HAND_PARTS if equipment[slot] != worn[slot]]


@dataclass(frozen=True)
class Piece:
    """One mesh object of the player, and where its vertices and polygons sit in the model a bake poses."""

    obj: bpy.types.Object
    # Each mesh vertex's index in the posed model, or -1 for a vertex the model lacks, which stays at `rest`.
    vertices: tuple[int, ...]
    # Each polygon's face index in the posed model's face inputs.
    polygons: tuple[int, ...]
    # The polygons' skin labels and rest alphas, or None for a mesh built before players stored them.
    faces: tuple[tuple[int, ...], tuple[int, ...]] | None
    rest: tuple[Vertex, ...] = ()

    def frames(self, posed: tuple[PosedFrame, ...]) -> tuple[PosedFrame, ...]:
        """The posed frames of the model cut down to this object's vertices and polygons."""
        return tuple(
            PosedFrame(
                frame.ticks,
                tuple(frame.vertices[v] if v >= 0 else self.rest[i] for i, v in enumerate(self.vertices)),
                None if frame.alphas is None else tuple(frame.alphas[f] for f in self.polygons),
            )
            for frame in posed
        )


def variant_inputs(
    found: Variant,
) -> tuple[tuple[Vertex, ...], tuple[int, ...], tuple[tuple[int, ...], tuple[int, ...]] | None]:
    """The variant's vertices and labels, and its faces' labels and rest alphas when it has face labels."""
    model = found.model
    if model.vertex_skins is None:
        raise ValueError("The held variant has no vertex skins")
    faces = None
    if model.face_skins is not None:
        faces = (tuple(model.face_skins), tuple(model.face_alphas or [0] * len(model.faces)))
    return tuple(model.vertices), tuple(model.vertex_skins), faces


def ensure_pieces(collection: bpy.types.Collection, found: Variant) -> list[Piece]:
    """The objects that show the variant, after giving the player an object for each held item it lacks."""
    _ensure_held_objects(collection, found)
    return _held_pieces(collection, found)


def _held_pieces(collection: bpy.types.Collection, found: Variant) -> list[Piece]:
    """The objects that show the variant: the body, the worn hand objects it keeps, and its held objects.

    A body vertex is found in the variant by its rest position, since the merged model shares one vertex per
    position; a vertex the variant lacks keeps its rest position. A body polygon keeps its offset within its slot's
    faces.
    """
    model = found.model
    by_position = {position: index for index, position in enumerate(model.vertices)}
    face_skins = model.face_skins or [0] * len(model.faces)
    face_alphas = model.face_alphas or [0] * len(model.faces)
    changed = changed_slots(collection, found.equipment)
    pieces = []
    for obj in appearance_collection.parts(collection):
        mesh = obj.data
        assert isinstance(mesh, bpy.types.Mesh)
        faces = appearance_preview.face_indices(mesh)
        if faces is None:
            raise ValueError(f"{collection.name} was built before held items. Update Player rebuilds it")
        part = obj.get(appearance_collection.PART_KEY)
        rest: tuple[Vertex, ...] = ()
        if part == appearance_collection.HELD:
            slot = obj[appearance_collection.HELD_SLOT_KEY]
            if slot not in changed or found.equipment[slot] != ITEM_OFFSET + obj[appearance_collection.HELD_ITEM_KEY]:
                continue
            vertices = tuple(appearance_preview.vertex_indices(mesh))
            polygons = tuple(faces)
        else:
            if any(p == part and slot in changed for slot, p in appearance_collection.HAND_PARTS):
                continue
            rest = tuple(found.worn_model.vertices[v] for v in appearance_preview.vertex_indices(mesh))
            vertices = tuple(by_position.get(position, -1) for position in rest)
            polygons = tuple(_variant_face(face, found) for face in faces)
        labels = tuple(face_skins[f] for f in polygons)
        alphas = tuple(face_alphas[f] for f in polygons)
        pieces.append(Piece(obj, vertices, polygons, (labels, alphas), rest))
    return pieces


def _variant_face(face: int, found: Variant) -> int:
    slot = next(slot for slot, faces in found.worn_slots.items() if face in faces)
    return found.slots[slot].start + face - found.worn_slots[slot].start


def _ensure_held_objects(collection: bpy.types.Collection, found: Variant) -> None:
    """Give the player an object for each item the variant holds, bound to its rig, unless it has one already.

    Labels that only the held items carry get label bones, under the joint that moves them.
    """
    rig_obj = appearance_collection.armature_of(collection)
    variant_rig = derive_rig(found.model)
    _ensure_label_bones(rig_obj, variant_rig)
    for slot in changed_slots(collection, found.equipment):
        item = found.equipment[slot] - ITEM_OFFSET
        if item < 0 or _held_object(collection, slot, item) is not None:
            continue
        name = found.names[item]
        obj = appearance_collection.mesh_object(
            found.model,
            found.shading,
            f"{collection.name} {name}",
            preferences.brightness(),
            collection,
            appearance_collection.HELD,
            found.slots[slot],
            False,
        )
        obj[appearance_collection.HELD_SLOT_KEY] = slot
        obj[appearance_collection.HELD_ITEM_KEY] = item
        obj[appearance_collection.HELD_NAME_KEY] = name
        appearance_collection.bind(obj, rig_obj, variant_rig)


def _held_object(collection: bpy.types.Collection, slot: int, item: int) -> bpy.types.Object | None:
    return next(
        (
            obj
            for obj in appearance_collection.parts(collection)
            if obj.get(appearance_collection.PART_KEY) == appearance_collection.HELD
            and obj[appearance_collection.HELD_SLOT_KEY] == slot
            and obj[appearance_collection.HELD_ITEM_KEY] == item
        ),
        None,
    )


def _ensure_label_bones(rig_obj: bpy.types.Object, variant_rig: Rig) -> None:
    armature = rig_obj.data
    assert isinstance(armature, bpy.types.Armature)
    missing = [
        bone for bone in variant_rig.bones if f"{appearance_collection.BONE_PREFIX}{bone.label}" not in armature.bones
    ]
    if not missing:
        return
    layer = bpy.context.view_layer
    previous, mode = layer.objects.active, rig_obj.mode
    layer.objects.active = rig_obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            labels = armature.collections[appearance_collection.LABEL_COLLECTION]
            for bone in missing:
                edit = armature.edit_bones.new(f"{appearance_collection.BONE_PREFIX}{bone.label}")
                edit.head = game_to_blender(bone.head)
                edit.tail = game_to_blender(bone.tail)
                owner = variant_rig.owner(bone.label)
                edit.parent = armature.edit_bones.get(owner) if owner is not None else None
                labels.assign(edit)
        finally:
            bpy.ops.object.mode_set(mode=mode)
    finally:
        layer.objects.active = previous


@contextmanager
def held_items_undone_on_failure(collection: bpy.types.Collection) -> Iterator[None]:
    """Run a bake's steps, and if one raises, remove the held objects and label bones the player gained meanwhile, so
    the failed bake leaves the player's objects, meshes and bones as they were (issue 13, decisions 1 and 4)."""
    parts = {obj.name for obj in appearance_collection.parts(collection)}
    bones = {bone.name for bone in appearance_collection.armature_data(collection).bones}
    try:
        yield
    except Exception:
        for obj in appearance_collection.parts(collection):
            if obj.name not in parts:
                _remove_object(obj)
        _remove_bones_except(appearance_collection.armature_of(collection), bones)
        raise


def _remove_bones_except(rig_obj: bpy.types.Object, kept: set[str]) -> None:
    armature = rig_obj.data
    assert isinstance(armature, bpy.types.Armature)
    added = [bone.name for bone in armature.bones if bone.name not in kept]
    if not added:
        return
    layer = bpy.context.view_layer
    previous, mode = layer.objects.active, rig_obj.mode
    layer.objects.active = rig_obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            for name in added:
                armature.edit_bones.remove(armature.edit_bones[name])
        finally:
            bpy.ops.object.mode_set(mode=mode)
    finally:
        layer.objects.active = previous


def key_visibility(collection: bpy.types.Collection, spans: Sequence[tuple[int, Sequence[int] | None]]) -> None:
    """Key which hand objects show: each span starts on a Blender frame and lasts until the next one, and shows the
    held items of its equipment (None for the worn equipment). Before the first span the worn items show. A held
    object that no span shows is removed.
    """
    worn = loads_preset(collection[appearance_preview.PRESET_KEY]).equipment
    ordered = sorted(spans, key=lambda span: span[0])
    for obj in appearance_collection.parts(collection):
        part = obj.get(appearance_collection.PART_KEY)
        if part == appearance_collection.HELD:
            slot, value = (
                obj[appearance_collection.HELD_SLOT_KEY],
                ITEM_OFFSET + obj[appearance_collection.HELD_ITEM_KEY],
            )
        else:
            slot = next((s for s, p in appearance_collection.HAND_PARTS if p == part), None)
            if slot is None:
                continue
            value = worn[slot]
        shown = [value == (worn if equipment is None else equipment)[slot] for _, equipment in ordered]
        if part == appearance_collection.HELD and not any(shown):
            _remove_object(obj)
            continue
        _key_object(obj, value == worn[slot], [(start, show) for (start, _), show in zip(ordered, shown, strict=True)])


def _key_object(obj: bpy.types.Object, before: bool, changes: list[tuple[int, bool]]) -> None:
    animation = obj.animation_data or obj.animation_data_create()
    old = animation.action
    if old is not None and VISIBILITY_KEY in old:
        animation.action = None
        if old.users == 0:
            bpy.data.actions.remove(old)
    elif old is not None:
        return
    if all(show == before for _, show in changes):
        for name in VISIBILITY:
            setattr(obj, name, not before)
        return
    action = bpy.data.actions.new(f"{obj.name} visibility")
    action[VISIBILITY_KEY] = True
    animation.action = action
    first = changes[0][0] if changes else 1
    for frame, show in [(first - 1, before), *changes]:
        for name in VISIBILITY:
            setattr(obj, name, not show)
            obj.keyframe_insert(name, frame=frame)
    for bag in _channelbags(action):
        for curve in bag.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "CONSTANT"


def _channelbags(action: bpy.types.Action):
    return [bag for layer in action.layers for strip in layer.strips for bag in strip.channelbags]  # pyrefly: ignore[missing-attribute]


def _remove_object(obj: bpy.types.Object) -> None:
    mesh = obj.data
    action = obj.animation_data.action if obj.animation_data is not None else None
    bpy.data.objects.remove(obj)
    if isinstance(mesh, bpy.types.Mesh) and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    if action is not None and action.users == 0:
        bpy.data.actions.remove(action)
