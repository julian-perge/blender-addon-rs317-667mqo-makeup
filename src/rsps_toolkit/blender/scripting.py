"""The functions that a script calls to build a scene (spec 170, ADR 0031).

Every input is an argument. No function here reads the add-on preferences or a scene property of the panel, and none
registers a class, so a script uses them with the add-on not enabled. `folder` is the cache folder, and `brightness`
is the client brightness that colours are shown at, such as 0.6 or 0.8. docs/scripted-use.md has an example of each
call.
"""

import functools
import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from ..animation.clip import CacheClip
from ..formats.appearance_look import Look, look_preset
from ..formats.cache_profile import shared_profile
from ..formats.item_model import inventory_model, item_lighting
from ..formats.item_wear import ItemWear, load_item_wear
from ..formats.js5 import Js5Store
from ..formats.lighting import light
from ..formats.region import REGION_SIZE, Terrain, load_terrain
from ..formats.travel import RUN_FRAMES_PER_TILE, WALK_FRAMES_PER_TILE, travel_frames
from . import appearance_clip, appearance_collection, appearance_preview, region_files, region_import
from .region_import import RegionReport
from .region_terrain import TILE_SIZE, tile_position


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

    It refuses what `look_preset` refuses, and a kit, item or model that the cache lacks. A failure removes what was
    made. The collection keeps the brightness, which lights the items that a later clip holds."""
    appearance_collection.check_no_edit_mode("creating a player")
    preset = look_preset(look, shared_profile(folder).kits, _item_wear())
    body, shading, slots = appearance_preview.assemble_parts(preset, folder)
    textures = appearance_preview.texture_pixels(folder, body, brightness)
    collection = appearance_collection.build_collection(
        body, shading, preset, name, brightness, location, slots, textures
    )
    collection[appearance_collection.BRIGHTNESS_KEY] = brightness
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
    units in the axes of the joint. `rotation` is an XYZ Euler in radians in those axes, and the object gets that
    rotation mode. It refuses a joint that the rig does not have, an object that is on a joint already and an object
    with a parent, before any change.

    Blender 5.3 gives a new Child Of constraint a pending inverse, which it sets at the next evaluation to cancel the
    target's transform at that moment. On a rig with a scale of 0.01, that made a held item 100 times too large
    (issue 170, gap e). So the inverse is the identity here, and nothing is pending."""
    joints = [] if rig.pose is None else [b.name for b in rig.pose.bones if not _is_label_bone(b.name)]
    if joint not in joints:
        raise ValueError(f"{rig.name} has no joint {joint!r}. Its joints are {', '.join(joints)}")
    if any(constraint.type == "CHILD_OF" for constraint in obj.constraints):
        raise ValueError(f"{obj.name} is on a joint already")
    if obj.parent is not None:
        raise ValueError(f"{obj.name} has the parent {obj.parent.name}, which would move it as well")
    constraint = obj.constraints.new("CHILD_OF")
    assert isinstance(constraint, bpy.types.ChildOfConstraint)
    constraint.target = rig
    constraint.subtarget = joint
    constraint.set_inverse_pending = False
    constraint.inverse_matrix = Matrix.Identity(4)
    obj.location = offset
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = rotation
    return constraint


def bake_clip(
    player: Player | bpy.types.Collection,
    folder: Path,
    sequence: int,
    *,
    start: int = 0,
    repeat_until: int | None = None,
    action: bool = False,
    smooth: bool = False,
    set_scene_timing: bool = False,
) -> bpy.types.NlaStrip:
    """Bake a sequence of the cache onto the rig of a player, or of a player collection, as a strip that starts at Blender frame
    `start`, which can be below 0, and return the strip. `repeat_until`, `action` and `smooth` are those of
    `appearance_clip.bake_clip_to_rig`, which also names what is refused.

    The frame rate and the frame range of the scene stay as they are, unless `set_scene_timing` is set. Then the bake
    sets them as the Bake Clip button does. One Blender frame of a clip is one client tick of 20 ms, so a clip plays
    at its game speed only at 50 frames in a second."""
    collection = player.collection if isinstance(player, Player) else player
    appearance_clip.bake_clip_to_rig(
        collection,
        CacheClip(Js5Store(folder), sequence),
        action=action,
        start=start,
        smooth=smooth,
        cache_folder=str(folder),
        set_scene_timing=set_scene_timing,
        repeat_until=repeat_until,
    )
    animation = appearance_collection.armature_of(collection).animation_data
    assert animation is not None
    return next(s for s in animation.nla_tracks[appearance_clip.CLIP_TRACK].strips if round(s.frame_start) == start)


