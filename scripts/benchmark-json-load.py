#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["msgspec==0.22.0", "orjson==3.11.4"]
# ///
"""Measures whether msgspec speeds up the JSON loads this add-on does, with the validation they need.

Run with `uv run scripts/benchmark-json-load.py [large.json ...]`. The animation manifest fixture is the real
source-loading input today (rsps_toolkit.animation.bundle reads it); extra files are compared as future work only. The
stdlib path uses the loader's own hooks, imported from that module, so the benchmark cannot drift from it. Timings are
wall-clock milliseconds, shown as the median and the range from fastest to slowest over repeated runs. Memory is not
measured, because Python's allocation tracing would distort the timings it sits beside.
"""

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import msgspec
import orjson

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from rsps_toolkit.animation.bundle import _nonfinite as nonfinite  # noqa: E402
from rsps_toolkit.animation.bundle import _unique_object as unique  # noqa: E402

MANIFEST = ROOT / "tests/fixtures/animations/2013/bundle-manifest.json"
REPEATS = 200
COLD_REPEATS = 10


def stdlib_strict(text: str) -> object:
    return json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)


def msgspec_only(text: str) -> object:
    return msgspec.json.decode(text)


def msgspec_with_precheck(text: str) -> object:
    # msgspec accepts duplicate keys, so the same check the stdlib hook gives needs a stdlib pass as well.
    json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    return msgspec.json.decode(text)


def orjson_only(text: str) -> object:
    return orjson.loads(text)


def orjson_with_precheck(text: str) -> object:
    json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    return orjson.loads(text)


def measure(function, argument) -> tuple[float, float, float]:
    times = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        function(argument)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times), min(times), max(times)


def report(label: str, path: Path) -> None:
    text = path.read_text()
    print(f"{label}: {path.name}, {len(text) / 1024:.0f} KiB")
    for name, function in (
        ("stdlib strict (current)", stdlib_strict),
        ("msgspec only (no duplicate-key check)", msgspec_only),
        ("msgspec + stdlib precheck (equal validation)", msgspec_with_precheck),
        ("orjson only (no duplicate-key check)", orjson_only),
        ("orjson + stdlib precheck (equal validation)", orjson_with_precheck),
    ):
        median, low, high = measure(function, text)
        print(f"  {name:48s} median {median:8.3f} ms  range {low:8.3f} to {high:8.3f}")


def cold_import(module: str) -> tuple[float, float, float]:
    times = []
    for _ in range(COLD_REPEATS):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-c", f"import {module}"], check=True)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times), min(times), max(times)


CASES = {
    "duplicate key at top level": '{"a": 1, "a": 2}',
    "duplicate key in nested object": '{"x": {"y": {"a": 1, "a": 2}}}',
    "duplicate key inside an array": '{"x": [{"a": 1, "a": 2}]}',
    "NaN": '{"a": NaN}',
    "Infinity": '{"a": Infinity}',
    "valid": '{"a": [1, 2.5, {"b": null}]}',
}


def accepts(function, text: str) -> bool:
    try:
        function(text)
    except ValueError:
        return False
    return True


def check_validation() -> None:
    print("accepted (True) or rejected (False), per input:")
    for name, text in CASES.items():
        print(
            f"  {name:34s} stdlib strict {accepts(stdlib_strict, text)!s:5}"
            f"  msgspec only {accepts(msgspec_only, text)!s:5}"
            f"  msgspec + precheck {accepts(msgspec_with_precheck, text)!s:5}"
            f"  orjson only {accepts(orjson_only, text)!s:5}"
            f"  orjson + precheck {accepts(orjson_with_precheck, text)}"
        )


def main() -> None:
    check_validation()
    report("current source-loading input", MANIFEST)
    for extra in sys.argv[1:]:
        report("future-work comparison", Path(extra))
    for label, module in (("import json", "json"), ("import msgspec", "msgspec"), ("import orjson", "orjson")):
        median, low, high = cold_import(module)
        print(f"cold interpreter start with {label:16s} median {median:6.1f} ms  range {low:6.1f} to {high:6.1f}")


if __name__ == "__main__":
    main()
