"""Decoders for the revision-149 frame map, frame and sequence files, and the client's per-tick frame counter.

The sequence decoder and the frame counter follow the revision-149 client (gamepack-149.jar) as read with
`javap -c -p`: offsets below are inside `jg.r(fe,int,int)` for the sequence opcodes and inside `ap.fb(ca,int,int)` for
the counter. Both are also checked by running the unchanged client in tests/fixtures/SequenceReference.java.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .bundle import Frame, FrameMap

# The client's sequence loader du.j reads opcodes until a 0 and hands each to jg.r, whose branches cover 1 to 13. Any
# other opcode falls through jg.r at offset 697 without reading a byte, so the client would read its operands as the
# next opcodes; this decoder refuses it instead.
KNOWN_OPCODES = frozenset(range(1, 14))


@dataclass(frozen=True)
class SequenceDefinition:
    """A decoded sequence. Defaults are the values jg's constructor stores (offsets 4 to 75) before any opcode.

    When the file lacks opcode 9 or 10, the constructor's -1 is replaced by the loader's follow-up jg.v (offsets 0 to
    116): 2 when the sequence has an interleave list and 0 otherwise.
    """

    # The opcodes in the order the file lists them.
    opcodes: tuple[int, ...]
    # Opcode 1: each frame is (group id, file id) in the frame index and lasts this many client ticks.
    frames: tuple[tuple[int, int], ...] = ()
    durations: tuple[int, ...] = ()
    # Opcode 2 (jg.p): how many frames an action sequence steps back after its last frame; -1 stops it instead.
    loop_offset: int = -1
    # Opcode 3 (jg.m): the frame map entries this sequence keeps when it plays over another one.
    interleave: tuple[int, ...] | None = None
    # Opcode 4 (jg.u).
    stretches: bool = False
    # Opcode 5 (jg.g).
    forced_priority: int = 5
    # Opcodes 6 and 7 (jg.k and jg.t): the held items the sequence substitutes, -1 for none.
    left_hand_item: int = -1
    right_hand_item: int = -1
    # Opcode 8 (jg.c): how many times an action sequence may pass its last frame before it stops.
    max_loops: int = 99
    # Opcodes 9 and 10 (jg.o and jg.x).
    precedence_animating: int = 0
    priority: int = 0
    # Opcode 11 (jg.f).
    reply_mode: int = 2
    # Opcode 12 (jg.l): (group id, file id) pairs, as in the frame list.
    chat_frames: tuple[tuple[int, int], ...] | None = None
    # Opcode 13 (jg.w): one 24-bit value per entry.
    frame_sounds: tuple[int, ...] | None = None


class _Reader:
    def __init__(self, data: bytes, kind: str) -> None:
        self.data = data
        self.kind = kind
        self.pos = 0

    def u8(self) -> int:
        self._need(1)
        self.pos += 1
        return self.data[self.pos - 1]

    def u16(self) -> int:
        self._need(2)
        self.pos += 2
        return int.from_bytes(self.data[self.pos - 2 : self.pos], "big")

    def u24(self) -> int:
        self._need(3)
        self.pos += 3
        return int.from_bytes(self.data[self.pos - 3 : self.pos], "big")

    def short_smart(self) -> int:
        self._need(1)
        if self.data[self.pos] < 128:
            return self.u8() - 64
        return self.u16() - 49152

    def _need(self, count: int) -> None:
        if self.pos + count > len(self.data):
            raise ValueError(f"The {self.kind} file ends early: it has {len(self.data)} bytes")


def decode_frame_map(data: bytes) -> FrameMap:
    reader = _Reader(data, "frame map")
    count = reader.u8()
    types = tuple(reader.u8() for _ in range(count))
    sizes = [reader.u8() for _ in range(count)]
    labels = tuple(tuple(reader.u8() for _ in range(size)) for size in sizes)
    if reader.pos != len(data):
        raise ValueError(f"Frame map has {len(data) - reader.pos} unread bytes")
    return FrameMap(types, labels)


def decode_frame(data: bytes, frame_map: FrameMap) -> Frame:
    """Decode a frame against its map, as the client does.

    Before each transform whose type is not 0, the nearest earlier pivot (type 0) that the frame skipped since its
    previous transform is inserted with zero offsets.
    """
    flags = _Reader(data, "frame")
    map_id = flags.u16()
    length = flags.u8()
    values = _Reader(data, "frame")
    values.pos = 3 + length
    indices: list[int] = []
    xs: list[int] = []
    ys: list[int] = []
    zs: list[int] = []
    last = -1
    for i in range(length):
        flag = flags.u8()
        if flag <= 0:
            continue
        if i >= len(frame_map.types):
            raise ValueError(f"The frame moves transform {i}, its frame map has {len(frame_map.types)}")
        kind = frame_map.types[i]
        if kind != 0:
            for j in range(i - 1, last, -1):
                if frame_map.types[j] == 0:
                    indices.append(j)
                    xs.append(0)
                    ys.append(0)
                    zs.append(0)
                    break
        default = 128 if kind == 3 else 0
        indices.append(i)
        for bit, out in ((1, xs), (2, ys), (4, zs)):
            out.append(values.short_smart() if flag & bit else default)
        last = i
    if values.pos != len(data):
        raise ValueError(f"Frame has {len(data) - values.pos} unread bytes")
    return Frame(map_id, tuple(indices), tuple(xs), tuple(ys), tuple(zs))


def decode_sequence(data: bytes) -> SequenceDefinition:
    """Decode a sequence file as the client's jg.r does, refusing opcodes the client does not read."""
    reader = _Reader(data, "sequence")
    opcodes: list[int] = []
    fields: dict[str, Any] = {}
    while (opcode := reader.u8()) != 0:
        if opcode not in KNOWN_OPCODES:
            raise ValueError(f"The sequence uses opcode {opcode}, which the revision-149 client does not read")
        opcodes.append(opcode)
        if opcode == 1:
            # Offsets 242 to 248 read a u16 count, then 38 to 153 read the durations, the file ids and the group ids,
            # each a u16.
            count = reader.u16()
            fields["durations"] = tuple(reader.u16() for _ in range(count))
            files = [reader.u16() for _ in range(count)]
            fields["frames"] = tuple(zip((reader.u16() for _ in range(count)), files, strict=True))
        elif opcode == 2:
            fields["loop_offset"] = reader.u16()  # offsets 205 to 215
        elif opcode == 3:
            # Offsets 446 to 451 read a u8 count and 717 to 728 one u8 per entry; 299 to 307 append 9999999.
            fields["interleave"] = tuple(reader.u8() for _ in range(reader.u8()))
        elif opcode == 4:
            fields["stretches"] = True  # offsets 350 to 352, no operand
        elif opcode == 5:
            fields["forced_priority"] = reader.u8()  # offsets 756 to 765
        elif opcode == 6:
            fields["left_hand_item"] = reader.u16()  # offsets 170 to 180
        elif opcode == 7:
            fields["right_hand_item"] = reader.u16()  # offsets 397 to 407
        elif opcode == 8:
            fields["max_loops"] = reader.u8()  # offsets 456 to 465
        elif opcode == 9:
            fields["precedence_animating"] = reader.u8()  # offsets 227 to 236
        elif opcode == 10:
            fields["priority"] = reader.u8()  # offsets 515 to 524
        elif opcode == 11:
            fields["reply_mode"] = reader.u8()  # offsets 480 to 489
        elif opcode == 12:
            # Offsets 577 to 582 read a u8 count, 358 to 367 the file ids and 664 to 687 the group ids, each a u16.
            count = reader.u8()
            files = [reader.u16() for _ in range(count)]
            fields["chat_frames"] = tuple(zip((reader.u16() for _ in range(count)), files, strict=True))
        else:
            # Opcode 13: offsets 746 to 751 read a u8 count and 771 to 783 one 24-bit value (fe.ae) per entry.
            fields["frame_sounds"] = tuple(reader.u24() for _ in range(reader.u8()))
    if reader.pos != len(data):
        raise ValueError(f"The sequence has {len(data) - reader.pos} bytes after its end marker")
    fallback = 0 if fields.get("interleave") is None else 2
    fields.setdefault("precedence_animating", fallback)
    fields.setdefault("priority", fallback)
    return SequenceDefinition(tuple(opcodes), **fields)


