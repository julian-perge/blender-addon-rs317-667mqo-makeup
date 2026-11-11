"""Which equipment slot each worn item uses and which kit slots it hides. Nothing here imports bpy.

Snapshot 430 items carry no wear positions, so `data/item_wear.json` takes them from OpenRS2 cache 2757 (2026) by
item id; `scripts/generate-item-wear.py` writes it and records both caches. An item it does not list has no slot.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PATH = Path(__file__).parent.parent / "data" / "item_wear.json"
# Statuses of items whose worn model ids differ between snapshot 430 and the recent cache.
MODELS_CHANGED = frozenset({"models_changed", "renamed_and_models_changed"})


@dataclass(frozen=True)
class ItemWear:
    slot_of: dict[int, int]
    hides: dict[int, frozenset[int]]
    status: dict[int, str]

    def models_changed(self, item_id: int) -> bool:
        """True when the recent cache gives the item other worn models, so its hidden slots may not fit the old ones."""
        return self.status.get(item_id) in MODELS_CHANGED


def load_item_wear(path: Path = PATH) -> ItemWear:
    items = {int(k): v for k, v in json.loads(path.read_text())["items"].items()}
    return ItemWear(
        {i: v["slot"] for i, v in items.items()},
        {i: frozenset(v["hides"]) for i, v in items.items()},
        {i: v["status"] for i, v in items.items()},
    )
