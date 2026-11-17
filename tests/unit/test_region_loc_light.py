from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from runelite_json import load_locs

from rsps_toolkit.formats.lighting import Shading, light
from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.model import Face, Model, Vertex
from rsps_toolkit.formats.region import Placement
from rsps_toolkit.formats.region_loc_light import loc_light
from rsps_toolkit.formats.region_placement import place_scenery

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOCS = load_locs(FIXTURES / "region/locs.json")

# Every client line below is in the 2018 Old School client, `runescape-client/src/main/java/`. Each expected value is
# the light of a model whose vertices the test turns, mirrors, scales or contours by hand from the client lines that it
# names. `formats/lighting.light` is the light of `ModelData.light`, which `tests/unit/test_lighting.py` checks.

VERTICES: list[Vertex] = [(0, 0, 0), (32, -10, -48), (-60, -200, 20)]
FACE: Face = (0, 1, 2)
COLOUR = (10 << 10) | (3 << 7) | 100
# ObjectComposition.java line 585 lights a loc with (ambient + 64, contrast + 768, -50, -10, -50). The loc of these
# tests has the ambient 16 and the contrast 50, which opcode 39 reads as 2 times 25 (line 410).
LOC_LIGHTING = (16 + 64, 50 + 768, -50, -10, -50)


def loc(**changes: Any) -> LocDefinition:
    """A loc with the defaults of the `ObjectComposition` constructor (lines 262 to 296), the ambient 16 and the contrast
    50, changed as given."""
    defaults: dict[str, Any] = {
        "models": (11,),
        "loc_types": None,
        "width": 1,
        "length": 1,
        "recolours": (),
        "retextures": (),
        "scale": (128, 128, 128),
        "offset": (0, 0, 0),
        "mirrored": False,
        "contoured_ground": -1,
        "non_flat_shading": False,
        "animation": -1,
        "decor_displacement": 16,
        "impostors": None,
        "impostor_varbit": -1,
        "impostor_varp": -1,
        "ambient": 16,
        "contrast": 50,
    }
    return replace(LOCS[83], **(defaults | changes))


def model(vertices: list[Vertex], face: Face = FACE) -> Model:
    return Model(
        vertices=vertices,
        faces=[face],
        face_colours=[COLOUR],
        face_textures=[None],
        render_priorities=[0],
        face_alphas=[0],
        face_texture_triangles=[None],
        flat_shaded=[False],
    )


def level(_x: int, _y: int) -> int:
    return -40


def tilt(_x: int, y: int) -> int:
    """Ground that rises by 1 game unit for each game unit north, so the terrain height at the game z of a point is -z.
    The client's y points down."""
    return -128 * y


def light_one(
    definition: LocDefinition,
    height: Callable[[int, int], int] = level,
    loc_type: int = 10,
    rotation: int = 0,
) -> Shading:
    """The loc light of the one part of a placement of loc 1 at tile (5, 7), with the model of `VERTICES`."""
    locs = {1: definition}
    placement = Placement(loc=1, level=0, x=5, y=7, loc_type=loc_type, rotation=rotation)
    (part,) = place_scenery([placement], locs, height)[0].parts
    return loc_light(placement, part, locs, model(VERTICES), height)


def test_a_loc_is_lit_with_its_ambient_and_contrast_and_the_loc_light_direction():
    assert light_one(loc()) == light(model(VERTICES), LOC_LIGHTING)


def test_a_loc_at_rotation_1_is_lit_after_the_quarter_turn():
    # ObjectComposition.java lines 792 to 794 call ModelData.method2649 (lines 1300 to 1308) for the rotation 1, which
    # makes x and z the old z and -x. The light comes after it (line 585).
    turned = [(0, 0, 0), (-48, -10, -32), (20, -200, 60)]
    shading = light_one(loc(), rotation=1)
    assert shading == light(model(turned), LOC_LIGHTING)
    assert shading != light_one(loc())


def test_a_mirrored_loc_is_lit_after_the_mirror_with_the_first_and_last_corners_swapped():
    # ObjectComposition.java lines 753 to 767 mirror the model with ModelData.method2633 (lines 1380 to 1390), which
    # negates z and swaps the first and the last corner of each face. So corner_a of the result is the model's last
    # corner.
    mirrored = [(0, 0, 0), (32, -10, 48), (-60, -200, -20)]
    shading = light_one(loc(mirrored=True))
    assert shading == light(model(mirrored, (2, 1, 0)), LOC_LIGHTING)
    assert shading != light_one(loc())


def test_a_scaled_loc_is_lit_after_the_scale():
    # ObjectComposition.java lines 813 to 815 call ModelData.method2674 (lines 1396 to 1404), which multiplies each axis
    # by its scale and divides by 128 toward zero.
    scaled = [(0, 0, 0), (64, -10, -24), (-120, -200, 10)]
    shading = light_one(loc(scale=(256, 128, 64)))
    assert shading == light(model(scaled), LOC_LIGHTING)
    assert shading != light_one(loc())


def test_a_diagonal_wall_decoration_is_lit_after_the_diagonal_turn_and_move():
    # A type 6 decoration at rotation 0 asks for getModel(4, 4) (PacketBuffer.java lines 422 to 430). The loc is
    # isRotated, so ObjectComposition.java line 753 does not mirror it. Lines 787 to 790 turn it with
    # ModelData.method2663(256) (lines 1332 to 1343), where the SINE and COSINE entries are both 46340, and move it by
    # (45, 0, -45). For (32, -10, -48): x is (46340 * -48 + 46340 * 32) >> 16 = -12 and z is
    # (46340 * -48 - 46340 * 32) >> 16 = -57. For (-60, -200, 20): x is -29 and z is 56.
    turned = [(45, 0, -45), (33, -10, -102), (16, -200, 11)]
    shading = light_one(loc(loc_types=(4,), mirrored=True), loc_type=6)
    assert shading == light(model(turned), LOC_LIGHTING)


