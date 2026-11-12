#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///
"""Verify packaged CLI reports against real output files and untouched inputs."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def hashes(cache):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cache.glob("main_file_cache.*"))}


def verify(args):
    if args.out.exists():
        raise FileExistsError(args.out)
    before = hashes(args.cache)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    log = args.out.with_suffix(".log")
    with tempfile.TemporaryDirectory(prefix="osrs430-report-") as temporary:
        cache = Path(temporary) / "cache"
        shutil.copytree(args.cache, cache)
        with log.open("w") as stream:
            result = subprocess.run(
                [
                    "java",
                    "-Djava.awt.headless=true",
                    "-Xmx2g",
                    "-jar",
                    str(args.jar),
                    "--cache",
                    str(cache),
                    "--keys",
                    str(args.keys),
                    "--names",
                    str(args.names),
                    "--out",
                    str(args.out),
                    "all",
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        assert before == hashes(cache), "Working cache changed"
    assert before == hashes(args.cache), "Original cache changed"
    (args.out / "verification-exit.json").write_text(json.dumps({"exit": result.returncode}) + "\n")
    report = json.loads((args.out / "dump-report.json").read_text())
    assert all(report["source_hashes"][name] == digest for name, digest in before.items())

    def count(relative, suffix):
        return len(list((args.out / relative).rglob(f"*{suffix}")))

    paths = {
        "items": "items/ItemDefinitions.json",
        "npcs": "npcs/NpcDefinitions.json",
        "objects": "objects/ObjectDefinitions.json",
        "varbits": "varbits/VarbitDefinitions.json",
        "enums": "enums/Enums.json",
        "structs": "structs/Structs.json",
        "spotanims": "spotanims/SpotAnimDefinitions.json",
    }
    expected = {target: len(json.loads((args.out / path).read_text())) for target, path in paths.items()}
    for target, path, suffix in (
        ("raw-items", "dump_index/items", ".dat"),
        ("raw-models", "dump_index/models", ".dat"),
        ("raw-maps", "dump_index/maps", ".dat"),
        ("raw-music", "dump_index/music", ".dat"),
        ("raw-configs", "dump_index/configs", ".dat"),
        ("sprites", "dump_index/sprites", ".png"),
        ("textures", "textures", ".png"),
        ("models-obj", "models_obj", ".obj"),
        ("sounds", "sounds", ".wav"),
        ("music-samples", "music/samples", ".wav"),
        ("item-icons", "item_icons", ".png"),
    ):
        expected[target] = count(path, suffix)
    expected["music"] = count("music/tracks", ".mid") + count("music/jingles", ".mid")
    expected["soundfont"] = count("music", ".sf2")
    assert len(expected) == 20
    assert set(expected) == set(report["requested_targets"]) == set(report["targets"])
    problems = []
    for target, written in expected.items():
        actual = report["targets"][target]["written"]
        if actual != written:
            problems.append(f"{target}: report says {actual} written; output contains {written}")
    failures = [
        (target, row["id"])
        for target, entry in report["targets"].items()
        for row in entry["entries"]
        if row["category"] == "failed"
    ]
    expected_failures = [] if args.expected_failed_icon is None else [("item-icons", str(args.expected_failed_icon))]
    if failures != expected_failures:
        problems.append(f"Failures: {failures!r}; expected {expected_failures!r}")
    if result.returncode != bool(expected_failures):
        problems.append(f"Exit {result.returncode}; expected {int(bool(expected_failures))}")
    assert report["targets"]["raw-maps"]["omitted"] == 268
    assert expected["raw-models"] == expected["models-obj"] == 33196
    assert expected["raw-maps"] == 1513 + 1245
    assert expected["textures"] == 59
    assert expected["item-icons"] == 21392 - len(expected_failures)
    if problems:
        raise AssertionError("\n".join(problems))
    print(f"All 20 target counts match output files; {len(failures)} expected failures; inputs unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache", "keys", "jar", "names", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--expected-failed-icon", type=int)
    verify(parser.parse_args())
