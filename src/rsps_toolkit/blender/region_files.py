"""A saved region: one imported region in its own .blend, with the key of its import (ADR 0033).

An import of a region takes seconds, and an append of the saved region takes about a second. The key names every input
of the import, so a file from other inputs is found stale before anything is appended.
"""

import functools
import hashlib
import json
import os
from pathlib import Path

import bpy

from ..formats.js5 import DATA_FILE
from ..formats.region import KEYS_FOLDER, region_id

# The folder of the add-on, whose files the key covers.
ADD_ON = Path(__file__).parent.parent
KEY_PREFIX = "rs_region_key "
KEY_VERSION = 1


@functools.cache
def add_on_hash() -> str:
    """The SHA-256 of every file of the add-on with its path: the code, the manifest with the version and the data
    tables. A script can run the add-on from a working tree, where the version does not change with the code."""
    digest = hashlib.sha256()
    for path in sorted(p for p in ADD_ON.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(path.relative_to(ADD_ON).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def region_key(folder: Path, x: int, y: int, brightness: float, decoration_clearance: float) -> str:
    """The key of an import of region (x, y) as JSON text: the files of the add-on, the size and the modified time of
    the cache data file and of the key file of the region, and the arguments of the import. Two imports with the same
    key make the same region."""
    return json.dumps(
        {
            "key_version": KEY_VERSION,
            "add_on": add_on_hash(),
            "cache": _file_state(folder / DATA_FILE),
            "landscape_key": _file_state(folder.parent / KEYS_FOLDER / f"{region_id(x, y)}.txt"),
            "x": x,
            "y": y,
            "brightness": brightness,
            "decoration_clearance": decoration_clearance,
        },
        sort_keys=True,
    )


def _file_state(path: Path) -> list[int] | None:
    """The size and the modified time of a file, or None when it does not exist."""
    if not path.is_file():
        return None
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def _key_name(key: str) -> str:
    """The name of the text datablock that holds the key. Blender lists the names of a .blend without loading its
    data, so the name alone tells whether the file fits."""
    return KEY_PREFIX + hashlib.sha256(key.encode()).hexdigest()[:32]


def save_region(collection: bpy.types.Collection, path: Path, key: str) -> None:
    """Write the region collection of an import, with everything it uses, and the key to a new .blend at `path`. The
    open file is not changed.

    The file is written beside `path` first and then moved there, so that another Blender that reads `path` at the
    same time gets the old file or the new one, and never a part of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = bpy.data.texts.new(_key_name(key))
    text.write(key)
    partial = path.with_name(f"{path.stem}.{os.getpid()}.partial.blend")
    try:
        bpy.data.libraries.write(str(partial), {collection, text}, fake_user=True)
        os.replace(partial, path)
    finally:
        bpy.data.texts.remove(text)
        partial.unlink(missing_ok=True)


def append_region(parent: bpy.types.Collection, path: Path, key: str) -> bpy.types.Collection | None:
    """Append the region of the saved region at `path` and link it to `parent`, when the file was saved with `key`.
    In every other case nothing changes and the result is None: no file, a file with another key, or a file that
    Blender cannot read. The caller then imports the region and saves it again."""
    if not path.is_file():
        return None
    record = json.loads(key)
    name = f"Region {record['x']}_{record['y']}"
    libraries = set(bpy.data.libraries)
    loaded: list = []
    try:
        with bpy.data.libraries.load(str(path)) as (saved, appended):  # pyrefly: ignore[bad-context-manager]
            if _key_name(key) in saved.texts and name in saved.collections:
                # Blender puts the appended collection in the place of its name when the block ends.
                appended.collections = loaded = [name]
    except OSError:
        pass
    regions = [item for item in loaded if isinstance(item, bpy.types.Collection)]
    # The load leaves a library datablock for the file, which an append does not use.
    for library in set(bpy.data.libraries) - libraries:
        bpy.data.libraries.remove(library)
    if not regions:
        return None
    parent.children.link(regions[0])
    return regions[0]
