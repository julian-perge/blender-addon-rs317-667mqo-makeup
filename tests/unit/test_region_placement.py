from collections.abc import Callable
from dataclasses import replace
from math import cos, pi, radians, sin
from pathlib import Path
from typing import Any

import pytest
from runelite_json import load_locs

from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.region import Placement
from rsps_toolkit.formats.region_placement import PlacedLoc, PlacedPart, Slot, place_scenery, slot_of

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOCS = load_locs(FIXTURES / "region/locs.json")

# Every client line below is in the 2018 Old School client, `runescape-client/src/main/java/`. A client turn is 2048
# units, which Blender sees as a turn of -2 pi / 2048 radians about z, because the client rotates by
# `ModelData.method2663` (lines 1332 to 1343) and Blender's axes are (x, z, -y) of the client's (see `model_to_object`).
UNIT = -2 * pi / 2048
QUARTER = 512 * UNIT


def flat(_x: int, _y: int) -> int:
    return 0


def loc(**changes: Any) -> LocDefinition:
    """A loc with the defaults of the `ObjectComposition` constructor (lines 262 to 296), changed as given. It has one
    model for each loc type that the tests ask for."""
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
        "animation": -1,
        "decor_displacement": 16,
        "impostors": None,
        "impostor_varbit": -1,
        "impostor_varp": -1,
    }
    return replace(LOCS[83], **(defaults | changes))


def typed(loc_type: int, **changes: Any) -> LocDefinition:
    """A loc whose one model is for `loc_type`, the type that the client passes to `getModel`: 4 for every wall decoration
    and 10 for objects of types 10 and 11."""
    return loc(loc_types=(loc_type,), **changes)


def at(loc_id: int, loc_type: int, rotation: int = 0, x: int = 5, y: int = 7) -> Placement:
    return Placement(loc=loc_id, level=0, x=x, y=y, loc_type=loc_type, rotation=rotation)


def place_one(
    definition: LocDefinition,
    loc_type: int,
    rotation: int = 0,
    height: Callable[[int, int], int] = flat,
    x: int = 5,
    y: int = 7,
) -> PlacedLoc:
    return place_scenery([at(1, loc_type, rotation, x, y)], {1: definition}, height)[0]


def only_part(placed: PlacedLoc) -> PlacedPart:
    assert len(placed.parts) == 1
    return placed.parts[0]


def test_each_loc_type_belongs_to_the_slot_that_the_client_gives_it():
    # PacketBuffer.java lines 212 to 503: 22 is the ground object, 12 and up and 9 to 11 are objects through
    # method2911, 0 to 3 are boundaries and 4 to 8 are boundary decorations.
    slots = [slot_of(loc_type) for loc_type in range(23)]
    assert slots == ([Slot.WALL] * 4 + [Slot.WALL_DECORATION] * 5 + [Slot.OBJECT] * 13 + [Slot.GROUND_DECORATION])


def test_a_loc_type_above_22_is_refused():
    with pytest.raises(ValueError, match="loc type"):
        slot_of(23)


def test_a_wall_stands_at_the_middle_of_its_tile_and_turns_with_its_rotation():
    # PacketBuffer.java lines 245 to 298 with Region.addBoundary lines 420 to 445: x = tile * 128 + 64, and the model
    # carries the rotation (ObjectComposition.java lines 792 to 797).
    part = only_part(place_one(typed(0), 0, rotation=1))
    assert part.slot is Slot.WALL
    assert (part.model_type, part.model_rotation) == (0, 1)
    assert part.location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))
    assert part.rotation == pytest.approx(QUARTER)
    assert part.scale == (1, 1, 1)


def test_a_wall_decoration_of_type_4_stands_at_the_middle_of_its_tile_without_an_offset():
    # PacketBuffer.java lines 402 to 412: the offsets of type 4 are 0 and 0.
    part = only_part(place_one(typed(4), 4, rotation=2))
    assert part.slot is Slot.WALL_DECORATION
    assert (part.model_type, part.model_rotation) == (4, 2)
    assert part.location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))
    assert part.rotation == pytest.approx(2 * QUARTER)


