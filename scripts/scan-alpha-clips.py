#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Prints the snapshot 430 player clips whose alpha transforms give the player's face labels more than one curve.

    uv run scripts/scan-alpha-clips.py --cache <path to cache>

A player clip is a sequence whose frames all use frame map 0, as in `scripts/generate-animation-names.py`. The scan
reads the player clips that have a face alpha transform (type 5) on some frame. For each one it computes the alpha of
each face label of the player on every frame, with the add-on's own frame evaluation. Every face starts at alpha 0,
because the player's bodies have no face alphas (`rest.o` is null in the `alpha-3364` recordings). Labels with the
same alphas on every frame share one curve, so the labels that keep alpha 0 on every frame also share one. Each clip
with more than one curve is printed on its own line, with the labels of each curve. This scan picked the `alpha-3364`
fixture of `tests/fixtures/animation149/`.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.animation.clip import CONFIG_INDEX, FRAME_INDEX, FRAME_MAP_INDEX, SEQUENCE_GROUP  # noqa: E402
from rsps_toolkit.animation.frames import decode_frame, decode_frame_map, decode_sequence  # noqa: E402
from rsps_toolkit.animation.poses import evaluate_frame  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402

PLAYER_FRAME_MAP = 0
ALPHA_TRANSFORM = 5
# Issue 29 gives these as the skin labels that the player's faces carry. The face labels of the male and female bodies
# that tests/unit/test_pose_149.py assembles are this same list.
PLAYER_FACE_LABELS = (0, 1, 2, 4, *range(9, 28))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    store = Js5Store(args.cache)
    frame_map = decode_frame_map(next(iter(store.files(FRAME_MAP_INDEX, PLAYER_FRAME_MAP).values())))
    groups = {group: store.files(FRAME_INDEX, group) for group in store.groups(FRAME_INDEX)}
    rest = (0,) * len(PLAYER_FACE_LABELS)
    scanned = 0
    for sequence_id, data in sorted(store.files(CONFIG_INDEX, SEQUENCE_GROUP).items()):
        frames = decode_sequence(data).frames
        files = [groups.get(group, {}).get(file, b"") for group, file in frames]
        if not files or any(not file or int.from_bytes(file[0:2], "big") != PLAYER_FRAME_MAP for file in files):
            continue
        decoded = [decode_frame(file, frame_map) for file in files]
        if not any(frame_map.types[index] == ALPHA_TRANSFORM for frame in decoded for index in frame.indices):
            continue
        scanned += 1
        alphas = [evaluate_frame((), (), rest, PLAYER_FACE_LABELS, frame, frame_map)[1] for frame in decoded]
        curves: dict[tuple[int, ...], list[int]] = {}
        for position, label in enumerate(PLAYER_FACE_LABELS):
            curves.setdefault(tuple(frame[position] for frame in alphas), []).append(label)
        if len(curves) > 1:
            print(f"{sequence_id}: " + " | ".join(" ".join(map(str, labels)) for labels in curves.values()))
    print(f"{scanned} player clips have a face alpha transform", file=sys.stderr)


if __name__ == "__main__":
    main()
