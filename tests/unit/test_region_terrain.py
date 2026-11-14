import gzip

import pytest
from js5_builder import REGION_FIXTURES, REGION_TERRAINS, build_region_cache

from rsps_toolkit.formats.js5 import Js5Store, unpack
from rsps_toolkit.formats.region import Tile, assemble_terrain, decode_terrain, load_terrain

NEIGHBOURS = [(x, y) for x in (47, 48, 49) for y in (49, 50, 51)]


def reference(x: int, y: int) -> dict[tuple[int, int, int], tuple[int, ...]]:
    """RuneLite's reading of region (x, y), written by the terrain mode of `tests/fixtures/RegionReference.java`, by
    level, x and y. Each value is the height, the settings, the underlay, the overlay, the overlay shape, the overlay
    rotation, and 1 when the group stores a height for the tile."""
    lines = gzip.decompress((REGION_FIXTURES / f"terrain-{x}_{y}.txt.gz").read_bytes()).decode().splitlines()
    assert len(lines) == 4 * 64 * 64
    keys = [(level, tx, ty) for level in range(4) for tx in range(64) for ty in range(64)]
    return {key: tuple(int(value) for value in line.split()) for key, line in zip(keys, lines, strict=True)}


def values(tile: Tile) -> tuple[int, ...]:
    return (tile.height, tile.settings, tile.underlay, tile.overlay, tile.overlay_shape, tile.overlay_rotation)


def region_tile(terrain, level: int, region: tuple[int, int], x: int, y: int) -> Tile:
    """Tile (x, y) of a region of the terrain, counted from that region's south-west corner."""
    return terrain.tile(level, (region[0] - terrain.x) * 64 + x, (region[1] - terrain.y) * 64 + y)


def test_every_tile_of_48_50_and_its_8_neighbours_on_every_level_equals_runelites_region_loader(tmp_path):
    build_region_cache(tmp_path)
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    assert terrain.missing == ()
    for region in NEIGHBOURS:
        expected = reference(*region)
        actual = {key: values(region_tile(terrain, key[0], region, key[1], key[2])) for key in expected}
        assert actual == {key: value[:6] for key, value in expected.items()}, region


def test_a_tile_with_no_stored_height_gets_the_height_of_the_runelite_reference(tmp_path):
    # Level 0 takes the client's noise at the tile's world position, and a level above takes 240 less than the level
    # below (SoundTaskDataProvider.java 64 to 69, Region.loadTerrain in RuneLite).
    build_region_cache(tmp_path)
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    checked = {0: 0, 1: 0}
    for region in NEIGHBOURS:
        for (level, x, y), value in reference(*region).items():
            if value[6] == 0:
                assert region_tile(terrain, level, region, x, y).height == value[0], (region, level, x, y)
                checked[min(level, 1)] += 1
    assert checked[0] > 1000
    assert checked[1] > 1000


def test_a_missing_west_neighbour_copies_the_heights_next_to_its_edges_as_the_client_does(tmp_path):
    # CombatInfo1.java 65 to 89 runs over 65 by 65 tiles: the missing region 47_50 and one more column and row. On level 0
    # it copies the height of the tile outside each edge: lines 74 to 76 for the column east of the region (x 0 of 48_50
    # takes x 1), lines 78 to 80 for its south row (from y 63 of 47_49), and lines 82 to 84 for the row north of it (y 0
    # of 47_51 and 48_51 takes y 1). At tile (0, 64) both lines 74 and 82 apply, and the later line wins. The tiles below
    # have heights that differ from the heights that a missing rule would leave.
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m47_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    centre, north = reference(48, 50), reference(48, 51)
    west_south, west_north = reference(47, 49), reference(47, 51)

    assert terrain.missing == ((47, 50),)
    for y in range(1, 64):
        assert terrain.tile(0, 0, y).height == centre[(0, 1, y)][0], y
    assert len({north[(0, 0, 0)][0], north[(0, 1, 0)][0], north[(0, 0, 1)][0]}) == 3
    assert terrain.tile(0, 0, 64).height == north[(0, 0, 1)][0]
    assert west_south[(0, 4, 63)][0] != 0
    assert terrain.tile(0, -60, 0).height == west_south[(0, 4, 63)][0]
    assert west_north[(0, 16, 0)][0] != west_north[(0, 16, 1)][0]
    assert terrain.tile(0, -48, 64).height == west_north[(0, 16, 1)][0]