def test_an_object_of_type_9_and_of_types_12_to_21_takes_one_tile_whatever_its_size():
    # PacketBuffer.java lines 236 and 393: method2911 gets the footprint 1 by 1, so x = tile * 128 + 64.
    for loc_type in (9, 12, 21):
        part = only_part(place_one(typed(loc_type, width=3, length=2), loc_type))
        assert part.slot is Slot.OBJECT
        assert part.location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))


def test_a_ground_decoration_stands_at_the_middle_of_its_tile():
    # PacketBuffer.java lines 212 to 227 with Region.groundObjectSpawned lines 362 to 376.
    part = only_part(place_one(typed(22), 22, rotation=3))
    assert part.slot is Slot.GROUND_DECORATION
    assert (part.model_type, part.model_rotation) == (22, 3)
    assert part.location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))


def test_a_wall_of_type_2_has_two_models_one_turned_a_quarter_further():
    # PacketBuffer.java lines 326 to 331: the models are getModel(2, rotation + 4) and getModel(2, rotation + 1 & 3).
    placed = place_one(typed(2), 2, rotation=3)
    first, second = placed.parts
    assert [(p.model_type, p.model_rotation) for p in placed.parts] == [(2, 7), (2, 0)]
    assert first.rotation == pytest.approx(3 * QUARTER)
    assert second.rotation == pytest.approx(0)
    assert first.location == second.location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))
    # Lines 753 and 1380: the model for rotation 7 is mirrored, the one for rotation 0 is not.
    assert first.scale == (1, -1, 1)
    assert second.scale == (1, 1, 1)


def test_a_placement_whose_loc_has_no_model_for_its_type_has_no_parts():
    # ObjectComposition.java lines 742 to 751: no model for the type gives null, so the client draws nothing.
    assert place_one(typed(0), 10).parts == ()


@pytest.mark.parametrize(
    ("rotation", "offset"),
    [(0, (16, 0)), (1, (0, -16)), (2, (-16, 0)), (3, (0, 16))],
)
def test_a_wall_decoration_of_type_5_is_offset_by_16_when_no_wall_is_on_its_tile(rotation, offset):
    # PacketBuffer.java lines 413 to 426: the displacement is 16 without a wall, and the offsets are
    # displacement * class50.field456[rotation] and displacement * field457[rotation] (class50.java lines 69 to 70).
    part = only_part(place_one(typed(4), 5, rotation))
    assert (part.model_type, part.model_rotation) == (4, rotation)
    assert part.location == pytest.approx((5 * 128 + 64 + offset[0], 7 * 128 + 64 + offset[1], 0))


@pytest.mark.parametrize(
    ("rotation", "offset"),
    [(0, (8, -8)), (1, (-8, -8)), (2, (-8, 8)), (3, (8, 8))],
)
def test_a_wall_decoration_of_type_6_is_offset_by_8_along_a_diagonal_when_no_wall_is_on_its_tile(rotation, offset):
    # PacketBuffer.java lines 427 to 440: displacement 8 without a wall, and field458 and field459 (class50.java lines
    # 71 to 72). The model is getModel(4, rotation + 4), so it carries the extra turn of 256 units.
    part = only_part(place_one(typed(4), 6, rotation))
    assert (part.model_type, part.model_rotation) == (4, rotation + 4)
    # The model's own translation of 45, 0, -45 (ModelData line 1346, ObjectComposition line 789) comes on top of
    # the wall decoration offset, turned by the quarter turn of the rotation.
    own = _rotated_quarters((45, -45), rotation)
    assert part.location == pytest.approx((5 * 128 + 64 + offset[0] + own[0], 7 * 128 + 64 + offset[1] + own[1], 0))


