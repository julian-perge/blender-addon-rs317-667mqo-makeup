"""Bakes a revision-149 game clip onto a player collection, as shape keys (exact) or as an NLA strip of bone keys.

The two bakes refuse what they cannot bake over, pose the clip (`appearance_pose`), place it and record it, and
Update Player bakes the records again. `appearance_shape_keys` writes the shape keys and `appearance_bone_action` the
bone action. The panel's two ways to choose the clip the bakes read are here too: the search over the cache's player
clips, and the buttons that choose a clip the weapon tables give the active player's weapon.
"""

import functools
import json
import math
from pathlib import Path

import bpy

from ..animation.clip import CacheClip, ClipSource, clip_from_record, source_of
from ..formats.appearance import ITEM_OFFSET
from ..formats.appearance_preset import loads_preset
from ..formats.weapon_clips import BLOCK, RUN, STAND, WALK, WeaponClips, WeaponClipTable, load_weapon_clips
from . import (
    appearance_bone_action,
    appearance_clip_cache,
    appearance_collection,
    appearance_fades,
    appearance_held,
    appearance_pose,
    appearance_preview,
    appearance_shape_keys,
)
from .appearance_props import PLAY_AS_ITEMS

# The NLA track that holds the bone bake's clip strips. Other tracks are the user's.
CLIP_TRACK = "RS clips"
# An empty track the bake keeps above the clip track, so Blender's Push Down puts the user's keys there, layered over
# the held clips, not between them on the clip track, where only one strip plays at a time.
USER_TRACK = "Your motion"
# One Blender frame is one client tick at 50 fps. The 20 ms tick is revision 1's clock and is unverified for
# revision 149.
CLIP_FPS = 50
# The NLA strip settings that Update and Duplicate Player copy onto the new rig for the user's own strips, in an order
# Blender accepts.
STRIP_SETTINGS = (
    "action_frame_end",
    "action_frame_start",
    "scale",
    "repeat",
    "blend_type",
    "extrapolation",
    "influence",
    "use_animated_influence",
    "blend_in",
    "blend_out",
    "use_auto_blend",
    "use_reverse",
    "mute",
)


def bake_clip(
    collection: bpy.types.Collection,
    clip: ClipSource | Path,
    *,
    action: bool = False,
    dump_folder: str = "",
    set_scene_timing: bool = True,
) -> int:
    """Replace the player's clip shape keys with one per frame of the clip, keyed on the ticks the client shows them.

    A pose sequence (the default) is baked for one cycle, which the scene range repeats; an action sequence is baked
    until the client stops it, following its loop offset and loop limit (`frames.frame_schedule`). Refuses a player
    with edits, since the clip is computed from the mesh as built, and a mesh with shape keys the bake did not make. A
    failure keeps the previous clip and removes the held objects and label bones the bake made (issue 13, decision 4).
    An action with held items is posed as the client's held variant (`appearance_pose`), and the hand objects it
    replaces are hidden while it plays (`appearance_held`). The scene is
    set to 50 fps and its range to the clip, unless `set_scene_timing` is False (`bake_recorded`). Returns the number
    of frames.
    """
    appearance_collection.check_object_mode(collection, "baking a clip")
    objects = appearance_collection.parts(collection)
    rig = appearance_collection.armature_of(collection)
    playing = _rig_action(rig)
    if playing is not None:
        raise ValueError(
            f"{rig.name} plays the action {playing.name!r}, and shape keys would move the mesh a second time. "
            "Unlink the rig's action first"
        )
    tracks = [] if rig.animation_data is None else [t.name for t in rig.animation_data.nla_tracks if len(t.strips)]
    if tracks:
        raise ValueError(
            f"{rig.name} has NLA strips on {', '.join(tracks)}, and shape keys would move the mesh a second time. "
            "Remove the strips first"
        )
    for obj in objects:
        others = appearance_shape_keys.foreign_keys(obj)
        if others:
            raise ValueError(
                f"{obj.name} has shape keys the bake did not make ({', '.join(map(repr, others))}). Remove them first"
            )
    if appearance_collection.is_edited(collection):
        raise ValueError(f"{collection.name} has edits, so a clip cannot be baked onto it")
    source = source_of(clip)
    posed = appearance_pose.pose_player(collection, source, action=action, dump_folder=dump_folder)
    with appearance_held.held_items_undone_on_failure(collection):
        parts = posed.ensure_parts()
        appearance_shape_keys.write(parts, posed.schedule)
    # The hand objects this clip hides, and held objects of an earlier clip, lose that clip's keys.
    for obj in set(appearance_collection.parts(collection)) - {part.obj for part in parts}:
        appearance_shape_keys.clear(obj)
    appearance_held.key_visibility(collection, [(1, posed.equipment)])
    if set_scene_timing:
        scene = bpy.context.scene
        scene.render.fps, scene.render.fps_base = CLIP_FPS, 1.0
        scene.frame_start, scene.frame_end = 1, sum(ticks for _, ticks in posed.schedule)
    collection[appearance_collection.CLIP_KEY] = json.dumps(
        {**source.record(), "method": "SHAPE_KEYS", "action": action, **posed.record}
    )
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    return len(posed.frames)


