#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Copies the raw kit and style enum definitions of the snapshot 430 cache into `tests/fixtures/appearance/`.

    uv run scripts/extract-config-fixtures.py --cache <openrs2-430 folder>/cache

It writes every kit of config group 3 to `kits/<id>.dat`, and the enums that `STYLE_ENUMS` names from config group 8
to `enums/<id>.dat`, unchanged. An existing file with different bytes stops the run, so the fixtures cannot change
without notice.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.formats.cache_profile import CONFIG_INDEX, ENUM_GROUP, KIT_GROUP  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402
from rsps_toolkit.formats.kit_names import STYLE_ENUMS  # noqa: E402

OUTPUT = Path(__file__).resolve().parent.parent / "tests/fixtures/appearance"


def write(folder: Path, files: dict[int, bytes]) -> None:
    folder.mkdir(exist_ok=True)
    for file, data in sorted(files.items()):
        path = folder / f"{file}.dat"
        if path.exists() and path.read_bytes() != data:
            raise SystemExit(f"{path} differs from the cache")
        path.write_bytes(data)
    print(f"{len(files)} files in {folder}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True, help="the cache/ folder of OpenRS2 snapshot 430")
    store = Js5Store(parser.parse_args().cache)
    write(OUTPUT / "kits", store.files(CONFIG_INDEX, KIT_GROUP))
    enums = store.files(CONFIG_INDEX, ENUM_GROUP)
    write(OUTPUT / "enums", {enum: enums[enum] for pair in STYLE_ENUMS.values() for enum in pair})


if __name__ == "__main__":
    main()
