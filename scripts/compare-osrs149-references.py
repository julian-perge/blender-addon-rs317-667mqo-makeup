#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Compares two folders of reference JSON files recorded by tests/fixtures/Osrs149Reference.java.

    uv run scripts/compare-osrs149-references.py --expected <source-refs> --actual <export-refs>

The expected folder is the recorder's output for the original DAT files and the actual folder is its output for the
files an export wrote. The recorder reads fields without using this add-on's codec, so a field the encoder drops
shows up here even if the decoder drops it too. Every field is compared except the hash of the source file, which
names the file and necessarily differs once the bytes differ. The exit code is 1 when a reference is missing from
the actual folder, a reference exists only there, any differs, or the expected folder holds none.
"""

import argparse
import json
import math
import sys
from pathlib import Path

IDENTITY_FIELDS = {"source_sha256"}


def differences(expected: object, actual: object, path: str = "") -> list[str]:
    """Every place the two values differ, as a dotted path with a short description."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = []
        for key in sorted(expected.keys() | actual.keys()):
            where = f"{path}.{key}" if path else key
            if not path and key in IDENTITY_FIELDS:
                continue
            if key not in actual:
                found.append(f"{where}: missing")
            elif key not in expected:
                found.append(f"{where}: unexpected")
            else:
                found += differences(expected[key], actual[key], where)
        return found
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: {len(expected)} entries expected, {len(actual)} found"]
        return [
            d for i, (e, a) in enumerate(zip(expected, actual, strict=True)) for d in differences(e, a, f"{path}[{i}]")
        ]
    both_nan = isinstance(expected, float) and isinstance(actual, float) and math.isnan(expected) and math.isnan(actual)
    same = both_nan or (expected == actual and type(expected) is type(actual))
    return [] if same else [f"{path}: {expected!r} became {actual!r}"]


def compare(expected_dir: Path, actual_dir: Path) -> dict[str, list[str]]:
    """The differences of every reference that is missing or changed, keyed by file name."""
    problems: dict[str, list[str]] = {}
    for path in sorted(expected_dir.glob("*.json")):
        other = actual_dir / path.name
        if not other.exists():
            problems[path.name] = ["missing from the actual folder"]
            continue
        found = differences(json.loads(path.read_text()), json.loads(other.read_text()))
        if found:
            problems[path.name] = found
    for path in sorted(actual_dir.glob("*.json")):
        if not (expected_dir / path.name).exists():
            problems[path.name] = ["present only in the actual folder"]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    arguments = parser.parse_args()
    expected = sorted(arguments.expected.glob("*.json"))
    problems = compare(arguments.expected, arguments.actual)
    print(json.dumps({"compared": len(expected), "different": len(problems), "problems": problems}, indent=1))
    return 1 if not expected or problems else 0


if __name__ == "__main__":
    sys.exit(main())