def bake_clip_to_rig(
    collection: bpy.types.Collection,
    clip: ClipSource | Path,
    *,
    action: bool = False,
    start: int = 1,
    smooth: bool = False,
    dump_folder: str = "",
    set_scene_timing: bool = True,
) -> int:
    """Add the clip to the rig as an NLA strip on the "RS clips" track, starting at Blender frame `start`.

    Each joint bone is keyed with the least-squares rotation, uniform scale and location that moves the vertices of
    the labels it owns closest to the client's posed vertices (`label_fit.fit_frame`), as seen from its parent, on
    the same ticks as `bake_clip`. Each label bone is keyed with what is left of its own label's fit under its joint,
    so the mesh moves exactly as the label fit moves it, and the joints carry the clip for the user's own keys. The
    result differs from the shape-key bake by the client's integer rounding (docs/research/osrs-149-animation.md,
    "Bone rig clip"). The strip holds its last pose until the next strip starts (Hold Forward), so the body never drops
    to the cache's rest pose between clips. The bake sets the scene to 50 fps, and the first clip sets the scene range
    to itself; later ones only extend its end. With `set_scene_timing` False (`bake_recorded`), the scene's rate and
    range stay as they are. A strip from an earlier bake that starts on the same frame is replaced; the rig's active
    action and other tracks are the user's and are left alone. Refuses an edited player, a mesh with shape keys, since
    both would move the mesh, and a strip that would overlap another on the track. A failure before the new strip is
    in place adds no objects, meshes, bones or actions, since the held objects, label bones and action made for the
    clip are removed again. A track it made stays, and a strip it replaced stays removed. The steps after the strip is
    in place (fades, visibility keys) are not undone (issue 13, decisions 1 and 3). An action with held items is posed
    as the client's held variant (`appearance_pose`), and every clip strip keys which hand objects show from its start
    until the next strip (`appearance_held`). Returns the number of frames.
    """
    appearance_collection.check_object_mode(collection, "baking a clip")
    objects = appearance_collection.parts(collection)
    rig = appearance_collection.armature_of(collection)
    if not appearance_collection.is_joint_rig(rig):
        raise ValueError(
            f"{collection.name} was built before players had joint bones. Update Player rebuilds it with them"
        )
    keyed = next((obj for obj in objects if appearance_shape_keys.has_keys(obj)), None)
    if keyed is not None:
        raise ValueError(
            f"{keyed.name} has shape keys, and a bone clip would move the mesh a second time on top of them. "
            "Update Player rebuilds the player without them"
        )
    if appearance_collection.is_edited(collection):
        raise ValueError(f"{collection.name} has edits, so a clip cannot be baked onto it")
    source = source_of(clip)
    posed = appearance_pose.pose_player(collection, source, action=action, dump_folder=dump_folder)
    length = sum(ticks for _, ticks in posed.schedule)
    track = _clip_track(rig)
    replaced = None if track is None else next((s for s in track.strips if round(s.frame_start) == start), None)
    if replaced is not None and appearance_collection.RIG_ACTION_KEY not in (replaced.action or {}):
        raise ValueError(f"The strip {replaced.name!r} on {CLIP_TRACK} starts on frame {start} and is not a bake")
    for other in [] if track is None else track.strips:
        if other != replaced and other.frame_start < start + length and start < other.frame_end:
            raise ValueError(
                f"The clip would cover frames {start} to {start + length}, over the strip {other.name!r}. "
                "Move the current frame or the strip"
            )
    with appearance_held.held_items_undone_on_failure(collection):
        parts = posed.ensure_parts()
        # A label and rest alpha fade alike on every part, so the rig keys one property for each.
        fades = list({fade.prop: fade for part in parts for fade in part.fades}.values())
        name = f"{collection.name} {_title(source)}"
        record = json.dumps({**source.record(), "method": "BONES", "action": action, "smooth": smooth, **posed.record})
        new, slot = appearance_bone_action.write(name, rig, posed, fades, smooth=smooth)
        try:
            new[appearance_collection.CLIP_KEY] = record
            animation = rig.animation_data or rig.animation_data_create()
            first = track is None or all(strip == replaced for strip in track.strips)
            if track is None:
                track = animation.nla_tracks.new()
                track.name = CLIP_TRACK
            if animation.nla_tracks.get(USER_TRACK) is None:
                animation.nla_tracks.new().name = USER_TRACK
                # Push Down gives its strip the rig's blending, so the user's keys add to the clip pose under them,
                # and a key at rest leaves the clips playing instead of covering them on every frame.
                animation.action_blend_type = "COMBINE"
            old = None
            if replaced is not None:
                old = replaced.action
                track.strips.remove(replaced)
            _add_clip_strip(track, name, start, new, slot, length)
        except Exception:
            bpy.data.actions.remove(new)
            raise
    for pose_bone in rig.pose.bones:  # pyrefly: ignore[missing-attribute]
        pose_bone.rotation_mode = "QUATERNION"
    for part in parts:
        appearance_fades.apply_fades(part.obj, rig, part.fades)
    appearance_held.key_visibility(collection, _strip_spans(collection, track))
    # Another rig can still use the replaced action, for example one the user assigned it to, so only an unused one is
    # removed (the owner's choice, issue 20).
    if old is not None and old.users == 0:
        bpy.data.actions.remove(old)
    if set_scene_timing:
        scene = bpy.context.scene
        scene.render.fps, scene.render.fps_base = CLIP_FPS, 1.0
        last = max(round(s.frame_end) for s in track.strips) - 1
        if first:
            scene.frame_start, scene.frame_end = 1, last
        else:
            scene.frame_end = max(scene.frame_end, last)
    if appearance_collection.CLIP_KEY in collection:
        del collection[appearance_collection.CLIP_KEY]
    collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    return len(posed.frames)


