"""The functions that a script calls to build a scene (spec 170, ADR 0031).

Every input is an argument. No function here reads the add-on preferences or a scene property of the panel, and none
registers a class, so a script uses them with the add-on not enabled. `folder` is the cache folder, and `brightness`
is the client brightness that colours are shown at, such as 0.6 or 0.8. docs/scripted-use.md has an example of each
call.
"""

from pathlib import Path

import bpy

from ..formats.cache_profile import shared_profile
from ..formats.item_model import inventory_model, item_lighting
from ..formats.lighting import light_hsl
from . import appearance_preview


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