def _rotated_quarters(point: tuple[float, float], quarters: int) -> tuple[float, float]:
    """The Blender point turned by `quarters` client quarter turns, which is -90 degrees each."""
    x, y = point
    for _ in range(quarters % 4):
        x, y = y, -x
    return x, y


def test_a_wall_decoration_of_type_7_is_turned_two_quarters_and_has_no_offset():
    # PacketBuffer.java lines 441 to 449: the model is getModel(4, (rotation + 2 & 3) + 4) and the offsets are 0.
    part = only_part(place_one(typed(4), 7, rotation=1))
    assert (part.model_type, part.model_rotation) == (4, 7)
    own = _rotated_quarters((45, -45), 3)
    assert part.location == pytest.approx((5 * 128 + 64 + own[0], 7 * 128 + 64 + own[1], 0))


def test_a_wall_decoration_of_type_8_has_two_models_and_only_the_first_is_offset():
    # PacketBuffer.java lines 450 to 467: getModel(4, rotation + 4) with the offset, and getModel(4, (rotation + 2 & 3)
    # + 4) without it. Region.java lines 1459 to 1461 draws renderable2 at var13.x - cameraX2 with no offsetX.
    placed = place_one(typed(4), 8, rotation=0)
    first, second = placed.parts
    assert [(p.model_type, p.model_rotation) for p in placed.parts] == [(4, 4), (4, 6)]
    own_first = _rotated_quarters((45, -45), 0)
    own_second = _rotated_quarters((45, -45), 2)
    assert first.location == pytest.approx((5 * 128 + 64 + 8 + own_first[0], 7 * 128 + 64 - 8 + own_first[1], 0))
    assert second.location == pytest.approx((5 * 128 + 64 + own_second[0], 7 * 128 + 64 + own_second[1], 0))


def test_a_wall_decoration_after_a_wall_takes_the_displacement_of_that_wall():
    # PacketBuffer.java lines 413 to 426 and Region.java lines 770 to 773: method2927 gives the wall of the tile, and
    # type 5 uses its decorDisplacement. Type 1 is a wall too, so its displacement counts.
    locs = {1: typed(1, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(1, 1), at(2, 5, rotation=0)], locs, flat)
    assert only_part(placed[1]).location == pytest.approx((5 * 128 + 64 + 32, 7 * 128 + 64, 0))


def test_a_wall_decoration_of_type_6_after_a_wall_takes_half_the_displacement():
    # PacketBuffer.java lines 427 to 440: displacement / 2, with integer division.
    locs = {1: typed(0, decor_displacement=25), 2: typed(4)}
    placed = place_scenery([at(1, 0), at(2, 6, rotation=0)], locs, flat)
    own = _rotated_quarters((45, -45), 0)
    assert only_part(placed[1]).location == pytest.approx((5 * 128 + 64 + 12 + own[0], 7 * 128 + 64 - 12 + own[1], 0))


def test_a_wall_decoration_of_type_8_after_a_wall_takes_half_the_displacement():
    # PacketBuffer.java lines 450 to 467, as for type 6.
    locs = {1: typed(2, decor_displacement=24), 2: typed(4)}
    placed = place_scenery([at(1, 2), at(2, 8, rotation=0)], locs, flat)
    own = _rotated_quarters((45, -45), 0)
    assert placed[1].parts[0].location == pytest.approx((5 * 128 + 64 + 12 + own[0], 7 * 128 + 64 - 12 + own[1], 0))


def test_a_wall_of_type_0_placed_after_a_wall_decoration_rescales_the_offset_of_that_decoration():
    # PacketBuffer.java lines 295 to 297 and Region.method3030 (lines 656 to 665): offsetX = displacement * offsetX / 16.
    # The decoration is placed first with the offset 16, and a wall with displacement 32 makes it 32.
    locs = {1: typed(0, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(2, 5, rotation=0), at(1, 0)], locs, flat)
    assert only_part(placed[0]).location == pytest.approx((5 * 128 + 64 + 32, 7 * 128 + 64, 0))


