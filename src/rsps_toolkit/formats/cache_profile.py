"""Finds the appearance resources of one revision 149 cache. Nothing here imports bpy.

The cache folder is the `cache/` folder of the OpenRS2 download of snapshot 430. Kits, items and enums are config
groups 3, 10 and 8 of index 2, as RuneLite's ConfigType (IDENTKIT, ITEM, ENUM) names them. Each model is file 0 of
the group with its id in index 7. The colour palette ships with the extension.
"""

import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, NamedTuple

from . import decode
from .appearance import Kit, Palette, WornItem, assemble_body, assemble_slots, load_palette
from .appearance_preset import AppearancePreset
from .enum_definition import EnumDefinition, decode_enum
from .item_definition import ItemDefinition, decode_item
from .js5 import DATA_FILE, REFERENCE_INDEX, DamagedGroupError, Js5Store, NotInCacheError
from .kit_definition import decode_kit
from .kit_names import STYLE_ENUMS, load_kit_names
from .model import Model

REVISION = 149
# OpenRS2 snapshot that the kit, item and model ids come from.
SNAPSHOT_ID = 430
PALETTE_PATH = Path(__file__).parent.parent / "data" / "revision149-palette.json"
CONFIG_INDEX, MODEL_INDEX = 2, 7
KIT_GROUP, ENUM_GROUP, ITEM_GROUP = 3, 8, 10
SET_CACHE_FOLDER = "Set the Cache folder in the add-on preferences."


class MissingResourceError(FileNotFoundError):
    """Something the appearance needs is not in the cache folder."""


class DamagedCacheError(ValueError):
    """A config group that a catalog reads does not match its CRC32, so the cache files are damaged."""


def read_kits(store: Js5Store) -> dict[int, Kit]:
    """Decode every kit. The decoder's IndexError for a kit cut short does not say which kit, so it is raised again
    with the kit's id."""
    kits = {}
    for kit_id, data in store.files(CONFIG_INDEX, KIT_GROUP).items():
        try:
            kits[kit_id] = decode_kit(kit_id, data)
        except IndexError as error:
            raise IndexError(f"Kit {kit_id} ends early") from error
    return kits


def read_items(store: Js5Store) -> dict[int, WornItem]:
    return {item_id: item.worn for item_id, item in read_item_definitions(store).items()}


def read_item_definitions(store: Js5Store) -> dict[int, ItemDefinition]:
    files = store.files(CONFIG_INDEX, ITEM_GROUP)
    return {item_id: decode_item(item_id, data) for item_id, data in files.items()}


def read_style_enums(store: Js5Store) -> dict[int, EnumDefinition]:
    """Decode only the enums that name kit styles. The other enums of the group are not needed. An enum cut short is
    an IndexError that names the enum, as in `read_kits`."""
    files = store.files(CONFIG_INDEX, ENUM_GROUP)
    enums = {}
    for enum_id in (enum_id for pair in STYLE_ENUMS.values() for enum_id in pair):
        if enum_id not in files:
            raise NotInCacheError(f"Group {ENUM_GROUP} of the cache has no enum {enum_id}")
        try:
            enums[enum_id] = decode_enum(enum_id, files[enum_id])
        except IndexError as error:
            raise IndexError(f"Enum {enum_id} ends early") from error
    return enums


class _Kept[T](NamedTuple):
    times: tuple[int, ...]
    catalog: T


