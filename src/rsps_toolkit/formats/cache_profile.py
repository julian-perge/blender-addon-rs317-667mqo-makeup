"""Finds the appearance resources of one revision 149 cache dump. Nothing here imports bpy.

The dump folder is the dumper's output for OpenRS2 snapshot 430. Kits come from the dumper's `kits` target, items
from its `items` target and model bytes from `dump_index/models`. The colour palette ships with the extension.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, NamedTuple

from . import decode
from .appearance import Kit, Palette, WornItem, assemble_body, assemble_slots, load_items, load_kits, load_palette
from .appearance_preset import AppearancePreset
from .enum_definition import EnumDefinition
from .kit_names import load_kit_names
from .model import Model

REVISION = 149
PALETTE_PATH = Path(__file__).parent.parent / "data" / "revision149-palette.json"


class MissingResourceError(FileNotFoundError):
    """A file the appearance needs is not in the dump folder."""


def _load_enums(path: Path) -> dict[int, EnumDefinition]:
    """Read the dumper's `enums/Enums.json`."""
    return {
        row["id"]: EnumDefinition(
            id=row["id"],
            keys=tuple(row.get("keys", ())),
            int_values=tuple(row.get("intVals", ())),
            string_values=tuple(row.get("stringVals", ())),
        )
        for row in json.loads(path.read_text())
    }


def _require(path: Path, hint: str) -> Path:
    if not path.is_file():
        raise MissingResourceError(f"Missing {path}. {hint}")
    return path


class _Kept[T](NamedTuple):
    times: tuple[int, ...]
    catalog: T


@dataclass(frozen=True)
class CacheProfile:
    """The dump's catalogs, each parsed again when one of the files it is read from has a new modified time, so a
    re-dump into the same folder is seen at the next use (issue 29, decision 3)."""

    dump_root: Path
    _kept: dict[str, _Kept[Any]] = field(default_factory=dict, compare=False, repr=False)

    def _kept_unless_changed[T](self, name: str, paths: Sequence[Path], load: Callable[[], T]) -> T:
        times = tuple(path.stat().st_mtime_ns for path in paths)
        kept = self._kept.get(name)
        if kept is not None and kept.times == times:
            return kept.catalog
        catalog = load()
        self._kept[name] = _Kept(times, catalog)
        return catalog

    def _kits_file(self) -> Path:
        hint = "Run the dumper's `kits` target to create kits/KitDefinitions.json."
        return _require(self.dump_root / "kits" / "KitDefinitions.json", hint)

    @property
    def kits(self) -> dict[int, Kit]:
        path = self._kits_file()
        return self._kept_unless_changed("kits", [path], lambda: load_kits(path))

    @property
    def kit_names(self) -> dict[int, str]:
        enums = _require(self.dump_root / "enums" / "Enums.json", "Run the dumper's `enums` target.")
        # Kits are named by the models they use, so a re-dumped kit catalog can rename them as well as new enums can.
        # The kits are read only inside the load, after both files' times are taken, so names built from kits that a
        # re-dump replaced meanwhile are kept under the older time and named again at the next use.
        return self._kept_unless_changed(
            "kit_names", [enums, self._kits_file()], lambda: load_kit_names(_load_enums(enums), self.kits)
        )

    @property
    def items(self) -> dict[int, WornItem]:
        path = _require(self.dump_root / "items" / "ItemDefinitions.json", "Run the dumper's `items` target.")
        return self._kept_unless_changed("items", [path], lambda: load_items(path))

    @cached_property
    def palette(self) -> Palette:
        return load_palette(_require(PALETTE_PATH, "The extension's colour palette is missing."))

    def load_model(self, model_id: int) -> Model:
        path = _require(
            self.dump_root / "dump_index" / "models" / f"{model_id}.dat", f"Model {model_id} is not dumped."
        )
        return decode(path.read_bytes(), profile="osrs-149")

    def assemble(self, preset: AppearancePreset) -> Model:
        """The preset's unlit body. A kit, item or model that the dump lacks is an error."""
        return assemble_body(
            preset.equipment,
            self.kits,
            self.load_model,
            preset.colours,
            self.palette,
            self.items,
            female=preset.female,
        )

    def assemble_slots(
        self, preset: AppearancePreset, equipment: Sequence[int] | None = None
    ) -> tuple[Model, dict[int, range]]:
        """`assemble`, with the faces each slot supplied, for the preset's equipment or `equipment` in its place."""
        return assemble_slots(
            preset.equipment if equipment is None else equipment,
            self.kits,
            self.load_model,
            preset.colours,
            self.palette,
            self.items,
            female=preset.female,
        )


_shared: dict[Path, CacheProfile] = {}


def shared_profile(dump_root: Path) -> CacheProfile:
    """The one profile kept for the dump folder until `clear_shared_profiles`, which unregistering the add-on calls, so
    the panel, Create, Update and held item bakes parse each catalog once until its file changes (issue 29, decisions 2
    and 3)."""
    return _shared.setdefault(dump_root, CacheProfile(dump_root))


def clear_shared_profiles() -> None:
    _shared.clear()
