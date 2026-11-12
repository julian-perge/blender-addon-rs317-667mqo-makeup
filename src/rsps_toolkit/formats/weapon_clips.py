"""The stand, walk, run and attack clips that two open tables give each weapon. Nothing here imports bpy.

The revision 149 client reads a player's stance clips from the appearance block the server sends, and no cache holds
a weapon to clip table (evidence: `docs/research/weapon-stance-sets.md`, sections 1 and 3). `data/weapon_clips.json`
takes them from tables of 2024 and 2026, so whether the game gave each weapon the same clips in July 2017 is not
verified. `scripts/generate-weapon-clips.py` writes it and records both sources and their licences.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PATH = Path(__file__).parent.parent / "data" / "weapon_clips.json"
# The stance clips are in the order the client reads them from the appearance block (research note, section 1).
STAND, TURN, WALK, WALK_BACK, WALK_LEFT, WALK_RIGHT, RUN = range(7)
# The attack clips are Alter's accurate, aggressive, controlled and defensive clips, then block. Plan 13 reads the
# four as the style buttons of the game's combat options in order, an inference from the whip and the 2h sword.
BLOCK = 4


@dataclass(frozen=True)
class WeaponClips:
    stance: tuple[int, ...]
    # A style button the weapon lacks, or a clip neither table gives, is -1.
    attack: tuple[int, ...]


@dataclass(frozen=True)
class WeaponClipTable:
    unarmed: WeaponClips
    # Every weapon either table lists, including those that use the unarmed clips.
    items: dict[int, WeaponClips]

    def lists(self, item_id: int) -> bool:
        return item_id in self.items

    def clips(self, item_id: int) -> WeaponClips:
        """The weapon's clips, or the unarmed ones for a weapon neither table lists, which is the user's choice."""
        return self.items.get(item_id, self.unarmed)

    def is_stance_clip(self, sequence_id: int) -> bool:
        """True when the clip is a stance clip of the unarmed set or of any weapon's set."""
        return sequence_id in self.unarmed.stance or any(sequence_id in clips.stance for clips in self.items.values())


def load_weapon_clips(path: Path = PATH) -> WeaponClipTable:
    data = json.loads(path.read_text())
    sets = {name: WeaponClips(tuple(row["stance"]), tuple(row["attack"])) for name, row in data["sets"].items()}
    return WeaponClipTable(sets[data["unarmed"]], {int(item): sets[name] for item, name in data["items"].items()})
