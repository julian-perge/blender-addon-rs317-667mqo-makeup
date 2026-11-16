#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Record the unchanged revision-149 client building the lit model of each test NPC in `npc/`, and posing it.

    uv run tests/fixtures/record_npc.py --client <reference work folder>/gamepack-149.jar --output <new file> \
        --poses <new file>

The NPC definitions are `npc/<id>.dat` and their models `npc/models/<id>.dat`, which
`scripts/extract-config-fixtures.py` copies from snapshot 430. The client loads and lights them itself through
`NpcModelReference.java`; no Python of the add-on runs. The fixture is `npc/lit.json`.

With `--poses`, the client also poses each of the five test NPCs with every frame of its stand and walk sequences, as
RuneLite's decoding in `npc/npcs.json` names them. The clip folders are `npc/clips/<sequence>/`, written by
`animation149/export_clip.py`. The fixture is `npc/poses.json`.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

CLIENT_HASH = "19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd"
HERE = Path(__file__).parent
NPCS = HERE / "npc"
# The five test NPCs of spec 13, whose stand and walk clips are posed. NPC 3078 plays the player's clips.
POSED = (4233, 6594, 2805, 260, 2477)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--poses", type=Path)
    args = parser.parse_args()
    if digest(args.client) != CLIENT_HASH:
        raise ValueError("Unrecognized revision-149 client")
    for output in (args.output, args.poses):
        if output is not None and output.exists():
            raise ValueError(f"Output must be a new file: {output}")
    decoded = {npc["id"]: npc for npc in json.loads((NPCS / "npcs.json").read_text())}
    clips = {npc: (decoded[npc]["standingAnimation"], decoded[npc]["walkingAnimation"]) for npc in POSED}
    plan = ";".join(f"{npc}:{stand},{walk}" for npc, (stand, walk) in clips.items())
    java_home = os.environ.get("JAVA_HOME") or subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
    sources = [
        HERE / "AppearanceReference.java",
        HERE / "NpcModelReference.java",
        HERE / "PoseReference.java",
        HERE / "SequenceReference.java",
    ]
    with tempfile.TemporaryDirectory(prefix="npc149-") as temporary:
        work = Path(temporary)
        subprocess.run([f"{java_home}/bin/javac", "-d", str(work), *map(str, sources)], check=True, timeout=120)
        subprocess.run(
            [
                f"{java_home}/bin/java",
                "-Djava.awt.headless=true",
                "-cp",
                str(work),
                "NpcModelReference",
                str(args.client.resolve()),
                str(NPCS.resolve()),
                str((NPCS / "models").resolve()),
                str(work / "lit.json"),
                *([str((NPCS / "clips").resolve()), str(work / "poses.json"), plan] if args.poses else []),
            ],
            check=True,
            timeout=120,
        )
        lit = json.loads((work / "lit.json").read_text())
        poses = json.loads((work / "poses.json").read_text()) if args.poses else None
    result = {
        "client_sha256": CLIENT_HASH,
        "harness_sha256": {path.name: digest(path) for path in sources},
        "runner_sha256": digest(Path(__file__)),
        "inputs_sha256": {
            **{path.name: digest(path) for path in sorted(NPCS.glob("*.dat"))},
            **{f"models/{path.name}": digest(path) for path in sorted((NPCS / "models").glob("*.dat"))},
        },
        "npcs": lit,
    }
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(f"Recorded {len(lit)} NPCs through the unchanged revision-149 client")
    if args.poses is not None and poses is not None:
        folders = [NPCS / "clips" / str(sequence) for pair in clips.values() for sequence in pair]
        args.poses.write_text(
            json.dumps(
                {
                    "client_sha256": CLIENT_HASH,
                    "harness_sha256": {path.name: digest(path) for path in sources},
                    "runner_sha256": digest(Path(__file__)),
                    "inputs_sha256": result["inputs_sha256"],
                    "clip_manifests_sha256": {f.name: digest(f / "manifest.json") for f in folders},
                    "clips": {str(npc): {"stand": stand, "walk": walk} for npc, (stand, walk) in clips.items()},
                    "npcs": poses,
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        print(f"Posed the stand and walk clips of {len(poses)} NPCs")


if __name__ == "__main__":
    main()
