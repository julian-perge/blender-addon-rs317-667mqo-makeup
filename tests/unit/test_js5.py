import hashlib
import json
import os
from pathlib import Path

import pytest
from js5_builder import (
    CONFIG_INDEX,
    ENUM_GROUP,
    ITEM_GROUP,
    KIT_GROUP,
    MODEL_INDEX,
    build_cache,
    container,
    grouped,
    table,
    write_store,
)

from rsps_toolkit.formats.js5 import Js5Store, reference_table, split

SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
WALK = Path(__file__).parents[1] / "fixtures/animation149/walk"
APPEARANCE = Path(__file__).parents[1] / "fixtures/appearance"


@pytest.fixture
def store(tmp_path):
    long_file = bytes(range(256)) * 5
    write_store(
        tmp_path,
        {
            (255, 0): container(table({3: (0,), 7: (2, 5)})),
            (0, 3): container(long_file),
            (0, 7): container(grouped([b"first", b"second!"]), kind=2),
        },
    )
    return Js5Store(tmp_path), long_file


def test_a_group_spread_over_sectors_is_read_whole(store):
    js5, long_file = store
    assert js5.container(0, 3) == long_file


def test_the_reference_table_lists_groups_and_their_files(store):
    js5, _ = store
    assert js5.groups(0) == {3: (0,), 7: (2, 5)}


def test_a_compressed_group_of_several_files_splits_by_its_chunk_table(store):
    js5, long_file = store
    assert js5.files(0, 7) == {2: b"first", 5: b"second!"}
    assert js5.files(0, 3) == {0: long_file}


def test_a_missing_group_or_folder_is_named(store, tmp_path):
    js5, _ = store
    with pytest.raises(LookupError, match="no group 4"):
        js5.container(0, 4)
    with pytest.raises(FileNotFoundError, match="main_file_cache.dat2"):
        Js5Store(tmp_path / "elsewhere")


def test_protocol_7_reference_tables_read_their_ids_as_smart_numbers():
    assert reference_table(table({1: (0, 4)}, protocol=7)) == {1: (0, 4)}


def test_split_refuses_a_chunk_table_longer_than_the_group():
    with pytest.raises(ValueError, match="chunk table"):
        split(b"\x05", (0, 1))


def raw_files(folder: Path) -> dict[int, bytes]:
    return {int(path.stem): path.read_bytes() for path in folder.glob("*.dat")}


def test_the_raw_kit_fixtures_are_the_kits_the_client_recording_read():
    recorded = json.loads((APPEARANCE / "reference.json").read_text())["raw_kits_sha256"]
    kits = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (APPEARANCE / "kits").glob("*.dat")}
    assert kits == recorded


def test_a_built_cache_holds_the_raw_kits_in_config_group_3(tmp_path):
    kits = raw_files(APPEARANCE / "kits")
    build_cache(tmp_path, kits=kits)
    assert len(kits) == 151
    assert Js5Store(tmp_path).files(CONFIG_INDEX, KIT_GROUP) == kits


def test_a_built_cache_holds_each_model_as_file_0_of_its_group_in_index_7(tmp_path):
    model = (APPEARANCE / "230.dat").read_bytes()
    build_cache(tmp_path, models={230: model})
    assert Js5Store(tmp_path).files(MODEL_INDEX, 230) == {0: model}


def test_a_built_cache_holds_items_in_config_group_10_and_enums_in_group_8(tmp_path):
    items = raw_files(APPEARANCE / "items")
    enums = raw_files(APPEARANCE / "enums")
    build_cache(tmp_path, items=items, enums=enums)
    assert len(enums) == 18
    assert Js5Store(tmp_path).files(CONFIG_INDEX, ITEM_GROUP) == items
    assert Js5Store(tmp_path).files(CONFIG_INDEX, ENUM_GROUP) == enums


def test_a_built_cache_holds_a_config_group_of_one_file(tmp_path):
    item = (APPEARANCE / "items/35.dat").read_bytes()
    build_cache(tmp_path, items={35: item})
    assert Js5Store(tmp_path).files(CONFIG_INDEX, ITEM_GROUP) == {35: item}


@pytest.mark.skipif(not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder")
def test_the_snapshot_430_walk_frames_map_and_sequence_match_the_fixture_hashes():
    js5 = Js5Store(SNAPSHOT_430)
    manifest = json.loads((WALK / "manifest.json").read_text())
    frames = js5.files(0, 207)
    for frame in manifest["frames"]:
        assert hashlib.sha256(frames[frame["file"]]).hexdigest() == frame["sha256"]
    assert js5.files(1, 0)[0] == (WALK / "maps/0.dat").read_bytes()
    assert hashlib.sha256(js5.files(2, 12)[819]).hexdigest() == manifest["sequence_sha256"]
