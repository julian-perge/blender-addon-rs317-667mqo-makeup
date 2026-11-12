"""The reference script of the hand-made motion runbook: it keys the sword flourish of issue 12 on the joints of a
player, and runs the scene checks.

Run inside Blender, in a scene with a player from Create Player that wears a sword and has a baked stand clip.
`build()` deletes the flourish strip and its action, and makes them again from POSES. `scene_checks(baseline_path)`
writes the baseline file on its first call, which must be before the first key, and compares with it after.

To make another motion, copy this file and change ACTION and POSES. The names RIG and WEAPON are those of the scene.
This file is evidence and a starting point. It is not toolkit code and has no tests.

Directions are in the frame of the torso: x is the player's left, -y is forward, z is up.
"""

import hashlib
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

RIG = "Player_rig"
WEAPON = "Player Weapon"
ACTION = "Player sword flourish"
CLIP_TRACK = "RS clips"
USER_TRACK = "Your motion"
ARM_JOINTS = [f"{name}.{side}" for side in "LR" for name in ("upper_arm", "forearm", "hand")]
LEG_JOINTS = [f"{name}.{side}" for side in "LR" for name in ("thigh", "shin", "foot")]
JOINTS = ["root", "spine", "head", *ARM_JOINTS, *LEG_JOINTS]

L, R = Vector((1, 0, 0)), Vector((-1, 0, 0))
F, B = Vector((0, -1, 0)), Vector((0, 1, 0))
U, D = Vector((0, 0, 1)), Vector((0, 0, -1))


def mix(**parts):
    """A unit direction from named parts, for example mix(R=0.8, D=0.5)."""
    names = {"L": L, "R": R, "F": F, "B": B, "U": U, "D": D}
    total = Vector((0, 0, 0))
    for name, amount in parts.items():
        total += names[name] * amount
    return total.normalized()


HIP_L = {"LU": mix(L=0.5, D=0.8, B=0.3), "LF": mix(R=0.35, F=0.2, D=0.9)}

