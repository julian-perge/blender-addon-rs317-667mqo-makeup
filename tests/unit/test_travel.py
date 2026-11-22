import pytest

from rsps_toolkit.formats.travel import RUN_FRAMES_PER_TILE, WALK_FRAMES_PER_TILE, travel_frames

TILE = 128  # A tile is 128 game units wide (GLOSSARY.md, Tile).


def test_a_walk_takes_30_frames_for_one_tile():
    # The owner states in issue 170 that a walk moves 1 tile in 0.6 seconds, and a clip plays at 50 frames in a second
    # (ADR 0035).
    assert WALK_FRAMES_PER_TILE == 0.6 * 50
    assert travel_frames([(0, 0, 0), (TILE, 0, 0)], 10, WALK_FRAMES_PER_TILE) == [10, 40]


def test_a_run_takes_15_frames_for_one_tile():
    # ADR 0035: a run moves 2 tiles in 0.6 seconds, which is general knowledge of the game and not checked in the
    # client.
    assert travel_frames([(0, 0, 0), (2 * TILE, 0, 0)], 0, RUN_FRAMES_PER_TILE) == [0, 30]


def test_the_walk_of_issue_170_over_3_tiles_takes_90_frames():
    assert travel_frames([(64, 64, 0), (64, 64 + 3 * TILE, -8)], 0, WALK_FRAMES_PER_TILE) == [0, 90]


def test_a_step_to_a_diagonal_tile_takes_the_time_of_a_straight_step():
    # ADR 0035: the time of a step comes from the longer of its x and y distances.
    assert travel_frames([(0, 0), (TILE, TILE), (3 * TILE, 2 * TILE)], 0, WALK_FRAMES_PER_TILE) == [0, 30, 90]


def test_each_point_gets_the_frame_after_the_steps_before_it_and_height_takes_no_time():
    points = [(0, 0, 0), (0, -TILE, 50), (TILE // 2, -TILE, 50), (TILE // 2, -TILE, 90)]
    assert travel_frames(points, -5, WALK_FRAMES_PER_TILE) == [-5, 25, 40, 40]


def test_a_part_of_a_frame_is_rounded_at_each_point_from_the_whole_distance():
    # 100 game units are 23.4375 frames, so two such steps end on frame 47, not on 23 + 23.
    assert travel_frames([(0, 0), (100, 0), (200, 0)], 0, WALK_FRAMES_PER_TILE) == [0, 23, 47]


@pytest.mark.parametrize("points", [[], [(0, 0, 0)]])
def test_fewer_than_two_points_are_refused(points):
    with pytest.raises(ValueError, match="at least two points"):
        travel_frames(points, 0, WALK_FRAMES_PER_TILE)
