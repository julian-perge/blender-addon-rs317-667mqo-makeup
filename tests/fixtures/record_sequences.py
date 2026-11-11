#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Record the unchanged revision-149 client decoding sequence files and advancing their frame counters per tick.

Every <id>.dat in --sequences is decoded by the client's own sequence loader. Each --timing case `id:pose:ticks` or
`id:action:ticks` steps the client's per-tick actor update with that sequence as the pose or the action sequence and
records the frame index before the first tick and after each tick (-1 once an action sequence has stopped).
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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--sequences", type=Path, required=True, help="folder of raw sequence files <id>.dat")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timing", nargs="*", default=[])
    args = parser.parse_args()
    if digest(args.client) != CLIENT_HASH:
        raise ValueError("Unrecognized revision-149 client")
    if args.output.exists():
        raise ValueError(f"Output must be a new file: {args.output}")
    java_home = os.environ.get("JAVA_HOME") or subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
    sources = [HERE / "AppearanceReference.java", HERE / "PoseReference.java", HERE / "SequenceReference.java"]
    with tempfile.TemporaryDirectory(prefix="sequence149-") as temporary:
        work = Path(temporary)
        subprocess.run([f"{java_home}/bin/javac", "-d", str(work), *map(str, sources)], check=True, timeout=120)
        subprocess.run(
            [
                f"{java_home}/bin/java",
                "-Djava.awt.headless=true",
                "-cp",
                str(work),
                "SequenceReference",
                str(args.client.resolve()),
                str(args.sequences.resolve()),
                str(work / "sequences.json"),
                *args.timing,
            ],
            check=True,
            timeout=300,
        )
        raw = json.loads((work / "sequences.json").read_text())
    inputs = sorted(args.sequences.glob("*.dat"), key=lambda path: int(path.stem))
    result = {
        "client_sha256": CLIENT_HASH,
        "harness_sha256": {path.name: digest(path) for path in sources},
        "runner_sha256": digest(Path(__file__)),
        "inputs_sha256": {path.stem: digest(path) for path in inputs},
        **raw,
    }
    args.output.write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    main()
