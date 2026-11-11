#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/animation_names.json`: the snapshot 430 sequences a player can play, with names.

    uv run scripts/generate-animation-names.py --snapshot <openrs2-430 folder> --names <AnimationID.java> \
        --commit <runelite commit>

A sequence is listed when every frame it shows uses frame map 0, the map of the player's walk (819). Names come from
RuneLite's generated `runelite-api/src/main/java/net/runelite/api/gameval/AnimationID.java` (BSD 2-Clause), downloaded
at the given commit; they are current names for the same ids. A listed sequence without a RuneLite name is refused,
so a gap cannot pass silently.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.animation.clip import CONFIG_INDEX, FRAME_INDEX, SEQUENCE_GROUP  # noqa: E402
from rsps_toolkit.animation.frames import decode_sequence  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402

OUTPUT = Path(__file__).parent.parent / "src/rsps_toolkit/data/animation_names.json"
PLAYER_FRAME_MAP = 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--names", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    names: dict[int, str] = {}
    for name, value in re.findall(r"int (\w+) = (\d+);", args.names.read_text()):
        names.setdefault(int(value), name)
    store = Js5Store(args.snapshot / "cache")
    frame_maps: dict[int, dict[int, int]] = {}
    for group in store.groups(FRAME_INDEX):
        files = store.files(FRAME_INDEX, group)
        frame_maps[group] = {file: int.from_bytes(data[0:2], "big") for file, data in files.items()}
    clips = {}
    for sequence_id, data in sorted(store.files(CONFIG_INDEX, SEQUENCE_GROUP).items()):
        frames = decode_sequence(data).frames
        if frames and all(frame_maps.get(group, {}).get(file) == PLAYER_FRAME_MAP for group, file in frames):
            if sequence_id not in names:
                raise SystemExit(f"Sequence {sequence_id} plays on the player but RuneLite has no name for it")
            clips[sequence_id] = names[sequence_id]
    metadata = json.loads((args.snapshot / "metadata.json").read_text())
    header = {
        "source": "Sequences of snapshot 430 whose frames all use frame map 0, the player's",
        "names": "RuneLite runelite-api/src/main/java/net/runelite/api/gameval/AnimationID.java, BSD 2-Clause",
        "runelite_commit": args.commit,
        "snapshot": {
            "openrs2_id": metadata["id"],
            "dat2_sha256": hashlib.sha256((args.snapshot / "cache/main_file_cache.dat2").read_bytes()).hexdigest(),
        },
        "generator": "scripts/generate-animation-names.py",
    }
    lines = [f'"{key}":{json.dumps(value, separators=(",", ":"))},' for key, value in header.items()]
    rows = [f'"{sequence_id}":{json.dumps(name)}' for sequence_id, name in clips.items()]
    args.output.write_text("{\n" + "\n".join(lines) + '\n"clips":{\n' + ",\n".join(rows) + "\n}\n}\n")
    print(f"{len(clips)} clips written to {args.output}")


if __name__ == "__main__":
    main()
