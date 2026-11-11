#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
"""Capture or replay the approved icon-edge policy with an unchanged rasterizer."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

SOURCE_SHA256 = "c75985f35c891fc1dcbe9ee978032878d5e4b1c8a9b8dcf0496c498bb6b8b973"
FACTORY_SHA256 = "5780d2d7f9a90f2792c4ab04446ad98be1c7f93e0f5bcb1bc4f9c6a32afb554c"
LIBRARY_SHA256 = "c71c4db7830d3828d15a96420e76cb24fe3f864f755799d5b3d618f09a15d623"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(args):
    if digest(args.sources) != SOURCE_SHA256 or digest(args.library) != LIBRARY_SHA256:
        raise ValueError("Reference artifacts differ from the pinned unmodified inputs")
    with zipfile.ZipFile(args.sources) as archive:
        original = archive.read("net/runelite/cache/item/ItemSpriteFactory.java")
    if hashlib.sha256(original).hexdigest() != FACTORY_SHA256:
        raise ValueError("Reference factory source differs")
    source = original.decode().replace("class ItemSpriteFactory", "class GuardedItemSpriteFactory")
    allocation = "new SpritePixels(36, 32)"
    if source.count(allocation) != 1:
        raise ValueError("Reference factory allocation is ambiguous")
    source = source.replace(allocation, "new SpritePixels(new int[36 * 32 + 1], 36, 32)")
    harness = Path(__file__).with_name("Osrs149IconReference.java")
    with tempfile.TemporaryDirectory(prefix="osrs149-icons-") as temporary:
        scratch = Path(temporary)
        guarded = scratch / "GuardedItemSpriteFactory.java"
        guarded.write_text(source)
        classes = scratch / "classes"
        classes.mkdir()
        source_input = args.closure
        if args.cache:
            source_input = scratch / "cache"
            shutil.copytree(args.cache, source_input)
        subprocess.run(
            ["javac", "-cp", str(args.library), "-d", str(classes), str(guarded), str(harness)],
            check=True,
        )
        subprocess.run(
            [
                "java",
                "-Djava.awt.headless=true",
                "-cp",
                f"{classes}:{args.library}",
                "Osrs149IconReference",
                "--cache" if args.cache else "--closure",
                str(source_input),
                str(args.output),
            ],
            check=True,
        )
    manifest = {
        "format": "osrs149-icon-reference",
        "version": 1,
        "snapshot_id": 430,
        "policy": "transparent-zero-neighbor-outside-framebuffer",
        "viewport": [36, 32],
        "items": [8283, 4151, 995],
        "arguments": {"quantity": 1, "border": 1, "shadow": 0x302020, "noted": False},
        "source_sha256": SOURCE_SHA256,
        "factory_sha256": FACTORY_SHA256,
        "guarded_factory_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "library_sha256": LIBRARY_SHA256,
        "recorder_sha256": digest(harness),
        "files": {
            str(path.relative_to(args.output)): digest(path)
            for path in sorted(args.output.rglob("*"))
            if path.is_file()
        },
    }
    (args.output / "coverage.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Captured item 8283 with the approved guard policy; both successful control icons are unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--cache", type=Path)
    inputs.add_argument("--closure", type=Path)
    for name in ("sources", "library", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    record(parser.parse_args())
