"""Writes small js5 disk caches that `Js5Store` reads, so tests need no real cache."""

import gzip
import os
import struct
from collections.abc import Callable, Mapping
from pathlib import Path

from rsps_toolkit.formats.js5 import REFERENCE_INDEX, SECTOR_SIZE, Js5Store

CONFIG_INDEX, MODEL_INDEX = 2, 7
KIT_GROUP, ENUM_GROUP, ITEM_GROUP = 3, 8, 10


def container(data: bytes, kind: int = 0) -> bytes:
    if kind == 0:
        return bytes([0]) + struct.pack(">I", len(data)) + data
    body = gzip.compress(data)
    return bytes([2]) + struct.pack(">II", len(body), len(data)) + body


def table(groups: dict[int, tuple[int, ...]], protocol: int = 6) -> bytes:
    def number(value: int) -> bytes:
        return struct.pack(">H", value)

    out = bytes([protocol]) + (b"\0\0\0\1" if protocol >= 6 else b"") + bytes([0]) + number(len(groups))
    last = 0
    for group in groups:
        out += number(group - last)
        last = group
    out += b"\0" * 8 * len(groups)
    out += b"".join(number(len(files)) for files in groups.values())
    for files in groups.values():
        last = 0
        for file in files:
            out += number(file - last)
            last = file
    return out


def grouped(files: list[bytes]) -> bytes:
    """Join the files into one chunk, then add the table of their sizes and a chunk count of 1."""
    sizes, last = b"", 0
    for data in files:
        sizes += struct.pack(">i", len(data) - last)
        last = len(data)
    return b"".join(files) + sizes + bytes([1])


def write_store(folder: Path, stored: dict[tuple[int, int], bytes]) -> None:
    """Write each (index, group) container into its own run of sectors, one after another, after an empty sector 0."""
    sectors: list[bytes] = [b"\0" * SECTOR_SIZE]
    entries: dict[int, dict[int, bytes]] = {}
    for (index, group), data in stored.items():
        chunks = [data[i : i + SECTOR_SIZE - 8] for i in range(0, len(data), SECTOR_SIZE - 8)] or [b""]
        first = len(sectors)
        for part, chunk in enumerate(chunks):
            following = first + part + 1 if part + 1 < len(chunks) else 0
            head = struct.pack(">HH", group, part) + following.to_bytes(3, "big") + bytes([index])
            sectors.append((head + chunk).ljust(SECTOR_SIZE, b"\0"))
        entries.setdefault(index, {})[group] = len(data).to_bytes(3, "big") + first.to_bytes(3, "big")
    (folder / "main_file_cache.dat2").write_bytes(b"".join(sectors))
    for index, groups in entries.items():
        out = bytearray(6 * (max(groups) + 1))
        for group, entry in groups.items():
            out[group * 6 : group * 6 + 6] = entry
        (folder / f"main_file_cache.idx{index}").write_bytes(bytes(out))


def build_cache(
    folder: Path,
    *,
    models: Mapping[int, bytes] | None = None,
    kits: Mapping[int, bytes] | None = None,
    items: Mapping[int, bytes] | None = None,
    enums: Mapping[int, bytes] | None = None,
) -> None:
    """Write a disk cache that holds each model as file 0 of its own group in index 7. The kits, enums and items become
    config groups 3, 8 and 10 in index 2, and each definition's id is its file id. A config group with one file has no
    size table, as in a real cache. A group with no files is left out."""
    config = {
        group: dict(sorted(files.items()))
        for group, files in ((KIT_GROUP, kits), (ENUM_GROUP, enums), (ITEM_GROUP, items))
        if files
    }
    folder.mkdir(parents=True, exist_ok=True)
    models = dict(sorted((models or {}).items()))
    stored = {
        (REFERENCE_INDEX, CONFIG_INDEX): container(table({group: tuple(files) for group, files in config.items()})),
        (REFERENCE_INDEX, MODEL_INDEX): container(table({model: (0,) for model in models})),
    }
    for group, files in config.items():
        data = grouped(list(files.values())) if len(files) > 1 else next(iter(files.values()))
        stored[(CONFIG_INDEX, group)] = container(data, kind=2)
    for model, data in models.items():
        stored[(MODEL_INDEX, model)] = container(data, kind=2)
    write_store(folder, stored)


def read_cache(folder: Path) -> dict[str, dict[int, bytes]]:
    """Read back the models, kits, items and enums of a cache that `build_cache` wrote, as its keyword arguments."""
    store = Js5Store(folder)
    config = store.groups(CONFIG_INDEX)
    return {
        "models": {model: store.container(MODEL_INDEX, model) for model in store.groups(MODEL_INDEX)},
        **{
            name: store.files(CONFIG_INDEX, group) if group in config else {}
            for name, group in (("kits", KIT_GROUP), ("items", ITEM_GROUP), ("enums", ENUM_GROUP))
        },
    }


def rewrite_cache(folder: Path, change: Callable[[dict[str, dict[int, bytes]]], object]) -> None:
    """Write the cache again with `change` applied to what `read_cache` returns, as a new download of the cache would.
    Every file's modified time becomes a second later than before, so the test does not depend on the file system's
    clock resolution."""
    before = {path: path.stat().st_mtime_ns for path in folder.iterdir()}
    parts = read_cache(folder)
    change(parts)
    build_cache(folder, **parts)
    for path in folder.iterdir():
        time = before.get(path, path.stat().st_mtime_ns) + 1_000_000_000
        os.utime(path, ns=(time, time))
