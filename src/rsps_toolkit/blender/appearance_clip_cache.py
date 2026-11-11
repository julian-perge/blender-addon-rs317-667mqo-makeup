"""The cache's player clips: a clip by its sequence id, its RuneLite name, and whether it holds items."""

import functools

from ..animation.clip import CacheClip, load_clip_names, read_sequence
from ..formats.js5 import Js5Store
from . import appearance_held, preferences


@functools.cache
def clip_names() -> dict[int, str]:
    return load_clip_names()


def clip_label(sequence_id: int) -> str:
    return f"{clip_names().get(sequence_id, 'Sequence')} ({sequence_id})"


def cache_clip(sequence_id: int) -> CacheClip:
    """The sequence in the cache folder the preferences name. Each folder's store is kept, so its tables are read once."""
    folder = preferences.cache_folder()
    if folder is None:
        raise ValueError("Set the cache folder in the add-on preferences to bake clips from the cache")
    if str(folder) not in _stores:
        _stores[str(folder)] = Js5Store(folder)
    return CacheClip(_stores[str(folder)], sequence_id)


_stores: dict[str, Js5Store] = {}


def holds_items(sequence_id: int) -> bool:
    """True when the cache's sequence sets a held item, which the client shows only when it plays as an action.

    The panel asks on every redraw, so each answer is kept; a sequence that cannot be read counts as holding none.
    """
    key = (str(preferences.cache_folder()), sequence_id)
    if key not in _holds:
        try:
            sequence = read_sequence(cache_clip(sequence_id))
        except (OSError, LookupError, ValueError):
            return False
        _holds[key] = appearance_held.held_items(sequence, action=True) is not None
    return _holds[key]


_holds: dict[tuple[str, int], bool] = {}
