import json
import os
import shutil
from pathlib import Path

import pytest
from js5_builder import REGION_FIXTURES, build_region_cache

from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.region import Placement, decode_landscape, load_landscape, region_id

KEY_FILE = REGION_FIXTURES / "keys/12338.txt"
SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()


@pytest.fixture
def region_cache(tmp_path):
    """A download folder: `cache/` holds the stored groups and `keys/` holds the key file of `48_50`."""
    build_region_cache(tmp_path / "cache")
    (tmp_path / "keys").mkdir()
    shutil.copyfile(KEY_FILE, tmp_path / "keys/12338.txt")
    return tmp_path


def test_the_region_id_is_x_times_256_plus_y():
    # OpenRS2's keys.json lists mapsquare 12338 for l48_50.
    assert region_id(48, 50) == 12338


def test_the_placements_of_48_50_equal_runelites_locations_loader_in_file_order(region_cache):
    landscape = load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    reference = json.loads((REGION_FIXTURES / "landscape.json").read_text())
    assert landscape.has_key
    assert len(reference) == 2545
    assert [
        {
            "id": p.loc,
            "level": p.level,
            "x": p.x,
            "y": p.y,
            "type": p.loc_type,
            "rotation": p.rotation,
        }
        for p in landscape.placements
    ] == reference


def test_a_missing_keys_folder_is_an_error_that_names_the_folder(region_cache):
    shutil.rmtree(region_cache / "keys")
    with pytest.raises(FileNotFoundError) as error:
        load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    assert str(region_cache / "keys") in str(error.value)


def test_a_missing_key_file_gives_an_empty_landscape_and_no_key_flag(region_cache):
    (region_cache / "keys/12338.txt").unlink()
    landscape = load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    assert landscape.placements == ()
    assert not landscape.has_key


def test_a_key_that_does_not_decrypt_the_landscape_is_an_error_that_names_the_key_file(region_cache):
    path = region_cache / "keys/12338.txt"
    first, *rest = KEY_FILE.read_text().split()
    path.write_text("\n".join([str(int(first) + 1), *rest]) + "\n")
    with pytest.raises(ValueError) as error:
        load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    assert str(path) in str(error.value)


@pytest.mark.parametrize(
    "text",
    ["1\n2\n3\n", "1 2 3 4\n", "1\n2\n3\n1_000\n", "1\n2\n3\n2147483648\n"],
    ids=["three lines", "one line", "underscore", "above 32 bits"],
)
def test_a_key_file_without_four_32_bit_numbers_one_per_line_is_an_error_that_names_the_key_file(region_cache, text):
    # Java's Integer.parseInt, which RegionReference.java uses, refuses "1_000" and 2147483648.
    path = region_cache / "keys/12338.txt"
    path.write_text(text)
    with pytest.raises(ValueError, match="does not hold four 32-bit whole numbers") as error:
        load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    assert str(path) in str(error.value)


def test_a_loc_id_step_of_32767_adds_to_the_next_value_and_a_position_step_can_take_two_bytes():
    # Client lines: Buffer.java 560 to 570 (a loc id step adds 32767 for each value of 32767), Client.java 1761 to 1801
    # (position bits: y in bits 0 to 5, x in bits 6 to 11, level in the bits from 12 up; type and rotation share one byte).
    data = bytes.fromhex(
        "ffff05"  # loc id step 32767 + 5, so the loc id is -1 + 32772
        "01"  # position step 1: position 0, tile (0, 0) on level 0
        "2a"  # type 10, rotation 2
        "90c8"  # position step 0x90C8 - 0x8000 = 4296: position 4295, level 1, x 3, y 7
        "5b"  # type 22, rotation 3
        "00"  # end of this loc id
        "00"  # end of the landscape
    )
    assert decode_landscape(data) == (
        Placement(loc=32771, level=0, x=0, y=0, loc_type=10, rotation=2),
        Placement(loc=32771, level=1, x=3, y=7, loc_type=22, rotation=3),
    )


def test_a_loc_id_step_adds_32767_for_each_value_of_32767_in_a_row():
    # Buffer.java 564 to 566: the loop adds 32767 for each value of 32767 and ends at the first other value.
    data = bytes.fromhex(
        "ffff"  # 32767
        "ffff"  # 32767 again
        "05"  # 5 ends the step: the loc id is -1 + 65539
        "01"  # position step 1: tile (0, 0) on level 0
        "00"  # type 0, rotation 0
        "00"  # end of this loc id
        "00"  # end of the landscape
    )
    assert decode_landscape(data) == (Placement(loc=65538, level=0, x=0, y=0, loc_type=0, rotation=0),)


def test_a_level_above_3_is_kept_as_the_client_reads_it():
    # Client.java 1782 reads the level as the position shifted right by 12, with no mask.
    data = bytes.fromhex(
        "01"  # loc id step 1: loc 0
        "c001"  # position step 0xC001 - 0x8000 = 16385: position 16384, level 4, x 0, y 0
        "00"  # type 0, rotation 0
        "00"  # end of this loc id
        "00"  # end of the landscape
    )
    assert decode_landscape(data) == (Placement(loc=0, level=4, x=0, y=0, loc_type=0, rotation=0),)


@pytest.mark.skipif(not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder")
@pytest.mark.parametrize("x, y", [(x, y) for x in (47, 48, 49) for y in (49, 50, 51) if (x, y) != (48, 50)])
def test_the_landscapes_of_the_8_neighbours_of_48_50_decrypt_and_decode(x, y):
    # The committed landscape of 48_50 cannot show whether XTEA covers the 4 bytes of expanded length, because its
    # encrypted part ends in the same 8-byte block either way. The landscapes of 48_49, 48_51, 49_49 and 49_51 can: with
    # the wrong range, the last bytes of their gzip data stay encrypted and gzip refuses them.
    assert load_landscape(Js5Store(SNAPSHOT_430), x, y).has_key


def test_a_landscape_that_ends_inside_a_placement_is_an_error():
    with pytest.raises(ValueError, match="ends early"):
        decode_landscape(bytes.fromhex("0101"))