# Each pose: the number of frames it is held, then the parts that differ from the stand pose.
#   yaw: turn of the root to the player's left, in degrees.   dip: root height change.
#   spine: (yaw, lean forward, lean to the left) on top of the root.   head: (yaw, nod forward) on top of the spine.
#   RU, RF, LU, LF: directions of the upper arms and the forearms.   blade, edge: directions of the sword.
POSES = [
    (3, {}),
    # The sword in front of the player.
    (5, {"RU": mix(D=0.9, F=0.4, R=0.1), "RF": mix(F=0.8, D=0.4, L=0.3), "blade": mix(F=0.6, D=0.5, L=0.5), "edge": D}),
    # Out to the right side.
    (
        4,
        {
            "yaw": -10,
            "RU": mix(R=0.8, D=0.5, F=0.2),
            "RF": mix(R=0.8, D=0.5, F=0.3),
            "blade": mix(R=0.7, D=0.6, F=0.3),
            "edge": D,
        },
    ),
    # Up across the chest, the turn starts.
    (
        4,
        {
            "yaw": 15,
            "RU": mix(D=0.7, F=0.5, R=0.2),
            "RF": mix(U=0.2, L=0.7, F=0.6),
            "blade": mix(U=0.8, R=0.5, B=0.2),
            "edge": L,
        },
    ),
    # The sword goes to the left side while the body turns left.
    (
        4,
        {
            "yaw": 35,
            "dip": -2,
            "spine": (20, 5, 0),
            "RU": mix(D=0.7, F=0.5, L=0.3),
            "RF": mix(L=0.7, D=0.5, F=0.4),
            "blade": mix(L=0.6, D=0.7, F=0.2),
            "edge": D,
        },
    ),
    (
        4,
        {
            "yaw": 60,
            "dip": -2,
            "spine": (30, 5, 0),
            "head": (-30, 0),
            "RU": mix(D=0.5, F=0.6, L=0.5),
            "RF": mix(L=0.8, F=0.3, D=0.4),
            "blade": mix(L=0.6, B=0.6, D=0.5),
            "edge": B,
        },
    ),
    # The twirl on the left side.
    (
        4,
        {
            "yaw": 70,
            "spine": (35, 0, 0),
            "head": (-50, 0),
            "RU": mix(D=0.5, F=0.6, L=0.5),
            "RF": mix(L=0.8, F=0.3, D=0.2),
            "blade": mix(U=0.9, L=0.3, B=0.1),
            "edge": F,
        },
    ),
    (
        5,
        {
            "yaw": 70,
            "spine": (35, 0, 0),
            "head": (-60, 0),
            "RU": mix(L=0.5, F=0.6, D=0.5),
            "RF": mix(L=0.6, F=0.5, U=0.2),
            "blade": mix(L=0.5, U=0.6, F=0.5),
            "edge": F,
        },
    ),
    # Back to the front.
    (
        4,
        {
            "yaw": 25,
            "spine": (10, 0, 0),
            "RU": mix(D=0.8, F=0.4),
            "RF": mix(F=0.6, D=0.5, L=0.5),
            "blade": mix(D=0.8, F=0.3, L=0.4),
            "edge": F,
        },
    ),
    # Out to the right side, the left hand on the hip.
    (
        4,
        {
            "spine": (-10, 0, 0),
            "RU": mix(R=0.8, D=0.5, F=0.1),
            "RF": mix(R=0.8, D=0.3, F=0.3),
            "blade": D,
            "edge": R,
            **HIP_L,
        },
    ),
    # The twirl on the right side.
    (
        3,
        {
            "spine": (-5, 0, 0),
            "RU": mix(R=0.8, D=0.5, F=0.1),
            "RF": mix(R=0.8, D=0.3, F=0.3),
            "blade": mix(R=0.9, U=0.4),
            "edge": D,
            **HIP_L,
        },
    ),
    (
        3,
        {
            "spine": (-5, 0, 0),
            "RU": mix(R=0.8, D=0.4, F=0.1),
            "RF": mix(R=0.8, D=0.1, F=0.3),
            "blade": mix(U=0.9, L=0.3),
            "edge": R,
            **HIP_L,
        },
    ),
    (
        3,
        {
            "spine": (-5, 0, 0),
            "RU": mix(R=0.8, D=0.3, F=0.2),
            "RF": mix(R=0.7, D=0.2, F=0.5),
            "blade": mix(L=0.8, D=0.3, F=0.5),
            "edge": U,
            **HIP_L,
        },
    ),
    (
        4,
        {
            "RU": mix(R=0.8, U=0.2, F=0.2),
            "RF": mix(R=0.3, D=0.8, F=0.3),
            "blade": mix(D=0.9, L=0.2),
            "edge": L,
            **HIP_L,
        },
    ),
    # Up over the right shoulder.
    (
        4,
        {
            "dip": -3,
            "RU": mix(R=0.8, U=0.4, F=0.2),
            "RF": mix(U=0.9, R=0.2, F=0.2),
            "blade": mix(U=0.8, R=0.3, B=0.4),
            "edge": B,
            **HIP_L,
        },
    ),
    (
        3,
        {
            "dip": -3,
            "RU": mix(R=0.7, F=0.5, D=0.2),
            "RF": mix(U=0.8, B=0.4, L=0.1),
            "blade": mix(L=0.6, B=0.5, U=0.5),
            "edge": U,
            **HIP_L,
        },
    ),
    # The sword lands across the shoulders.
    (
        4,
        {
            "dip": -4,
            "head": (0, 8),
            "RU": mix(R=0.6, F=0.6, D=0.5),
            "RF": mix(L=0.27, B=0.65, U=0.65),
            "blade": L,
            "edge": U,
            **HIP_L,
        },
    ),
    (14, {"RU": mix(R=0.6, F=0.6, D=0.5), "RF": mix(L=0.27, B=0.65, U=0.65), "blade": L, "edge": U, **HIP_L}),
    # Back to the stand pose.
    (5, {"RU": mix(R=0.7, F=0.5, D=0.4), "RF": mix(U=0.6, F=0.5, R=0.2), "blade": mix(U=0.8, F=0.4, L=0.2), "edge": F}),
    (
        4,
        {
            "RU": mix(D=0.9, F=0.2, R=0.2),
            "RF": mix(F=0.7, D=0.5, U=0.1),
            "blade": mix(F=0.6, U=0.7),
            "edge": mix(F=1, D=1),
        },
    ),
    (2, {}),
]