def key_travel(rig: bpy.types.Object, points: Sequence[Sequence[float]], *, start: int, run: bool = False) -> int:
    """Key the location of the rig object so that the actor is at the first point on frame `start` and goes from
    point to point at one speed: 30 frames for a tile at a walk and 15 at a run (ADR 0035). It returns the frame of
    the last point. Each point is x, y and z in the space of the rig object, such as a `Regions.tile_point`.

    The keys go to the action of the rig object, beside the clip strips of the bone bakes. The actor does not turn
    toward its direction. It refuses fewer than two points, a point without x, y and z, and two points in a row at
    the same x and y, which would get the same frame, before any key."""
    for number, point in enumerate(points, 1):
        if len(point) != 3:
            raise ValueError(f"Point {number} {tuple(point)} needs x, y and z")
    for number, (before, after) in enumerate(zip(points, points[1:], strict=False), 1):
        if (before[0], before[1]) == (after[0], after[1]):
            raise ValueError(f"Points {number} and {number + 1} are at the same x and y")
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


@dataclass(frozen=True)
class Regions:
    """The regions of one `import_regions` call, in the order of the call."""

    collections: tuple[bpy.types.Collection, ...]
    appended: tuple[bool, ...]
    """For each region, whether it came from its saved region."""
    reports: tuple[RegionReport | None, ...]
    """The report of each import, or None for an appended region."""
    _terrains: dict[tuple[int, int], Terrain]
    _origin: Vector
    _turn: Matrix

    def tile_point(self, x: int, y: int) -> Vector:
        """The Blender point of the centre of world tile (x, y) at its ground height, after the region origin and the
        turn. A script puts a player there. It refuses a tile outside the regions."""
        return self._turn @ (_unmoved_tile_point(self._terrains, x, y) - self._origin)


def import_regions(
    folder: Path,
    regions: Sequence[tuple[int, int]],
    *,
    brightness: float,
    origin_tile: tuple[int, int] | None = None,
    turn: float = 0.0,
    decoration_clearance: float = 0.0,
    saved_folder: Path | None = None,
    parent: bpy.types.Collection | None = None,
) -> Regions:
    """Import the regions, given by their x and y numbers, side by side as in the game, into `parent` or the scene
    collection (ADR 0031).

    `origin_tile` is the region origin: a world tile of one of the regions, whose centre goes to the Blender origin at
    its ground height. With None, the south-west corner of the first region is at the origin at height 0, as the
    operator puts one region. `turn` is in degrees, counterclockwise seen from above, around the origin. Both change
    only the location and the rotation of each object. `decoration_clearance` is the wall decoration clearance in
    game units (ADR 0034).

    With `saved_folder`, a region comes from its saved region `region-<x>_<y>.blend` there when the key of that file
    fits (ADR 0033). In every other case the region is imported and saved there.

    It refuses no region, a region named twice, a region that the cache lacks and a region origin outside the
    regions, before any change. When `region_import.import_region` refuses a region for another cause, the regions
    before it stay in the file. A saved region that cannot be written gives a warning, and the import goes on."""
    regions = [(x, y) for x, y in regions]
    if not regions:
        raise ValueError("An import needs at least one region")
    for x, y in regions:
        if regions.count((x, y)) > 1:
            raise ValueError(f"Region {x}_{y} is named twice")
    store = Js5Store(folder)
    terrains = {(x, y): load_terrain(store, x, y) for x, y in regions}
    for x, y in regions:
        if (x, y) in terrains[x, y].missing:
            raise region_import.RefusalError(f"The cache has no terrain for region {x}_{y}")
    origin = Vector() if origin_tile is None else _unmoved_tile_point(terrains, *origin_tile)
    turned = Matrix.Rotation(math.radians(turn), 3, "Z")
    parent = _scene_collection() if parent is None else parent
    collections: list[bpy.types.Collection] = []
    reports: list[RegionReport | None] = []
    for x, y in regions:
        collection = report = None
        path = None if saved_folder is None else saved_folder / f"region-{x}_{y}.blend"
        key = "" if path is None else region_files.region_key(folder, x, y, brightness, decoration_clearance)
        if path is not None:
            collection = region_files.append_region(parent, path, key)
        if collection is None:
            collection, report = region_import.import_region(parent, folder, x, y, brightness, decoration_clearance)
            if path is not None:
                try:
                    region_files.save_region(collection, path, key)
                except OSError as error:
                    warnings.warn(f"Region {x}_{y} was not saved to {path}: {error}", stacklevel=2)
        offset = _region_offset(terrains, x, y) - origin
        # A list, because Blender 5.3 crashed on a change of objects during a loop over `all_objects`.
        for obj in list(collection.all_objects):
            obj.location = turned @ (obj.location + offset)
            obj.rotation_euler.z += math.radians(turn)
        collections.append(collection)
        reports.append(report)
    return Regions(
        tuple(collections), tuple(report is None for report in reports), tuple(reports), terrains, origin, turned
    )


