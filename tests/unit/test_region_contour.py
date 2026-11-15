from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from math import cos, pi
from pathlib import Path
from typing import Any

import pytest
from runelite_json import load_locs

from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.model import Vertex
from rsps_toolkit.formats.region import Placement
from rsps_toolkit.formats.region_contour import own_vertices
from rsps_toolkit.formats.region_placement import place_scenery

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOCS = load_locs(FIXTURES / "region/locs.json")

# Every client line below is in the 2018 Old School client, `runescape-client/src/main/java/`. The expected vertices
# come from a scratch Java copy of the lines that each test names, run on the vertices and heights of the test. The copy
# stays out of the repo. A game point (x, y, z) is the Blender point (x, z, -y), as in `model_to_object`.


def loc(**changes: Any) -> LocDefinition:
    """A loc with the defaults of the `ObjectComposition` constructor (lines 262 to 296), changed as given."""
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
    }
    return replace(LOCS[83], **(defaults | changes))


def slope(x: int, y: int) -> int:
    return -16 * x - 8 * y


def level(_x: int, _y: int) -> int:
    return -40


def step(x: int, _y: int) -> int:
    return -100 if x <= 4 else 0


def contour_one(
    definition: LocDefinition,
    vertices: Sequence[Vertex],
    height: Callable[[int, int], int],
    loc_type: int = 10,
    rotation: int = 0,
    locs: Mapping[int, LocDefinition] | None = None,
    part_index: int | None = None,
) -> list[tuple[float, float, float]] | None:
    """The absolute Blender vertices of a part of a placement of loc 1 at tile (5, 7), or None when it shares. A
    placement with two parts needs `part_index`."""
    locs = {1: definition} if locs is None else locs
    placement = Placement(loc=1, level=0, x=5, y=7, loc_type=loc_type, rotation=rotation)
    parts = place_scenery([placement], locs, height)[0].parts
    if part_index is None:
        (part,) = parts
    else:
        part = parts[part_index]
    relative = own_vertices(placement, part, locs, vertices, height)
    if relative is None:
        return None
    x, y, z = part.location
    return [(x + dx, y + dy, z + dz) for dx, dy, dz in relative]


def assert_vertices(actual: list[tuple[float, float, float]] | None, expected: list[tuple[float, float, float]]):
    assert actual is not None
    assert actual == [pytest.approx(vertex) for vertex in expected]


def test_a_contoured_placement_on_flat_ground_shares_its_mesh():
    # ModelData.java lines 1147 to 1153 and Model.method2720: when the four corners under the model's bounds have the
    # placement's height, the client returns the model unchanged.
    vertices = [(0, 0, 0), (32, -10, -48), (-60, -200, 20)]
    assert contour_one(loc(contoured_ground=0), vertices, level) is None


def test_a_contoured_placement_on_uneven_ground_has_each_vertex_at_the_terrain_height_under_it():
    # Model.method2720, the branch for a contoured ground of 0: each vertex moves by the bilinear terrain height under
    # it less the placement's height. The placement stands at (704, 960) with the height -148 (PacketBuffer.java lines
    # 197 to 200).
    vertices = [(0, 0, 0), (32, -10, -48), (-60, -200, 20)]
    actual = contour_one(loc(contoured_ground=0), vertices, slope)
    assert_vertices(actual, [(704, 960, 148), (736, 912, 159), (644, 980, 343)])


def test_a_contoured_ground_above_0_bends_the_low_vertices_and_puts_the_others_at_height_0():
    # Model.java lines 429 to 443 (method2720, the other branch): a vertex below contouredGround / 65536 of the model
    # height moves by (contouredGround - t) / contouredGround of the terrain change, where t is its own height in
    # 65536ths. The new model's height array starts at 0 (line 400) and the loop writes only those vertices, so the
    # vertex at y -200 ends at the placement's height, Blender z 148.
    vertices = [(0, 0, 0), (32, -50, 0), (-20, -200, 40)]
    actual = contour_one(loc(contoured_ground=128 * 256), vertices, slope)
    assert_vertices(actual, [(704, 960, 148), (736, 960, 200), (684, 1000, 148)])


