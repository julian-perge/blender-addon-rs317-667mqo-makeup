#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/npc_clips.json`: the attack, flinch and death clips of the NPCs that the AnotherScape
models mod lists and that fit snapshot 430.

    uv run scripts/generate-npc-clips.py --mod <AnotherScape models mod jar> --snapshot <openrs2-430 folder>

The jar holds a `source.json` for each model under `assets/anotherscape/meshsets/`. The rules are rules 1 to 10 of
`spec/160-npc-clips.md`, in that order, and the run prints how many records and clips each rule drops. The counts of
the Spec stage are in `docs/research/160-npc-clips.md`. NPCs and sequences are decoded by the add-on's own decoders.
"""

import argparse
import hashlib
import json
import re
import sys
import tomllib
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.animation.clip import CONFIG_INDEX, FRAME_INDEX, SEQUENCE_GROUP, frame_map_id  # noqa: E402
from rsps_toolkit.animation.frames import decode_sequence  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402
from rsps_toolkit.formats.npc_clips import button_order  # noqa: E402
from rsps_toolkit.formats.npc_definition import NPC_GROUP, decode_npc  # noqa: E402

OUTPUT = Path(__file__).parent.parent / "src/rsps_toolkit/data/npc_clips.json"
MESHSETS = re.compile(r"assets/anotherscape/meshsets/([^/]+)/source\.json")
KEPT_MARK = "cache_same_rig_verified"
DROPPED_KEYS = ("idle", "walk")
REPEAT_KEYS = ("melee", "range", "mage")
RUNELITE_NAME = re.compile(r"[A-Z0-9_]+")


class Snapshot:
    """The NPCs, sequences and frame groups of snapshot 430, read once."""

    def __init__(self, folder: Path):
        self.store = Js5Store(folder / "cache")
        self.npcs = self.store.files(CONFIG_INDEX, NPC_GROUP)
        self.sequences = self.store.files(CONFIG_INDEX, SEQUENCE_GROUP)
        self.groups: dict[int, dict[int, bytes]] = {}

    def first_frame_map(self, sequence_id: int) -> int | None:
        """The frame map of the first frame of the sequence, or None when the sequence has no frames or its first
        frame is not in the cache."""
        frames = decode_sequence(self.sequences[sequence_id]).frames
        if not frames:
            return None
        group, file = frames[0]
        if group not in self.groups:
            self.groups[group] = self.store.files(FRAME_INDEX, group)
        data = self.groups[group].get(file)
        return None if data is None else frame_map_id(data)


def read_mod(jar: Path) -> tuple[dict, list[tuple[str, dict]]]:
    with zipfile.ZipFile(jar) as archive:
        toml = tomllib.loads(archive.read("META-INF/neoforge.mods.toml").decode())
        mod = next(entry for entry in toml["mods"] if entry["modId"] == "anotherscape_models")
        files = sorted(
            (match[1], json.loads(archive.read(name).decode("utf-8-sig")))
            for name in archive.namelist()
            if (match := MESHSETS.fullmatch(name))
        )
    described = {
        "display_name": mod["displayName"],
        "mod_id": mod["modId"],
        "version": mod["version"],
        "file": jar.name,
        "sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
    }
    return described, files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    mod, files = read_mod(args.mod)
    snapshot = Snapshot(args.snapshot)
    print(f"{len(files)} source.json files")

    # Rule 1.
    records = [(folder, record) for folder, record in files if "npcId" in record]
    print(f"Rule 1, a file with no npcId: {len(files) - len(records)} files dropped, {len(records)} records kept")

    # Rule 2.
    in_snapshot = [(folder, record) for folder, record in records if record["npcId"] in snapshot.npcs]
    print(f"Rule 2, the NPC id is not in snapshot 430: {len(records) - len(in_snapshot)} records dropped")
    named = [
        (folder, record, npc)
        for folder, record in in_snapshot
        if (npc := decode_npc(record["npcId"], snapshot.npcs[record["npcId"]])).name.casefold()
        == record["npcName"].casefold()
    ]
    print(f"Rule 2, another name in snapshot 430: {len(in_snapshot) - len(named)} records dropped, {len(named)} kept")

    # Rule 3.
    stood = []
    for folder, record, npc in named:
        stand_map = snapshot.first_frame_map(npc.stand) if npc.stand in snapshot.sequences else None
        if stand_map is not None:
            stood.append((folder, record, stand_map))
    print(f"Rule 3, no stand sequence in snapshot 430: {len(named) - len(stood)} records dropped, {len(stood)} kept")

    # Rule 4.
    marks = Counter(clip["source"] for _, record, _ in stood for clip in record.get("clipSources", {}).values())
    clips = [
        (folder, record, stand_map, key, clip)
        for folder, record, stand_map in stood
        for key, clip in record.get("clipSources", {}).items()
        if clip["source"] == KEPT_MARK
    ]
    dropped_marks = {mark: count for mark, count in sorted(marks.items()) if mark != KEPT_MARK}
    print(f"Rule 4, the clips of each mark that is not {KEPT_MARK}: {dropped_marks}. {len(clips)} clips kept")

    # Rule 5.
    present = [entry for entry in clips if entry[4]["animationId"] in snapshot.sequences]
    print(f"Rule 5, the sequence is not in snapshot 430: {len(clips) - len(present)} clips dropped")
    fitting = [entry for entry in present if snapshot.first_frame_map(entry[4]["animationId"]) == entry[2]]
    print(f"Rule 5, another frame map: {len(present) - len(fitting)} clips dropped. {summary(fitting)}")

    # Rule 6.
    keyed = [entry for entry in fitting if entry[3] not in DROPPED_KEYS]
    print(f"Rule 6, the keys {' and '.join(DROPPED_KEYS)}: {len(fitting) - len(keyed)} clips dropped. {summary(keyed)}")

    # Rule 7.
    names: dict[int, str] = {}
    table: dict[int, dict[str, dict]] = {}
    merged = 0
    for folder, record, _, key, clip in keyed:
        npc_id = record["npcId"]
        names.setdefault(npc_id, record["npcName"])
        row = table.setdefault(npc_id, {})
        if key in row:
            if row[key]["animationId"] != clip["animationId"]:
                raise ValueError(f"Two files give NPC {npc_id} two {key} sequences, the second in {folder}")
            merged += 1
            continue
        row[key] = clip
    print(f"Rule 7, the same clip in two files of one NPC id: {merged} clips dropped")

    # Rule 8.
    repeats = 0
    for row in table.values():
        attack = row.get("attack")
        for key in REPEAT_KEYS:
            if attack is not None and key in row and row[key]["animationId"] == attack["animationId"]:
                del row[key]
                repeats += 1
    print(f"Rule 8, a {', '.join(REPEAT_KEYS)} key that repeats the attack sequence: {repeats} clips dropped")

    # Rules 9 and 10.
    clip_count = sum(len(row) for row in table.values())
    print(
        f"Final: {clip_count} clips of {len(table)} NPCs. Keys: {dict(Counter(k for r in table.values() for k in r))}"
    )
    rows = [
        f'"{npc_id}":'
        + json.dumps(
            {
                "name": names[npc_id],
                "clips": {key: entry(row[key]) for key in sorted(row, key=button_order)},
            },
            separators=(",", ":"),
        )
        for npc_id, row in sorted(table.items())
    ]
    header = {
        "source": "The attack, flinch and death clips that the AnotherScape models mod gives each NPC id, kept when "
        "they fit snapshot 430",
        "mod": mod,
        "snapshot": 430,
        "generator": "scripts/generate-npc-clips.py",
        "research": "docs/research/160-npc-clips.md",
        "note": (
            "A clip is kept only when the mod marks it cache_same_rig_verified, the NPC id has the same name in "
            "snapshot 430 with case ignored, and the first frame of the clip uses the frame map of the first frame of "
            "the NPC's stand sequence. The mod reads a current cache, so each clip is unverified for July 2017 "
            "(ADR 0030). runelite_name is the mod's label when it is a RuneLite name."
        ),
        "counts": {"npcs": len(table), "clips": clip_count},
    }
    lines = [f'"{key}":{json.dumps(value, separators=(",", ":"))},' for key, value in header.items()]
    args.output.write_text("{\n" + "\n".join(lines) + '\n"npcs":{\n' + ",\n".join(rows) + "\n}\n}\n")
    print(f"Written to {args.output}")


def entry(clip: dict) -> dict:
    label = clip.get("label", "")
    if RUNELITE_NAME.fullmatch(label):
        return {"sequence": clip["animationId"], "runelite_name": label}
    return {"sequence": clip["animationId"]}


def summary(entries: list) -> str:
    return f"{len(entries)} clips of {len({entry[1]['npcId'] for entry in entries})} NPCs kept"


if __name__ == "__main__":
    main()