def test_a_wall_of_type_2_placed_after_a_wall_decoration_of_type_5_rescales_its_offsets_on_both_axes():
    # PacketBuffer.java lines 358 to 360 (type 2 calls method3030 too). Rotation 1 gives the offsets 0 and -16.
    locs = {1: typed(2, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(2, 5, rotation=1), at(1, 2)], locs, flat)
    assert only_part(placed[0]).location == pytest.approx((5 * 128 + 64, 7 * 128 + 64 - 32, 0))


def test_an_object_of_type_9_placed_after_a_wall_decoration_rescales_its_offset_too():
    # PacketBuffer.java lines 398 to 400: type 9 calls method3030 when its displacement is not 16.
    locs = {1: typed(9, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(2, 5, rotation=0), at(1, 9)], locs, flat)
    assert only_part(placed[0]).location == pytest.approx((5 * 128 + 64 + 32, 7 * 128 + 64, 0))


def test_a_wall_of_type_1_placed_after_a_wall_decoration_leaves_its_offset_alone():
    # PacketBuffer.java lines 299 to 324: type 1 does not call method3030.
    locs = {1: typed(1, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(2, 5, rotation=0), at(1, 1)], locs, flat)
    assert only_part(placed[0]).location == pytest.approx((5 * 128 + 64 + 16, 7 * 128 + 64, 0))


def test_a_wall_of_another_tile_does_not_change_a_wall_decoration():
    locs = {1: typed(0, decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(1, 0, x=6), at(2, 5, rotation=0)], locs, flat)
    assert only_part(placed[1]).location == pytest.approx((5 * 128 + 64 + 16, 7 * 128 + 64, 0))


def test_a_wall_with_no_model_does_not_count_as_a_wall_for_a_decoration():
    # Region.addBoundary (lines 420 to 423) stores nothing when both renderables are null, so method2927 gives 0.
    locs = {1: loc(models=(), decor_displacement=32), 2: typed(4)}
    placed = place_scenery([at(1, 0), at(2, 5, rotation=0)], locs, flat)
    assert placed[0].parts == ()
    assert only_part(placed[1]).location == pytest.approx((5 * 128 + 64 + 16, 7 * 128 + 64, 0))


def test_an_object_of_type_10_wider_than_a_tile_stands_at_the_middle_of_its_footprint():
    # PacketBuffer.java lines 169 to 200 and 478: x = (tile << 7) + (width << 6) and likewise for y, and the
    # footprint swaps its sides at rotations 1 and 3 (lines 169 to 177).
    definition = loc(width=3, length=2)
    straight = only_part(place_one(definition, 10, rotation=0))
    assert straight.location == pytest.approx((5 * 128 + 3 * 64, 7 * 128 + 2 * 64, 0))
    for rotation in (1, 3):
        turned = only_part(place_one(definition, 10, rotation=rotation))
        assert turned.location == pytest.approx((5 * 128 + 2 * 64, 7 * 128 + 3 * 64, 0))


def test_an_object_of_type_11_is_turned_a_further_256_units():
    # PacketBuffer.java line 478: method2911 gets var5 == 11 ? 256 : 0 as the orientation, and
    # Region.java line 1366 draws with it. 256 units is an eighth of a turn.
    straight = only_part(place_one(loc(), 10, rotation=1))
    diagonal = only_part(place_one(loc(), 11, rotation=1))
    assert straight.rotation is not None
    assert diagonal.rotation == pytest.approx(straight.rotation + 256 * UNIT)
    assert (diagonal.model_type, diagonal.model_rotation) == (10, 1)


def test_an_object_of_type_11_with_an_offset_turns_the_offset_with_it():
    # The offset is part of the model (ObjectComposition.java lines 817 to 819), and the orientation rotates the model
    # (Model.draw, lines 1564 to 1570 and 537 to 543), so it turns the offset too.
    definition = loc(offset=(100, 0, 0))
    part = only_part(place_one(definition, 11, rotation=0))
    turn = 256 * UNIT
    assert part.location == pytest.approx((5 * 128 + 64 + 100 * cos(turn), 7 * 128 + 64 + 100 * sin(turn), 0))