def test_an_animated_loc_with_a_contoured_ground_above_0_keeps_the_heights_of_the_vertices_it_does_not_bend():
    # ObjectComposition.java lines 668 to 676 (method5092): a DynamicObject's model is a copy with every height
    # (Model.toSharedModel), and method2720 writes into it, so the vertex at y -200 keeps it, Blender z 148 + 200.
    vertices = [(0, 0, 0), (32, -50, 0), (-20, -200, 40)]
    actual = contour_one(loc(contoured_ground=128 * 256, animation=1), vertices, slope)
    assert_vertices(actual, [(704, 960, 148), (736, 960, 200), (684, 1000, 348)])


def test_a_contoured_diagonal_wall_decoration_with_an_uneven_scale_on_flat_ground_still_gets_its_own_vertices():
    # The ground is flat, so the contour leaves the model alone (Model.java line 372), but the transform still
    # cannot go on the object. The vertices are those of the diagonal test below.
    definition = loc(loc_types=(4,), scale=(64, 128, 128), contoured_ground=0)
    actual = contour_one(definition, [(0, 0, 0), (100, -40, 0)], level, loc_type=6)
    assert_vertices(actual, [(734, 907, 40), (769, 836, 80)])


def test_a_turned_contoured_wall_with_an_offset_is_contoured_after_the_turn_and_the_offset():
    # ObjectComposition.java lines 790 to 819: getModel(0, 1) turns the model by method2649 (x, z become z, -x) and
    # moves it by the offset (16, 0, 0) of method2630 before the contour of line 600 reads its vertices.
    definition = loc(loc_types=(0,), contoured_ground=0, offset=(16, 0, 0))
    vertices = [(0, 0, 0), (64, -10, 0), (0, -20, 64)]
    actual = contour_one(definition, vertices, slope, loc_type=0, rotation=1)
    assert_vertices(actual, [(720, 960, 150), (720, 896, 156), (784, 960, 178)])


def test_an_object_of_type_11_is_contoured_before_the_client_turns_it_by_256_units():
    # PacketBuffer.java lines 472 to 478: getModel(10, 0) contours the model unturned, and method2911 turns it by 256
    # units when it draws it. A turn of 256 units is -pi / 4 about Blender z (see test_region_placement.py).
    actual = contour_one(loc(contoured_ground=0), [(0, 0, 0), (64, -10, 0)], slope, loc_type=11)
    half = 64 * cos(pi / 4)
    assert_vertices(actual, [(704, 960, 148), (704 + half, 960 - half, 166)])


def test_a_contoured_ground_above_0_on_a_model_with_no_height_is_refused():
    # Model.method2720 divides by the model height, which is 0 when no vertex is above the origin, and Java then throws.
    with pytest.raises(ValueError, match="height"):
        contour_one(loc(contoured_ground=256), [(0, 0, 0), (32, 10, 0)], slope)


def test_a_loc_that_is_not_contoured_shares_its_mesh_on_uneven_ground():
    # ObjectComposition.java line 600: only a contouredGround of 0 or more changes the model.
    assert contour_one(loc(), [(0, 0, 0), (32, -10, -48)], slope) is None


def test_a_lit_contoured_loc_tests_the_ground_at_the_corners_of_the_circle_around_its_origin():
    # Model.method2720 tests the corners of a square of half width XYZMag (calculateBoundsCylinder), here 70, which
    # reach the tile corner x = 4 to the west, where the ground is lower. No vertex is over that corner, so the
    # heights stay, but the placement still gets its own vertices.
    actual = contour_one(loc(contoured_ground=0), [(0, 0, 0), (70, -30, 0)], step)
    assert_vertices(actual, [(704, 960, 0), (774, 960, 30)])


def test_a_non_flat_shading_contoured_loc_tests_the_ground_at_the_corners_of_its_box():
    # ObjectComposition.java lines 596 to 605 contour a non-flat-shading loc with ModelData.method2625, which tests the
    # corners of the model's box (method2637). The box spans x 0 to 70 and stays east of the step.
    assert contour_one(loc(contoured_ground=0, non_flat_shading=True), [(0, 0, 0), (70, -30, 0)], step) is None


