import pytest
from js5_builder import REGION_FIXTURES
from runelite_json import load_locs

from rsps_toolkit.formats.loc_definition import decode_loc


def test_every_loc_of_the_level_0_placements_and_their_impostors_equals_runelites_object_loader():
    decoded = {
        int(path.stem): decode_loc(int(path.stem), path.read_bytes())
        for path in (REGION_FIXTURES / "locs").glob("*.dat")
    }
    assert len(decoded) == 287
    assert decoded == load_locs(REGION_FIXTURES / "locs.json")


def test_a_loc_that_uses_every_opcode_of_load_data_except_5_and_92_reads_to_its_end():
    # Each opcode below is one branch of ObjectComposition.loadData (lines 347 to 513), with the values that the branch
    # reads. The expected values follow the lines named beside them. The tests below cover opcodes 5 and 92.
    data = b"".join(
        [
            bytes([1, 2, 0x01, 0x02, 10, 0x03, 0x04, 11]),  # 350 to 364: two models with their loc types
            bytes([2]) + b"Tree\0",  # 365 to 366: name
            bytes([14, 3, 15, 2, 17, 18, 19, 1, 21, 22, 23]),  # 381 to 397
            bytes([24, 0x01, 0x00, 27, 28, 8, 29, 0xFF, 39, 2]),  # 398 to 410
            bytes([30]) + b"Chop\0" + bytes([34]) + b"Hidden\0",  # 411 to 415: actions
            bytes([40, 1, 0x12, 0x34, 0xFF, 0xFE]),  # 416 to 424: one recolour
            bytes([41, 1, 0x00, 0x05, 0x00, 0x06]),  # 425 to 433: one retexture
            bytes([62, 64, 65, 0x01, 0x00, 66, 0x00, 0x40, 67, 0x00, 0x80, 68, 0x00, 0x09, 69, 0x0F]),  # 434 to 447
            bytes([70, 0xFF, 0xF0, 71, 0x00, 0x10, 72, 0x80, 0x00, 73, 74, 75, 1]),  # 448 to 459
            bytes([78, 0x00, 0x07, 3]),  # 461 to 463: ambient sound
            bytes([79, 0x00, 0x01, 0x00, 0x02, 4, 2, 0x00, 0x03, 0x00, 0x04]),  # 464 to 473: ambient sounds
            bytes([81, 2, 82, 0x00, 0x0B]),  # 474 to 477: contour of 2 * 256, map icon
            bytes([77, 0x00, 0x05, 0xFF, 0xFF, 1, 0x00, 0x0A, 0xFF, 0xFF]),  # 481 to 510: varbit 5, two impostors
            bytes([249, 2, 1, 0, 0, 1]) + b"text\0" + bytes([0, 0, 0, 2, 0, 0, 0, 7]),  # 478 to 479: two parameters
            bytes([0]),
        ]
    )
    loc = decode_loc(1, data)
    assert (loc.models, loc.loc_types) == ((0x0102, 0x0304), (10, 11))
    assert (loc.width, loc.length) == (3, 2)
    assert (loc.contoured_ground, loc.non_flat_shading, loc.animation) == (512, True, 256)
    assert (loc.decor_displacement, loc.casts_shadow, loc.mirrored) == (8, False, True)
    assert loc.recolours == ((0x1234, 0xFFFE),)
    assert loc.retextures == ((5, 6),)
    assert loc.scale == (256, 64, 128)
    # Lines 449 to 453 read the offsets as signed shorts.
    assert loc.offset == (-16, 16, -32768)
    # Lines 482 to 510: a varp of 0xFFFF is -1, and opcode 77 sets the last impostor to -1.
    assert (loc.impostor_varbit, loc.impostor_varp, loc.impostors) == (5, -1, (10, -1, -1))


def test_opcode_92_ends_the_impostors_with_its_own_default():
    # ObjectComposition.java lines 493 to 510: opcode 92 reads one more id, the last impostor.
    loc = decode_loc(1, bytes([92, 0xFF, 0xFF, 0x00, 0x03, 0x00, 0x2A, 0, 0x00, 0x0B, 0]))
    assert (loc.impostor_varbit, loc.impostor_varp, loc.impostors) == (-1, 3, (11, 42))


def test_a_second_model_list_is_skipped():
    # ObjectComposition.java lines 353 to 354 and 370 to 371: once a loc has models, a later opcode 1 or 5 is skipped,
    # because the import assumes that the client's low memory mode is off (`GameCanvas.java` line 295).
    loc = decode_loc(1, bytes([5, 1, 0x00, 0x07, 1, 1, 0x00, 0x08, 10, 5, 1, 0x00, 0x09, 0]))
    assert (loc.models, loc.loc_types) == ((7,), None)


def test_an_empty_model_list_keeps_the_models_unset():
    # ObjectComposition.java lines 352 and 369: a count of 0 reads nothing, so a later list is still read.
    loc = decode_loc(1, bytes([1, 0, 5, 1, 0x00, 0x09, 0]))
    assert (loc.models, loc.loc_types) == ((9,), None)


@pytest.mark.parametrize("opcode", [3, 6, 7, 61, 89, 93])
def test_a_loc_with_an_opcode_that_load_data_does_not_read_is_refused(opcode):
    with pytest.raises(ValueError, match=f"unknown opcode {opcode}"):
        decode_loc(1, bytes([opcode, 0]))


def test_a_loc_with_bytes_after_its_end_is_refused():
    with pytest.raises(ValueError, match="after its closing opcode"):
        decode_loc(1, bytes([14, 2, 0, 0]))
