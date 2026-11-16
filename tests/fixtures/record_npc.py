#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Record the unchanged revision-149 client building the lit model of each test NPC in `npc/`.

    uv run tests/fixtures/record_npc.py --client <reference work folder>/gamepack-149.jar --output <new file>

The NPC definitions are `npc/<id>.dat` and their models `npc/models/<id>.dat`, which
`scripts/extract-config-fixtures.py` copies from snapshot 430. The client loads and lights them itself through
`NpcModelReference.java`; no Python of the add-on runs. The fixture is `npc/lit.json`.
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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if digest(args.client) != CLIENT_HASH:
        raise ValueError("Unrecognized revision-149 client")
    if args.output.exists():
        raise ValueError(f"Output must be a new file: {args.output}")
    java_home = os.environ.get("JAVA_HOME") or subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
    sources = [HERE / "AppearanceReference.java", HERE / "NpcModelReference.java"]
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
            ],
            check=True,
            timeout=120,
        )
        lit = json.loads((work / "lit.json").read_text())
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


if __name__ == "__main__":
    main()
