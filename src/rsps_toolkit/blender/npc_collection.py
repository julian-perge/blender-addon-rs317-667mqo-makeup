"""The NPC collection: an NPC's lit mesh and its rig, built from an NPC definition of snapshot 430 (spec 13).

An NPC is created and baked only (ADR 0025). Its collection stores no appearance preset, so the player operators and
`appearance_preview.collection_of` do not take it for a player.
"""

import json
import struct
import zlib
from collections.abc import Mapping
from pathlib import Path

import bpy
from mathutils import Vector

from ..animation.bundle import FrameMap
from ..animation.clip import CacheClip, frame_map_id
from ..animation.frames import decode_frame_map, decode_sequence
from ..formats.appearance_rig import derive_rig, frame_map_joint_specs
from ..formats.cache_profile import shared_profile
from ..formats.js5 import Js5Store
from ..formats.lighting import Shading, light
from ..formats.model import Model
from ..formats.npc_definition import LIGHT_DIRECTION, NpcDefinition, npc_lighting, npc_model, npc_scale, read_npc
from . import appearance_collection, appearance_preview, mesh, preferences, rs_layers

# On an NPC collection: the NPC id, its name, the frame map of its rig and the sequences its definition names, as JSON.
# The NPC id is null for an NPC that Make rig built, which also stores the sequence that the user typed (the decision
# comment of issue 95).
NPC_KEY = "rs_npc"
SEQUENCE_FIELDS = ("stand", "walk", "turn_left", "turn_right", "walk_back", "walk_left", "walk_right")
# A model that Make rig rigs has no NPC definition. The owner chose to light it as an NPC whose definition keeps the
# constructor's ambient and contrast of 0 (the decision comment of issue 95, `NPCComposition.java` lines 192 to 217),
# which `npc_lighting` turns into 64 and 850.
MADE_RIG_LIGHTING = (64, 850, *LIGHT_DIRECTION)


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
    return sequence_frame_map(store, npc.stand, f"The stand sequence {npc.stand} of NPC {npc.name}")


def sequence_frame_map(store: Js5Store, sequence_id: int, described: str) -> tuple[int, FrameMap]:
    """The id and the frame map of the first frame of the sequence, which `described` names in the refusal of a
    sequence with no frames. A sequence that the cache lacks raises LookupError."""
    clip = CacheClip(store, sequence_id)
    sequence = decode_sequence(clip.sequence_bytes())
    if not sequence.frames:
        raise ValueError(f"{described} has no frames")
    group, file = sequence.frames[0]
    map_id = frame_map_id(clip.frame_bytes(group, file))
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
    sequences = {field: getattr(npc, field) for field in SEQUENCE_FIELDS if getattr(npc, field) != -1}
    record = {"npc": npc_id, "name": npc.name, "frame_map": map_id, "sequences": sequences}
    return _build(model, shading, map_id, frame_map, npc_scale(npc), npc.name, record, brightness)


def make_rig(obj: bpy.types.Object | None, sequence_id: int, folder: Path, brightness: float) -> bpy.types.Collection:
    """Build an NPC collection from the model of a mesh object with vertex skins, rigged for the frame map of the first
    frame of the sequence, beside the players and NPCs of the file (spec 13, Make rig).

    The new collection has its own mesh, so the object keeps its mesh, transform and collections. The model is the
    one that model export would write: the mesh's own positions, with no object transform, and a vertex in no vertex
    skin group has label 0. The collection takes the object's name and has a scale of 1 (the decision comment of
    issue 95). Everything that can fail runs before any Blender data exists: an object that is not a mesh with vertex
    skins, and a sequence that the cache lacks, are refused.
    """
    if obj is None:
        raise ValueError("Make rig needs an active mesh object, and there is no active object")
    if obj.type != "MESH":
        raise ValueError(f"Make rig needs a mesh object, and {obj.name!r} is not a mesh")
    if rs_layers.read_vertex_skins(obj) is None:
        raise ValueError(f"{obj.name!r} has no vertex skins, so it cannot have a rig")
    map_id, frame_map = sequence_frame_map(Js5Store(folder), sequence_id, f"Sequence {sequence_id}")
    model = mesh.object_to_model(obj)
    shading = light(model, MADE_RIG_LIGHTING)
    record = {"npc": None, "name": obj.name, "frame_map": map_id, "sequences": {}, "sequence": sequence_id}
    return _build(model, shading, map_id, frame_map, (1.0, 1.0, 1.0), obj.name, record, brightness)