def test_an_object_of_type_11_is_lit_before_the_client_turns_it_by_256_units():
    # PacketBuffer.java line 478 gives an object of type 11 the turn of 256 units when the client draws it, after the
    # light. So it has the light of the same object of type 10.
    assert light_one(loc(), loc_type=11) == light_one(loc())


def test_a_contoured_loc_on_uneven_ground_has_the_light_of_its_flat_model():
    # ObjectComposition.java lines 584 and 585 light the model, and lines 600 to 606 contour it after the light.
    assert light_one(loc(contoured_ground=0), tilt) == light(model(VERTICES), LOC_LIGHTING)


def test_a_non_flat_shading_contoured_loc_on_uneven_ground_has_the_light_of_its_contoured_model():
    # ObjectComposition.java lines 586 to 590 keep the ambient and the contrast and do not light the model. Lines 600 to
    # 606 contour it with ModelData.method2625 (from line 1141), which also drops the normals (method2638, lines 1483 to
    # 1488). Region.applyLighting (lines 846 to 865) then lights it with the direction (-50, -10, -50) that class24.java
    # line 316 passes. The placement stands at (704, 960) with the height -960 (PacketBuffer.java lines 197 to 200).
    # Method2625 with a contoured ground of 0 moves each vertex by the terrain height under it, -(960 + z), less -960,
    # so by -z.
    contoured = [(0, 0, 0), (32, 38, -48), (-60, -220, 20)]
    shading = light_one(loc(contoured_ground=0, non_flat_shading=True), tilt)
    assert shading == light(model(contoured), LOC_LIGHTING)
    assert shading != light(model(VERTICES), LOC_LIGHTING)


def test_a_non_flat_shading_loc_with_a_contoured_ground_above_0_is_lit_with_the_heights_of_its_bent_model():
    # ModelData.method2625 (lines 1212 to 1228) bends a vertex whose share (-y << 16) / 200 is below 32768, where 200 is
    # the model height. It writes nothing for any other vertex into the new height array of line 1188, so that vertex is
    # at height 0.
    # Vertex 0 has the share 0 and moves by -z = 0. Vertex 1 has the share 3276 and goes to
    # (32768 - 3276) * 48 / 32768 - 10 = 33. Vertex 2 has the share 65536 and goes to 0.
    contoured = [(0, 0, 0), (32, 33, -48), (-60, 0, 20)]
    shading = light_one(loc(contoured_ground=32768, non_flat_shading=True), tilt)
    assert shading == light(model(contoured), LOC_LIGHTING)


def test_an_animated_non_flat_shading_contoured_loc_has_the_light_of_its_flat_model():
    # An animated loc is a DynamicObject (PacketBuffer.java lines 214 to 218). ObjectComposition.method5092 lights its
    # model at line 662 whatever nonFlatShading is, and contours it after the light (lines 675 to 677).
    definition = loc(contoured_ground=0, non_flat_shading=True, animation=5)
    assert light_one(definition, tilt) == light(model(VERTICES), LOC_LIGHTING)


def test_a_non_flat_shading_contoured_loc_on_flat_ground_has_the_light_of_its_model():
    # ModelData.java lines 1147 to 1153: on flat ground method2625 returns the model unchanged.
    assert light_one(loc(contoured_ground=0, non_flat_shading=True)) == light(model(VERTICES), LOC_LIGHTING)


def test_a_placement_that_shows_nothing_is_refused():
    # ObjectComposition.getImpostor (lines 830 to 845) gives -1 for this loc, so it shows nothing. The part comes from a
    # loc that shows a model, because place_scenery gives the placement that shows nothing no part.
    locs = {1: loc(impostors=(-1,)), 2: loc()}
    (part,) = place_scenery([Placement(loc=2, level=0, x=5, y=7, loc_type=10, rotation=0)], locs, level)[0].parts
    placement = Placement(loc=1, level=0, x=5, y=7, loc_type=10, rotation=0)
    with pytest.raises(ValueError, match=r"The placement at \(5, 7\) shows nothing"):
        loc_light(placement, part, locs, model(VERTICES), level)


@pytest.mark.parametrize("loc_type", [4, 5, 6, 7, 8])
def test_a_non_flat_shading_wall_decoration_is_refused(loc_type: int):
    # ObjectComposition.java lines 586 to 590 leave a non-flat-shading model unlit. Region.applyLighting (lines 831 to
    # 865) lights the walls, the objects and the ground decorations, and skips the wall decorations, and
    # Renderable.draw (lines 38 to 44) draws nothing for a model that is not lit. The owner chose on 2026-11-17 (issue
    # 128) to refuse such a decoration.
    locs = {1: loc(loc_types=(4,), non_flat_shading=True)}
    placement = Placement(loc=1, level=0, x=5, y=7, loc_type=loc_type, rotation=0)
    part = place_scenery([placement], locs, level)[0].parts[0]
    with pytest.raises(ValueError, match=r"The wall decoration at \(5, 7\) is non-flat-shading"):
        loc_light(placement, part, locs, model(VERTICES), level)


def test_an_animated_non_flat_shading_wall_decoration_is_lit():
    # An animated decoration of type 4 is a DynamicObject (PacketBuffer.java lines 403 to 406), and method5092 lights
    # it at ObjectComposition.java line 662 whatever nonFlatShading is.
    definition = loc(loc_types=(4,), non_flat_shading=True, animation=5)
    assert light_one(definition, loc_type=4) == light(model(VERTICES), LOC_LIGHTING)