def _add_clip_strip(
    track: bpy.types.NlaTrack,
    name: str,
    start: int,
    action: bpy.types.Action,
    slot: bpy.types.ActionSlot,
    length: int,
) -> None:
    """Add the clip's strip at `start`, playing the action's frames 1 to 1 + `length` and then holding its last pose
    until the next strip starts (Hold Forward).

    Blender sizes a new strip from its action's frame range, and the baked keys start at frame 0. So the action first
    gets its own range of 1 to 1 + `length` (Manual Frame Range). Without it the new strip would come out one frame
    longer than the clip, and Blender would refuse it where it ends at the start of the next strip (issue 13,
    decision 3).
    """
    action.use_frame_range = True
    action.frame_start, action.frame_end = 1, 1 + length
    strip = track.strips.new(name, start, action)
    strip.action_slot = slot
    strip.action_frame_end = 1 + length
    strip.action_frame_start = 1
    strip.extrapolation = "HOLD_FORWARD"


def _strip_spans(
    collection: bpy.types.Collection, track: bpy.types.NlaTrack
) -> list[tuple[int, tuple[int, ...] | None]]:
    """Each clip strip's start frame and, for a clip with held items, the equipment the client shows while it plays."""
    spans = []
    for strip in track.strips:
        record = (
            json.loads(strip.action[appearance_collection.CLIP_KEY])
            if strip.action is not None and appearance_collection.CLIP_KEY in strip.action
            else {}
        )
        spans.append((round(strip.frame_start), appearance_pose.shown_equipment(collection, record)))
    return spans


def bake_recorded(collection: bpy.types.Collection, clip: str, start: int = 1, dump_folder: str = "") -> int:
    """Bake a clip recorded by an earlier bake, as Update and Duplicate Player do for the player they build. Returns
    the frame count.

    The scene's rate and range stay as they are: the user chose that only their click changes the rate (plan 14,
    decision 4), and resetting the range could cut another player's longer clip off it.
    """
    record = json.loads(clip)
    if record["method"] == "BONES":
        return bake_clip_to_rig(
            collection,
            clip_from_record(record),
            action=record["action"],
            start=start,
            smooth=record.get("smooth", False),
            dump_folder=dump_folder,
            set_scene_timing=False,
        )
    return bake_clip(
        collection,
        clip_from_record(record),
        action=record["action"],
        dump_folder=dump_folder,
        set_scene_timing=False,
    )


