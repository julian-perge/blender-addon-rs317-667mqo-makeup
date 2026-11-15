"""Reads one region of a snapshot 430 cache: the terrain of the region and its 8 neighbours, and the placements of its landscape.

Nothing here imports bpy. A region is 64 by 64 tiles, named by its x and y numbers. Its terrain is the group `m<x>_<y>` of
index 5. Its landscape is the group `l<x>_<y>`, which the cache stores encrypted with the region's four XTEA keys. The keys sit
in `keys/<region id>.txt`, in the folder next to the cache folder, as an OpenRS2 download lays it out (`GLOSSARY.md`,
Landscape keys). The terrain records are checked against RuneLite 1.9.0's `MapLoader` and `Region.loadTerrain` in
`tests/fixtures/region/terrain-<x>_<y>.txt.gz`, and the placements against RuneLite's `LocationsLoader` in
`tests/fixtures/region/landscape.json`.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import cos
from pathlib import Path

from rsps_toolkit.formats.js5 import DecryptionError, Js5Store, Keys, NotInCacheError

MAP_INDEX = 5
KEYS_FOLDER = "keys"
KEY_LINE = re.compile(r"[+-]?[0-9]+")
INT32 = range(-(1 << 31), 1 << 31)
REGION_SIZE = 64
LEVELS = 4
AREA_SIZE = 3 * REGION_SIZE
LEVEL_STEP = 240
EDGE_COPY_REGION_Y_LIMIT = 100


@dataclass(frozen=True)
class Tile:
    """The terrain record of one tile on one level. Ids are as the cache stores them: 0 means none, and n means the
    definition n - 1. The client reads both ids with `& 255` (`class24.java` lines 187 to 188) and looks up definition
    n - 1 (`class24.java` lines 133 and 243)."""

    height: int
    """The height of the tile's south-west corner in game units, as the client stores it (`SoundTaskDataProvider.java` 64 to 80)."""
    settings: int
    underlay: int
    overlay: int
    overlay_shape: int
    overlay_rotation: int


EMPTY_TILE = Tile(0, 0, 0, 0, 0, 0)

type RegionTiles = tuple[tuple[tuple[Tile, ...], ...], ...]
"""The tiles of one region, indexed as `[level][x][y]`."""


@dataclass(frozen=True)
class Terrain:
    """The terrain of region (x, y), with the terrain of its 8 neighbours around it, so that the tiles at the region's edge
    have the heights and underlays beyond it (ADR 0023, Edges)."""

    x: int
    y: int
    tiles: tuple[tuple[tuple[Tile, ...], ...], ...]
    """The tiles indexed as `[level][x + 64][y + 64]`, so that the region's own tiles start at index 64."""
    missing: tuple[tuple[int, int], ...]
    """The regions, of these 9, whose terrain group the cache lacks, as (x, y) in the client's order: x first, then y
    (`ScriptEvent.java` lines 177 to 186). The client also gives their tile corners the loc shadow 127
    (`CombatInfo1.java` line 69), which the terrain light needs."""

    def tile(self, level: int, x: int, y: int) -> Tile:
        """Tile (x, y) of a level, counted from the south-west corner of region (x, y). A tile of a neighbour has an x or y
        from -64 to -1 or from 64 to 127."""
        column, row = x + REGION_SIZE, y + REGION_SIZE
        if not (0 <= column < AREA_SIZE and 0 <= row < AREA_SIZE):
            raise IndexError(f"Tile ({x}, {y}) is outside region {self.x}_{self.y} and its neighbours")
        return self.tiles[level][column][row]


@dataclass(frozen=True)
class Placement:
    """One loc standing on one tile. `x` and `y` count tiles from the south-west corner of the region, from 0 to 63."""

    loc: int
    level: int
    x: int
    y: int
    loc_type: int
    rotation: int


@dataclass(frozen=True)
class Landscape:
    placements: tuple[Placement, ...]
    """The placements in the order of the file. Empty when the region has no key file."""
    has_key: bool
    """False when the keys folder has no key file for the region, which the import reports."""


def region_id(x: int, y: int) -> int:
    """The number that names a region's key file. Region `48_50` is 12338."""
    return x * 256 + y


def read_keys(path: Path) -> Keys:
    """The four numbers of a key file, one per line. Each is a whole number that fits in 32 bits with its sign.

    `tests/fixtures/RegionReference.java` reads a key file with Java's `Integer.parseInt`, which takes the same numbers.
    """
    error = f"{path} does not hold four 32-bit whole numbers, one per line"
    try:
        lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    except UnicodeDecodeError as cause:
        raise ValueError(error) from cause
    if len(lines) != 4 or not all(KEY_LINE.fullmatch(line) and int(line) in INT32 for line in lines):
        raise ValueError(error)
    a, b, c, d = (int(line) for line in lines)
    return a, b, c, d


