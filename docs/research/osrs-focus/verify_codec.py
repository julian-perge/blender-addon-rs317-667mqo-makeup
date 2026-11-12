#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
"""Round-trip snapshot 430 through the public codec without changing source files."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from rsps_toolkit.formats import decode, encode  # noqa: E402


def verify(args):
    args.output.mkdir(parents=True, exist_ok=False)
    original_digest = hashlib.sha256()
    encodings = Counter()
    errors = []
    paths = sorted(args.models.glob("*.dat"), key=lambda path: int(path.stem))
    for index, path in enumerate(paths, 1):
        data = path.read_bytes()
        original_digest.update(path.name.encode() + b"\0" + hashlib.sha256(data).digest())
        try:
            model = decode(data, profile="osrs-149")
            exported = encode(model)
            if decode(exported, profile="osrs-149") != model:
                raise ValueError("Decoded model differs after round trip")
            (args.output / path.name).write_bytes(exported)
            encodings[model.encoding.value] += 1
        except Exception as error:
            errors.append({"id": int(path.stem), "error": f"{type(error).__name__}: {error}"})
        if index % 1000 == 0:
            print(f"Checked {index}/{len(paths)} models", flush=True)
    result = {
        "models": len(paths),
        "encodings": dict(encodings),
        "errors": errors,
        "source_sha256": original_digest.hexdigest(),
    }
    (args.output / "roundtrip.json").write_text(json.dumps(result, indent=2) + "\n")
    inventory = json.loads(args.inventory.read_text())
    if original_digest.hexdigest() != inventory["dataset_sha256_name_nul_per_file_digest"]:
        raise ValueError("Source dataset differs from Gate 0")
    print(json.dumps(result), flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("models", "output", "inventory"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    verify(parser.parse_args())
