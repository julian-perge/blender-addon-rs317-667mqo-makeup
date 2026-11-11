#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/item_wear.json` from a recent OSRS cache and the snapshot 430 cache.

    uv run scripts/generate-item-wear.py --cache <openrs2-2757 folder> --snapshot <openrs2-430 folder>

Each folder is an OpenRS2 download with `metadata.json` and the disk cache in `cache/`. Snapshot 430 items carry no
wear positions (every one is -1), so they are read from the recent cache by item id, for every snapshot 430 item with
a worn model that the recent cache gives an equipment slot. Each item records whether its name or worn model ids
changed since snapshot 430. The research behind this is `docs/research/cache-2757-wear-positions.md`.

The item decoder follows RuneLite's ItemLoader at commit 8f2aca1 (cache/src/main/java/net/runelite/cache/definitions/
loaders/ItemLoader.java). An unknown opcode, or a definition whose bytes do not end right after its closing opcode 0,
stops the run, so a drifting parse cannot pass silently.
"""

import argparse
import bz2
import collections
import gzip
import hashlib
import json
import struct
from pathlib import Path

OUTPUT = Path(__file__).parent.parent / "src/rsps_toolkit/data/item_wear.json"
MODEL_KEYS = ("maleModel0", "maleModel1", "maleModel2", "femaleModel0", "femaleModel1", "femaleModel2")


class Store:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.data = (folder / "main_file_cache.dat2").read_bytes()

    def raw(self, index: int, group: int) -> bytes:
        entries = (self.folder / f"main_file_cache.idx{index}").read_bytes()
        size = int.from_bytes(entries[group * 6 : group * 6 + 3], "big")
        sector = int.from_bytes(entries[group * 6 + 3 : group * 6 + 6], "big")
        out = bytearray()
        head = 10 if group > 65535 else 8
        part = 0
        while len(out) < size:
            block = self.data[sector * 520 : sector * 520 + 520]
            stored_group = int.from_bytes(block[0 : head - 6], "big")
            stored_part = int.from_bytes(block[head - 6 : head - 4], "big")
            nxt = int.from_bytes(block[head - 4 : head - 1], "big")
            stored_index = block[head - 1]
            assert (stored_group, stored_part, stored_index) == (group, part, index), (stored_group, stored_part)
            out += block[head : head + min(size - len(out), 520 - head)]
            sector = nxt
            part += 1
        return bytes(out)

    def container(self, index: int, group: int) -> bytes:
        raw = self.raw(index, group)
        kind = raw[0]
        length = struct.unpack(">I", raw[1:5])[0]
        if kind == 0:
            return raw[5 : 5 + length]
        expanded = struct.unpack(">I", raw[5:9])[0]
        body = raw[9 : 9 + length]
        out = bz2.decompress(b"BZh1" + body) if kind == 1 else gzip.decompress(body)
        assert len(out) == expanded
        return out


class Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError("read past end")
        self.pos += n
        return self.data[self.pos - n : self.pos]

    def u8(self) -> int:
        return self.take(1)[0]

    def s8(self) -> int:
        return struct.unpack(">b", self.take(1))[0]

    def u16(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def s16(self) -> int:
        return struct.unpack(">h", self.take(2))[0]

    def u24(self) -> int:
        return int.from_bytes(self.take(3), "big")

    def s32(self) -> int:
        return struct.unpack(">i", self.take(4))[0]

    def s64(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def big_smart(self) -> int:
        if self.data[self.pos] & 0x80:
            return self.s32() & 0x7FFFFFFF
        return self.u16()

    def string(self) -> str:
        end = self.data.index(0, self.pos)
        text = self.data[self.pos : end].decode("cp1252", errors="replace")
        self.pos = end + 1
        return text


def reference_table(store: Store, index: int) -> dict[int, list[int]]:
    r = Reader(store.container(255, index))
    protocol = r.u8()
    if protocol >= 6:
        r.s32()
    flags = r.u8()
    count = r.big_smart() if protocol >= 7 else r.u16()
    read_id = r.big_smart if protocol >= 7 else r.u16
    ids, last = [], 0
    for _ in range(count):
        last += read_id()
        ids.append(last)
    if flags & 1:
        r.take(4 * count)
    r.take(4 * count)
    if flags & 8:
        r.take(4 * count)
    if flags & 2:
        r.take(64 * count)
    if flags & 4:
        r.take(8 * count)
    r.take(4 * count)
    counts = [read_id() for _ in range(count)]
    files = {}
    for group, n in zip(ids, counts, strict=True):
        last, out = 0, []
        for _ in range(n):
            last += read_id()
            out.append(last)
        files[group] = out
    return files


def split(data: bytes, ids: list[int]) -> dict[int, bytes]:
    if len(ids) == 1:
        return {ids[0]: data}
    chunks = data[-1]
    pos = len(data) - 1 - chunks * len(ids) * 4
    rows = []
    for _ in range(chunks):
        delta, row = 0, []
        for _ in ids:
            delta += struct.unpack(">i", data[pos : pos + 4])[0]
            pos += 4
            row.append(delta)
        rows.append(row)
    parts = [bytearray() for _ in ids]
    pos = 0
    for row in rows:
        for i, n in enumerate(row):
            parts[i] += data[pos : pos + n]
            pos += n
    return {fid: bytes(p) for fid, p in zip(ids, parts, strict=True)}


def decode(item_id: int, data: bytes, opcode_counts: collections.Counter) -> dict:
    d: dict = {
        "id": item_id,
        "name": "null",
        "wearPos1": -1,
        "wearPos2": -1,
        "wearPos3": -1,
        "maleModel0": -1,
        "maleModel1": -1,
        "maleModel2": -1,
        "femaleModel0": -1,
        "femaleModel1": -1,
        "femaleModel2": -1,
        "maleHeadModel": -1,
        "maleHeadModel2": -1,
        "femaleHeadModel": -1,
        "femaleHeadModel2": -1,
        "notedTemplate": -1,
        "placeholderTemplateId": -1,
        "boughtTemplateId": -1,
    }
    r = Reader(data)
    while True:
        op = r.u8()
        if op == 0:
            break
        opcode_counts[op] += 1
        if op in (1, 4, 5, 6, 7, 8, 94, 95, 97, 98, 99, 110, 111, 112, 139, 140, 148, 149):
            value = r.u16()
            names = {
                97: "notedID",
                98: "notedTemplate",
                139: "boughtId",
                140: "boughtTemplateId",
                148: "placeholderId",
                149: "placeholderTemplateId",
            }
            if op in names:
                d[names[op]] = value
        elif op in (2, 3, 9):
            text = r.string()
            if op == 2:
                d["name"] = text
        elif op in (11, 15, 16, 65, 160, 251):
            pass
        elif op == 12:
            r.s32()
        elif op == 13:
            d["wearPos1"] = r.s8()
        elif op == 14:
            d["wearPos2"] = r.s8()
        elif op == 27:
            d["wearPos3"] = r.s8()
        elif op == 23:
            d["maleModel0"] = r.u16()
            r.u8()
        elif op == 24:
            d["maleModel1"] = r.u16()
        elif op == 25:
            d["femaleModel0"] = r.u16()
            r.u8()
        elif op == 26:
            d["femaleModel1"] = r.u16()
        elif 30 <= op < 40:
            r.string()
        elif op in (40, 41):
            n = r.u8()
            r.take(4 * n)
        elif op == 42:
            r.s8()
        elif op == 43:
            r.u8()
            while r.u8() != 0:
                r.string()
        elif op == 44:
            r.s32()
        elif op == 45:
            d["maleModel0"] = r.s32()
            r.u8()
        elif op == 46:
            d["maleModel1"] = r.s32()
        elif op == 47:
            d["maleModel2"] = r.s32()
        elif op == 48:
            d["femaleModel0"] = r.s32()
            r.u8()
        elif op == 49:
            d["femaleModel1"] = r.s32()
        elif op == 50:
            d["femaleModel2"] = r.s32()
        elif op in (51, 52, 53, 54):
            d[{51: "maleHeadModel", 52: "maleHeadModel2", 53: "femaleHeadModel", 54: "femaleHeadModel2"}[op]] = r.s32()
        elif op == 75:
            r.s16()
        elif op == 78:
            d["maleModel2"] = r.u16()
        elif op == 79:
            d["femaleModel2"] = r.u16()
        elif op in (90, 91, 92, 93):
            d[{90: "maleHeadModel", 91: "femaleHeadModel", 92: "maleHeadModel2", 93: "femaleHeadModel2"}[op]] = r.u16()
        elif 100 <= op < 110:
            r.u16()
            r.u16()
        elif op in (113, 114):
            r.s8()
        elif op == 115:
            r.u8()
        elif op == 161:
            n = r.u16()
            r.take(2 * n)
        elif op == 200:
            r.u8()
            r.u8()
            r.string()
        elif op == 201:
            r.u8()
            r.u16()
            r.u16()
            r.s32()
            r.s32()
            r.string()
        elif op == 202:
            r.u8()
            r.u16()
            r.u16()
            r.u16()
            r.s32()
            r.s32()
            r.string()
        elif op == 249:
            for _ in range(r.u8()):
                kind = r.u8()
                r.u24()
                if kind == 1:
                    r.string()
                elif kind == 2:
                    r.s64()
                else:
                    r.s32()
        else:
            raise ValueError(f"item {item_id}: unknown opcode {op} at {r.pos - 1}")
    if r.pos != len(data):
        raise ValueError(f"item {item_id}: {len(data) - r.pos} bytes left after opcode 0")
    return d


def load_items(folder: Path) -> dict[int, dict]:
    store = Store(folder / "cache")
    files = reference_table(store, 2)[10]
    group = split(store.container(2, 10), files)
    counts: collections.Counter = collections.Counter()
    return {i: decode(i, group[i], counts) for i in sorted(group)}


def describe(folder: Path) -> dict:
    metadata = json.loads((folder / "metadata.json").read_text())
    return {
        "openrs2_id": metadata["id"],
        "build": metadata["builds"][0]["major"],
        "timestamp": metadata["timestamp"],
        "dat2_sha256": hashlib.sha256((folder / "cache/main_file_cache.dat2").read_bytes()).hexdigest(),
    }


def status(old: dict, new: dict) -> str:
    models_same = [old[k] for k in MODEL_KEYS] == [new[k] for k in MODEL_KEYS]
    if new["name"] != old["name"]:
        return "renamed" if models_same else "renamed_and_models_changed"
    return "match" if models_same else "models_changed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    new, old = load_items(args.cache), load_items(args.snapshot)
    rows = []
    for item_id, item in old.items():
        recent = new.get(item_id)
        if item["maleModel0"] == -1 and item["femaleModel0"] == -1 or recent is None or recent["wearPos1"] == -1:
            continue
        hides = sorted({recent["wearPos2"], recent["wearPos3"]} - {-1})
        entry = {"slot": recent["wearPos1"], "hides": hides, "status": status(item, recent)}
        rows.append(f'"{item_id}":{json.dumps(entry, separators=(",", ":"))}')
    header = {
        "source": "Item wear positions (opcodes 13, 14 and 27) of a recent OSRS cache, by item id",
        "cache": describe(args.cache),
        "snapshot": describe(args.snapshot),
        "generator": "scripts/generate-item-wear.py",
        "note": (
            "Slot numbers are the client's: 0 head, 1 cape, 2 neck, 3 weapon, 4 torso, 5 shield, 6 arms, 7 legs, "
            "8 hair, 9 hands, 10 feet, 11 jaw. slot is the item's wearPos1; hides lists its wearPos2 and wearPos3, "
            "the slots the game server empties while the item is worn. status compares the snapshot item with the "
            "recent one: match, renamed, models_changed or renamed_and_models_changed (worn model ids differ)."
        ),
    }
    lines = [f'"{key}":{json.dumps(value, separators=(",", ":"))},' for key, value in header.items()]
    args.output.write_text("{\n" + "\n".join(lines) + '\n"items":{\n' + ",\n".join(rows) + "\n}\n}\n")
    print(f"{len(rows)} items written to {args.output}")


if __name__ == "__main__":
    main()
