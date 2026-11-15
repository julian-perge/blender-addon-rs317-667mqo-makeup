import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from js5_builder import build_region_cache
from runelite_json import load_locs

from rsps_toolkit.formats import decode
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.model import Vertex
from rsps_toolkit.formats.region import Placement, Terrain, load_terrain
from rsps_toolkit.formats.region_colours import corner_light
from rsps_toolkit.formats.region_light import loc_shadows
from rsps_toolkit.formats.region_loc import LocModel
from rsps_toolkit.formats.region_placement import place_scenery

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOCS = load_locs(FIXTURES / "region/locs.json")
MODEL_1686 = decode((FIXTURES / "models/osrs149/1686.dat").read_bytes(), profile="osrs-149")

# Every client line below is in the 2018 Old School client, `runescape-client/src/main/java/`. The expected lights come
# from a scratch Java copy of `PacketBuffer.java` lines 263 to 265 (the wall of type 0 at rotation 1) and 478 to 493 (the
# object), `Model.java` lines 601 to 627 (`calculateBoundsCylinder`, run on the vertices of RuneLite's
# `tests/fixtures/models/osrs149/1686.json`) and `class24.java` lines 98 to 116 (the light). Its input was the level 0
# heights of the terrain of 48_50, with that one placement as the only loc. The copy stays out of the repo.


@pytest.fixture(scope="module")
def terrain(tmp_path_factory) -> Terrain:
    folder = tmp_path_factory.mktemp("cache")
    build_region_cache(folder)
    return load_terrain(Js5Store(folder), 48, 50)


def loc(**changes: Any) -> LocDefinition:
    """Loc 1163 of 48_50, a loc of type 10 with model 1686 that writes loc shadows, changed as given."""
    return replace(LOCS[1163], **changes)


def flat(_x: int, _y: int) -> int:
    return 0


def shadows(
    placements: Sequence[Placement],
    locs: Mapping[int, LocDefinition],
    vertices: Sequence[Vertex] = MODEL_1686.vertices,
) -> dict[tuple[int, int], int]:
    def model_vertices(model: LocModel) -> Sequence[Vertex]:
        assert len(model.model_ids) == 1
        return vertices

    return loc_shadows(place_scenery(placements, locs, flat), locs, model_vertices)


def at(x: int, y: int, loc_type: int, rotation: int = 0, loc_id: int = 1) -> Placement:
    return Placement(loc=loc_id, level=0, x=x, y=y, loc_type=loc_type, rotation=rotation)


def test_model_1686_decodes_to_the_vertices_of_runelite():
    reference = json.loads((FIXTURES / "models/osrs149/1686.json").read_text())
    expected = list(zip(reference["vertex_x"], reference["vertex_y"], reference["vertex_z"], strict=True))
    assert [tuple(vertex) for vertex in MODEL_1686.vertices] == expected


def test_a_corner_shadowed_by_a_wall_gets_the_light_of_the_client(terrain):
    # Loc 980 at (27, 49), a wall of type 0 at rotation 1, writes 50 at its north corners (PacketBuffer.java lines 263
    # to 265).
    written = shadows([at(27, 49, 0, 1, loc_id=980)], LOCS)
    assert written == {(27, 50): 50, (28, 50): 50}
    lights = {corner: corner_light(terrain, *corner, written) for corner in ((27, 50), (28, 50), (27, 51), (26, 50))}
    assert lights == {(27, 50): 38, (28, 50): 33, (27, 51): 60, (26, 50): 75}


def test_a_corner_shadowed_by_an_object_gets_the_light_of_the_client(terrain):
    # Loc 1163 at (40, 40), an object of type 10. Model 1686 has the XYZMag 25, so the shadow is 25 / 4 = 6 at the 4
    # corners of its tile (PacketBuffer.java lines 480 to 493).
    written = shadows([at(40, 40, 10, loc_id=1163)], LOCS)
    assert written == {(40, 40): 6, (41, 40): 6, (40, 41): 6, (41, 41): 6}
    lights = {corner: corner_light(terrain, *corner, written) for corner in ((40, 40), (41, 41), (40, 39))}
    assert lights == {(40, 40): 57, (41, 41): 78, (40, 39): 61}


def test_a_loc_with_the_non_flat_shading_flag_writes_15():
    # ObjectComposition.java lines 584 to 595: a non-flat-shading loc gives a ModelData, not a Model, so the shadow keeps
    # the 15 of PacketBuffer.java line 479.
    written = shadows([at(5, 5, 10)], {1: loc(non_flat_shading=True)})
    assert written == {(5, 5): 15, (6, 5): 15, (5, 6): 15, (6, 6): 15}


def test_a_non_flat_shading_loc_with_no_model_for_its_type_writes_no_shadow():
    # ObjectComposition.java lines 579 to 583: getModel returns null before it tests the flag, and PacketBuffer.java line
    # 478 then writes nothing.
    assert shadows([at(5, 5, 10)], {1: loc(non_flat_shading=True, loc_types=(22,), models=(1686,))}) == {}


@pytest.mark.parametrize(
    "changes",
    [
        {"animation": 7},
        {"animation": 7, "loc_types": (22,), "models": (1686,)},
        {"impostors": (-1, -1), "impostor_varbit": 3},
    ],
)
def test_an_animated_loc_or_a_loc_with_impostors_writes_15_even_when_it_shows_nothing(changes):
    # PacketBuffer.java lines 472 to 476: such a loc is a DynamicObject, not a Model, so the shadow keeps the 15 of line
    # 479. The DynamicObject is never null, so the client writes it also when the loc has no model for its type or the
    # impostor shows nothing.
    written = shadows([at(5, 5, 10)], {1: loc(**changes)})
    assert written == {(5, 5): 15, (6, 5): 15, (5, 6): 15, (6, 6): 15}


