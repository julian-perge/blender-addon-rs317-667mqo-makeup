#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
"""Record a compact source closure without importing the production codec."""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(args):
    if digest(args.library) != "c71c4db7830d3828d15a96420e76cb24fe3f864f755799d5b3d618f09a15d623":
        raise ValueError("Reference library differs from the pinned unmodified artifact")
    models = args.models.resolve()
    inventory = json.loads(args.inventory.read_text())
    selected = {0, 1, 49, 96, 5452, 5409, 7978, 12153, 32971}
    selected.update(inventory["referenced_complex_models"])
    selected.update(inventory["render2_models"])
    selected.update(inventory["above63"])
    seen_flags = set()
    seen_tails = set()
    for entry in inventory["metadata_models"]:
        if entry["hex"] not in seen_tails:
            selected.add(entry["id"])
            seen_tails.add(entry["hex"])
    source_digest = hashlib.sha256()
    for path in sorted(models.glob("*.dat"), key=lambda p: int(p.stem)):
        data = path.read_bytes()
        source_digest.update(path.name.encode() + b"\0" + hashlib.sha256(data).digest())
        if data[-2:] != b"\xff\xff":
            continue
        footer = struct.unpack_from(">HHBBBBBBBHHHHH", data, len(data) - 23)
        flags = tuple(footer[3:9])
        if flags not in seen_flags:
            selected.add(int(path.stem))
            seen_flags.add(flags)
    if source_digest.hexdigest() != inventory["dataset_sha256_name_nul_per_file_digest"]:
        raise ValueError("Source dataset differs from the independently recorded inventory")
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    harness = Path(__file__).with_name("Osrs149Reference.java")
    with tempfile.TemporaryDirectory(prefix="osrs149-record-") as temporary:
        scratch = Path(temporary)
        closure = scratch / "models"
        classes = scratch / "classes"
        closure.mkdir()
        classes.mkdir()
        for model_id in sorted(selected):
            shutil.copy2(models / f"{model_id}.dat", closure)
        subprocess.run(["javac", "-cp", str(args.library), "-d", str(classes), str(harness)], check=True)
        subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                "-cp",
                f"{classes}:{args.library}",
                "Osrs149Reference",
                "--input",
                str(closure),
                "--output",
                str(closure),
                "--client",
                str(args.client),
            ],
            check=True,
        )
        shutil.copy2(args.inventory, closure / "inventory.json")
        records = {}
        for model_id in sorted(selected):
            dat = closure / f"{model_id}.dat"
            reference = dat.with_suffix(".json")
            records[str(model_id)] = {
                "path": dat.name,
                "sha256": digest(dat),
                "reference": reference.name,
                "reference_sha256": digest(reference),
            }
        coverage = {
            "format": "osrs149-static-reference",
            "version": 1,
            "profile": "osrs-149",
            "source": {
                "snapshot_id": 430,
                "revision": 149,
                "dataset_sha256": source_digest.hexdigest(),
                "client_sha256": digest(args.client),
                "library_sha256": digest(args.library),
                "recorder_sha256": digest(harness),
                "inventory_sha256": digest(args.inventory),
            },
            "models": records,
        }
        (closure / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
        shutil.copytree(closure, args.output)
    print(f"Captured {len(selected)} models covering {len(seen_flags)} newer footer combinations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("models", "inventory", "client", "library", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    record(parser.parse_args())