def import_region(
    folder: Path,
    x: int,
    y: int,
    *,
    brightness: float,
    origin_tile: tuple[int, int] | None = None,
    turn: float = 0.0,
    decoration_clearance: float = 0.0,
    saved_folder: Path | None = None,
    parent: bpy.types.Collection | None = None,
) -> Regions:
    """`import_regions` for the one region (x, y)."""
    return import_regions(
        folder,
        [(x, y)],
        brightness=brightness,
        origin_tile=origin_tile,
        turn=turn,
        decoration_clearance=decoration_clearance,
        saved_folder=saved_folder,
        parent=parent,
    )


def _region_offset(terrains: dict[tuple[int, int], Terrain], x: int, y: int) -> Vector:
    """Where the south-west corner of region (x, y) is from that of the first region, in game units."""
    first_x, first_y = next(iter(terrains))
    return Vector(((x - first_x) * REGION_SIZE * TILE_SIZE, (y - first_y) * REGION_SIZE * TILE_SIZE, 0.0))


def _unmoved_tile_point(terrains: dict[tuple[int, int], Terrain], x: int, y: int) -> Vector:
    """The centre of world tile (x, y) at its ground height, before the region origin and the turn."""
    region = (x // REGION_SIZE, y // REGION_SIZE)
    if region not in terrains:
        names = ", ".join(f"{region_x}_{region_y}" for region_x, region_y in terrains)
        raise ValueError(f"Tile ({x}, {y}) is in none of the regions {names}")
    point = tile_position(terrains[region], x % REGION_SIZE, y % REGION_SIZE)
    return Vector(point) + _region_offset(terrains, *region)


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

    A textured face shows its texture times its light value, and a face that the client never draws is left out (ADR
    0036). It refuses an item that the cache lacks, an item with no inventory model, and a texture that the cache
    lacks. Everything that can fail runs before any Blender data exists."""
    profile = shared_profile(folder)
    definition = profile.item_definitions.get(item_id)
    if definition is None:
        raise ValueError(f"The cache at {folder} has no item {item_id}")
    model = inventory_model(definition, profile.load_model)
    shading = light(model, item_lighting(definition))
    textures = appearance_preview.texture_pixels(folder, model, brightness)
    name = f"{definition.worn.name} {item_id}" if name is None else name
    mesh = appearance_preview.build_mesh(model, shading, name, brightness, loose=False, textures=textures)
    obj = bpy.data.objects.new(name, mesh)
    (_scene_collection() if collection is None else collection).objects.link(obj)
    return obj


def _scene_collection() -> bpy.types.Collection:
    scene = bpy.context.scene
    assert scene is not None
    return scene.collection