def recorded_clips(collection: bpy.types.Collection) -> list[tuple[str, int]]:
    """Every clip baked onto the player, as its record and start frame, in the order Update bakes them again.

    A shape-key clip, or a bone clip baked before clips became strips, is recorded on the collection and starts on
    frame 1. Bone clips are recorded on their strips' actions.
    """
    clips = []
    if appearance_collection.CLIP_KEY in collection:
        clips.append((collection[appearance_collection.CLIP_KEY], 1))
    track = _clip_track(appearance_collection.armature_of(collection))
    for strip in [] if track is None else track.strips:
        if strip.action is not None and appearance_collection.CLIP_KEY in strip.action:
            clips.append((strip.action[appearance_collection.CLIP_KEY], round(strip.frame_start)))
    return clips


def carry_animation(old: bpy.types.Object, new: bpy.types.Object, *, copy_actions: bool = False) -> None:
    """Give the new rig that Update or Duplicate Player builds the user's own animation: the active action unless a
    bake made it, its blending, and every NLA strip a bake did not make, on a track of the same name, with each
    strip's frames, blending and repeats. A user's strip on the clip track, where Push Down put it before the bake
    kept a track for it, moves to that track. The clip track is made empty in its old place, under the user's tracks,
    and Update or Duplicate Player bakes the clip strips into it again. The bones keep their names.

    Update hands the same actions to the rebuilt rig. Duplicate Player passes `copy_actions`, so the copy plays one
    copy of each action: keys changed on one player leave the other alone, and strips that shared an action on the
    old rig share its copy on the new one.
    """
    source = old.animation_data
    if source is None:
        return
    copies: dict[bpy.types.Action, bpy.types.Action] = {}

    def own(action: bpy.types.Action) -> bpy.types.Action:
        if not copy_actions:
            return action
        if action not in copies:
            copies[action] = action.copy()
        return copies[action]

    target = new.animation_data or new.animation_data_create()
    for name in ("action_blend_type", "action_extrapolation", "action_influence"):
        setattr(target, name, getattr(source, name))
    action = source.action
    if action is not None and appearance_collection.RIG_ACTION_KEY not in action:
        target.action = own(action)
        target.action_slot = _same_slot(target.action, source.action_slot)
    for track in source.nla_tracks:
        strips = [
            s for s in track.strips if s.action is not None and appearance_collection.RIG_ACTION_KEY not in s.action
        ]
        if track.name == CLIP_TRACK:
            target.nla_tracks.new().name = CLIP_TRACK
            if not strips:
                continue
        name = USER_TRACK if track.name == CLIP_TRACK else track.name
        copy = target.nla_tracks.get(name) or target.nla_tracks.new()
        copy.name, copy.mute, copy.is_solo = name, track.mute, track.is_solo
        for strip in strips:
            assert strip.action is not None
            action = own(strip.action)
            placed = copy.strips.new(strip.name, round(strip.frame_start), action)
            placed.action_slot = _same_slot(action, strip.action_slot)
            for name in STRIP_SETTINGS:
                setattr(placed, name, getattr(strip, name))


def _same_slot(action: bpy.types.Action, slot: bpy.types.ActionSlot | None) -> bpy.types.ActionSlot | None:
    """The slot of `action` that has the identifier of `slot`. `slot` belongs either to `action` itself or to the
    action that `action` was copied from. Returns None when `slot` is None or `action` has no slot with that
    identifier."""
    if slot is None:
        return None
    return next((own for own in action.slots if own.identifier == slot.identifier), None)


def has_own_animation(rig: bpy.types.Object) -> bool:
    """True when the rig plays an action or strip that no bake made."""
    animation = rig.animation_data
    if animation is None:
        return False
    actions = [animation.action] + [strip.action for track in animation.nla_tracks for strip in track.strips]
    return any(action is not None and appearance_collection.RIG_ACTION_KEY not in action for action in actions)


