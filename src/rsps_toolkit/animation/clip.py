"""Poses a model through the frames of one revision-149 sequence, read from a clip folder or from the js5 cache."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..formats.js5 import Js5Store
from ..formats.model import Vertex
from .frames import SequenceDefinition, decode_frame, decode_frame_map, decode_sequence
from .poses import evaluate_frame

# Where snapshot 430 keeps clip data: frames are the files of index 0 groups, each frame map is the one file of the
# index 1 group with the map's id, and sequences are the files of index 2 group 12.
FRAME_INDEX, FRAME_MAP_INDEX, CONFIG_INDEX, SEQUENCE_GROUP = 0, 1, 2, 12
NAMES_PATH = Path(__file__).parent.parent / "data" / "animation_names.json"


class ClipSource(Protocol):
    def sequence_bytes(self) -> bytes: ...
    def frame_bytes(self, group: int, file: int) -> bytes: ...
    def frame_map_bytes(self, map_id: int) -> bytes: ...
    def record(self) -> dict[str, object]: ...


def load_clip_names(path: Path = NAMES_PATH) -> dict[int, str]:
    """The sequences a player can play, by id, with RuneLite's names, as `scripts/generate-animation-names.py` wrote."""
    return {int(k): v for k, v in json.loads(path.read_text())["clips"].items()}


def clip_from_record(record: dict) -> "ClipSource":
    """The clip a `record()` describes: a cache folder and sequence id, or a clip folder."""
    if "sequence" in record:
        return CacheClip(Js5Store(Path(record["cache"])), record["sequence"])
    return FolderClip(Path(record["folder"]))


@dataclass(frozen=True)
class FolderClip:
    """A folder written by `tests/fixtures/animation149/export_clip.py`: sequence.dat, frames/ and maps/."""

    folder: Path

    def sequence_bytes(self) -> bytes:
        return _read(self.folder / "sequence.dat")

    def frame_bytes(self, group: int, file: int) -> bytes:
        return _read(self.folder / "frames" / f"{group}_{file}.dat")

    def frame_map_bytes(self, map_id: int) -> bytes:
        return _read(self.folder / "maps" / f"{map_id}.dat")

    def record(self) -> dict[str, object]:
        return {"folder": str(self.folder.resolve())}


@dataclass
class CacheClip:
    """One sequence of a js5 cache, its frames and frame maps read on demand, each frame group once."""

    store: Js5Store
    sequence_id: int
    _groups: dict[int, dict[int, bytes]] = field(default_factory=dict)

    def sequence_bytes(self) -> bytes:
        sequences = self.store.files(CONFIG_INDEX, SEQUENCE_GROUP)
        if self.sequence_id not in sequences:
            raise LookupError(f"The cache has no sequence {self.sequence_id}")
        return sequences[self.sequence_id]

    def frame_bytes(self, group: int, file: int) -> bytes:
        if group not in self._groups:
            self._groups[group] = self.store.files(FRAME_INDEX, group)
        if file not in self._groups[group]:
            raise LookupError(f"Frame group {group} of the cache has no frame {file}")
        return self._groups[group][file]

    def frame_map_bytes(self, map_id: int) -> bytes:
        return next(iter(self.store.files(FRAME_MAP_INDEX, map_id).values()))

    def record(self) -> dict[str, object]:
        return {"cache": str(self.store.folder.resolve()), "sequence": self.sequence_id}


@dataclass(frozen=True)
class PosedFrame:
    # The frame's duration as the sequence file stores it; frames.frame_schedule gives how long the client shows it.
    ticks: int
    vertices: tuple[Vertex, ...]
    # Face alphas after the frame's alpha transforms, when face labels were given.
    alphas: tuple[int, ...] | None = None


def source_of(clip: "ClipSource | Path") -> ClipSource:
    return FolderClip(clip) if isinstance(clip, Path) else clip


def read_sequence(clip: ClipSource | Path) -> SequenceDefinition:
    return decode_sequence(source_of(clip).sequence_bytes())


def pose_vertices(
    vertices: tuple[Vertex, ...],
    labels: tuple[int, ...],
    clip: ClipSource | Path,
    face_labels: tuple[int, ...] | None = None,
    alphas: tuple[int, ...] = (),
) -> tuple[PosedFrame, ...]:
    """Pose vertices that carry vertex skin labels.

    With `face_labels` and the faces' rest `alphas`, each frame also holds the face alphas its alpha transforms
    (type 5) give, as the client computes them from the rest alphas.
    """
    source = source_of(clip)
    sequence = decode_sequence(source.sequence_bytes())
    if not sequence.frames:
        raise ValueError("The clip's sequence has no frames")
    maps: dict[int, bytes] = {}
    result = []
    for (group, file), ticks in zip(sequence.frames, sequence.durations, strict=True):
        data = source.frame_bytes(group, file)
        map_id = int.from_bytes(data[0:2], "big")
        if map_id not in maps:
            maps[map_id] = source.frame_map_bytes(map_id)
        frame_map = decode_frame_map(maps[map_id])
        frame = decode_frame(data, frame_map)
        posed, faded = evaluate_frame(vertices, labels, alphas, face_labels, frame, frame_map)
        result.append(PosedFrame(ticks, posed, faded if face_labels is not None else None))
    return tuple(result)


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"The clip folder lacks {path.name}: {path}")
    return path.read_bytes()