def load_landscape(store: Js5Store, x: int, y: int) -> Landscape:
    """The landscape of region (x, y). The keys come from `keys/<region id>.txt` next to the store's cache folder.

    A missing keys folder is an error that names the folder. A missing key file for the region gives no placements and
    `has_key` False. A key that does not decrypt the landscape is an error that names the key file.
    """
    keys_folder = store.folder.parent / KEYS_FOLDER
    if not keys_folder.is_dir():
        raise FileNotFoundError(
            f"The folder {keys_folder} holds no landscape keys; an OpenRS2 download has a keys folder next to its cache folder"
        )
    key_file = keys_folder / f"{region_id(x, y)}.txt"
    if not key_file.is_file():
        return Landscape((), has_key=False)
    keys = read_keys(key_file)
    group = store.group_named(MAP_INDEX, f"l{x}_{y}")
    try:
        data = store.container(MAP_INDEX, group, keys)
    except DecryptionError as error:
        raise ValueError(f"The key in {key_file} does not decrypt the landscape of region {x}_{y}") from error
    return Landscape(decode_landscape(data), has_key=True)


def decode_landscape(data: bytes) -> tuple[Placement, ...]:
    """The placements of a decompressed landscape, in the order of the file.

    A step of the loc id is an extended smart (`Buffer.java` 560 to 570, `Client.java` 1761 to 1801): each value of 32767 adds
    32767 and the next value ends the step. A step of the position is a smart (`Buffer.java` 550 to 552). A step of 0 ends a
    loc's list, and a loc id step of 0 ends the file. The position packs y in bits 0 to 5, x in bits 6 to 11 and the level in
    the bits from 12 up (`Client.java` 1780 to 1782). The level is not masked, as in the client. RuneLite's `LocationsLoader`
    masks it with 3, but no landscape of snapshot 430 has a level above 3. The attribute byte packs the loc type in its upper 6
    bits and the rotation in its lower 2.
    """
    pos = 0

    def take(count: int) -> bytes:
        nonlocal pos
        if pos + count > len(data):
            raise ValueError("The landscape ends early")
        pos += count
        return data[pos - count : pos]

    def smart() -> int:
        if pos < len(data) and data[pos] < 128:
            return take(1)[0]
        return int.from_bytes(take(2), "big") - 0x8000

    def extended_smart() -> int:
        total = 0
        value = smart()
        while value == 32767:
            total += 32767
            value = smart()
        return total + value

    placements = []
    loc = -1
    while step := extended_smart():
        loc += step
        position = 0
        while offset := smart():
            position += offset - 1
            attributes = take(1)[0]
            placements.append(
                Placement(
                    loc=loc,
                    level=position >> 12,
                    x=position >> 6 & 63,
                    y=position & 63,
                    loc_type=attributes >> 2,
                    rotation=attributes & 3,
                )
            )
    return tuple(placements)


def load_terrain(store: Js5Store, x: int, y: int) -> Terrain:
    """The terrain of region (x, y) and its 8 neighbours, read from the groups `m<x>_<y>` of index 5. A region whose group
    the cache lacks is handled as `assemble_terrain` says."""
    groups: dict[tuple[int, int], bytes | None] = {}
    for region_x in range(x - 1, x + 2):
        for region_y in range(y - 1, y + 2):
            try:
                groups[(region_x, region_y)] = store.container(
                    MAP_INDEX, store.group_named(MAP_INDEX, f"m{region_x}_{region_y}")
                )
            except NotInCacheError:
                groups[(region_x, region_y)] = None
    return assemble_terrain(x, y, groups)


