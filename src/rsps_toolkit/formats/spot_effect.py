"""Spot effects (config group 13): a model, its recolours, a sequence, a scale, a turn and light values. Nothing here
imports bpy.

The decoder follows `ii.r` of gamepack 149 and the model follows `ii.v` (`getModel`), read with javap
(docs/research/spot-effects.md). The client calls a spot effect a spotanim.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ._stream import Reader
from .js5 import Js5Store, NotInCacheError
from .model import Model
from .region_loc import recolour_model

CONFIG_INDEX, SPOT_EFFECT_GROUP = 2, 13
# The light direction of `ii.v` (offsets 226 to 255).
LIGHT_DIRECTION = (-30, -50, -30)


@dataclass(frozen=True)
class SpotEffect:
    """One spot effect. Fields that no opcode sets keep the defaults of the constructor `ii.<init>`."""

    id: int
    model: int = 0
    sequence: int = -1
    """The sequence that plays the effect, or -1 for none."""
    resize_width: int = 128
    """The scale in game x and z. 128 is a scale of 1."""
    resize_height: int = 128
    """The scale in game height. 128 is a scale of 1."""
    rotation: int = 0
    """A turn in degrees around the up axis: 0, 90, 180 or 270."""
    ambient: int = 0
    contrast: int = 0
    recolours: tuple[tuple[int, int], ...] = ()
    """Pairs of the face colour to find and the colour to show, as unsigned 16-bit values."""
    retextures: tuple[tuple[int, int], ...] = ()


def decode_spot_effect(spot_effect_id: int, data: bytes) -> SpotEffect:
    """Read one spot effect as `ii.r` does (spot-effects.md, section 1). The ambient and the contrast are unsigned bytes
    with no factor. The client reads no value for an opcode that it does not know, so this decoder refuses it, and it
    refuses bytes after the closing opcode 0."""
    reader = Reader(data)
    fields: dict[str, object] = {}
    while (opcode := reader.u8()) != 0:
        if opcode == 1:
            fields["model"] = reader.u16()
        elif opcode == 2:
            fields["sequence"] = reader.u16()
        elif opcode == 4:
            fields["resize_width"] = reader.u16()
        elif opcode == 5:
            fields["resize_height"] = reader.u16()
        elif opcode == 6:
            fields["rotation"] = reader.u16()
        elif opcode == 7:
            fields["ambient"] = reader.u8()
        elif opcode == 8:
            fields["contrast"] = reader.u8()
        elif opcode in (40, 41):
            pairs = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
            fields["recolours" if opcode == 40 else "retextures"] = pairs
        else:
            raise ValueError(f"Spot effect {spot_effect_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"Spot effect {spot_effect_id} has {reader.remaining} byte(s) after its closing opcode")
    return SpotEffect(spot_effect_id, **fields)  # pyrefly: ignore[bad-argument-type]


def read_spot_effect(store: Js5Store, spot_effect_id: int) -> SpotEffect:
    """The spot effect of the cache with this id. An id that the cache lacks is an error."""
    files = store.files(CONFIG_INDEX, SPOT_EFFECT_GROUP)
    if spot_effect_id not in files:
        raise NotInCacheError(
            f"Group {SPOT_EFFECT_GROUP} of index {CONFIG_INDEX} of the cache has no spot effect {spot_effect_id}"
        )
    return decode_spot_effect(spot_effect_id, files[spot_effect_id])


def spot_effect_model(effect: SpotEffect, load_model: Callable[[int], Model]) -> Model:
    """The model of the spot effect before the light: loaded, recoloured, then retextured (`ii.v` offsets 39 to 217).
    The scale and the turn come after the animation, so they are not here (`spot_effect_scale`)."""
    return recolour_model(load_model(effect.model), effect.recolours, effect.retextures)


def spot_effect_lighting(effect: SpotEffect) -> tuple[int, int, int, int, int]:
    """The light of `ii.v` (offsets 226 to 255): `dv.ae(64 + ambient, 850 + contrast, -30, -50, -30)`."""
    return (64 + effect.ambient, 850 + effect.contrast, *LIGHT_DIRECTION)


def spot_effect_scale(effect: SpotEffect) -> tuple[float, float, float]:
    """The scale in game x, height and z that `ii.v` gives the posed model (`ej.i(width, height, width)`, offsets 351 to
    374). The client divides each coordinate with Java's integer division, which this float scale leaves out."""
    width, height = effect.resize_width / 128, effect.resize_height / 128
    return (width, height, width)