def test_the_height_of_a_placement_on_a_slope_is_the_mean_of_the_four_corner_heights():
    # PacketBuffer.java line 198: (h[x1][y1] + h[x0][y1] + h[x1][y0] + h[x0][y0]) >> 2. Height is down, so
    # Blender z is its negative.
    corners = {(5, 7): 100, (6, 7): 140, (5, 8): 120, (6, 8): 200}
    part = only_part(place_one(typed(22), 22, height=lambda x, y: corners[(x, y)]))
    assert part.location[2] == pytest.approx(-140)


def test_the_height_mean_rounds_toward_minus_infinity():
    # `>> 2` of -5 is -2 in Java and in Python.
    corners = {(5, 7): -1, (6, 7): -1, (5, 8): -1, (6, 8): -2}
    part = only_part(place_one(typed(22), 22, height=lambda x, y: corners[(x, y)]))
    assert part.location[2] == pytest.approx(2)


def test_the_height_of_a_footprint_wider_than_a_tile_reads_the_corners_under_its_middle():
    # PacketBuffer.java lines 179 to 198: with width 3 the columns are x + 1 and x + 2, and with length 2 the rows are
    # y + 1 and y + 1. Width 2 gives column x + 1 twice.
    def height(x: int, y: int) -> int:
        return 10 * x + 3 * y

    part = only_part(place_one(loc(width=3, length=2), 10, rotation=0, height=height))
    columns, rows = (6, 7), (8, 8)
    expected = sum(height(x, y) for x in columns for y in rows) >> 2
    assert part.location[2] == pytest.approx(-expected)
    turned = only_part(place_one(loc(width=3, length=2), 10, rotation=1, height=height))
    # Rotation 1 swaps the sides: width 2 and length 3, columns x + 1 twice and rows y + 1 and y + 2.
    columns, rows = (6, 6), (8, 9)
    expected = sum(height(x, y) for x in columns for y in rows) >> 2
    assert turned.location[2] == pytest.approx(-expected)


def test_the_height_of_a_type_9_object_uses_its_whole_footprint_though_it_takes_one_tile():
    # PacketBuffer.java lines 169 to 200 use the loc's width and length for every type, and line 393 places type 9 on
    # one tile.
    def height(x: int, y: int) -> int:
        return 10 * x

    part = only_part(place_one(typed(9, width=3), 9, height=height))
    assert part.location[2] == pytest.approx(-((10 * 6 + 10 * 7) * 2 >> 2))


def test_a_mirrored_loc_has_a_scale_of_minus_1_on_the_axis_that_the_client_negates():
    # ModelData.method2633 (lines 1380 to 1390) negates vertexZ, which is Blender y.
    part = only_part(place_one(loc(mirrored=True), 10))
    assert part.model.mirrored
    assert part.scale == (1, -1, 1)


def test_a_scaled_loc_with_an_offset_has_that_scale_and_an_offset_that_the_rotation_does_not_turn():
    # ObjectComposition.java lines 786 to 819: the rotation turns the model first (lines 792 to 797), then the scale
    # applies to the turned model (ModelData.method2674, lines 1396 to 1404, called on line 814), then the offset is added
    # (method2630, lines 1346 to 1353, called on line 818). The scale is in the client's x, height and z. A scale on x and z of a model that
    # is turned a quarter acts on the other axis, so Blender sees the sides swapped.
    definition = loc(scale=(64, 256, 192), offset=(10, 20, 30))
    part = only_part(place_one(definition, 10, rotation=1))
    assert part.rotation == pytest.approx(QUARTER)
    assert part.scale == pytest.approx((192 / 128, 64 / 128, 256 / 128))
    # The offset is client (10, 20, 30), Blender (10, 30, -20), and the rotation does not turn it.
    assert part.location == pytest.approx((5 * 128 + 64 + 10, 7 * 128 + 64 + 30, -20))