def test_the_object_shadow_is_at_most_30():
    # PacketBuffer.java lines 481 to 484: the XYZMag 200 gives 50, and the client keeps 30.
    written = shadows([at(5, 5, 11)], {1: loc()}, vertices=[(0, -10, 0), (120, 0, -160)])
    assert set(written.values()) == {30}


def test_the_xyzmag_is_rounded_up_and_reads_only_x_and_z():
    # Model.java lines 620 to 626: the largest x * x + z * z is 15 * 15 + 1 = 226, the root 15.03 is rounded up to 16 by
    # the 0.99 that the client adds, and the height -1000 does not count. The shadow is 16 / 4 = 4.
    written = shadows([at(5, 5, 10)], {1: loc()}, vertices=[(15, 0, 1), (0, -1000, 0)])
    assert set(written.values()) == {4}


def test_the_xyzmag_reads_the_vertices_after_the_scale_and_the_offset_of_the_loc():
    # ObjectComposition.java lines 811 to 819: getModel scales the model and moves it by the offset before the client
    # measures it. x 40 scaled to 80, then moved by 20 to 100, gives the XYZMag 100 and the shadow 25.
    written = shadows([at(5, 5, 10)], {1: loc(scale=(256, 128, 128), offset=(20, 0, 0))}, vertices=[(40, 0, 0)])
    assert set(written.values()) == {25}


def test_an_object_writes_at_every_corner_of_its_footprint_swapped_at_rotation_1():
    # PacketBuffer.java lines 169 to 177 and 487 to 493: a loc 2 wide and 1 long at rotation 1 covers 1 by 2 tiles, so 2
    # by 3 corners.
    written = shadows([at(5, 5, 10, 1)], {1: loc(width=2, length=1)})
    assert set(written) == {(x, y) for x in (5, 6) for y in (5, 6, 7)}


def test_overlapping_objects_keep_the_larger_shadow_and_a_wall_writes_50_over_them():
    # PacketBuffer.java lines 489 to 490 keep the larger object shadow. Lines 255 to 256 set 50 whatever the corner held.
    small = loc(models=(1,))
    locs = {1: loc(), 2: small, 3: LOCS[980]}

    def model_vertices(model: LocModel) -> Sequence[Vertex]:
        return [(8, 0, 0)] if model.model_ids == (1,) else MODEL_1686.vertices

    # The small object writes 2 at (6, 5) and (6, 6) after the first wrote 6 there, and the wall of type 0 at rotation 0
    # writes 50 at (5, 5) and (5, 6) after the first object wrote 6 there.
    placements = [at(5, 5, 10, loc_id=1), at(6, 5, 10, loc_id=2), at(5, 5, 0, loc_id=3)]
    written = loc_shadows(place_scenery(placements, locs, flat), locs, model_vertices)
    assert written == {(5, 5): 50, (6, 5): 6, (5, 6): 50, (6, 6): 6, (7, 5): 2, (7, 6): 2}


WALL_CORNERS = {
    # PacketBuffer.java lines 254 to 284 for type 0, and 307 to 316 and 370 to 379 for types 1 and 3.
    (0, 0): {(5, 5), (5, 6)},
    (0, 1): {(5, 6), (6, 6)},
    (0, 2): {(6, 5), (6, 6)},
    (0, 3): {(5, 5), (6, 5)},
    (1, 0): {(5, 6)},
    (1, 1): {(6, 6)},
    (1, 2): {(6, 5)},
    (1, 3): {(5, 5)},
    (3, 0): {(5, 6)},
    (3, 1): {(6, 6)},
    (3, 2): {(6, 5)},
    (3, 3): {(5, 5)},
}


@pytest.mark.parametrize(("loc_type", "rotation"), WALL_CORNERS)
def test_a_wall_writes_50_at_the_corners_of_its_type_and_rotation(loc_type, rotation):
    wall = LOCS[980]
    written = shadows([at(5, 5, loc_type, rotation)], {1: wall})
    assert written == dict.fromkeys(WALL_CORNERS[(loc_type, rotation)], 50)


def test_a_wall_writes_its_shadow_also_when_it_has_no_model_for_its_type():
    # PacketBuffer.java lines 252 to 255 do not test the model that line 247 gave.
    wall = replace(LOCS[980], loc_types=(22,), models=(1,))
    assert shadows([at(5, 5, 0)], {1: wall}) == {(5, 5): 50, (5, 6): 50}


@pytest.mark.parametrize("loc_type", [2, 4, 5, 6, 7, 8, 9, 12, 21, 22])
def test_the_other_loc_types_write_no_shadow(loc_type):
    # Only the branches of types 0, 1, 3, 10 and 11 in PacketBuffer.java write class50.field449.
    definition = loc(loc_types=(loc_type, 4), models=(1686, 1686), casts_shadow=True)
    assert shadows([at(5, 5, loc_type)], {1: definition}) == {}


@pytest.mark.parametrize("loc_type", [0, 1, 3, 10, 11])
def test_a_loc_that_does_not_cast_a_shadow_writes_none(loc_type):
    # PacketBuffer.java lines 254, 263, 272, 281, 307, 370 and 478 test `clipped`.
    definition = loc(loc_types=(loc_type,), models=(1686,), casts_shadow=False)
    assert shadows([at(5, 5, loc_type)], {1: definition}) == {}


def test_an_object_with_no_model_for_its_type_writes_no_shadow():
    # PacketBuffer.java line 478 tests that getModel gave a model.
    assert shadows([at(5, 5, 10)], {1: loc(loc_types=(22,), models=(1686,))}) == {}
