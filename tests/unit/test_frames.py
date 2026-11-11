import itertools
import json
from pathlib import Path

import pytest

from rsps_toolkit.animation.bundle import FrameMap
from rsps_toolkit.animation.frames import (
    decode_frame,
    decode_frame_map,
    decode_sequence,
    frame_schedule,
)

ROOT = Path(__file__).parents[1] / "fixtures/animation149"
FIXTURES = ROOT / "walk"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())
# The unchanged revision-149 client's decoding (du.j) of every file in animation149/sequences and its per-tick frame
# counters (ap.fb), recorded by record_sequences.py.
CLIENT = json.loads((ROOT / "sequences.json").read_text())
TIMING = {(case["sequence"], case["mode"]): case["frames"] for case in CLIENT["timing"]}
SEQUENCE_IDS = sorted(int(name) for name in CLIENT["sequences"])


def sequence(sequence_id: int):
    return decode_sequence((ROOT / f"sequences/{sequence_id}.dat").read_bytes())


def packed(pairs):
    return None if pairs is None else [group << 16 | file for group, file in pairs]


def test_the_walk_sequence_has_eight_frames_of_six_ticks_in_group_207():
    result = decode_sequence((FIXTURES / "sequence.dat").read_bytes())
    assert result.durations == (6,) * 8
    assert result.frames == tuple((207, file) for file in range(357, 365))
    assert [(f["group"], f["file"]) for f in MANIFEST["frames"]] == list(result.frames)


def test_the_sample_uses_every_opcode_the_client_reads():
    # Opcodes 1 to 13 are the branches of jg.r (offsets 0 to 790); each must appear in at least one sample file.
    seen = set()
    for sequence_id in SEQUENCE_IDS:
        seen |= set(sequence(sequence_id).opcodes)
    assert seen == set(range(1, 14))


@pytest.mark.parametrize("sequence_id", SEQUENCE_IDS)
def test_every_sample_sequence_decodes_as_the_client_does(sequence_id):
    client = CLIENT["sequences"][str(sequence_id)]
    result = sequence(sequence_id)
    assert packed(result.frames) == client["frames"]
    assert list(result.durations) == client["durations"]
    assert result.loop_offset == client["loop_offset"]
    # The client ends its interleave list with the sentinel 9999999 (jg.r offset 299 to 307).
    assert (None if result.interleave is None else [*result.interleave, 9999999]) == client["interleave"]
    assert result.stretches == client["stretches"]
    assert result.forced_priority == client["forced_priority"]
    assert result.left_hand_item == client["left_hand_item"]
    assert result.right_hand_item == client["right_hand_item"]
    assert result.max_loops == client["max_loops"]
    assert result.precedence_animating == client["precedence_animating"]
    assert result.priority == client["priority"]
    assert result.reply_mode == client["reply_mode"]
    assert packed(result.chat_frames) == client["chat_frames"]
    assert (None if result.frame_sounds is None else list(result.frame_sounds)) == client["frame_sounds"]


@pytest.mark.parametrize("clip", ["walk", "idle", "run"])
def test_the_player_clips_have_no_held_items_and_only_a_frame_list(clip):
    result = decode_sequence((ROOT / clip / "sequence.dat").read_bytes())
    assert result.opcodes == (1,)
    assert (result.left_hand_item, result.right_hand_item) == (-1, -1)


def test_an_opcode_the_client_does_not_read_is_refused():
    # One frame of 6 ticks, then opcode 14, which jg.r skips without reading (offset 697 to 790).
    with pytest.raises(ValueError, match="opcode 14"):
        decode_sequence(bytes.fromhex("0100010006000100020e00"))


def test_a_sequence_without_its_end_marker_is_refused():
    with pytest.raises(ValueError, match="sequence file ends early"):
        decode_sequence(bytes.fromhex("01000100060001000204"))


def frame_map():
    return decode_frame_map((FIXTURES / "maps/0.dat").read_bytes())