def plays_at_another_rate(scene: bpy.types.Scene, collection: bpy.types.Collection) -> bool:
    """True when the player has baked clips and the scene plays at another rate than the `CLIP_FPS` frames per second
    the bakes set, so the clips would run at another speed than they were baked for. A player whose clips cannot be
    read, such as one holding two rigs, is not flagged.
    """
    try:
        clips = recorded_clips(collection)
    except ValueError:
        return False
    # Blender stores fps_base in single precision, so a base of 1.2 reads back as 1.2000000477, and the rate is
    # compared with a tolerance instead of exactly.
    return bool(clips) and not math.isclose(scene.render.fps / scene.render.fps_base, CLIP_FPS, rel_tol=1e-6)


class RSPS_OT_set_clip_fps(bpy.types.Operator):
    bl_idname = "rsps.set_clip_fps"
    bl_label = f"Set {CLIP_FPS} fps"
    bl_description = (
        f"Set the scene to {CLIP_FPS} frames per second, the rate the bakes set and the clips are timed for"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.render.fps, context.scene.render.fps_base = CLIP_FPS, 1.0
        return {"FINISHED"}


def _title(source: ClipSource) -> str:
    return (
        appearance_clip_cache.clip_label(source.sequence_id)
        if isinstance(source, CacheClip)
        else Path(str(source.record()["folder"])).name
    )


def _clip_track(rig: bpy.types.Object):
    animation = rig.animation_data
    return None if animation is None else animation.nla_tracks.get(CLIP_TRACK)


def _rig_action(rig: bpy.types.Object) -> bpy.types.Action | None:
    return None if rig.animation_data is None else rig.animation_data.action


def _clip_items(self, context) -> list[tuple[str, str, str]]:
    return _clip_choices


_clip_choices = [(str(i), appearance_clip_cache.clip_label(i), "") for i in sorted(appearance_clip_cache.clip_names())]


class RSPS_OT_pick_clip(bpy.types.Operator):
    bl_idname = "rsps.pick_clip"
    bl_label = "Search Clips"
    bl_description = "Find a player animation by typing part of its RuneLite name or its id, and choose it for baking"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "clip"

    clip: bpy.props.EnumProperty(name="Clip", items=_clip_items)  # pyrefly: ignore[bad-assignment]

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        context.scene.rs_appearance.clip_sequence = int(self.clip)
        return {"FINISHED"}


# The panel's two rows of weapon clip buttons. Each button has a choice, a label, a tooltip and the place of its clip
# among the weapon's stance clips or its attack clips.
STANCE_BUTTONS = (
    ("STAND", "Stand", "Choose the weapon's stand clip, baked as a Pose", STAND),
    ("WALK", "Walk", "Choose the weapon's walk clip, baked as a Pose", WALK),
    ("RUN", "Run", "Choose the weapon's run clip, baked as a Pose", RUN),
)
ATTACK_BUTTONS = (
    ("ATTACK_1", "1", "Choose the weapon's attack for the first combat style button, baked as an Action", 0),
    ("ATTACK_2", "2", "Choose the weapon's attack for the second combat style button, baked as an Action", 1),
    ("ATTACK_3", "3", "Choose the weapon's attack for the third combat style button, baked as an Action", 2),
    ("ATTACK_4", "4", "Choose the weapon's attack for the fourth combat style button, baked as an Action", 3),
    ("BLOCK", "Block", "Choose the weapon's block clip, baked as an Action", BLOCK),
)


@functools.cache
def weapon_clip_table() -> WeaponClipTable:
    return load_weapon_clips()


def worn_weapon(player: bpy.types.Collection) -> int | None:
    """The item id in the player's weapon slot, from its stored settings, or None when the slot holds no item."""
    value = loads_preset(player[appearance_preview.PRESET_KEY]).equipment[appearance_collection.WEAPON_SLOT]
    return value - ITEM_OFFSET if value >= ITEM_OFFSET else None


def worn_weapon_clips(player: bpy.types.Collection) -> WeaponClips:
    """The weapon table's clips for the player's weapon, or the unarmed clips for an empty weapon slot.

    Every table read gives an empty hand the unarmed clips (research note, section 1).
    """
    weapon = worn_weapon(player)
    return weapon_clip_table().unarmed if weapon is None else weapon_clip_table().clips(weapon)


def unlisted_weapon(player: bpy.types.Collection) -> int | None:
    """The item id of the player's weapon when neither weapon table lists it, or None."""
    weapon = worn_weapon(player)
    return weapon if weapon is not None and not weapon_clip_table().lists(weapon) else None


def button_clip(clips: WeaponClips, choice: str) -> tuple[int, str]:
    """The clip a weapon clip button picks, -1 when the weapon has none, and the Play As it bakes with.

    A stance clip bakes as a Pose, since the client plays it in the pose slot (research note, section 1), and an
    attack clip as an Action.
    """
    stance = {name: place for name, _, _, place in STANCE_BUTTONS}
    if choice in stance:
        return clips.stance[stance[choice]], "POSE"
    attack = {name: place for name, _, _, place in ATTACK_BUTTONS}
    return clips.attack[attack[choice]], "ACTION"


class RSPS_OT_pick_weapon_clip(bpy.types.Operator):
    bl_idname = "rsps.pick_weapon_clip"
    bl_label = "Weapon Clip"
    bl_description = "Choose a clip that the weapon tables give the active player's weapon"
    bl_options = {"REGISTER", "UNDO"}

    choice: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        items=[(name, label, text) for name, label, text, _ in STANCE_BUTTONS + ATTACK_BUTTONS], options={"HIDDEN"}
    )

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    @classmethod
    def description(cls, context, properties):
        return next(text for name, _, text, _ in STANCE_BUTTONS + ATTACK_BUTTONS if name == properties.choice)

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        clip, play_as = button_clip(worn_weapon_clips(player), self.choice)
        if clip < 0:
            self.report({"ERROR"}, "The weapon has no clip for this button")
            return {"CANCELLED"}
        context.scene.rs_appearance.clip_sequence = clip
        context.scene.rs_appearance.clip_play_as = play_as
        return {"FINISHED"}


