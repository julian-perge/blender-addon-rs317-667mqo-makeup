"""Reads the placements of one region of a snapshot 430 cache: its keys, its landscape group and the landscape's records.

Nothing here imports bpy. A region is 64 by 64 tiles, named by its x and y numbers. Its landscape is the group `l<x>_<y>` of
index 5, which the cache stores encrypted with the region's four XTEA keys. The keys sit in `keys/<region id>.txt`, in the folder
next to the cache folder, as an OpenRS2 download lays it out (`GLOSSARY.md`, Landscape keys). The records are checked against
RuneLite's `LocationsLoader` in `tests/fixtures/region/landscape.json`.
"""

from dataclasses import dataclass
from pathlib import Path

from rsps_toolkit.formats.js5 import DecryptionError, Js5Store, Keys, unpack

MAP_INDEX = 5
KEYS_FOLDER = "keys"


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
    """The four numbers of a key file, one per line."""
    try:
        a, b, c, d = (int(line) for line in path.read_text().split())
    except ValueError as error:
        raise ValueError(f"{path} does not hold four whole numbers, one per line") from error
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
    stored = store.raw(MAP_INDEX, store.group_named(MAP_INDEX, f"l{x}_{y}"))
    try:
        data = unpack(stored, keys)
    except DecryptionError as error:
        raise ValueError(f"The key in {key_file} does not decrypt the landscape of region {x}_{y}") from error
    return Landscape(decode_landscape(data), has_key=True)


def decode_landscape(data: bytes) -> tuple[Placement, ...]:
    """The placements of a decompressed landscape, in the order of the file.

    A step of the loc id is an extended smart (`Buffer.java` 560 to 570, `Client.java` 1761 to 1801): each value of 32767 adds
    32767 and the next value ends the step. A step of the position is a smart (`Buffer.java` 550 to 552). A step of 0 ends a
    loc's list, and a loc id step of 0 ends the file. The position packs the level in bits 12 and 13, x in bits 6 to 11 and y in
    bits 0 to 5. The attribute byte packs the loc type in its upper 6 bits and the rotation in its lower 2.
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
                    level=position >> 12 & 3,
                    x=position >> 6 & 63,
                    y=position & 63,
                    loc_type=attributes >> 2,
                    rotation=attributes & 3,
                )
            )
    return tuple(placements)
