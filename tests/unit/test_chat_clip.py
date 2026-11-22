"""Chat clips (spec 183, section 6): `jg.p` of gamepack 149 applies the frame of a step and then its chat frame to the
same model (docs/research/chatheads.md, section 1), and the chat clips have the names of seq.sym."""

import struct

from rsps_toolkit.animation.clip import FolderClip, load_chat_clip_names, pose_vertices

# A frame map with one translate transform (type 1) that moves label 1.
FRAME_MAP = bytes([1, 1, 1, 1])


def frame(flag: int, value: int) -> bytes:
    """A frame of map 9 that moves transform 0 by `value` on the axes of `flag` (1 is x, 2 is y), as `decode_frame`
    reads it: the map id, the count, the flags and one one-byte smart value for each axis (value + 64)."""
    return struct.pack(">HB", 9, 1) + bytes([flag, value + 64])


def clip_folder(tmp_path, chat_files: list[int]) -> FolderClip:
    """Two frames of group 7, file 0 (x + 10) and file 1 (x + 20), and the chat frames of `chat_files` in group 7,
    where file 2 is y + 5."""
    (tmp_path / "frames").mkdir()
    (tmp_path / "maps").mkdir()
    (tmp_path / "maps" / "9.dat").write_bytes(FRAME_MAP)
    for file, data in ((0, frame(1, 10)), (1, frame(1, 20)), (2, frame(2, 5))):
        (tmp_path / "frames" / f"7_{file}.dat").write_bytes(data)
    sequence = bytes([1]) + struct.pack(">H", 2) + struct.pack(">HH", 3, 4) + struct.pack(">HH", 0, 1)
    sequence += struct.pack(">HH", 7, 7)
    sequence += bytes([12, len(chat_files)]) + b"".join(struct.pack(">H", f) for f in chat_files)
    sequence += b"".join(struct.pack(">H", 7) for _ in chat_files) + bytes([0])
    (tmp_path / "sequence.dat").write_bytes(sequence)
    return FolderClip(tmp_path)


def test_a_chat_step_applies_its_frame_and_then_its_chat_frame(tmp_path):
    frames = pose_vertices(((0, 0, 0),), (1,), clip_folder(tmp_path, [2]), chat=True)
    assert frames[0].vertices == ((10, 5, 0),)


def test_a_step_past_the_end_of_the_chat_frames_gets_its_frame_only(tmp_path):
    frames = pose_vertices(((0, 0, 0),), (1,), clip_folder(tmp_path, [2]), chat=True)
    assert frames[1].vertices == ((20, 0, 0),)


def test_a_chat_frame_with_the_file_id_65535_is_skipped(tmp_path):
    frames = pose_vertices(((0, 0, 0),), (1,), clip_folder(tmp_path, [65535, 2]), chat=True)
    assert [f.vertices for f in frames] == [((10, 0, 0),), ((20, 5, 0),)]


def test_an_actor_clip_leaves_the_chat_frames_out(tmp_path):
    # jg.p, the only reader of the chat frames, is called only by Widget.getModel (chatheads.md, section 1).
    frames = pose_vertices(((0, 0, 0),), (1,), clip_folder(tmp_path, [2]))
    assert frames[0].vertices == ((10, 0, 0),)


def test_the_chat_clips_have_the_names_of_seq_sym():
    # osrs-dumps symbols/seq.sym: 567 chathap1, 588 chatneu1, 554 chatquiz1 and 617 chatang4. 566, 579, 604 and 609
    # in that block are not chat clips (docs/research/chatheads.md).
    names = load_chat_clip_names()
    assert (names[567], names[588], names[554], names[617]) == ("chathap1", "chatneu1", "chatquiz1", "chatang4")
    assert {566, 579, 604, 609}.isdisjoint(names)
    assert set(range(554, 618)) - {566, 579, 604, 609} <= set(names)