def test_an_animated_non_flat_shading_contoured_loc_tests_the_circle_like_a_lit_one():
    # PacketBuffer.java makes a DynamicObject of an animated loc, and DynamicObject.getModel contours it with
    # ObjectComposition.method5092, which always uses the lit Model and so Model.method2720.
    definition = loc(contoured_ground=0, non_flat_shading=True, animation=1)
    actual = contour_one(definition, [(0, 0, 0), (70, -30, 0)], step)
    assert_vertices(actual, [(704, 960, 0), (774, 960, 30)])


def test_an_impostor_contours_at_the_footprint_of_the_loc_that_it_shows():
    # DynamicObject.getModel reads the width and length of the impostor, so the contour of a 2 by 1 impostor is at
    # (768, 960) with the height -156 under that footprint. The object stands where the placed 1 by 1 loc stands, at
    # (704, 960) with the height -148 (PacketBuffer.java lines 165 to 200).
    locs = {1: loc(impostors=(2,), impostor_varbit=5), 2: loc(contoured_ground=0, width=2)}
    actual = contour_one(locs[1], [(0, 0, 0), (40, -20, 0)], slope, loc_type=10, locs=locs)
    assert_vertices(actual, [(704, 960, 148), (744, 960, 173)])


def test_a_diagonal_wall_decoration_with_a_different_x_and_z_scale_gets_the_client_vertices():
    # ObjectComposition.java lines 753 to 815: the model of rotation 4 is mirrored (ModelData.method2633), then turned
    # by ModelData.method2663(256) with the SINE and COSINE tables of Graphics3D.java lines 97 to 98, moved by
    # (45, 0, -45), and scaled by method2674 with (64, 128, 128). The ground is flat and the loc is not contoured. A type
    # 6 decoration at rotation 0 with no wall stands at (712, 952), offset by (8, -8) (PacketBuffer.java lines 422 to
    # 430).
    vertices = [(0, 0, 0), (100, -40, 0), (-30, -80, 50)]
    actual = contour_one(loc(loc_types=(4,), scale=(64, 128, 128)), vertices, level, loc_type=6)
    floor = 40
    assert_vertices(actual, [(734, 907, floor), (769, 836, floor + 40), (706, 892, floor + 80)])


def test_a_diagonal_wall_decoration_with_an_even_scale_shares_its_mesh():
    vertices = [(0, 0, 0), (100, -40, 0)]
    assert contour_one(loc(loc_types=(4,), scale=(64, 128, 64)), vertices, level, loc_type=6) is None


def bumps(x: int, y: int) -> int:
    return -40 * ((3 * x + 5 * y) % 7)


def step_east(x: int, _y: int) -> int:
    return -100 if x >= 7 else 0


def step_north(_x: int, y: int) -> int:
    return -100 if y >= 9 else 0


def test_a_turned_loc_of_2_by_1_contours_at_the_middle_of_its_swapped_footprint():
    # PacketBuffer.java lines 168 to 200: at rotation 1 the footprint is 1 by 2, so the model stands at (704, 1024) with
    # the height -160, and Model.method2720 contours it there after the quarter turn of method2649. The ground is uneven
    # and irregular, because on a plane or a smooth curve the contour gives the same heights wherever it stands.
    definition = loc(contoured_ground=0, width=2)
    vertices = [(0, 0, 0), (32, -10, -48), (-60, -200, 20)]
    actual = contour_one(definition, vertices, bumps, rotation=1)
    assert_vertices(actual, [(704, 1024, 160), (656, 992, 189), (724, 1084, 298)])


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        # ModelData.method2627 (lines 1311 to 1318): x and z become -x and -z.
        (2, [(704, 960, 148), (640, 960, 150), (704, 896, 164)]),
        # ModelData.method2641 (lines 1321 to 1329): x and z become -z and x.
        (3, [(704, 960, 148), (704, 1024, 162), (640, 960, 160)]),
    ],
)
def test_a_contoured_wall_at_rotation_2_or_3_is_turned_before_the_contour(
    rotation: int, expected: list[tuple[float, float, float]]
):
    # ObjectComposition.java lines 792 to 799 pick the quarter turn from the rotation.
    definition = loc(loc_types=(0,), contoured_ground=0)
    actual = contour_one(definition, [(0, 0, 0), (64, -10, 0), (0, -20, 64)], slope, loc_type=0, rotation=rotation)
    assert_vertices(actual, expected)