def assemble_terrain(x: int, y: int, groups: Mapping[tuple[int, int], bytes | None]) -> Terrain:
    """The terrain of region (x, y) from the decompressed terrain groups of the region and its 8 neighbours, by region
    (x, y). A group of None is a region that the cache lacks.

    A missing region gets the tile `EMPTY_TILE` on every level. The client leaves its heights as they were (`tileHeights` is
    made once, `class50.java` line 64, and never cleared). The owner chose 0, the height of the first scene after the client
    starts, on 2026-11-14 (issue 37). The ids and settings are 0 because the client makes new id arrays for each scene
    (`class173.java` lines 39 to 42) and sets the settings to 0 (`Client.java` lines 1700 to 1706).

    When region y is less than 100, each missing region then copies level 0 heights at its edges
    (`CombatInfo1.java` lines 65 to 89). The client runs this only while the scene centre is below chunk y 800
    (`Client.java` line 1740, where `class54.field495` is the scene centre's y in 8-tile chunks, set at
    `ClanMemberManager.java` lines 277 to 285). The client's scene is 104 tiles wide, and these 9 regions are 192: the
    bounds of the copy here are the edges of the 192 tiles, which differ from the client's only more than 20 tiles away from
    region (x, y).
    """
    regions = [(region_x, region_y) for region_x in range(x - 1, x + 2) for region_y in range(y - 1, y + 2)]
    columns = [[[EMPTY_TILE] * AREA_SIZE for _ in range(AREA_SIZE)] for _ in range(LEVELS)]
    missing = []
    for region_x, region_y in regions:
        data = groups[(region_x, region_y)]
        if data is None:
            missing.append((region_x, region_y))
            continue
        tiles = decode_terrain(data, region_x, region_y)
        left, bottom = (region_x - x + 1) * REGION_SIZE, (region_y - y + 1) * REGION_SIZE
        for level in range(LEVELS):
            for tile_x in range(REGION_SIZE):
                columns[level][left + tile_x][bottom : bottom + REGION_SIZE] = tiles[level][tile_x]
    if y < EDGE_COPY_REGION_Y_LIMIT:
        for region_x, region_y in missing:
            copy_edge_heights(columns[0], (region_x - x + 1) * REGION_SIZE, (region_y - y + 1) * REGION_SIZE)
    return Terrain(
        x,
        y,
        tuple(tuple(tuple(column) for column in level) for level in columns),
        tuple(missing),
    )


def copy_edge_heights(level_0: list[list[Tile]], left: int, bottom: int) -> None:
    """`CombatInfo1.method1601` (lines 65 to 89) for the missing region whose south-west tile is (left, bottom) of the 192
    tiles. It goes over 65 by 65 tiles, the region and one more column and row. A tile on the west column takes the height
    of the tile west of it (lines 70 to 72), on the east column the height east of it (lines 74 to 76), on the south row the
    height south of it (lines 78 to 80), and on the north row the height north of it (lines 82 to 84). A later line wins at a
    corner. Every height that it reads lies outside the 65 by 65 tiles, so the order of the tiles does not matter."""
    last = AREA_SIZE - 1
    for row in range(bottom, bottom + REGION_SIZE + 1):
        for column in range(left, left + REGION_SIZE + 1):
            if not (0 <= column < AREA_SIZE and 0 <= row < AREA_SIZE):
                continue
            height = level_0[column][row].height
            if column == left and column > 0:
                height = level_0[column - 1][row].height
            if column == left + REGION_SIZE and column < last:
                height = level_0[column + 1][row].height
            if row == bottom and row > 0:
                height = level_0[column][row - 1].height
            if row == bottom + REGION_SIZE and row < last:
                height = level_0[column][row + 1].height
            level_0[column][row] = replace(level_0[column][row], height=height)


def decode_terrain(data: bytes, x: int, y: int) -> RegionTiles:
    """The tiles of the decompressed terrain group of region (x, y), as `loadTerrain` reads them
    (`SoundTaskDataProvider.java` lines 57 to 115). The records go by level, then x, then y. Each record is a list of
    opcode bytes:

    - 0 ends the record, and the tile has no stored height. On level 0 its height is the client's noise at the tile's world
      position, times -8 (line 66). On a level above it is the height below, less 240 (line 68).
    - 1 is followed by the height byte, and ends the record. A height byte of 1 means 0 (lines 74 to 77). On level 0 the
      height is the byte times -8 (line 80). On a level above it is the height below, less the byte times 8 (line 82).
    - 2 to 49 are followed by the overlay byte. The shape is (opcode - 2) / 4 and the rotation is (opcode - 2) & 3 (lines
      88 to 90).
    - 50 to 81 set the settings to opcode - 49 (line 92), and 82 to 255 set the underlay to opcode - 81 (line 94).
    """
    pos = 0

    def byte() -> int:
        nonlocal pos
        if pos >= len(data):
            raise ValueError(f"The terrain of region {x}_{y} ends early")
        pos += 1
        return data[pos - 1]

    levels: list[tuple[tuple[Tile, ...], ...]] = []
    below: tuple[tuple[Tile, ...], ...] | None = None
    for level in range(LEVELS):
        columns = []
        for tile_x in range(REGION_SIZE):
            column = []
            for tile_y in range(REGION_SIZE):
                settings = underlay = overlay = shape = rotation = 0
                while True:
                    opcode = byte()
                    if opcode == 0:
                        if below is None:
                            height = (
                                -terrain_noise(x * REGION_SIZE + tile_x + 932731, y * REGION_SIZE + tile_y + 556238) * 8
                            )
                        else:
                            height = below[tile_x][tile_y].height - LEVEL_STEP
                        break
                    if opcode == 1:
                        stored = byte()
                        stored = 0 if stored == 1 else stored
                        height = -stored * 8 if below is None else below[tile_x][tile_y].height - stored * 8
                        break
                    if opcode <= 49:
                        overlay = byte()
                        shape = (opcode - 2) // 4
                        rotation = (opcode - 2) & 3
                    elif opcode <= 81:
                        settings = opcode - 49
                    else:
                        underlay = opcode - 81
                column.append(Tile(height, settings, underlay, overlay, shape, rotation))
            columns.append(tuple(column))
        below = tuple(columns)
        levels.append(below)
    return tuple(levels)