def test_a_missing_east_neighbour_gives_its_west_column_the_heights_west_of_it(tmp_path):
    # CombatInfo1.java 70 to 72: x 0 of the missing region 49_50 takes the height of x 63 of 48_50.
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m49_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    centre = reference(48, 50)
    assert terrain.missing == ((49, 50),)
    assert centre[(0, 63, 4)][0] != 0
    for y in range(1, 64):
        assert terrain.tile(0, 64, y).height == centre[(0, 63, y)][0], y


def test_a_missing_neighbour_on_the_edge_of_the_9_regions_copies_nothing_from_beyond_them(tmp_path):
    # The client's bound is the edge of its scene (CombatInfo1.java 70, `var5 > 0`). Here the edge is the west side of the
    # 9 regions, so x -64 of the missing region 47_50 keeps height 0 and does not take a height from the east side.
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m47_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    assert reference(49, 50)[(0, 63, 30)][0] != 0
    assert terrain.tile(0, -64, 30).height == 0


def test_a_missing_neighbour_changes_no_level_above_0_and_nothing_but_the_height(tmp_path):
    # CombatInfo1.java 70 to 84 writes only tileHeights[0], and line 69 writes the loc shadow, which the terrain does
    # not hold.
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m47_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    centre = reference(48, 50)
    for level in range(4):
        tile = values(terrain.tile(level, 0, 10))
        expected = centre[(level, 0, 10)][:6]
        assert tile[1:] == expected[1:]
        if level > 0:
            assert tile[0] == expected[0]


def test_the_inner_tiles_of_a_missing_neighbour_have_height_0_and_no_underlay_or_overlay(tmp_path):
    # The client never writes the heights inside a missing region, and tileHeights is a Java array that starts at 0
    # (class50.java line 64); the owner chose this first-scene value on 2026-11-14 (issue 37). The underlays, overlays,
    # shapes and rotations are new arrays for each scene (class173.java 39 to 42), and the settings are set to 0
    # (Client.java 1700 to 1706).
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m47_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    for level in range(4):
        assert terrain.tile(level, -30, 30) == Tile(0, 0, 0, 0, 0, 0)


def test_a_missing_neighbour_of_a_region_with_y_100_or_more_changes_no_tile_next_to_it():
    # Client.java 1740 runs CombatInfo1.method1601 only while class54.field495 < 800. field495 is the y of the scene
    # centre in 8-tile chunks (ClanMemberManager.java 277 to 285), so a region with y 100 or more never gets the copies.
    # The groups of 48_50 and its neighbours stand in for region 48_100 and its neighbours. A stored height does not
    # depend on the world position, so the RuneLite reference still gives it.
    groups = {
        (x, y + 50): None if (x, y) == (47, 50) else unpack((REGION_FIXTURES / f"m{x}_{y}.dat").read_bytes())
        for x, y in NEIGHBOURS
    }
    terrain = assemble_terrain(48, 100, groups)
    centre = reference(48, 50)
    stored = [y for y in range(64) if centre[(0, 0, y)][6] == 1]

    assert terrain.missing == ((47, 100),)
    assert any(centre[(0, 0, y)][0] != centre[(0, 1, y)][0] for y in stored)
    for y in stored:
        assert terrain.tile(0, 0, y).height == centre[(0, 0, y)][0], y
    assert terrain.tile(0, -30, 30) == Tile(0, 0, 0, 0, 0, 0)


def test_a_region_whose_terrain_group_is_missing_is_handled_like_a_missing_neighbour(tmp_path):
    # The client runs the same rule for every region of its scene (Client.java 1735 to 1743), the centre one included.
    build_region_cache(tmp_path, tuple(name for name in REGION_TERRAINS if name != "m48_50"))
    terrain = load_terrain(Js5Store(tmp_path), 48, 50)
    assert terrain.missing == ((48, 50),)
    assert terrain.tile(0, 30, 30) == Tile(0, 0, 0, 0, 0, 0)


@pytest.mark.parametrize("x, y", [(-65, 0), (128, 0), (0, -65), (0, 128)])
def test_a_tile_outside_the_region_and_its_neighbours_is_an_error(x, y):
    terrain = assemble_terrain(48, 50, dict.fromkeys(NEIGHBOURS))
    with pytest.raises(IndexError):
        terrain.tile(0, x, y)


def test_a_terrain_that_ends_before_its_last_tile_is_an_error():
    # The client reads 4 levels of 64 by 64 records (Client.java 1826 to 1833), and a record of one byte 0 is the shortest.
    with pytest.raises(ValueError, match="ends early"):
        decode_terrain(bytes(4 * 64 * 64 - 1), 48, 50)
