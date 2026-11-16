"""The NPC collection: an NPC's lit mesh and its rig, built from an NPC definition of snapshot 430 (spec 13).

An NPC is created and baked only (ADR 0025). Its collection stores no appearance preset, so the player operators and
`appearance_preview.collection_of` do not take it for a player.
"""

import json
import struct
import zlib
from pathlib import Path

import bpy
from mathutils import Vector

from ..animation.bundle import FrameMap
from ..animation.clip import CacheClip
from ..animation.frames import decode_frame_map, decode_sequence
from ..formats.appearance_rig import derive_rig, frame_map_joint_specs
from ..formats.cache_profile import shared_profile
from ..formats.js5 import Js5Store
from ..formats.lighting import light
from ..formats.npc_definition import NpcDefinition, npc_lighting, npc_model, npc_scale, read_npc
from . import appearance_collection, appearance_preview, preferences

# On an NPC collection: the NPC id, its name, the frame map of its rig and the sequences its definition names, as JSON.
NPC_KEY = "rs_npc"
SEQUENCE_FIELDS = ("stand", "walk", "turn_left", "turn_right", "walk_back", "walk_left", "walk_right")


def npc_of(obj: bpy.types.Object | None) -> bpy.types.Collection | None:
    """The NPC collection that holds the object, if it is part of one."""
    if obj is None:
        return None
    return next((c for c in obj.users_collection if NPC_KEY in c), None)


def stand_frame_map(store: Js5Store, npc: NpcDefinition) -> tuple[int, FrameMap]:
    """The id and the frame map of the first frame of the NPC's stand sequence. An NPC with no stand sequence is
    refused, because it then has no frame map (spec 13, Refusals)."""
    if npc.stand == -1:
        raise ValueError(f"NPC {npc.name} has no stand sequence, so it has no frame map for a rig")
    clip = CacheClip(store, npc.stand)
    sequence = decode_sequence(clip.sequence_bytes())
    if not sequence.frames:
        raise ValueError(f"The stand sequence {npc.stand} of NPC {npc.name} has no frames")
    group, file = sequence.frames[0]
    # A frame file starts with the id of its frame map (`pose_vertices` reads it the same way).
    map_id = int.from_bytes(clip.frame_bytes(group, file)[0:2], "big")
    return map_id, decode_frame_map(clip.frame_map_bytes(map_id))


def create_npc(npc_id: int, folder: Path, brightness: float) -> bpy.types.Collection:
    """Build the NPC collection of the NPC with this id beside the players and NPCs of the file.

    Everything that can fail runs before any Blender data exists: the NPC is read, its model built and lit, and its
    frame map read.
    """
    store = Js5Store(folder)
    npc = read_npc(store, npc_id)
    model = npc_model(npc, shared_profile(folder).load_model)
    shading = light(model, npc_lighting(npc))
    map_id, frame_map = stand_frame_map(store, npc)
    assert model.vertex_skins is not None
    rig = derive_rig(model, frame_map_joint_specs(map_id, frame_map, model.vertex_skins))
    scale = npc_scale(npc)
    location = beside_actors(min(x for x, _, _ in model.vertices) * scale[0])
    name = npc.name
    collection = bpy.data.collections.new(name)
    try:
        bpy.context.scene.collection.children.link(collection)
        mesh_obj = appearance_collection.mesh_object(
            model, shading, name, brightness, collection, appearance_collection.BODY
        )
        armature_obj = appearance_collection._armature_object(rig, name, collection)
        appearance_collection.bind(mesh_obj, armature_obj, rig)
        armature_obj.location = location
        # Game (x, y, z) is Blender (x, z, -y), so the width scale goes on Blender x and y and the height scale on z.
        armature_obj.scale = (scale[0], scale[2], scale[1])
        bpy.context.view_layer.update()
        sequences = {field: getattr(npc, field) for field in SEQUENCE_FIELDS if getattr(npc, field) != -1}
        collection[NPC_KEY] = json.dumps({"npc": npc_id, "name": npc.name, "frame_map": map_id, "sequences": sequences})
        collection[appearance_collection.HASH_KEY] = appearance_collection.fingerprint(collection)
    except Exception:
        appearance_collection.remove_collection(collection)
        raise
    return collection


def beside_actors(left: float) -> tuple[float, float, float]:
    """Where to put a new NPC's rig so its mesh, whose leftmost point is `left` from the rig in Blender x, starts
    PLAYER_GAP to the right of every player and NPC mesh in the file (spec 13, NPC collection)."""
    right = max(
        (
            (obj.matrix_world @ Vector(corner)).x
            for obj in bpy.data.objects
            if obj.type == "MESH" and (appearance_preview.collection_of(obj) is not None or npc_of(obj) is not None)
            for corner in obj.bound_box
        ),
        default=None,
    )
    if right is None:
        return (0.0, 0.0, 0.0)
    return (right + appearance_collection.PLAYER_GAP - left, 0.0, 0.0)


class RSPS_OT_create_npc(bpy.types.Operator):
    bl_idname = "rsps.create_npc"
    bl_label = "Create NPC"
    bl_description = "Build the NPC with this id from the cache into a collection with a lit mesh and a rig"
    bl_options = {"REGISTER", "UNDO"}

    npc_id: bpy.props.IntProperty(name="NPC id", min=0)  # pyrefly: ignore[bad-assignment]
    cache_folder: appearance_collection._cache_folder_property()  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        try:
            appearance_collection.check_no_edit_mode("creating an NPC")
            folder = appearance_preview.cache_folder(self.cache_folder)
            collection = create_npc(self.npc_id, folder, preferences.brightness())
        except (OSError, LookupError, ValueError, RuntimeError, EOFError, zlib.error, struct.error) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        mesh_obj = appearance_collection.mesh_of(collection)
        for other in context.selected_objects or ():
            other.select_set(False)
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        appearance_preview.show_lit_colours(context)
        return {"FINISHED"}


def register_properties() -> None:
    bpy.types.Scene.rs_npc_id = bpy.props.IntProperty(  # pyrefly: ignore[missing-attribute]
        name="NPC id", description="The id of the NPC that Create NPC builds", min=0
    )


def unregister_properties() -> None:
    del bpy.types.Scene.rs_npc_id  # pyrefly: ignore[missing-attribute]


classes = (RSPS_OT_create_npc,)
