"""Which model a loc placement shows, and how its colours and textures change. Nothing here imports bpy.

Every rule follows the 2018 Old School client (`ObjectComposition.java` and `ModelData.java`), as the spec of issue 35
lists them. Revision 149 is not checked against it, and the rules have no second reader.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .loc_definition import LocDefinition
from .model import Model

_NO_TEXTURE = 0xFFFF
"""The value that a retexture would write as the texture -1 of the client's `short`."""

_TEXTURED_FACE_COLOUR = 127
"""The colour that the client gives a textured face of an old-format model (`ModelData.java` line 943)."""


@dataclass(frozen=True)
class LocModel:
    """What `ObjectComposition.getModel` picks for one loc type and rotation. The recolours, retextures, scale and
    offset of the loc stay on its `LocDefinition`, which the caller already holds."""

    model_ids: tuple[int, ...]
    """The cache models to show. The client joins several models into one (`ObjectComposition.java` lines 728 to 733),
    which this module leaves to the caller."""
    mirrored: bool
    """Whether the client mirrors each model before it does anything else with it (`ModelData.method2633`, lines 1380 to
    1390): z is negated and the two corners of each face swap."""


def shown_loc_id(loc_id: int, locs: Mapping[int, LocDefinition]) -> int | None:
    """The id of the loc that a placement of `loc_id` shows, or None when it shows nothing.

    A loc with impostors shows the impostor for the value 0 of its varbit or varp, the state of a new account
    (`ObjectComposition.getImpostor`, lines 830 to 845). A loc with neither a varbit nor a varp keeps the client's value
    -1, which takes the last impostor id. An id of -1 shows nothing.
    """
    definition = locs[loc_id]
    impostors = definition.impostors
    if impostors is None:
        return loc_id
    value = 0 if definition.impostor_varbit != -1 or definition.impostor_varp != -1 else -1
    shown = impostors[value] if 0 <= value < len(impostors) - 1 else impostors[-1]
    return None if shown == -1 else shown


def pick_model(definition: LocDefinition, loc_type: int, rotation: int) -> LocModel | None:
    """The model of `definition` for a loc type and a rotation of 0 to 7, or None when the loc has no model for it
    (`ObjectComposition.getModel`, lines 689 to 760).

    The client asks with a rotation above 3 for the second model of a type 2 placement and for a diagonal wall
    decoration (`Region.java` from line 1360), so the rotation matters here only for the mirror.
    """
    if not 0 <= rotation <= 7:
        raise ValueError(f"The rotation is {rotation}, outside 0 to 7")
    if definition.loc_types is None:
        # Lines 694 to 703: a loc without loc types shows only for type 10. The mirror is the loc's own, because the
        # client's test for type 2 on line 704 never holds when the type is 10.
        if loc_type != 10 or not definition.models:
            return None
        model_ids, mirrored = definition.models, definition.mirrored
    else:
        # Lines 742 to 753: the first model of the loc type, mirrored when isRotated and rotation > 3 differ.
        if loc_type not in definition.loc_types:
            return None
        model_ids = (definition.models[definition.loc_types.index(loc_type)],)
        mirrored = definition.mirrored != (rotation > 3)
    return LocModel(model_ids=model_ids, mirrored=mirrored)


def recolour_model(model: Model, recolours: Sequence[tuple[int, int]], retextures: Sequence[tuple[int, int]]) -> Model:
    """A copy of `model` with the recolours, then the retextures, applied as the client does (`ObjectComposition.java`
    lines 801 to 811, `ModelData.recolor` and `ModelData.method2632`, lines 1358 to 1376).

    Each pair changes every face that has the colour or texture to find, and the pairs apply in order, so a later pair
    sees what an earlier one wrote. A model of the new format keeps a colour for a textured face too (`ModelData.java`
    line 636), and a recolour changes that colour as well. A retexture to 65535 is refused, because the client then
    gives the face no texture (-1) and Model cannot hold that with the colour that the face then shows. A recolour of
    127 on an old-format model with a textured face is refused too: the client gives such a face the colour 127, Model
    does not store it, and the recolour would miss that face without a sign.
    """
    for _, replacement in retextures:
        if replacement == _NO_TEXTURE:
            raise ValueError("A retexture to 65535 is not supported")
    if (
        model.new_data is None
        and any(texture is not None for texture in model.face_textures)
        and any(find == _TEXTURED_FACE_COLOUR for find, _ in recolours)
    ):
        raise ValueError("A recolour of 127 on a textured face of an old-format model is not supported")
    colours = list(model.face_colours)
    textures = list(model.face_textures)
    new_data = model.new_data
    kept = list(new_data.textured_face_colours) if new_data is not None else []
    for find, replacement in recolours:
        colours = [replacement if colour == find else colour for colour in colours]
        kept = [replacement if colour == find else colour for colour in kept]
    for find, replacement in retextures:
        textures = [replacement if texture == find else texture for texture in textures]
    if new_data is not None:
        new_data = replace(new_data, textured_face_colours=tuple(kept))
    return replace(model, face_colours=colours, face_textures=textures, new_data=new_data)