def ground_height(terrain: Terrain, x: int, y: int) -> int:
    """The level 0 height in game units at the game point (x, y), counted from the south-west corner of the terrain's
    region, as `getTileHeight` blends the heights of the four corners of the point's tile (`class264.java` lines 96 to
    108).

    On a bridge tile the client reads the heights of level 1 instead (lines 99 to 101), which is the bridge. This function
    reads level 0 there, the ground under the bridge, because the import has no level 1 (spec 35, part 8).

    The point's tile and the tiles east and north of it must be in the region or its neighbours, or `Terrain.tile` raises
    `IndexError`.
    """
    tile_x, tile_y = x >> 7, y >> 7
    offset_x, offset_y = x & 127, y & 127

    def corner(dx: int, dy: int) -> int:
        return terrain.tile(0, tile_x + dx, tile_y + dy).height

    south = ((128 - offset_x) * corner(0, 0) + offset_x * corner(1, 0)) >> 7
    north = (corner(0, 1) * (128 - offset_x) + offset_x * corner(1, 1)) >> 7
    return (north * offset_y + south * (128 - offset_y)) >> 7


def terrain_noise(x: int, y: int) -> int:
    """The client's terrain noise at (x, y), from 10 to 60 (`class83.java` lines 107 to 117)."""
    value = (
        smooth_noise(x + 45365, y + 91923, 4)
        - 128
        + (smooth_noise(x + 10294, y + 37821, 2) - 128 >> 1)
        + (smooth_noise(x, y, 1) - 128 >> 2)
    )
    return min(max(int(0.3 * value) + 35, 10), 60)


def smooth_noise(x: int, y: int, scale: int) -> int:
    """`UnitPriceComparator.getSmoothNoise` (lines 45 to 57): the noise of the grid of `scale` tiles, blended between the 4
    grid points around (x, y). Its x and y are always positive here, so the division matches Java's."""
    grid_x, step_x = x // scale, x & scale - 1
    grid_y, step_y = y // scale, y & scale - 1
    south = blend(soft_noise(grid_x, grid_y), soft_noise(grid_x + 1, grid_y), step_x, scale)
    north = blend(soft_noise(grid_x, grid_y + 1), soft_noise(grid_x + 1, grid_y + 1), step_x, scale)
    return blend(south, north, step_y, scale)


def soft_noise(x: int, y: int) -> int:
    """`JagexGame.getSmoothNoise2D` (lines 71 to 76): the noise at (x, y) mixed with its 8 neighbours."""
    corners = noise(x - 1, y - 1) + noise(x + 1, y - 1) + noise(x - 1, y + 1) + noise(x + 1, y + 1)
    sides = noise(x - 1, y) + noise(x + 1, y) + noise(x, y - 1) + noise(x, y + 1)
    return corners // 16 + sides // 8 + noise(x, y) // 4


def noise(x: int, y: int) -> int:
    """`MapCacheArchiveNames.method518` (lines 60 to 65), from 0 to 255. The client works in 32-bit Java ints, which wrap."""
    value = to_int32(y * 57 + x)
    value = to_int32(value ^ value << 13)
    value = to_int32(value * to_int32(value * value * 15731 + 789221) + 1376312589) & 0x7FFFFFFF
    return value >> 19 & 255


def blend(start: int, end: int, step: int, scale: int) -> int:
    """`class158.method3316` (lines 71 to 74): a cosine blend from `start` to `end` at `step` of `scale`. The client's
    cosine table holds `65536 * cos(i * 0.0030679615)` as a whole number (`Graphics3D.java` line 98)."""
    weight = 65536 - int(65536.0 * cos(step * 1024 // scale * 0.0030679615)) >> 1
    return ((65536 - weight) * start >> 16) + (weight * end >> 16)


def to_int32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value >= 1 << 31 else value