def test_the_frame_map_has_a_label_list_per_transform():
    result = frame_map()
    assert len(result.types) == len(result.labels) > 0
    assert set(result.types) <= {0, 1, 2, 3, 5}


@pytest.mark.parametrize("entry", MANIFEST["frames"], ids=lambda e: str(e["file"]))
def test_every_walk_frame_decodes_with_no_unread_bytes(entry):
    result = decode_frame((FIXTURES / f"frames/{entry['group']}_{entry['file']}.dat").read_bytes(), frame_map())
    assert result.map_id == entry["map"] == 0
    assert len(result.indices) == len(result.x) == len(result.y) == len(result.z) > 0
    types = frame_map().types
    for position, index in enumerate(result.indices):
        if types[index] in (2, 3):
            assert any(types[j] == 0 for j in result.indices[:position]), "a rotate or scale follows a pivot"


def test_a_scale_without_an_axis_value_defaults_to_128():
    # One scale transform (type 3) preceded by a pivot (type 0); the frame sets only the x axis.
    simple = FrameMap((0, 3), ((1,), (2,)))
    data = bytes([0, 0, 2, 0, 1]) + bytes([64 + 5])
    result = decode_frame(data, simple)
    assert result.indices == (0, 1) and result.x[1] == 5 and (result.y[1], result.z[1]) == (128, 128)


def cuts(data: bytes) -> list[int]:
    return sorted({0, 1, 2, len(data) // 2, len(data) - 1})


@pytest.mark.parametrize("cut", cuts((FIXTURES / "maps/0.dat").read_bytes()))
def test_a_truncated_frame_map_is_named(cut):
    with pytest.raises(ValueError, match="frame map file ends early"):
        decode_frame_map((FIXTURES / "maps/0.dat").read_bytes()[:cut])


@pytest.mark.parametrize("cut", cuts((FIXTURES / "frames/207_357.dat").read_bytes()))
def test_a_truncated_frame_is_named(cut):
    with pytest.raises(ValueError, match="frame file ends early"):
        decode_frame((FIXTURES / "frames/207_357.dat").read_bytes()[:cut], frame_map())


@pytest.mark.parametrize("cut", cuts((FIXTURES / "sequence.dat").read_bytes()))
def test_a_truncated_sequence_is_named(cut):
    with pytest.raises(ValueError, match="sequence file ends early"):
        decode_sequence((FIXTURES / "sequence.dat").read_bytes()[:cut])


def test_a_frame_that_moves_a_transform_its_map_lacks_is_refused():
    # Two transforms, the second moved on x by 0, against a map that has one transform.
    with pytest.raises(ValueError, match="transform 1, its frame map has 1"):
        decode_frame(bytes([0, 0, 2, 0, 1, 64]), FrameMap((0,), ((1,),)))


@pytest.mark.parametrize(("sequence_id", "mode"), sorted(TIMING))
def test_the_schedule_lists_the_clients_frames_in_order(sequence_id, mode):
    schedule = frame_schedule(sequence(sequence_id), action=mode == "action")
    client = TIMING[sequence_id, mode]
    ticks = [frame for frame, length in schedule for _ in range(length)]
    if mode == "pose":
        # A pose sequence repeats its schedule forever, so the recording is the schedule played over and over.
        assert (ticks * (len(client) // len(ticks) + 1))[: len(client)] == client
    else:
        if -1 in client:
            assert ticks == client[: client.index(-1)]
        else:
            assert ticks[: len(client)] == client


def test_a_pose_sequence_ignores_its_loop_offset():
    # Sequence 1499 has a loop offset of 4, and the client's pose counter still returns to frame 0 (ap.fb 1820 to 1857).
    assert sequence(1499).loop_offset == 4
    runs = [frame for frame, _ in itertools.groupby(TIMING[1499, "pose"])]
    assert runs[:27] == [*range(26), 0]