def test_the_first_model_of_a_type_2_wall_is_mirrored_but_not_turned_diagonally():
    # PacketBuffer.java line 330 asks for getModel(2, 4). ObjectComposition.java line 753 mirrors it, because the
    # rotation is above 3, and line 787 turns a model by 256 units only for the loc type 4.
    definition = loc(loc_types=(2,), contoured_ground=0)
    actual = contour_one(definition, [(0, 0, 0), (64, -10, 0), (0, -20, 64)], slope, loc_type=2, part_index=0)
    assert_vertices(actual, [(704, 960, 148), (768, 960, 166), (704, 896, 164)])


@pytest.mark.parametrize(
    ("vertices", "height", "expected"),
    [
        ([(0, 0, 0), (70, -30, 0)], step_east, [(704, 960, 0), (774, 960, 35)]),
        ([(0, 0, 0), (0, -30, 70)], step_north, [(704, 960, 0), (704, 1030, 35)]),
    ],
)
def test_a_lit_contoured_loc_rounds_the_east_and_north_edges_of_its_circle_up_to_the_next_tile_corner(
    vertices: list[Vertex], height: Callable[[int, int], int], expected: list[tuple[float, float, float]]
):
    # Model.java lines 369 to 372: the east and north edges are (edge + 127) >> 7. Here the edge 1030 or 774 reaches
    # the tile corner 9 or 7, where the ground steps down, so the client contours the model.
    assert_vertices(contour_one(loc(contoured_ground=0), vertices, height), expected)


def test_a_vertex_below_the_origin_is_bent_with_java_integer_division():
    # Model.java lines 429 to 440: for the vertex at y 10, t is (-10 << 16) / 50, which Java rounds toward zero to
    # -13107, and the bend (32768 + 13107) * (ground - reference) / 32768 rounds toward zero too.
    vertices = [(0, 0, 0), (32, -50, 0), (-20, 10, 40)]
    actual = contour_one(loc(contoured_ground=128 * 256), vertices, slope)
    assert_vertices(actual, [(704, 960, 148), (736, 960, 148), (684, 1000, 139)])


def test_a_vertex_at_exactly_the_contoured_ground_is_not_bent():
    # Model.java line 431 bends a vertex only when t < contouredGround. The vertex at y -50 of a model of height 100 has
    # t = 32768, the same as the contoured ground, so it stays at height 0 of the new array, Blender z 148.
    vertices = [(0, 0, 0), (32, -50, 0), (-20, -100, 40)]
    actual = contour_one(loc(contoured_ground=128 * 256), vertices, slope)
    assert_vertices(actual, [(704, 960, 148), (736, 960, 148), (684, 1000, 148)])


def test_an_impostor_wall_contours_at_the_footprint_swapped_by_the_rotation_of_its_part():
    # PacketBuffer.java lines 326 to 334: the second model of a type 2 wall at rotation 0 is a DynamicObject with the
    # orientation 1. DynamicObject.java lines 139 to 155 swap the 2 by 1 footprint of the impostor by that orientation,
    # not by the placement's rotation 0, so the contour is at (704, 1024) with the height -160. The wall stands at the
    # middle of its tile with the height -130 of the placed 1 by 1 loc. The ground is irregular, as in the test of a
    # turned loc of 2 by 1.
    locs = {1: loc(impostors=(2,), impostor_varbit=5), 2: loc(loc_types=(2,), contoured_ground=0, width=2)}
    actual = contour_one(locs[1], [(0, 0, 0), (40, -20, 0)], bumps, loc_type=2, locs=locs, part_index=1)
    assert_vertices(actual, [(704, 960, 130), (704, 920, 132)])
