"""The functions that a script calls to build a scene (spec 170, ADR 0031).

Every input is an argument. No function here reads the add-on preferences or a scene property of the panel, and none
registers a class, so a script uses them with the add-on not enabled. `folder` is the cache folder, and `brightness`
is the client brightness that colours are shown at, such as 0.6 or 0.8. docs/scripted-use.md has an example of each
call.
"""

import functools
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Matrix

from ..animation.clip import CacheClip
from ..formats.appearance_look import Look, look_preset
from ..formats.cache_profile import shared_profile
from ..formats.item_model import inventory_model, item_lighting
from ..formats.item_wear import ItemWear, load_item_wear
from ..formats.js5 import Js5Store
from ..formats.lighting import light_hsl
from ..formats.travel import RUN_FRAMES_PER_TILE, WALK_FRAMES_PER_TILE, travel_frames
from . import appearance_clip, appearance_collection, appearance_preview


@dataclass(frozen=True)
class Player:
    collection: bpy.types.Collection
    """The player collection, which the bakes and `save_player` take."""
    rig: bpy.types.Object
    parts: tuple[bpy.types.Object, ...]
    """The mesh objects: the body, then a worn weapon and a worn shield."""


def create_player(
    folder: Path,
    look: Look,
    *,
    brightness: float,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    name: str = "Player",
) -> Player:
    """A new player of the look, with its rig at `location`, linked to the scene (ADR 0031). Blender adds `.001` to a
    name that is taken. Two calls with one location put two players on the same place.

    It refuses what `look_preset` refuses, and a kit, item or model that the cache lacks. Everything that can fail
    runs before any Blender data exists."""
    appearance_collection.check_no_edit_mode("creating a player")
    preset = look_preset(look, shared_profile(folder).kits, _item_wear())
    body, shading, slots = appearance_preview.assemble_parts(preset, folder)
    collection = appearance_collection.build_collection(body, shading, preset, name, brightness, location, slots)
    return Player(
        collection, appearance_collection.armature_of(collection), tuple(appearance_collection.parts(collection))
    )


def attach_to_joint(
    obj: bpy.types.Object,
    rig: bpy.types.Object,
    joint: str,
    *,
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Constraint:
    """Put `obj` on a joint of a rig with a new Child Of constraint, so that it follows the joint through every clip
    and takes the scale of the rig. `offset` is the place of the object's origin from the head of the joint, in game
    units in the axes of the joint. `rotation` is an XYZ Euler in radians in those axes. It refuses a joint that the
    rig does not have, before any change.

    Blender 5.3 gives a new Child Of constraint a pending inverse, which it sets at the next evaluation to cancel the
    target's transform at that moment. On a rig with a scale of 0.01, that made a held item 100 times too large
    (issue 170, gap e). So the inverse is the identity here, and nothing is pending."""
    joints = [] if rig.pose is None else [b.name for b in rig.pose.bones if not _is_label_bone(b.name)]
    if joint not in joints:
        raise ValueError(f"{rig.name} has no joint {joint!r}. Its joints are {', '.join(joints)}")
    constraint = obj.constraints.new("CHILD_OF")
    assert isinstance(constraint, bpy.types.ChildOfConstraint)
    constraint.target = rig
    constraint.subtarget = joint
    constraint.set_inverse_pending = False
    constraint.inverse_matrix = Matrix.Identity(4)
    obj.location = offset
    obj.rotation_euler = rotation
    return constraint


def bake_clip(
    player: bpy.types.Collection,
    folder: Path,
    sequence: int,
    *,
    start: int = 0,
    repeat_until: int | None = None,
    action: bool = False,
    smooth: bool = False,
    set_scene_timing: bool = False,
) -> bpy.types.NlaStrip:
    """Bake a sequence of the cache onto the rig of a player collection as a strip that starts at Blender frame
    `start`, which can be below 0, and return the strip. `repeat_until`, `action` and `smooth` are those of
    `appearance_clip.bake_clip_to_rig`, which also names what is refused.

    The frame rate and the frame range of the scene stay as they are, unless `set_scene_timing` is set. Then the bake
    sets them as the Bake Clip button does. One Blender frame of a clip is one client tick of 20 ms, so a clip plays
    at its game speed only at 50 frames in a second."""
    appearance_clip.bake_clip_to_rig(
        player,
        CacheClip(Js5Store(folder), sequence),
        action=action,
        start=start,
        smooth=smooth,
        cache_folder=str(folder),
        set_scene_timing=set_scene_timing,
        repeat_until=repeat_until,
    )
    animation = appearance_collection.armature_of(player).animation_data
    assert animation is not None
    return next(s for s in animation.nla_tracks[appearance_clip.CLIP_TRACK].strips if round(s.frame_start) == start)


def key_travel(rig: bpy.types.Object, points: Sequence[Sequence[float]], *, start: int, run: bool = False) -> int:
    """Key the location of the rig object so that the actor is at the first point on frame `start` and goes from
    point to point at one speed: 30 frames for a tile at a walk and 15 at a run (ADR 0035). It returns the frame of
    the last point. Each point is x, y and z in the space of the rig object, such as a `Regions.tile_point`.

    The keys go to the action of the rig object, beside the clip strips of the bone bakes. The actor does not turn
    toward its direction. It refuses fewer than two points, before any key."""
    frames = travel_frames(points, start, RUN_FRAMES_PER_TILE if run else WALK_FRAMES_PER_TILE)
    for point, frame in zip(points, frames, strict=True):
        rig.location = (point[0], point[1], point[2])
        rig.keyframe_insert("location", frame=frame)
    animation = rig.animation_data
    assert animation is not None and animation.action is not None
    for layer in animation.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:  # pyrefly: ignore[missing-attribute]
                for curve in bag.fcurves:
                    if curve.data_path == "location":
                        for key in curve.keyframe_points:
                            if start <= key.co.x <= frames[-1]:
                                key.interpolation = "LINEAR"
    return frames[-1]


def _is_label_bone(name: str) -> bool:
    return name.startswith(appearance_collection.BONE_PREFIX)


@functools.cache
def _item_wear() -> ItemWear:
    return load_item_wear()


def import_item(
    folder: Path,
    item_id: int,
    *,
    brightness: float,
    collection: bpy.types.Collection | None = None,
    name: str | None = None,
) -> bpy.types.Object:
    """A new mesh object of the inventory model of an item, lit with the item light (ADR 0032), in `collection` or the
    scene collection. The corner colours are in `rs_lit`, and the material is the emission material of players. The
    object is in game units with the origin of the model, so it has its true size beside a player. `name` defaults to
    the name and id of the item, such as `Waterskin(4) 1823`.

    It refuses an item that the cache lacks, an item with no inventory model, and a model with a textured face or a
    face alpha of 254 or 255 (`lighting.light_hsl`). Everything that can fail runs before any Blender data exists."""
    profile = shared_profile(folder)
    definition = profile.item_definitions.get(item_id)
    if definition is None:
        raise ValueError(f"The cache at {folder} has no item {item_id}")
    model = inventory_model(definition, profile.load_model)
    shading = light_hsl(model, item_lighting(definition))
    name = f"{definition.worn.name} {item_id}" if name is None else name
    obj = bpy.data.objects.new(name, appearance_preview.build_mesh(model, shading, name, brightness, loose=False))
    (_scene_collection() if collection is None else collection).objects.link(obj)
    return obj


def _scene_collection() -> bpy.types.Collection:
    scene = bpy.context.scene
    assert scene is not None
    return scene.collection