class RSPS_OT_bake_clip(bpy.types.Operator):
    bl_idname = "rsps.bake_clip"
    bl_label = "Bake Clip"
    bl_description = (
        "Bake the chosen game clip from the cache onto the active player, as exact shape keys or as editable bone keys"
    )
    bl_options = {"REGISTER", "UNDO"}

    sequence: bpy.props.IntProperty(name="Sequence", default=-1, options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    # Overrides the add-on preference for the dump a clip's held items are assembled from; scripts and tests set it.
    dump_folder: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})  # pyrefly: ignore[bad-assignment]
    smooth: bpy.props.BoolProperty(name="Smooth", options={"HIDDEN"})  # pyrefly: ignore[bad-assignment]
    # Scripts and tests bake a folder written by tests/fixtures/animation149/export_clip.py instead of the cache.
    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})  # pyrefly: ignore[bad-assignment]
    # The panel passes its own Play As choice.
    play_as: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Play As",
        description="How the client advances the clip's frames",
        items=PLAY_AS_ITEMS,
        default="POSE",
        options={"HIDDEN"},
    )
    method: bpy.props.EnumProperty(  # pyrefly: ignore[bad-assignment]
        name="Method",
        description="What the clip is baked onto",
        items=(
            ("SHAPE_KEYS", "Shape Keys", "One shape key per frame, equal to the client's vertices"),
            (
                "BONES",
                "Bones",
                "Keys on the label bones, editable, up to 2.1 game units from the client on the recorded clips",
            ),
        ),
        default="SHAPE_KEYS",
    )

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        try:
            if self.directory:
                clip: ClipSource | Path = Path(self.directory)
            elif self.sequence < 0:
                raise ValueError("Choose a clip first")
            else:
                clip = appearance_clip_cache.cache_clip(self.sequence)
            action = self.play_as == "ACTION"
            if self.method == "BONES":
                frames = bake_clip_to_rig(
                    player,
                    clip,
                    action=action,
                    start=context.scene.frame_current,
                    smooth=self.smooth,
                    dump_folder=self.dump_folder,
                )
            else:
                frames = bake_clip(player, clip, action=action, dump_folder=self.dump_folder)
        except (OSError, LookupError, ValueError, RuntimeError) as error:
            appearance_preview.fail(self, context, error)
            return {"CANCELLED"}
        context.scene.rs_appearance.last_error = ""
        target = "its bones" if self.method == "BONES" else "shape keys"
        self.report({"INFO"}, f"Baked {frames} frames onto {player.name} as {target}")
        return {"FINISHED"}


classes = (RSPS_OT_pick_clip, RSPS_OT_pick_weapon_clip, RSPS_OT_bake_clip, RSPS_OT_set_clip_fps)