def _build(
    model: Model,
    shading: Shading,
    map_id: int,
    frame_map: FrameMap,
    scale: tuple[float, float, float],
    name: str,
    record: Mapping[str, object],
    brightness: float,
) -> bpy.types.Collection:
    """The NPC collection of a lit model: the mesh, the rig for the frame map with the scale in game x, height and z,
    and the record that `NPC_KEY` describes. The joints are derived before any Blender data exists."""
    assert model.vertex_skins is not None
    rig = derive_rig(model, frame_map_joint_specs(map_id, frame_map, model.vertex_skins))
    location = beside_actors(min(x for x, _, _ in model.vertices) * scale[0])
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
        collection[NPC_KEY] = json.dumps(record)
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
        _make_active(context, collection)
        return {"FINISHED"}


class RSPS_OT_make_rig(bpy.types.Operator):
    bl_idname = "rsps.make_rig"
    bl_label = "Make Rig"
    bl_description = (
        "Build an NPC from the active mesh object, which needs vertex skins, with a rig for the frame map of this "
        "sequence. The active object stays as it is"
    )
    bl_options = {"REGISTER", "UNDO"}

    sequence: bpy.props.IntProperty(name="Sequence id", min=0)  # pyrefly: ignore[bad-assignment]
    cache_folder: appearance_collection._cache_folder_property()  # pyrefly: ignore[bad-assignment]

    def execute(self, context):
        try:
            appearance_collection.check_no_edit_mode("making a rig")
            folder = appearance_preview.cache_folder(self.cache_folder)
            collection = make_rig(context.active_object, self.sequence, folder, preferences.brightness())
        except (OSError, LookupError, ValueError, RuntimeError, EOFError, zlib.error, struct.error) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        _make_active(context, collection)
        return {"FINISHED"}


def _make_active(context, collection: bpy.types.Collection) -> None:
    """Select the new NPC's mesh alone and make it active, so the panel shows its bake rows, and show lit colours."""
    mesh_obj = appearance_collection.mesh_of(collection)
    for other in context.selected_objects or ():
        other.select_set(False)
    mesh_obj.select_set(True)
    context.view_layer.objects.active = mesh_obj
    appearance_preview.show_lit_colours(context)


def register_properties() -> None:
    bpy.types.Scene.rs_npc_id = bpy.props.IntProperty(  # pyrefly: ignore[missing-attribute]
        name="NPC id", description="The id of the NPC that Create NPC builds", min=0
    )
    bpy.types.Scene.rs_make_rig_sequence = bpy.props.IntProperty(  # pyrefly: ignore[missing-attribute]
        name="Sequence id",
        description="The id of the sequence whose frame map Make rig gives the rig of the active mesh object",
        min=0,
    )
    bpy.types.Scene.rs_npc_sequence = bpy.props.IntProperty(  # pyrefly: ignore[missing-attribute]
        name="Sequence id",
        description="The id of the sequence that Bake at the current frame reads from the cache for the active NPC",
        min=0,
    )
    bpy.types.Scene.rs_npc_smooth = bpy.props.BoolProperty(  # pyrefly: ignore[missing-attribute]
        name="Smooth",
        description="Blend the NPC's clips from each game frame to the next. The game itself holds each frame for "
        "its ticks, which is how clips bake when this is off",
    )


def unregister_properties() -> None:
    del bpy.types.Scene.rs_npc_smooth  # pyrefly: ignore[missing-attribute]
    del bpy.types.Scene.rs_npc_sequence  # pyrefly: ignore[missing-attribute]
    del bpy.types.Scene.rs_make_rig_sequence  # pyrefly: ignore[missing-attribute]
    del bpy.types.Scene.rs_npc_id  # pyrefly: ignore[missing-attribute]


classes = (RSPS_OT_create_npc, RSPS_OT_make_rig)
