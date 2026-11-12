#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/player_joints.json`: the joints of the player's frame map (frame map 0).

    uv run scripts/generate-player-joints.py --snapshot <openrs2-430 folder>

The joints are the rotate transforms (type 2) in NAMES: the classic skeleton of the map (transforms 0 to 81) that
most player clips use. Later transforms (112 to 198) repeat the same body parts with slightly different pivots and
are left out; the clip bake keys each label bone's remaining motion under its joint, so clips using them still play
as the client shows them. A joint's pivot is the nearest earlier pivot transform (type 0), as the client uses it,
and its labels are every label the rotation moves. The plan behind this is
`tasks/old/osrs-focus/plans/11-joint-rig.md`.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.animation.clip import FRAME_MAP_INDEX  # noqa: E402
from rsps_toolkit.animation.frames import decode_frame_map  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402

OUTPUT = Path(__file__).parent.parent / "src/rsps_toolkit/data/player_joints.json"
PLAYER_FRAME_MAP = 0
PIVOT, ROTATE = 0, 2
# Names by rotate transform, read from the labels each moves on the default bodies. The side suffix is added when
# the rig is built, from where the joint sits.
NAMES = {
    2: "root",
    7: "spine",
    4: "head",
    22: "upper_arm",
    24: "forearm",
    27: "hand",
    30: "upper_arm",
    32: "forearm",
    35: "hand",
    9: "thigh",
    11: "shin",
    13: "foot",
    15: "thigh",
    17: "shin",
    19: "foot",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    store = Js5Store(args.snapshot / "cache")
    frame_map = decode_frame_map(next(iter(store.files(FRAME_MAP_INDEX, PLAYER_FRAME_MAP).values())))
    joints = []
    pivot = None
    for index, (kind, labels) in enumerate(zip(frame_map.types, frame_map.labels, strict=True)):
        if kind == PIVOT:
            pivot = index
        elif kind == ROTATE and index in NAMES:
            if pivot is None:
                raise SystemExit(f"Rotate transform {index} has no earlier pivot")
            joints.append(
                {
                    "name": NAMES[index],
                    "rotate": index,
                    "pivot": pivot,
                    "pivot_labels": sorted(frame_map.labels[pivot]),
                    "labels": sorted(labels),
                }
            )
    header = {
        "source": "The named rotate transforms of snapshot 430 frame map 0, each with the pivot transform the client uses",
        "snapshot_dat2_sha256": hashlib.sha256((args.snapshot / "cache/main_file_cache.dat2").read_bytes()).hexdigest(),
        "generator": "scripts/generate-player-joints.py",
    }
    lines = [f'"{key}":{json.dumps(value)},' for key, value in header.items()]
    rows = [json.dumps(joint, separators=(",", ":")) for joint in joints]
    args.output.write_text("{\n" + "\n".join(lines) + '\n"joints":[\n' + ",\n".join(rows) + "\n]\n}\n")
    print(f"{len(joints)} joints written to {args.output}")


if __name__ == "__main__":
    main()