def test_a_scale_acts_on_the_same_axes_for_a_quarter_turn_of_3_and_for_none():
    definition = loc(scale=(64, 128, 192))
    straight = only_part(place_one(definition, 10, rotation=0))
    assert straight.scale == pytest.approx((64 / 128, 192 / 128, 1))
    three = only_part(place_one(definition, 10, rotation=3))
    assert three.scale == pytest.approx((192 / 128, 64 / 128, 1))
    two = only_part(place_one(definition, 10, rotation=2))
    assert two.scale == pytest.approx((64 / 128, 192 / 128, 1))


def test_an_impostor_with_a_scale_scales_the_placement_of_the_loc_that_it_shows():
    # Loc 26813 shows loc 26797 for value 0 (ObjectComposition.java lines 830 to 845), whose model size is 78 in all
    # three axes in RuneLite's ObjectLoader (tests/fixtures/region/locs.json). The footprint and the height still come
    # from the placed loc, 26813 (PacketBuffer.java lines 169 to 200, DynamicObject lines 129 to 133).
    shown = LOCS[26797]
    assert shown.scale == (78, 78, 78)
    placed = place_scenery([at(26813, 10, x=24, y=44)], LOCS, flat)[0]
    part = only_part(placed)
    assert part.scale == pytest.approx((78 / 128, 78 / 128, 78 / 128))
    placed_width, placed_length = LOCS[26813].width, LOCS[26813].length
    assert part.location[:2] == pytest.approx((24 * 128 + placed_width * 64, 44 * 128 + placed_length * 64))


def test_an_impostor_takes_the_footprint_and_the_height_of_the_placed_loc_not_of_the_shown_one():
    # DynamicObject lines 129 to 133 take the model of the shown loc, while PacketBuffer.java lines 169 to 200 read the
    # width and the length of the loc that the landscape names. Loc 1 is 3 by 2 and shows loc 2, which is 1 by 1.
    locs = {1: loc(width=3, length=2, impostors=(2, 5), impostor_varbit=3), 2: loc(width=1, length=1)}

    def height(x: int, y: int) -> int:
        return 10 * x + 3 * y

    part = only_part(place_scenery([at(1, 10)], locs, height)[0])
    assert part.location[:2] == pytest.approx((5 * 128 + 3 * 64, 7 * 128 + 2 * 64))
    columns, rows = (6, 7), (8, 8)
    assert part.location[2] == pytest.approx(-(sum(height(x, y) for x in columns for y in rows) >> 2))


@pytest.mark.parametrize(
    "no_model_wall",
    [
        loc(models=(), animation=5, decor_displacement=48),
        loc(models=(), impostors=(-1,), impostor_varbit=3, decor_displacement=48),
    ],
    ids=["animated", "impostors"],
)
def test_an_animated_or_impostor_wall_without_a_model_still_replaces_the_wall_of_its_tile(no_model_wall):
    # PacketBuffer.java lines 270 to 281: an animated loc or a loc with impostors is a DynamicObject, which is not null,
    # so Region.addBoundary (lines 420 to 440) stores it and the decoration reads its displacement.
    locs = {1: loc(decor_displacement=32), 2: no_model_wall, 3: typed(4)}
    placed = place_scenery([at(1, 0), at(2, 0), at(3, 5, rotation=0)], locs, flat)
    assert placed[1].parts == ()
    assert only_part(placed[2]).location == pytest.approx((5 * 128 + 64 + 48, 7 * 128 + 64, 0))


@pytest.mark.parametrize("loc_type", [2, 8])
def test_a_wall_of_type_2_and_a_decoration_of_type_8_have_no_parts_when_the_loc_has_no_model_for_them(loc_type):
    # ObjectComposition.java lines 694 to 751 decide on the loc type only, and both calls of the placement have the same
    # type (2, or 4 for a decoration), so the two models are both present or both missing.
    assert place_one(typed(0), loc_type).parts == ()


