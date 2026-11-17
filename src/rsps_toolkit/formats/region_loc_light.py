"""The loc light of one part of a placement: the lit corner colours that the client draws it with. Nothing here imports
bpy.

Every rule follows the 2018 Old School client (`ObjectComposition.java`, `ModelData.java` and `Region.java` in
`runescape-client/src/main/java/` of the May 2018 RuneLite tree), as the spec of issue 105 lists them. Revision 149 is
not checked against it. The client merges the normals of touching non-flat-shading locs before it lights them
(`Region.applyLighting`, lines 831 to 865). This module leaves that merge out, as the spec of issue 105 decides.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace

from .lighting import Shading, light
from .loc_definition import LocDefinition
from .model import Model
from .region import Placement
from .region_contour import client_vertex, contour_heights
from .region_loc import shown_loc_id
from .region_placement import PlacedPart


def loc_light(
    placement: Placement,
    part: PlacedPart,
    locs: Mapping[int, LocDefinition],
    model: Model,
    height: Callable[[int, int], int],
) -> Shading:
    """The lit corner colours of one part of a placement, in the face and corner order of the client's model.

    `model` is the model of the part as the cache stores it, with the models of `part.model` joined in order, the
    recolours and retextures of the shown loc applied, and the mirror not yet applied. When `part.model.mirrored` is
    true, the client swaps the first and the last corner of each face (`ModelData.method2633`, lines 1380 to 1390), so
    `corner_a` of the result belongs to the last corner of the model's face and `corner_c` to the first.

    `height(x, y)` is the height of the tile corner (x, y) in game units, as `place_scenery` reads it.
    """
    raw = locs[placement.loc]
    shown_id = shown_loc_id(placement.loc, locs)
    if shown_id is None:
        raise ValueError(f"The placement at ({placement.x}, {placement.y}) shows nothing, so it has no light")
    shown = locs[shown_id]
    # ObjectComposition.java line 585 and Region.java lines 846 to 865 with class24.java line 316 give a loc the same
    # lighting, whichever of the two lights it.
    lighting = (shown.ambient + 64, shown.contrast + 768, -50, -10, -50)
    # The client lights the model after the mirror, the turns, the scale and the offset of getModel (ObjectComposition.java
    # lines 753 to 820). The turn of 256 units of an object of type 11 comes when the client draws it (PacketBuffer.java
    # line 478), after the light, so it is left out here as `client_vertex` leaves it out.
    vertices = [client_vertex(vertex, part, shown) for vertex in model.vertices]
    faces = [(c, b, a) for a, b, c in model.faces] if part.model.mirrored else model.faces
    # A non-flat-shading loc is lit after the contour, on the normals of the contoured model (ObjectComposition.java
    # lines 586 to 590 and 600 to 606, ModelData.method2625 from line 1141, Region.java lines 846 to 865). Any other loc
    # is lit before the contour (line 585). An animated loc or a loc with impostors is a DynamicObject (PacketBuffer.java
    # lines 214 to 218), which ObjectComposition.method5092 lights before the contour whatever the flag is (lines 662
    # and 675 to 677).
    dynamic = raw.animation != -1 or raw.impostors is not None
    if shown.non_flat_shading and not dynamic and 4 <= placement.loc_type <= 8:
        # Region.applyLighting (lines 831 to 865) skips the wall decorations, and Renderable.draw (lines 38 to 44) draws
        # nothing for a model that is not lit, so the client shows no such decoration. The owner chose on 2026-11-17
        # (issue 128) to refuse it.
        raise ValueError(
            f"The wall decoration at ({placement.x}, {placement.y}) is non-flat-shading, and the client never lights "
            "or draws it"
        )
    if shown.non_flat_shading and not dynamic and shown.contoured_ground >= 0:
        heights = contour_heights(placement, part, raw, shown, vertices, height)
        if heights is not None:
            vertices = [(x, y, z) for (x, _, z), y in zip(vertices, heights, strict=True)]
    return light(replace(model, vertices=vertices, faces=faces), lighting)
