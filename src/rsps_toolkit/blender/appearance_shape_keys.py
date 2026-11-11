"""Writes a posed clip onto a player's mesh objects as shape keys, one per frame."""

import re

import bpy

from . import appearance_fades
from .appearance_pose import PosedPart
from .axes import game_to_blender

KEY_PREFIX = "clip_"
BASIS = "Basis"
# A new bake builds its keys under this prefix and renames them to clip_<n> only once all of them exist.
NEW_PREFIX = "clip_new_"


def has_keys(obj: bpy.types.Object) -> bool:
    """True when the object has any shape key, a bake's or the user's."""
    return bool(_key_blocks(obj))


def foreign_keys(obj: bpy.types.Object) -> list[str]:
    """The names of the object's shape keys that no bake made."""
    return [key.name for key in _key_blocks(obj) if not _is_clip_key(key.name)]


def write(parts: list[PosedPart], schedule: tuple[tuple[int, int], ...]) -> None:
    """Replace each part's clip shape keys with one per frame, keyed with its fades on the ticks of the schedule.

    Every part's new keys are added before any old key is removed, and a failure while adding removes the keys it
    added, so the previous clip stays.
    """
    made = []
    try:
        for part in parts:
            made.append((part, part.obj.data.shape_keys is None))  # pyrefly: ignore[missing-attribute]
            _add_keys(part.obj, part.frames, schedule)
    except Exception:
        for part, made_basis in made:
            new = [key.name for key in _key_blocks(part.obj) if key.name.startswith(NEW_PREFIX)]
            _remove_keys(part.obj, new + ([BASIS] if made_basis else []))
        raise
    for part in parts:
        obj = part.obj
        _remove_keys(obj, [key.name for key in _key_blocks(obj) if _is_clip_key(key.name) and key.name != BASIS])
        for index in range(len(part.frames)):
            obj.data.shape_keys.key_blocks[f"{NEW_PREFIX}{index}"].name = f"{KEY_PREFIX}{index}"  # pyrefly: ignore[missing-attribute]
        _key_fades(obj, part.fades, schedule)
        _hold_each_value(obj)


def clear(obj: bpy.types.Object) -> None:
    """Remove every shape key of an object the next clip does not show, with its fade curves and fade materials.

    This removes keys whoever made them, so the shape-key bake first refuses an object with `foreign_keys`.
    """
    if _key_blocks(obj):
        _key_fades(obj, [], ())
    else:
        appearance_fades.clear_fades(obj)
    _remove_keys(obj, [key.name for key in _key_blocks(obj) if key.name != BASIS])
    _remove_keys(obj, [BASIS] if _key_blocks(obj) else [])


def _is_clip_key(name: str) -> bool:
    return name == BASIS or re.fullmatch(rf"{KEY_PREFIX}\d+", name) is not None


def _key_blocks(obj: bpy.types.Object):
    shape_keys = obj.data.shape_keys  # pyrefly: ignore[missing-attribute]
    return () if shape_keys is None else shape_keys.key_blocks


def _add_keys(obj: bpy.types.Object, posed, schedule: tuple[tuple[int, int], ...]) -> None:
    """Add one key per frame, off at Blender frame 0, and on for each run of ticks the schedule shows it.

    Blender frame 1 is the tick the sequence starts on.
    """
    if obj.data.shape_keys is None:  # pyrefly: ignore[missing-attribute]
        obj.shape_key_add(name=BASIS, from_mix=False)
    keys = []
    for index, frame in enumerate(posed):
        key = obj.shape_key_add(name=f"{NEW_PREFIX}{index}", from_mix=False)
        key.data.foreach_set("co", [c for point in frame.vertices for c in game_to_blender(point)])  # pyrefly: ignore[missing-attribute]
        key.value = 0.0
        key.keyframe_insert("value", frame=0)
        keys.append(key)
    start = 1
    for index, ticks in schedule:
        key = keys[index]
        for frame_number, value in ((start, 1.0), (start + ticks, 0.0)):
            key.value = value
            key.keyframe_insert("value", frame=frame_number)
        start += ticks


def _key_fades(obj: bpy.types.Object, fades, schedule: tuple[tuple[int, int], ...]) -> None:
    """Replace the shape keys' fade curves and materials with the new clip's, keyed on the same ticks as its keys."""
    key = obj.data.shape_keys  # pyrefly: ignore[missing-attribute]
    for bag in _channelbags(key):
        for curve in [c for c in bag.fcurves if c.data_path.startswith(f'["{appearance_fades.PROPERTY_PREFIX}')]:
            bag.fcurves.remove(curve)
    appearance_fades.clear_fades(obj)
    for fade in fades:
        path = f'["{fade.prop}"]'
        key[fade.prop] = float(fade.rest)
        key.keyframe_insert(path, frame=0)
        start = 1
        for index, ticks in schedule:
            key[fade.prop] = float(fade.values[index])
            key.keyframe_insert(path, frame=start)
            start += ticks
        key[fade.prop] = float(fade.rest)
        key.keyframe_insert(path, frame=start)
    appearance_fades.apply_fades(obj, key, fades)


def _remove_keys(obj: bpy.types.Object, names: list[str]) -> None:
    """Remove the named shape keys and their animation curves, which Blender would otherwise leave in the action.

    Removing the last key block also removes the Key datablock.
    """
    shape_keys = obj.data.shape_keys  # pyrefly: ignore[missing-attribute]
    if shape_keys is None:
        return
    paths = {f'key_blocks["{name}"].value' for name in names}
    for bag in _channelbags(shape_keys):
        for curve in [curve for curve in bag.fcurves if curve.data_path in paths]:
            bag.fcurves.remove(curve)
    for name in names:
        obj.shape_key_remove(obj.data.shape_keys.key_blocks[name])  # pyrefly: ignore[missing-attribute]


def _channelbags(shape_keys: bpy.types.Key) -> list:
    animation = shape_keys.animation_data
    if animation is None or animation.action is None:
        return []
    return [bag for layer in animation.action.layers for strip in layer.strips for bag in strip.channelbags]


def _hold_each_value(obj: bpy.types.Object) -> None:
    """Make every keyframe constant, so a frame shows exactly one pose with no blending."""
    for bag in _channelbags(obj.data.shape_keys):  # pyrefly: ignore[bad-argument-type, missing-attribute]
        for curve in bag.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "CONSTANT"
