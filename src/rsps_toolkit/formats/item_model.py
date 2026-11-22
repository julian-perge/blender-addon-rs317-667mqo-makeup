"""The inventory model of an item as the client builds it, and the item light. Nothing here imports bpy.

This follows `ItemComposition.getModel` (`iz.p`) of gamepack 149, read with javap (docs/research/item-light.md).
"""

from collections.abc import Callable
from dataclasses import replace

from .item_definition import ItemDefinition
from .model import Model
from .region_loc import recolour_model

NO_RESIZE = (128, 128, 128)
# The direction of the item light (`iz.p` offsets 536 to 540).
LIGHT_DIRECTION = (-50, -10, -50)


def item_lighting(definition: ItemDefinition) -> tuple[int, int, int, int, int]:
    """The ambient, contrast and direction that the client lights the inventory model with (`iz.p` offsets 511 to
    542): `dv.ae(64 + ambient, 768 + contrast, -50, -10, -50)`."""
    return (definition.ambient + 64, definition.contrast + 768, *LIGHT_DIRECTION)


def inventory_model(definition: ItemDefinition, load_model: Callable[[int], Model]) -> Model:
    """The inventory model of the item before the light: loaded, scaled by the resize when one of its three values is
    not 128, then recoloured and retextured (`iz.p` offsets 185 to 436). It refuses an item with no inventory model.

    The scale is `dv.h`: each coordinate times its resize value, divided by 128 with Java's division, which rounds
    toward zero. The client shows some items as a stack of another item (`countObj`). That is not done here."""
    if definition.inventory_model < 0:
        raise ValueError(f"Item {definition.worn.id} has no inventory model")
    model = load_model(definition.inventory_model)
    if definition.resize != NO_RESIZE:
        model = replace(
            model,
            vertices=[
                (_scaled(x, definition.resize[0]), _scaled(y, definition.resize[1]), _scaled(z, definition.resize[2]))
                for x, y, z in model.vertices
            ],
        )
    return recolour_model(model, definition.worn.recolours, definition.worn.retextures)


def _scaled(value: int, resize: int) -> int:
    quotient = abs(value * resize) // 128
    return quotient if value >= 0 else -quotient