def _rot(axis, degrees):
    return Matrix.Rotation(math.radians(degrees), 3, axis)


def _aim(direction):
    """The smallest rotation that points a limb, which hangs down at rest, along `direction`."""
    return D.rotation_difference(direction).to_matrix()


def _frame(first, second):
    """An orthonormal basis whose first axis is `first` and whose second axis is as near `second` as it can be."""
    a = first.normalized()
    b = (second - a * second.dot(a)).normalized()
    c = a.cross(b)
    return Matrix((a, b, c)).transposed()


def _user_strip(rig):
    track = rig.animation_data.nla_tracks[USER_TRACK]
    return track, next((s for s in track.strips if s.action and s.action.name == ACTION), None)


def _remove_flourish(rig):
    track, strip = _user_strip(rig)
    if strip:
        track.strips.remove(strip)
    action = bpy.data.actions.get(ACTION)
    if action:
        bpy.data.actions.remove(action)


def _sword_ends(weapon_eval, ends=None):
    """World positions of the two vertices at the ends of the sword's long axis: the hilt end and the tip."""
    points = np.array([list(weapon_eval.matrix_world @ v.co) for v in weapon_eval.data.vertices])
    if ends is None:
        centre = points.mean(0)
        axis = np.linalg.svd(points - centre)[2][0]
        along = (points - centre) @ axis
        ends = (int(along.argmin()), int(along.argmax()))
    return ends, Vector(points[ends[0]]), Vector(points[ends[1]])


def _stand(rig, frame):
    """The stand pose on `frame`, read while the flourish strip is absent."""
    scene = bpy.context.scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pose = {}
    for name in JOINTS:
        bone = rig.pose.bones[name]
        rest = rig.data.bones[name].matrix_local.to_3x3()
        pose[name] = {
            "quat": bone.rotation_quaternion.copy(),
            "location": bone.location.copy(),
            "world": bone.matrix.to_3x3().normalized() @ rest.inverted(),
        }
    return pose


def _local(stand, child, parent):
    return stand[parent]["world"].inverted() @ stand[child]["world"]


def _solve(spec, stand, sword_rest):
    """The rotation of each joint from its rest, in the space of the rig, for one pose."""
    world = {}
    world["root"] = _rot("Z", spec.get("yaw", 0)) @ stand["root"]["world"]
    if "spine" in spec:
        yaw, forward, left = spec["spine"]
        world["spine"] = world["root"] @ _rot("Z", yaw) @ _rot("X", forward) @ _rot("Y", -left)
    else:
        world["spine"] = world["root"] @ _local(stand, "spine", "root")
    torso = world["spine"]
    if "head" in spec:
        yaw, nod = spec["head"]
        world["head"] = torso @ _rot("Z", yaw) @ _rot("X", nod)
    else:
        world["head"] = torso @ _local(stand, "head", "spine")
    for side in "LR":
        upper, fore, hand = f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"
        key = side + "U"
        world[upper] = torso @ _aim(spec[key]) if key in spec else torso @ _local(stand, upper, "spine")
        key = side + "F"
        world[fore] = torso @ _aim(spec[key]) if key in spec else world[upper] @ _local(stand, fore, upper)
        if side == "R" and "blade" in spec:
            world[hand] = torso @ _frame(spec["blade"], spec["edge"]) @ sword_rest.transposed()
        else:
            world[hand] = world[fore] @ _local(stand, hand, fore)
        thigh, shin, foot = f"thigh.{side}", f"shin.{side}", f"foot.{side}"
        world[thigh] = world["root"] @ _local(stand, thigh, "root")
        world[shin] = world[thigh] @ _local(stand, shin, thigh)
        world[foot] = world[shin] @ _local(stand, foot, shin)
    return world