@dataclass(frozen=True)
class CacheProfile:
    """The cache's catalogs, each parsed again when the cache's data file, config index or reference index has a new
    modified time, so a cache replaced in the same folder is seen at the next use (issue 29, decision 3)."""

    cache_folder: Path
    _kept: dict[str, _Kept[Any]] = field(default_factory=dict, compare=False, repr=False)

    def _config_files(self) -> list[Path]:
        files = [
            self.cache_folder / DATA_FILE,
            self.cache_folder / f"main_file_cache.idx{CONFIG_INDEX}",
            self.cache_folder / f"main_file_cache.idx{REFERENCE_INDEX}",
        ]
        for path in files:
            if not path.is_file():
                raise MissingResourceError(f"Missing {path}. {SET_CACHE_FOLDER}")
        return files

    def _kept_unless_changed[T](self, name: str, load: Callable[[Js5Store], T], groups: tuple[int, ...]) -> T:
        """The catalog parsed from a new store, which reads the cache's reference tables again, whenever the files'
        modified times change. A group or definition the cache lacks becomes a MissingResourceError that names the
        preference.

        When the load fails in any other way, the config `groups` that the catalog reads are checked against their
        CRC32 values. A group that does not match, or an index 2 reference table that cannot be read, becomes a
        DamagedCacheError. When all match, a group that does not decompress is a DamagedCacheError too, because the
        stored bytes are the ones the cache was written with. Any other error passes unchanged, such as the IndexError
        of a definition cut short. A check that cannot find a group lets the load's own error pass. The check runs
        only after a load fails, so a cache that loads is never read a second time."""
        times = tuple(path.stat().st_mtime_ns for path in self._config_files())
        kept = self._kept.get(name)
        if kept is not None and kept.times == times:
            return kept.catalog
        store = Js5Store(self.cache_folder)
        try:
            catalog = load(store)
        except NotInCacheError as error:
            raise MissingResourceError(f"{error} in {self.cache_folder}. {SET_CACHE_FOLDER}") from error
        except (DamagedCacheError, MissingResourceError):
            raise
        except (ValueError, IndexError, OSError, EOFError, zlib.error) as error:
            for group in groups:
                try:
                    store.check(CONFIG_INDEX, group)
                except DamagedGroupError as damage:
                    raise DamagedCacheError(
                        f"{damage}, in the cache at {self.cache_folder}. Download the cache again."
                    ) from error
                except (LookupError, OSError):
                    raise error from None
            if isinstance(error, (OSError, EOFError, zlib.error)):
                listed = " or ".join(str(group) for group in groups)
                raise DamagedCacheError(
                    f"{error}: config group {listed} does not decompress although its CRC32 matches, in the cache at "
                    f"{self.cache_folder}. Download the cache again."
                ) from error
            raise
        self._kept[name] = _Kept(times, catalog)
        return catalog

    @property
    def kits(self) -> dict[int, Kit]:
        return self._kept_unless_changed("kits", read_kits, (KIT_GROUP,))

    @property
    def kit_names(self) -> dict[int, str]:
        # Kits are named by the models they use, so a changed kit group can rename them as well as changed enums can.
        # The kits are read only inside the load, after the files' times are taken, so names built from kits that
        # changed meanwhile are kept under the older time and named again at the next use.
        return self._kept_unless_changed(
            "kit_names", lambda store: load_kit_names(read_style_enums(store), self.kits), (ENUM_GROUP, KIT_GROUP)
        )

    @property
    def item_definitions(self) -> dict[int, ItemDefinition]:
        return self._kept_unless_changed("item_definitions", read_item_definitions, (ITEM_GROUP,))

    @property
    def items(self) -> dict[int, WornItem]:
        return self._kept_unless_changed("items", read_items, (ITEM_GROUP,))

    @cached_property
    def palette(self) -> Palette:
        if not PALETTE_PATH.is_file():
            raise MissingResourceError(f"Missing {PALETTE_PATH}. Reinstall the extension.")
        return load_palette(PALETTE_PATH)

    def load_model(self, model_id: int) -> Model:
        """Read and decode one model with the revision 149 profile."""
        return decode(self.model_bytes(model_id), profile="osrs-149")

    def model_bytes(self, model_id: int) -> bytes:
        """Return the model file exactly as the cache stores it. This needs no reference table, so it reads the cache
        files each time and keeps nothing."""
        try:
            store = Js5Store(self.cache_folder)
        except FileNotFoundError as error:
            raise MissingResourceError(f"{error}. {SET_CACHE_FOLDER}") from error
        try:
            return store.container(MODEL_INDEX, model_id)
        except (NotInCacheError, FileNotFoundError) as error:
            raise MissingResourceError(f"Model {model_id} is not in {self.cache_folder}. {SET_CACHE_FOLDER}") from error

    def assemble(self, preset: AppearancePreset) -> Model:
        """The preset's unlit body. A kit, item or model that the cache lacks is an error."""
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


def shared_profile(cache_folder: Path) -> CacheProfile:
    """The one profile kept for the cache folder until `clear_shared_profiles`, which unregistering the add-on calls,
    so the panel, Create, Update and held item bakes parse each catalog once until the cache changes (issue 29,
    decisions 2 and 3)."""
    return _shared.setdefault(cache_folder, CacheProfile(cache_folder))


def clear_shared_profiles() -> None:
    _shared.clear()