def test_a_loc_type_above_22_in_a_placement_is_refused_even_when_the_loc_has_no_model():
    with pytest.raises(ValueError, match="loc type"):
        place_one(typed(0), 23)


def test_a_placement_that_names_an_unknown_loc_is_refused_with_its_tile():
    with pytest.raises(ValueError, match=r"\(5, 7\).*loc 99"):
        place_scenery([at(99, 0)], {1: typed(0)}, flat)


def test_an_impostor_that_shows_nothing_gives_no_parts():
    definition = loc(impostors=(-1, 5), impostor_varbit=3)
    assert place_one(definition, 10).parts == ()


def test_a_placement_with_an_animated_loc_is_placed_like_any_other():
    assert only_part(place_one(loc(animation=7), 10)).location == pytest.approx((5 * 128 + 64, 7 * 128 + 64, 0))


def test_a_diagonal_wall_decoration_turns_by_256_units_more_and_moves_by_45_0_minus_45():
    # ObjectComposition.java lines 787 to 790: for type 4 with a rotation above 3 the model turns 256 units and moves
    # by (45, 0, -45) before the quarter turn. In Blender the move is (45, -45, 0).
    part = only_part(place_one(typed(4), 7, rotation=0))
    assert (part.model_type, part.model_rotation) == (4, 6)
    assert part.rotation == pytest.approx(2 * QUARTER + 256 * UNIT)
    own = _rotated_quarters((45, -45), 2)
    assert part.location[:2] == pytest.approx((5 * 128 + 64 + own[0], 7 * 128 + 64 + own[1]))


def test_a_diagonal_wall_decoration_of_a_loc_with_the_same_x_and_z_scale_keeps_a_plain_transform():
    # The scale applies after the turn (lines 792 to 814) and an equal scale on x and z commutes with the turn.
    # The move of 45, 0, -45 is scaled with the model.
    definition = typed(4, scale=(64, 200, 64))
    part = only_part(place_one(definition, 7, rotation=0))
    assert not part.own_mesh
    # The model for rotation 6 is mirrored (lines 753 and 1380), so y is negative.
    assert part.scale == pytest.approx((0.5, -0.5, 200 / 128))
    own = _rotated_quarters((45, -45), 2)
    assert part.location[:2] == pytest.approx((5 * 128 + 64 + 0.5 * own[0], 7 * 128 + 64 + 0.5 * own[1]))


def test_a_diagonal_wall_decoration_of_a_loc_with_different_x_and_z_scales_is_marked_for_its_own_mesh():
    # The scale of line 814 acts on the model after the turn of 256 units, so x and z scales that differ shear
    # it, which a location, a rotation and a scale cannot hold.
    definition = typed(4, scale=(64, 128, 192))
    part = only_part(place_one(definition, 7, rotation=0))
    assert part.own_mesh
    assert part.rotation is None
    assert part.scale is None


def test_a_loc_with_different_x_and_z_scales_that_is_not_diagonal_is_not_marked():
    part = only_part(place_one(typed(4, scale=(64, 128, 192)), 4, rotation=0))
    assert not part.own_mesh
    assert part.rotation is not None


def _client_point(
    vertex: tuple[float, float, float],
    part: PlacedPart,
    definition: LocDefinition,
    orientation: int,
    position: tuple[float, float, float],
) -> tuple[float, float, float]:
    """One model vertex through the client's steps, written as they are in `ObjectComposition.java` lines 786 to 819,
    `ModelData` lines 1300 to 1404 and `Model.draw`, then turned into Blender axes."""

    def turn(x: float, z: float, units: int) -> tuple[float, float]:
        s, c = sin(radians(units * 360 / 2048)), cos(radians(units * 360 / 2048))
        return s * z + c * x, c * z - s * x

    x, y, z = vertex
    if part.model.mirrored:
        z = -z
    if part.model_type == 4 and part.model_rotation > 3:
        x, z = turn(x, z, 256)
        x, y, z = x + 45, y, z - 45
    quarters = part.model_rotation & 3
    for _ in range(quarters):
        x, z = z, -x
    sx, sy, sz = (value / 128 for value in definition.scale)
    x, y, z = x * sx, y * sy, z * sz
    ox, oy, oz = definition.offset
    x, y, z = x + ox, y + oy, z + oz
    x, z = turn(x, z, orientation)
    px, py, pz = position
    return x + px, z + pz, -(y + py)


