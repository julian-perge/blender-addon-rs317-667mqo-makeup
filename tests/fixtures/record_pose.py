#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Record the unchanged revision-149 client posing a default player with each frame of one exported clip.

The body type picks the client's own default equipment from the appearance reference (`client_default_equipment`).
The result is written to <clip>/pose-<body>.json unless --output names another new file.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CLIENT_HASH = "19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd"
HERE = Path(__file__).parent
COLOURS = [0, 0, 0, 0, 0]
WEAPON_SLOT, SHIELD_SLOT, ITEM_OFFSET = 3, 5, 512


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--kits", type=Path, required=True, help="folder of raw identkit files 0.dat to 150.dat")
    parser.add_argument("--clip", type=Path, required=True, help="a folder written by animation149/export_clip.py")
    parser.add_argument("--body", choices=("male", "female"), required=True)
    parser.add_argument("--models", type=Path, default=HERE / "appearance")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--held",
        action="store_true",
        help="decode the clip's sequence.dat with the client's loader, so its held items apply, and load the raw item "
        "files in <clip>/items and their models in <clip>/models",
    )
    parser.add_argument("--weapon", type=int, help="an item id worn in the weapon slot")
    parser.add_argument("--shield", type=int, help="an item id worn in the shield slot")
    args = parser.parse_args()
    output = args.output or args.clip / f"pose-{args.body}.json"
    if digest(args.client) != CLIENT_HASH:
        raise ValueError("Unrecognized revision-149 client")
    if output.exists():
        raise ValueError(f"Output must be a new file: {output}")
    appearance = json.loads((args.models / "reference.json").read_text())
    equipment = list(appearance["client_default_equipment"][args.body])
    for slot, item in ((WEAPON_SLOT, args.weapon), (SHIELD_SLOT, args.shield)):
        if item is not None:
            equipment[slot] = ITEM_OFFSET + item
    java_home = os.environ.get("JAVA_HOME") or subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
    sources = [HERE / "AppearanceReference.java", HERE / "SequenceReference.java", HERE / "PoseReference.java"]
    with tempfile.TemporaryDirectory(prefix="pose149-") as temporary:
        work = Path(temporary)
        models = args.models.resolve()
        held = []
        if args.held:
            # The harness reads one model folder, so the body's models and the clip's item models are copied into one.
            models = work / "models"
            models.mkdir()
            for path in [*args.models.glob("*.dat"), *(args.clip / "models").glob("*.dat")]:
                shutil.copyfile(path, models / path.name)
            held = [str((args.clip / "items").resolve())]
        subprocess.run([f"{java_home}/bin/javac", "-d", str(work), *map(str, sources)], check=True, timeout=120)
        subprocess.run(
            [
                f"{java_home}/bin/java",
                "-Djava.awt.headless=true",
                "-cp",
                str(work),
                "PoseReference",
                str(args.client.resolve()),
                str(models),
                str(args.kits.resolve()),
                str(args.clip.resolve()),
                str(work / "pose.json"),
                args.body,
                ",".join(map(str, equipment)),
                ",".join(map(str, COLOURS)),
                *held,
            ],
            check=True,
            timeout=120,
        )
        raw = json.loads((work / "pose.json").read_text())
    result = {
        "client_sha256": CLIENT_HASH,
        "harness_sha256": {path.name: digest(path) for path in sources},
        "runner_sha256": digest(Path(__file__)),
        "clip_manifest_sha256": digest(args.clip / "manifest.json"),
        "appearance_reference_sha256": digest(args.models / "reference.json"),
        "equipment": equipment,
        "colours": COLOURS,
        "female": args.body == "female",
        **(
            {
                "held_inputs_sha256": {
                    f"{p.parent.name}/{p.name}": digest(p)
                    for p in sorted([*(args.clip / "items").glob("*.dat"), *(args.clip / "models").glob("*.dat")])
                }
            }
            if args.held
            else {}
        ),
        **raw,
    }
    output.write_text(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
