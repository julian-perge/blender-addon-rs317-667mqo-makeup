import gzip
import hashlib
import json
import os
import struct
from pathlib import Path

import pytest

from rsps_toolkit.formats.js5 import SECTOR_SIZE, Js5Store, reference_table, split

SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
WALK = Path(__file__).parents[1] / "fixtures/animation149/walk"


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
    """Files joined into one chunk, followed by the chunk table of their sizes and a chunk count of 1."""
    sizes, last = b"", 0
    for data in files:
        sizes += struct.pack(">i", len(data) - last)
        last = len(data)
    return b"".join(files) + sizes + bytes([1])


def write_store(folder: Path, stored: dict[tuple[int, int], bytes]) -> None:
    """Write each (index, group) container into sectors, the second sector of a group placed after another group's."""
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


@pytest.fixture
def store(tmp_path):
    long_file = bytes(range(256)) * 5
    write_store(
        tmp_path,
        {
            (255, 0): container(table({3: (0,), 7: (2, 5)})),
            (0, 3): container(long_file),
            (0, 7): container(grouped([b"first", b"second!"]), kind=2),
        },
    )
    return Js5Store(tmp_path), long_file


def test_a_group_spread_over_sectors_is_read_whole(store):
    js5, long_file = store
    assert js5.container(0, 3) == long_file


def test_the_reference_table_lists_groups_and_their_files(store):
    js5, _ = store
    assert js5.groups(0) == {3: (0,), 7: (2, 5)}


def test_a_compressed_group_of_several_files_splits_by_its_chunk_table(store):
    js5, long_file = store
    assert js5.files(0, 7) == {2: b"first", 5: b"second!"}
    assert js5.files(0, 3) == {0: long_file}


def test_a_missing_group_or_folder_is_named(store, tmp_path):
    js5, _ = store
    with pytest.raises(LookupError, match="no group 4"):
        js5.container(0, 4)
    with pytest.raises(FileNotFoundError, match="main_file_cache.dat2"):
        Js5Store(tmp_path / "elsewhere")


def test_protocol_7_reference_tables_read_their_ids_as_smart_numbers():
    assert reference_table(table({1: (0, 4)}, protocol=7)) == {1: (0, 4)}


def test_split_refuses_a_chunk_table_longer_than_the_group():
    with pytest.raises(ValueError, match="chunk table"):
        split(b"\x05", (0, 1))


@pytest.mark.skipif(not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder")
def test_the_snapshot_430_walk_frames_map_and_sequence_match_the_fixture_hashes():
    js5 = Js5Store(SNAPSHOT_430)
    manifest = json.loads((WALK / "manifest.json").read_text())
    frames = js5.files(0, 207)
    for frame in manifest["frames"]:
        assert hashlib.sha256(frames[frame["file"]]).hexdigest() == frame["sha256"]
    assert js5.files(1, 0)[0] == (WALK / "maps/0.dat").read_bytes()
    assert hashlib.sha256(js5.files(2, 12)[819]).hexdigest() == manifest["sequence_sha256"]