def build(poses=POSES, start=1):
    """Make the flourish action from `poses` and put it on the Your motion track. Returns a report per pose."""
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    _remove_flourish(rig)
    length = sum(hold for hold, _ in poses)
    end = start + length - 1
    stand_first = _stand(rig, start)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ends, hilt, tip = _sword_ends(bpy.data.objects[WEAPON].evaluated_get(depsgraph))
    hand = rig.pose.bones["hand.R"]
    if (hilt - hand.head).length > (tip - hand.head).length:
        ends, hilt, tip = (ends[1], ends[0]), tip, hilt
    blade = (tip - hilt).normalized()
    # The sword's edge is the direction in the plane of the blade that points away from the player in the stand pose.
    weapon_eval = bpy.data.objects[WEAPON].evaluated_get(depsgraph)
    points = np.array([list(weapon_eval.matrix_world @ v.co) for v in weapon_eval.data.vertices])
    second = Vector(np.linalg.svd(points - points.mean(0))[2][1])
    edge = second if second.dot(mix(F=1, D=1)) > 0 else -second
    # The sword's basis as it would be with the hand at rest.
    sword_rest = stand_first["hand.R"]["world"].inverted() @ _frame(blade, edge)
    stand_last = _stand(rig, end)

    action = bpy.data.actions.new(ACTION)
    slot = action.slots.new(id_type="OBJECT", name=rig.name)
    bag = action.layers.new("Layer").strips.new(type="KEYFRAME").channelbag(slot, ensure=True)
    curves = {}
    for name in JOINTS:
        path = f'pose.bones["{name}"].rotation_quaternion'
        curves[name] = [bag.fcurves.new(path, index=i, group_name=name) for i in range(4)]
    root_path = 'pose.bones["root"].location'
    location_curves = [bag.fcurves.new(root_path, index=i, group_name="root") for i in range(3)]

    def key(curve, frame, value):
        point = curve.keyframe_points.insert(frame, value, options={"FAST"})
        point.interpolation = "CONSTANT"

    frame = start
    starts = []
    for index, (hold, spec) in enumerate(poses):
        starts.append(frame)
        if not spec:
            # A pose with no parts is the stand pose: the stand clip's own values on that frame.
            stand = stand_first if index == 0 else stand_last
            for name in JOINTS:
                for i in range(4):
                    key(curves[name][i], frame, stand[name]["quat"][i])
            for i in range(3):
                key(location_curves[i], frame, stand["root"]["location"][i])
        else:
            world = _solve(spec, stand_first, sword_rest)
            for name in JOINTS:
                bone = rig.data.bones[name]
                rest = bone.matrix_local.to_3x3()
                parent = world[bone.parent.name] if bone.parent else Matrix.Identity(3)
                quat = (rest.inverted() @ parent.inverted() @ world[name] @ rest).to_quaternion()
                for i in range(4):
                    key(curves[name][i], frame, quat[i])
            location = stand_first["root"]["location"].copy()
            location.y += spec.get("dip", 0)
            for i in range(3):
                key(location_curves[i], frame, location[i])
        frame += hold
    for curve in [*location_curves, *(c for group in curves.values() for c in group)]:
        curve.update()

    track = rig.animation_data.nla_tracks[USER_TRACK]
    strip = track.strips.new(ACTION, start, action)
    strip.action_slot = slot
    strip.blend_type = "REPLACE"
    strip.extrapolation = "NOTHING"
    strip.frame_end = end

    report = []
    weapon = bpy.data.objects[WEAPON]
    for first in starts:
        scene.frame_set(first)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        _, hilt, tip = _sword_ends(weapon.evaluated_get(depsgraph), ends)
        report.append(
            {
                "frame": first,
                "wrist": [round(x) for x in rig.pose.bones["hand.R"].head],
                "hilt": [round(x) for x in hilt],
                "tip": [round(x) for x in tip],
                "left_wrist": [round(x) for x in rig.pose.bones["hand.L"].head],
            }
        )
    return {"frames": [start, end], "pose_starts": starts, "poses": report}


def _digest(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]