def _frames_per_tick(sequence: SequenceDefinition, *, action: bool) -> Iterator[int]:
    """The frame shown at tick 0, 1, 2 and on, from frame 0 with its tick counter at 0, as ap.fb advances it.

    Each tick the counter goes up by one; when it passes the frame's duration the counter becomes 1 and the next frame
    starts (pose: offsets 2683 to 2692 and 1739 to 1787; action: 2553 to 2615, 675 to 679 and 2636 to 2645). Frame 0
    starts with the counter at 0, so it shows one tick longer than its duration. Past the last frame a pose sequence
    returns to frame 0 with the counter at 0 (offsets 1820 to 1833, 168 to 170 and 1852 to 1854), so this holds on
    every cycle, and the pose sequence ignores its loop offset. An action sequence instead steps back by its loop
    offset and counts a loop (offsets 2659 to 2707), and stops when it has looped `max_loops` times (2710 to 2748) or
    the step leaves the frame list (2754 to 2804 and 2297 to 2309); the frame it steps back to starts with the counter
    at 1, so in an action only the very first frame gets the extra tick. For a pose sequence this yields one full
    cycle, which then repeats; for an action sequence it yields every tick until the sequence stops.
    """
    count = len(sequence.frames)
    if count == 0:
        raise ValueError("The sequence has no frames")
    frame, counter, loops = 0, 0, 0
    while True:
        yield frame
        counter += 1
        if counter > sequence.durations[frame]:
            counter = 1
            frame += 1
        if frame < count:
            continue
        if not action:
            return
        frame -= sequence.loop_offset
        loops += 1
        if loops >= sequence.max_loops or not 0 <= frame < count:
            return


def frame_schedule(sequence: SequenceDefinition, *, action: bool) -> tuple[tuple[int, int], ...]:
    """The frames in the order they show, each with how many ticks it shows in a row.

    For a pose sequence this is one cycle, which repeats; for an action sequence it runs until the sequence stops.
    """
    runs: list[tuple[int, int]] = []
    for frame in _frames_per_tick(sequence, action=action):
        if runs and runs[-1][0] == frame:
            runs[-1] = (frame, runs[-1][1] + 1)
        else:
            runs.append((frame, 1))
    return tuple(runs)
