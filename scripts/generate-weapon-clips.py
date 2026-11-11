#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Writes `src/rsps_toolkit/data/weapon_clips.json`: the stance and attack clips of each snapshot 430 weapon.

    uv run scripts/generate-weapon-clips.py --alter <folder> --alter-commit <sha> \
        --plugin <folder> --plugin-commit <sha>

The revision 149 client reads a player's stance clips from the appearance block the server sends, and neither the
snapshot 430 cache nor a 2026 cache holds a weapon to clip table (evidence: `docs/research/weapon-stance-sets.md`,
sections 1 and 3). The clips come from two open tables of 2024 and 2026, downloaded at the given commits; whether the
game gave each weapon the same clips in July 2017 is not verified.

- `--alter` holds `item_bas.json`, `bas_mappings.json` and `LICENSE` from AlterRSPS/Alter
  (`data/cfg/items/renderAnimations/`), BSD 2-Clause. It is the table: an item it lists takes its set, gaps
  included, which is the user's choice (ADR 0014).
- `--plugin` holds `data.json` and `LICENSE` from geheur/weapon-animation-replacer
  (`src/main/resources/com/weaponanimationreplacer/`), BSD 2-Clause. Its developer tool records players in the live
  game; that every set in `data.json` came from it is a guess. It gives an item Alter does not list its stance clips
  and its block clip. Every item whose stance clips or block clip the plugin gives differently is listed under
  `disagreements` with the plugin's values.

A weapon is an item that `data/item_wear.json` puts in slot 3. A clip that a written set gives and that is not a
player clip of snapshot 430 (`data/animation_names.json`) stops the run, so a clip added to the game later cannot
reach a button. The plugin's values under `disagreements` are kept as they are, so they can name such clips (11466).
"""

import argparse
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "src/rsps_toolkit/data"
OUTPUT = DATA / "weapon_clips.json"
WEAPON_SLOT = 3
UNARMED = "bas.default_player"
STANCE_FIELDS = ("readyAnim", "turnAnim", "walkAnim", "walkAnimBack", "walkAnimLeft", "walkAnimRight", "runAnim")
ATTACK_FIELDS = ("accurateAnim", "aggressiveAnim", "controlledAnim", "defensiveAnim", "blockAnim")
# The plugin's AnimationType order (Swap.java): stand, walk, run, walk back, walk left, walk right, turn, stab,
# slash, crush, special, defend, and more after.
PLUGIN_STANCE = (0, 6, 1, 3, 4, 5, 2)
PLUGIN_BLOCK = 11
ALTER_FILES = ("item_bas.json", "bas_mappings.json")
PLUGIN_FILE = "data.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alter", type=Path, required=True)
    parser.add_argument("--alter-commit", required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--plugin-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    wear = json.loads((DATA / "item_wear.json").read_text())["items"]
    weapons = {int(item) for item, entry in wear.items() if entry["slot"] == WEAPON_SLOT}
    player_clips = {int(clip) for clip in json.loads((DATA / "animation_names.json").read_text())["clips"]}

    mappings = json.loads((args.alter / "bas_mappings.json").read_text())
    alter_sets = {
        entry["name"]: {
            "stance": [entry[field] for field in STANCE_FIELDS],
            "attack": [entry[field] for field in ATTACK_FIELDS],
        }
        for entry in mappings.values()
    }
    if len(alter_sets) != len(mappings):
        raise ValueError("Two of Alter's sets share a name")
    names_by_number = {int(number): entry["name"] for number, entry in mappings.items()}
    items = {
        int(item): names_by_number[number]
        for item, number in json.loads((args.alter / "item_bas.json").read_text()).items()
        if int(item) in weapons
    }

    plugin = json.loads((args.plugin / PLUGIN_FILE).read_text())
    plugin_sets = {
        f"plugin.{entry['name']}": {
            "stance": [entry["animations"][index] for index in PLUGIN_STANCE],
            "attack": [-1, -1, -1, -1, entry["animations"][PLUGIN_BLOCK]],
        }
        for entry in plugin["animationSets"]
    }
    plugin_items = {
        item: f"plugin.{name}" for name, ids in plugin["poseanims"].items() for item in ids if item in weapons
    }

    disagreements = {}
    for item, name in sorted(plugin_items.items()):
        if item not in items:
            items[item] = name
            continue
        theirs, ours = plugin_sets[name], alter_sets[items[item]]
        block_differs = theirs["attack"][-1] not in (-1, ours["attack"][-1])
        if theirs["stance"] != ours["stance"] or block_differs:
            disagreements[str(item)] = {
                "plugin_set": name,
                "plugin_stance": theirs["stance"],
                "plugin_block": theirs["attack"][-1],
            }

    sets = {**alter_sets, **plugin_sets}
    used = sorted({UNARMED, *items.values()})
    for name in used:
        unknown = sorted({clip for clip in sets[name]["stance"] + sets[name]["attack"] if clip != -1} - player_clips)
        if unknown:
            raise ValueError(f"Set {name!r} names clips that are not player clips of snapshot 430: {unknown}")

    header = {
        "source": "The stance and attack clips two open tables of 2024 and 2026 give each snapshot 430 weapon",
        "alter": {
            "repository": "https://github.com/AlterRSPS/Alter",
            "commit": args.alter_commit,
            "files": {f"data/cfg/items/renderAnimations/{f}": sha256(args.alter / f) for f in ALTER_FILES},
            "licence": (args.alter / "LICENSE").read_text(),
        },
        "plugin": {
            "repository": "https://github.com/geheur/weapon-animation-replacer",
            "commit": args.plugin_commit,
            "files": {
                f"src/main/resources/com/weaponanimationreplacer/{PLUGIN_FILE}": sha256(args.plugin / PLUGIN_FILE)
            },
            "licence": (args.plugin / "LICENSE").read_text(),
        },
        "generator": "scripts/generate-weapon-clips.py",
        "research": "docs/research/weapon-stance-sets.md",
        "note": (
            "stance holds stand, turn, walk, walk back, walk left, walk right and run, in the order the client reads "
            "them from the appearance block. attack holds Alter's accurate, aggressive, controlled and defensive "
            "clips, read as the four style buttons of the game's combat options in order (an inference from the "
            "whip and the 2h sword, see plan 13), then block. -1 means none. An item Alter lists takes Alter's set; an item only the plugin lists takes the plugin's stance "
            "clips and block clip. disagreements lists the items whose stance clips or block clip the plugin gives "
            "differently, with the plugin's values; they are not checked against snapshot 430."
        ),
        "unarmed": UNARMED,
        "disagreements": disagreements,
    }
    lines = [f'"{key}":{json.dumps(value, separators=(",", ":"))},' for key, value in header.items()]
    set_rows = [f"{json.dumps(name)}:{json.dumps(sets[name], separators=(',', ':'))}" for name in used]
    item_rows = [f'"{item}":{json.dumps(items[item])}' for item in sorted(items)]
    args.output.write_text(
        "{\n"
        + "\n".join(lines)
        + '\n"sets":{\n'
        + ",\n".join(set_rows)
        + '\n},\n"items":{\n'
        + ",\n".join(item_rows)
        + "\n}\n}\n"
    )
    print(f"{len(items)} weapons, {len(used)} sets, {len(disagreements)} disagreements written to {args.output}")


if __name__ == "__main__":
    main()
