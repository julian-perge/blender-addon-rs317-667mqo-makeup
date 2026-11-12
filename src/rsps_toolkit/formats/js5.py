"""Reads groups and files out of a js5 disk cache: `main_file_cache.dat2` and its `main_file_cache.idx<n>` files.

Nothing here imports bpy. The layout follows RuneLite's cache library (`DiskStorage`, `Container` and `IndexData` in
`net.runelite.cache.fs.jagex`). Each read seeks to the group's sectors, so the 54 MB data file is never loaded whole.
Encrypted groups (map landscapes) are not supported; frames, frame maps and configs are not encrypted.
"""

import bz2
import gzip
import struct
from pathlib import Path

SECTOR_SIZE = 520
REFERENCE_INDEX = 255
DATA_FILE = "main_file_cache.dat2"


class NotInCacheError(LookupError):
    """The cache has no such group, or its group has no such file."""


class Js5Store:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        if not (folder / DATA_FILE).is_file():
            raise FileNotFoundError(f"{folder} holds no {DATA_FILE}; choose the cache folder of an OpenRS2 download")
        self._tables: dict[int, dict[int, tuple[int, ...]]] = {}

    def raw(self, index: int, group: int) -> bytes:
        """The group's stored bytes, still compressed, gathered from its chain of sectors."""
        index_path = self.folder / f"main_file_cache.idx{index}"
        if not index_path.is_file():
            raise FileNotFoundError(f"The cache has no index {index}: {index_path}")
        with index_path.open("rb") as entries:
            entries.seek(group * 6)
            entry = entries.read(6)
        size = int.from_bytes(entry[0:3], "big") if len(entry) == 6 else 0
        if size == 0:
            raise NotInCacheError(f"Index {index} of the cache has no group {group}")
        sector = int.from_bytes(entry[3:6], "big")
        head = 10 if group > 0xFFFF else 8
        out = bytearray()
        with (self.folder / DATA_FILE).open("rb") as data:
            part = 0
            while len(out) < size:
                data.seek(sector * SECTOR_SIZE)
                block = data.read(SECTOR_SIZE)
                stored = (
                    int.from_bytes(block[0 : head - 6], "big"),
                    int.from_bytes(block[head - 6 : head - 4], "big"),
                    block[head - 1] if len(block) >= head else -1,
                )
                if stored != (group, part, index):
                    raise ValueError(f"Sector {sector} of the cache does not continue group {group} of index {index}")
                out += block[head : head + min(size - len(out), SECTOR_SIZE - head)]
                sector = int.from_bytes(block[head - 4 : head - 1], "big")
                part += 1
        return bytes(out)

    def container(self, index: int, group: int) -> bytes:
        """The group's bytes, decompressed."""
        return unpack(self.raw(index, group))

    def groups(self, index: int) -> dict[int, tuple[int, ...]]:
        """Every group of an index with its file ids, from the index's reference table, read once."""
        if index not in self._tables:
            self._tables[index] = reference_table(self.container(REFERENCE_INDEX, index))
        return self._tables[index]

    def files(self, index: int, group: int) -> dict[int, bytes]:
        """The files of one group, by file id."""
        ids = self.groups(index).get(group)
        if ids is None:
            raise NotInCacheError(f"Index {index} of the cache has no group {group}")
        return split(self.container(index, group), ids)


def unpack(raw: bytes) -> bytes:
    """Decompress a container: kind 0 is stored, 1 is bzip2 without its header, 2 is gzip."""
    kind = raw[0]
    length = struct.unpack(">I", raw[1:5])[0]
    if kind == 0:
        return raw[5 : 5 + length]
    expanded = struct.unpack(">I", raw[5:9])[0]
    body = raw[9 : 9 + length]
    if kind == 1:
        out = bz2.decompress(b"BZh1" + body)
    elif kind == 2:
        out = gzip.decompress(body)
    else:
        raise ValueError(f"Unknown container compression {kind}")
    if len(out) != expanded:
        raise ValueError(f"A container expanded to {len(out)} bytes, its header says {expanded}")
    return out


def reference_table(data: bytes) -> dict[int, tuple[int, ...]]:
    """Group ids with their file ids, from an index's reference table. Name hashes and checksums are skipped."""
    pos = 0

    def take(count: int) -> bytes:
        nonlocal pos
        if pos + count > len(data):
            raise ValueError("The reference table ends early")
        pos += count
        return data[pos - count : pos]

    def number(smart: bool) -> int:
        if smart and data[pos] & 0x80:
            return int.from_bytes(take(4), "big") & 0x7FFFFFFF
        return int.from_bytes(take(2), "big")

    protocol = take(1)[0]
    if protocol >= 6:
        take(4)
    flags = take(1)[0]
    smart = protocol >= 7
    count = number(smart)
    ids, last = [], 0
    for _ in range(count):
        last += number(smart)
        ids.append(last)
    for flag, width in ((1, 4), (0, 4), (8, 4), (2, 64), (4, 8), (0, 4)):
        if flag == 0 or flags & flag:
            take(width * count)
    counts = [number(smart) for _ in range(count)]
    table = {}
    for group, files in zip(ids, counts, strict=True):
        last, out = 0, []
        for _ in range(files):
            last += number(smart)
            out.append(last)
        table[group] = tuple(out)
    return table


def split(data: bytes, ids: tuple[int, ...]) -> dict[int, bytes]:
    """Split a group into its files. A group of several files ends with a table of chunk sizes and a chunk count."""
    if len(ids) == 1:
        return {ids[0]: data}
    chunks = data[-1]
    pos = len(data) - 1 - chunks * len(ids) * 4
    if pos < 0:
        raise ValueError("A group's chunk table is longer than the group")
    sizes = []
    for _ in range(chunks):
        delta, row = 0, []
        for _ in ids:
            delta += struct.unpack(">i", data[pos : pos + 4])[0]
            pos += 4
            row.append(delta)
        sizes.append(row)
    parts = [bytearray() for _ in ids]
    pos = 0
    for row in sizes:
        for i, size in enumerate(row):
            parts[i] += data[pos : pos + size]
            pos += size
    return {file: bytes(part) for file, part in zip(ids, parts, strict=True)}
