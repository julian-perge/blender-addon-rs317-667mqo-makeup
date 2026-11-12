"""What a user or File > Append put into a player's collection, and how Update carries it to the rebuilt player.

The add-on makes a player's meshes and rig. Anything else in the player's collection is the user's: a child collection
(a nested player, or one of their own) or an object that is neither a mesh nor an armature. Update removes the old
player and builds a new one, so it lifts these out of the old collection first and links them into the new one
(issue 27, decisions 1 to 4). It links the objects and collections themselves, so their data, transforms and own
parents stay as they are.
"""

import dataclasses

import bpy

# The view layer settings of a collection that Blender resets when the collection is linked again.
_LAYER_FLAGS = ("exclude", "hide_viewport", "holdout", "indirect_only")
_MADE_BY_THE_ADD_ON = ("MESH", "ARMATURE")


def not_made_by_the_add_on(
    collection: bpy.types.Collection,
) -> tuple[list[bpy.types.Collection], list[bpy.types.Object]]:
    """Return the collection's child collections and its objects that are neither meshes nor armatures."""
    objects = [obj for obj in collection.objects if obj.type not in _MADE_BY_THE_ADD_ON]
    return list(collection.children), objects


@dataclasses.dataclass
class ViewState:
    """What the view layers say about some collections and objects: which collections are excluded, hidden, held out
    or indirect only, and which objects are hidden. Linking a collection or object again creates it anew in every
    view layer, so these are read before and written back after."""

    collections: dict[tuple[str, str, str], tuple[bool, ...]]
    hidden: dict[tuple[str, str, str], bool]

    @classmethod
    def read(cls, collections: list[bpy.types.Collection], objects: list[bpy.types.Object]) -> "ViewState":
        state = cls({}, {})
        for scene, layer in _view_layers():
            for collection in collections:
                found = _layer_collection(layer.layer_collection, collection.name)
                if found is not None:
                    state.collections[(scene.name, layer.name, collection.name)] = tuple(
                        getattr(found, flag) for flag in _LAYER_FLAGS
                    )
            for obj in objects:
                if layer.objects.get(obj.name) is not None:
                    state.hidden[(scene.name, layer.name, obj.name)] = obj.hide_get(view_layer=layer)
        return state

    def write(self) -> None:
        """Write the state back to the collections and objects that now have the names it was read under."""
        for (scene_name, layer_name, name), hidden in self.hidden.items():
            layer = _layer(scene_name, layer_name)
            obj = bpy.data.objects.get(name)
            if layer is not None and obj is not None and layer.objects.get(name) is not None:
                obj.hide_set(hidden, view_layer=layer)
        for (scene_name, layer_name, name), flags in self.collections.items():
            layer = _layer(scene_name, layer_name)
            found = None if layer is None else _layer_collection(layer.layer_collection, name)
            if found is not None:
                # Setting `exclude` even to its current value resets the exclusions of the collections below, so a
                # flag is written only where it differs.
                for flag, value in zip(_LAYER_FLAGS, flags, strict=True):
                    if getattr(found, flag) != value:
                        setattr(found, flag, value)


@dataclasses.dataclass
class Extras:
    """The child collections and objects lifted out of an old player, with their view layer state."""

    children: list[bpy.types.Collection]
    objects: list[bpy.types.Object]
    view_state: ViewState

    @classmethod
    def lift(cls, old: bpy.types.Collection) -> "Extras":
        """Unlink them from the old player, so that removing it takes nothing else with it."""
        children, objects = not_made_by_the_add_on(old)
        below = [*children, *(grandchild for child in children for grandchild in child.children_recursive)]
        view_objects = [*objects, *(obj for collection in below for obj in collection.objects)]
        state = ViewState.read(below, view_objects)
        for child in children:
            old.children.unlink(child)
        for obj in objects:
            old.objects.unlink(obj)
        return cls(children, objects, state)

    def link_into(self, player: bpy.types.Collection) -> None:
        """Link the child collections and objects into the player, then write back their view layer state."""
        for child in self.children:
            player.children.link(child)
        for obj in self.objects:
            player.objects.link(obj)
        bpy.context.view_layer.update()
        self.view_state.write()


def follow_to_counterparts(removed: dict[str, bpy.types.Object | None]) -> None:
    """Move what points at the objects about to be removed onto their rebuilt counterparts.

    `removed` maps the name of each object that will be removed to the object that replaces it, or None when the
    rebuild has none (a weapon the new settings no longer wear). An object parented to a removed object, in any
    collection, gets the counterpart as its parent and keeps its place in the world. With no counterpart it loses its
    parent and keeps its place. A parent bone the new rig lacks becomes a plain object parent. A constraint that
    targets a removed object targets the counterpart. With no counterpart the constraint is left alone, and Blender
    clears its target when the object is removed.
    """
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.name in removed:
            continue
        if obj.parent is not None and obj.parent.name in removed:
            _reparent(obj, removed[obj.parent.name])
        for constraint in obj.constraints:
            target = getattr(constraint, "target", None)
            if target is not None and removed.get(target.name) is not None:
                constraint.target = removed[target.name]


def take_place(player: bpy.types.Collection, parents: list[bpy.types.Collection]) -> None:
    """Link the player into these collections, and out of the current scene's collection unless it is one of them."""
    for parent in parents:
        if player.name not in parent.children:
            parent.children.link(player)
    scene_collection = bpy.context.scene.collection
    if scene_collection not in parents:
        scene_collection.children.unlink(player)


def parents_of(collection: bpy.types.Collection) -> list[bpy.types.Collection]:
    """The collections that link this one as a child, including the scene collections."""
    scenes = [scene.collection for scene in bpy.data.scenes]
    return [
        parent
        for parent in (*bpy.data.collections, *scenes)
        if parent != collection and collection.name in parent.children
    ]


def _reparent(obj: bpy.types.Object, parent: bpy.types.Object | None) -> None:
    world = obj.matrix_world.copy()
    obj.parent = parent
    if parent is None:
        obj.parent_type = "OBJECT"
        obj.parent_bone = ""
    elif obj.parent_type == "BONE" and not (
        isinstance(parent.data, bpy.types.Armature) and obj.parent_bone in parent.data.bones
    ):
        obj.parent_type = "OBJECT"
        obj.parent_bone = ""
    obj.matrix_world = world


def _view_layers() -> list[tuple[bpy.types.Scene, bpy.types.ViewLayer]]:
    return [(scene, layer) for scene in bpy.data.scenes for layer in scene.view_layers]


def _layer(scene_name: str, layer_name: str) -> bpy.types.ViewLayer | None:
    scene = bpy.data.scenes.get(scene_name)
    return None if scene is None else scene.view_layers.get(layer_name)


def _layer_collection(layer_collection: bpy.types.LayerCollection, name: str) -> bpy.types.LayerCollection | None:
    if layer_collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = _layer_collection(child, name)
        if found is not None:
            return found
    return None
