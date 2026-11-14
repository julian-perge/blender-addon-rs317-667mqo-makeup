import json
import shutil

import pytest
from js5_builder import REGION_FIXTURES, build_region_cache

from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.region import Placement, decode_landscape, load_landscape, region_id

KEY_FILE = REGION_FIXTURES / "keys/12338.txt"


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


def test_a_key_file_without_four_numbers_is_an_error_that_names_the_key_file(region_cache):
    path = region_cache / "keys/12338.txt"
    path.write_text("1\n2\n3\n")
    with pytest.raises(ValueError) as error:
        load_landscape(Js5Store(region_cache / "cache"), 48, 50)
    assert str(path) in str(error.value)


def test_a_loc_id_step_of_32767_adds_to_the_next_value_and_a_position_step_can_take_two_bytes():
    # Client lines: Buffer.java 560 to 570 (a loc id step adds 32767 for each value of 32767), Client.java 1761 to 1801
    # (position bits: y in bits 0 to 5, x in bits 6 to 11, level in bits 12 and 13; type and rotation share one byte).
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


def test_a_landscape_that_ends_inside_a_placement_is_an_error():
    with pytest.raises(ValueError, match="ends early"):
        decode_landscape(bytes.fromhex("0101"))
