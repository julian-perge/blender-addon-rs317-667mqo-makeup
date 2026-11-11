#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/item_wear.json` from a recent OSRS cache and the snapshot 430 cache.

    uv run scripts/generate-item-wear.py --cache <openrs2-2757 folder> --snapshot <openrs2-430 folder>

Each folder is an OpenRS2 download with `metadata.json` and the disk cache in `cache/`. Snapshot 430 items carry no
wear positions (every one is -1), so they are read from the recent cache by item id, for every snapshot 430 item with
a worn model that the recent cache gives an equipment slot. Each item records whether its name or worn model ids
changed since snapshot 430. The research behind this is `docs/research/cache-2757-wear-positions.md`.

Items are decoded by `rsps_toolkit.formats.item_definition`, the decoder the add-on uses. An unknown opcode, or a
definition whose bytes do not end right after its closing opcode 0, stops the run.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rsps_toolkit.formats.item_definition import ItemDefinition, decode_item  # noqa: E402
from rsps_toolkit.formats.js5 import Js5Store  # noqa: E402

OUTPUT = Path(__file__).parent.parent / "src/rsps_toolkit/data/item_wear.json"
CONFIG_INDEX, ITEM_GROUP = 2, 10


def load_items(folder: Path) -> dict[int, ItemDefinition]:
    files = Js5Store(folder / "cache").files(CONFIG_INDEX, ITEM_GROUP)
    return {item_id: decode_item(item_id, files[item_id]) for item_id in sorted(files)}


def models(item: ItemDefinition) -> tuple[int, ...]:
    return (*item.worn.male_models, *item.worn.female_models)


def describe(folder: Path) -> dict:
    metadata = json.loads((folder / "metadata.json").read_text())
    return {
        "openrs2_id": metadata["id"],
        "build": metadata["builds"][0]["major"],
        "timestamp": metadata["timestamp"],
        "dat2_sha256": hashlib.sha256((folder / "cache/main_file_cache.dat2").read_bytes()).hexdigest(),
    }


def status(old: ItemDefinition, new: ItemDefinition) -> str:
    models_same = models(old) == models(new)
    if new.worn.name != old.worn.name:
        return "renamed" if models_same else "renamed_and_models_changed"
    return "match" if models_same else "models_changed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    new, old = load_items(args.cache), load_items(args.snapshot)
    rows = []
    for item_id, item in old.items():
        recent = new.get(item_id)
        worn = item.worn
        if worn.male_models[0] == -1 and worn.female_models[0] == -1 or recent is None:
            continue
        slot, *hidden = recent.wear_positions
        if slot == -1:
            continue
        hides = sorted(set(hidden) - {-1})
        entry = {"slot": slot, "hides": hides, "status": status(item, recent)}
        rows.append(f'"{item_id}":{json.dumps(entry, separators=(",", ":"))}')
    header = {
        "source": "Item wear positions (opcodes 13, 14 and 27) of a recent OSRS cache, by item id",
        "cache": describe(args.cache),
        "snapshot": describe(args.snapshot),
        "generator": "scripts/generate-item-wear.py",
        "note": (
            "Slot numbers are the client's: 0 head, 1 cape, 2 neck, 3 weapon, 4 torso, 5 shield, 6 arms, 7 legs, "
            "8 hair, 9 hands, 10 feet, 11 jaw. slot is the item's wearPos1; hides lists its wearPos2 and wearPos3, "
            "the slots the game server empties while the item is worn. status compares the snapshot item with the "
            "recent one: match, renamed, models_changed or renamed_and_models_changed (worn model ids differ)."
        ),
    }
    lines = [f'"{key}":{json.dumps(value, separators=(",", ":"))},' for key, value in header.items()]
    args.output.write_text("{\n" + "\n".join(lines) + '\n"items":{\n' + ",\n".join(rows) + "\n}\n}\n")
    print(f"{len(rows)} items written to {args.output}")


if __name__ == "__main__":
    main()
