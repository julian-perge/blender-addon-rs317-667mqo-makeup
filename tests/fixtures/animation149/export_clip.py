#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# ///
"""Exports the raw frame data of one OSRS sequence from a js5 disk cache, for the revision-149 pose reference.

Reads main_file_cache.dat2 and the idx files (never writes to them). Writes decompressed file bytes: the sequence file
as the dumper wrote it, one file per frame of the sequence, one file per frame map those frames use, and a manifest
with SHA-256 hashes. Index 0 holds frame groups, index 1 holds frame maps.

Usage: export_clip.py --cache <cache folder> --sequence <sequence .dat> --output <folder>
"""

import argparse
import bz2
import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

# The sequence decoder of the add-on itself, which tests/unit/test_frames.py checks against the revision-149 client.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from rsps_toolkit.animation.frames import decode_sequence  # noqa: E402


class Store:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.data = (folder / "main_file_cache.dat2").read_bytes()

    def raw(self, index: int, group: int) -> bytes:
        entries = (self.folder / f"main_file_cache.idx{index}").read_bytes()
        size = int.from_bytes(entries[group * 6 : group * 6 + 3], "big")
        sector = int.from_bytes(entries[group * 6 + 3 : group * 6 + 6], "big")
        out = bytearray()
        while len(out) < size:
            offset = sector * 520
            wide = group > 65535
            head = 10 if wide else 8
            block = self.data[offset : offset + 520]
            body = block[head : head + min(size - len(out), 520 - head)]
            out += body
            nxt = int.from_bytes(block[head - 4 : head - 1], "big")
            sector = nxt
        return bytes(out)

    def container(self, index: int, group: int) -> bytes:
        return unpack(self.raw(index, group))


def unpack(raw: bytes) -> bytes:
    kind = raw[0]
    length = struct.unpack(">I", raw[1:5])[0]
    if kind == 0:
        return raw[5 : 5 + length]
    expanded = struct.unpack(">I", raw[5:9])[0]
    body = raw[9 : 9 + length]
    out = bz2.decompress(b"BZh1" + body) if kind == 1 else gzip.decompress(body)
    assert len(out) == expanded, (len(out), expanded)
    return out


def reference_table(store: Store, index: int) -> dict[int, list[int]]:
    """Group id to its file ids (named-index hashes are skipped)."""
    data = store.container(255, index)
    pos = 0

    def u8():
        nonlocal pos
        pos += 1
        return data[pos - 1]

    def u16():
        nonlocal pos
        pos += 2
        return int.from_bytes(data[pos - 2 : pos], "big")

    def u32():
        nonlocal pos
        pos += 4
        return int.from_bytes(data[pos - 4 : pos], "big")

    protocol = u8()
    if protocol >= 6:
        u32()
    flags = u8()
    count = u16() if protocol < 7 else None
    assert count is not None
    ids, last = [], 0
    for _ in range(count):
        last += u16()
        ids.append(last)
    if flags & 1:
        pos += 4 * count  # name hashes
    pos += 4 * count  # crcs
    if flags & 8:
        pos += 4 * count  # hashes
    if flags & 2:
        pos += 64 * count  # whirlpool digests
    if flags & 4:
        pos += 8 * count  # compressed and uncompressed sizes
    pos += 4 * count  # revisions
    file_counts = [u16() for _ in range(count)]
    files = {}
    for group, n in zip(ids, file_counts, strict=True):
        last, out = 0, []
        for _ in range(n):
            last += u16()
            out.append(last)
        files[group] = out
    return files


def split(data: bytes, ids: list[int]) -> dict[int, bytes]:
    """Split a group into its files (the format of the trailing chunk table)."""
    if len(ids) == 1:
        return {ids[0]: data}
    chunks = data[-1]
    table = len(data) - 1 - chunks * len(ids) * 4
    pos = table
    per_chunk = []
    for _ in range(chunks):
        delta = 0
        row = []
        for _ in range(len(ids)):
            delta += struct.unpack(">i", data[pos : pos + 4])[0]
            pos += 4
            row.append(delta)
        per_chunk.append(row)
    parts = [bytearray() for _ in ids]
    pos = 0
    for row in per_chunk:
        for i, n in enumerate(row):
            parts[i] += data[pos : pos + n]
            pos += n
    return {fid: bytes(p) for fid, p in zip(ids, parts, strict=True)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    store = Store(args.cache)
    sequence = args.sequence.read_bytes()
    decoded = decode_sequence(sequence)
    frames, durations = list(decoded.frames), list(decoded.durations)
    frame_files = reference_table(store, 0)
    map_files = reference_table(store, 1)
    out = args.output
    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "maps").mkdir(exist_ok=True)
    (out / "sequence.dat").write_bytes(sequence)
    manifest = {
        "sequence": int(args.sequence.stem),
        "source_cache_dat2_sha256": hashlib.sha256(store.data).hexdigest(),
        "sequence_sha256": hashlib.sha256(sequence).hexdigest(),
        "durations": durations,
        "frames": [],
        "maps": {},
    }
    cache: dict[int, dict[int, bytes]] = {}
    for group, file in frames:
        if group not in cache:
            cache[group] = split(store.container(0, group), frame_files[group])
        data = cache[group][file]
        name = f"{group}_{file}.dat"
        (out / "frames" / name).write_bytes(data)
        map_id = int.from_bytes(data[0:2], "big")
        manifest["frames"].append(
            {"group": group, "file": file, "map": map_id, "sha256": hashlib.sha256(data).hexdigest()}
        )
        if map_id not in manifest["maps"]:
            parts = split(store.container(1, map_id), map_files[map_id])
            blob = parts[0]
            (out / "maps" / f"{map_id}.dat").write_bytes(blob)
            manifest["maps"][map_id] = hashlib.sha256(blob).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(frames)} frames, {len(manifest['maps'])} frame maps -> {out}")


if __name__ == "__main__":
    main()