def fingerprint():
    """Digests of the things that the flourish must not change, for both players."""
    out = {}
    for rig in (o for o in bpy.context.scene.objects if o.type == "ARMATURE"):
        strips = []
        for strip in rig.animation_data.nla_tracks[CLIP_TRACK].strips:
            action = strip.action
            keys = [
                [fc.data_path, fc.array_index, [[*k.co, k.interpolation] for k in fc.keyframe_points]]
                for layer in action.layers
                for s in layer.strips
                for bag in s.channelbags
                for fc in bag.fcurves
            ]
            settings = [strip.name, action.name, strip.frame_start, strip.frame_end, strip.blend_type]
            settings += [strip.extrapolation, strip.influence, strip.mute, strip.repeat, strip.scale]
            strips.append([settings, _digest(keys)])
        bones = [
            [b.name, b.parent.name if b.parent else None, [round(x, 5) for row in b.matrix_local for x in row]]
            for b in rig.data.bones
        ]
        meshes = {}
        for mesh in (o for o in rig.children_recursive if o.type == "MESH"):
            data = mesh.data
            vertices = [[round(x, 5) for x in v.co] for v in data.vertices]
            weights = [[[g.group, round(g.weight, 5)] for g in v.groups] for v in data.vertices]
            meshes[mesh.name] = {
                "vertices": _digest(vertices),
                "faces": _digest([list(p.vertices) for p in data.polygons]),
                "weights": _digest(weights),
                "groups": [g.name for g in mesh.vertex_groups],
                "modifiers": [m.type for m in mesh.modifiers],
                "constraints": len(mesh.constraints),
                "shape_keys": bool(data.shape_keys),
            }
        out[rig.name] = {
            "clip_strips": strips,
            "bones": _digest(bones),
            "bone_count": len(bones),
            "bone_constraints": sum(len(b.constraints) for b in rig.pose.bones),
            "rig_constraints": len(rig.constraints),
            "meshes": meshes,
        }
    return out


def _toolkit_is_edited(rig):
    """What the toolkit says: has the user edited this player's meshes or rig?"""
    module = next((m for n, m in sys.modules.items() if n.endswith("blender.appearance_collection")), None)
    if module is None:
        return "toolkit module not found"
    return bool(module.is_edited(rig.users_collection[0]))


def scene_checks(baseline_path):
    """The scene checks of the spec. Writes the baseline on the first call, before any key exists."""
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    now = fingerprint()
    if not os.path.exists(baseline_path):
        with open(baseline_path, "w") as handle:
            json.dump(now, handle, indent=1, sort_keys=True)
        return {"baseline": "written"}
    with open(baseline_path) as handle:
        baseline = json.load(handle)
    now = json.loads(json.dumps(now))
    track, strip = _user_strip(rig)
    action = strip.action
    curves = [fc for layer in action.layers for s in layer.strips for bag in s.channelbags for fc in bag.fcurves]
    allowed = {f'pose.bones["{name}"].rotation_quaternion' for name in JOINTS} | {'pose.bones["root"].location'}
    start, end = int(strip.frame_start), int(strip.frame_end)
    key_frames = sorted({k.co[0] for fc in curves for k in fc.keyframe_points})

    def evaluated(frame):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        return {name: [x for row in rig.pose.bones[name].matrix for x in row] for name in JOINTS}

    with_flourish = {frame: evaluated(frame) for frame in (start, end)}
    strip.mute = True
    stand_only = {frame: evaluated(frame) for frame in (start, end)}
    strip.mute = False
    scene.frame_set(start)
    difference = max(
        abs(a - b)
        for frame in (start, end)
        for name in JOINTS
        for a, b in zip(with_flourish[frame][name], stand_only[frame][name])
    )
    return {
        "curves": len(curves),
        "every_curve_targets_a_joint": all(fc.data_path in allowed for fc in curves),
        "every_key_is_constant": all(k.interpolation == "CONSTANT" for fc in curves for k in fc.keyframe_points),
        "every_key_on_a_whole_frame": all(float(f).is_integer() for f in key_frames),
        "frames": [start, end],
        "length": end - start + 1,
        "poses": len(key_frames),
        "first_and_last_pose_max_difference_from_stand": difference,
        "first_and_last_pose_equal_stand": difference < 1e-4,
        "clip_strips_unchanged": all(now[r]["clip_strips"] == baseline[r]["clip_strips"] for r in baseline),
        "meshes_and_weights_unchanged": all(now[r]["meshes"] == baseline[r]["meshes"] for r in baseline),
        "bones_unchanged": all(
            now[r][k] == baseline[r][k]
            for r in baseline
            for k in ("bones", "bone_count", "bone_constraints", "rig_constraints")
        ),
        "toolkit_says_player_is_edited": _toolkit_is_edited(rig),
        "flourish_strip": [strip.blend_type, strip.extrapolation, track.name],
    }