@pytest.mark.parametrize("loc_type", [2, 4, 7, 10, 11])
@pytest.mark.parametrize("rotation", [0, 1, 2, 3])
@pytest.mark.parametrize("mirrored", [False, True])
def test_the_location_rotation_and_scale_give_the_vertices_that_the_client_steps_give(loc_type, rotation, mirrored):
    # Each vertex goes through the client's steps in order, and through the part's location, rotation and scale. Both
    # must land on the same Blender point. The scale has equal x and z, so that a diagonal decoration stays plain. Types
    # 2, 4, 7, 10 and 11 have no wall decoration offset, so the tile's middle is the position.
    definition = typed(
        {7: 4, 11: 10}.get(loc_type, loc_type), scale=(96, 200, 96), offset=(7, -9, 13), mirrored=mirrored
    )
    middle = (5 * 128 + 64, 0, 7 * 128 + 64)
    placed = place_one(definition, loc_type, rotation)
    orientation = 256 if loc_type == 11 else 0
    assert placed.parts
    for part in placed.parts:
        assert not part.own_mesh
        assert part.rotation is not None
        assert part.scale is not None
        for vertex in [(30, -50, 70), (-110, 20, 5), (0, 0, 0)]:
            expected = _client_point(vertex, part, definition, orientation, middle)
            x, y, z = vertex[0], vertex[2], -vertex[1]
            x, y, z = x * part.scale[0], y * part.scale[1], z * part.scale[2]
            c, s = cos(part.rotation), sin(part.rotation)
            got = (c * x - s * y + part.location[0], s * x + c * y + part.location[1], z + part.location[2])
            assert got == pytest.approx(expected, abs=1e-6)


def test_the_placements_come_out_in_the_order_of_the_landscape():
    locs = {1: typed(0), 2: typed(22), 3: typed(10)}
    placements = [at(3, 10, x=1), at(1, 0, x=2), at(2, 22, x=3)]
    placed = place_scenery(placements, locs, flat)
    assert [p.placement for p in placed] == placements


def test_a_placement_above_level_0_is_refused():
    with pytest.raises(ValueError, match="level"):
        place_scenery([Placement(loc=1, level=1, x=0, y=0, loc_type=10, rotation=0)], {1: loc()}, flat)


@pytest.mark.parametrize("rotation", [0, 1, 2, 3])
def test_the_linear_matrix_gives_the_vertices_that_the_client_steps_give_for_an_unequal_diagonal_scale(rotation):
    # The own mesh path uses `linear` alone, so it must match the client steps when no plain scale exists.
    definition = typed(4, scale=(64, 200, 192), offset=(7, -9, 13))
    part = only_part(place_one(definition, 7, rotation))
    assert part.own_mesh
    middle = (5 * 128 + 64, 0, 7 * 128 + 64)
    for vertex in [(30, -50, 70), (-110, 20, 5)]:
        expected = _client_point(vertex, part, definition, 0, middle)
        moved = tuple(
            sum(part.linear[i][k] * v for k, v in enumerate((vertex[0], vertex[2], -vertex[1]))) + part.location[i]
            for i in range(3)
        )
        assert moved == pytest.approx(expected, abs=1e-6)


def test_a_placement_with_a_rotation_above_3_is_refused():
    with pytest.raises(ValueError, match="rotation"):
        place_one(typed(4), 5, rotation=4)
