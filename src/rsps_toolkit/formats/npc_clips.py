"""The attack, flinch and death clips that the AnotherScape models mod gives an NPC id. Nothing here imports bpy.

`scripts/generate-npc-clips.py` writes `data/npc_clips.json` from the mod and snapshot 430. The mod reads a current
cache, so whether each clip was that NPC's clip in July 2017 is not verified (ADR 0030).
"""

import json
from dataclasses import dataclass
from pathlib import Path

PATH = Path(__file__).parent.parent / "data" / "npc_clips.json"
# The order of the Combat buttons. A key that is not here comes after them, by name (Design decision 6 of issue 160).
BUTTON_ORDER = ("attack", "melee", "range", "mage", "flinch", "death")


@dataclass(frozen=True)
class NpcClip:
    key: str
    sequence: int
    runelite_name: str | None


@dataclass(frozen=True)
class NpcClipTable:
    header: dict
    # The npcName of the mod for each NPC id of the table.
    names: dict[int, str]
    # The clips of each NPC id, in the button order.
    rows: dict[int, tuple[NpcClip, ...]]

    def clips(self, npc_id: int) -> tuple[NpcClip, ...]:
        """The clips of the NPC id, or none for an NPC id that the mod does not list."""
        return self.rows.get(npc_id, ())


def button_order(key: str) -> tuple[int, str]:
    return (BUTTON_ORDER.index(key) if key in BUTTON_ORDER else len(BUTTON_ORDER), key)


def load_npc_clips(path: Path = PATH) -> NpcClipTable:
    data = json.loads(path.read_text())
    npcs = data.pop("npcs")
    rows = {
        int(npc_id): tuple(
            NpcClip(key, clip["sequence"], clip.get("runelite_name"))
            for key, clip in sorted(row["clips"].items(), key=lambda item: button_order(item[0]))
        )
        for npc_id, row in npcs.items()
    }
    return NpcClipTable(data, {int(npc_id): row["name"] for npc_id, row in npcs.items()}, rows)
