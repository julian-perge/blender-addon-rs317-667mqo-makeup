import os
from pathlib import Path

import pytest
from js5_builder import build_cache, rewrite_cache

from rsps_toolkit.formats.appearance import assemble_body, default_equipment
from rsps_toolkit.formats.appearance_preset import AppearancePreset
from rsps_toolkit.formats.cache_profile import CacheProfile, MissingResourceError
from rsps_toolkit.formats.enum_definition import decode_enum
from rsps_toolkit.formats.item_definition import decode_item
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.kit_definition import decode_kit

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"


def raw_files(folder: Path) -> dict[int, bytes]:
    return {int(path.stem): path.read_bytes() for path in folder.glob("*.dat")}


def write_cache(folder: Path, **changes: dict[int, bytes]) -> Path:
    """Write the appearance fixtures as a cache, with any of its models, kits, items or enums replaced."""
    parts = {
        "models": raw_files(FIXTURES),
        "kits": raw_files(FIXTURES / "kits"),
        "items": raw_files(FIXTURES / "items"),
        "enums": raw_files(FIXTURES / "enums"),
    }
    build_cache(folder, **(parts | changes))
    return folder


@pytest.fixture
def cache(tmp_path):
    return write_cache(tmp_path)


def test_profile_assembles_the_default_male_body(cache):
    profile = CacheProfile(cache)
    body = assemble_body(default_equipment(profile.kits), profile.kits, profile.load_model, [0] * 5, profile.palette)
    assert (len(body.faces), len(body.vertices)) == (476, 264)


def test_the_shipped_palette_is_the_fixture_palette():
    from rsps_toolkit.formats.cache_profile import PALETTE_PATH

    assert PALETTE_PATH.read_bytes() == (FIXTURES / "revision149-palette.json").read_bytes()


def test_a_folder_without_a_cache_names_the_folder_and_the_preference(tmp_path):
    with pytest.raises(MissingResourceError, match=r"main_file_cache\.dat2.*Set the Cache folder in the add-on"):
        CacheProfile(tmp_path).kits


def test_a_missing_model_names_the_model_and_the_preference(tmp_path):
    models = raw_files(FIXTURES)
    del models[230]
    cache = write_cache(tmp_path, models=models)
    with pytest.raises(MissingResourceError, match="Model 230.*Set the Cache folder in the add-on"):
        CacheProfile(cache).load_model(230)


def test_items_come_from_the_cache(cache):
    # The item 35 row of ItemDefinitions.json has femaleOffset 6.
    assert CacheProfile(cache).items[35].female_offset == 6


def test_kit_names_come_from_the_caches_enums(cache, tmp_path_factory):
    assert CacheProfile(cache).kit_names[101] == "Leggings"
    without_enums = write_cache(tmp_path_factory.mktemp("cache"), enums={})
    with pytest.raises(MissingResourceError, match="no group 8"):
        CacheProfile(without_enums).kit_names


def test_a_missing_style_enum_is_named(cache):
    rewrite_cache(cache, lambda parts: parts["enums"].pop(778))
    with pytest.raises(MissingResourceError, match="enum 778.*Set the Cache folder in the add-on"):
        CacheProfile(cache).kit_names


def test_a_cut_short_kit_is_a_decoding_error_not_a_missing_resource(cache):
    rewrite_cache(cache, lambda parts: parts["kits"].update({0: parts["kits"][0][:3]}))
    with pytest.raises(IndexError):
        CacheProfile(cache).kits


def test_an_unchanged_cache_is_parsed_once(cache):
    profile = CacheProfile(cache)
    assert profile.kits is profile.kits


def test_a_changed_cache_is_parsed_again(cache):
    # The user chose that a catalog is parsed again at the next use when its files' modified times change (issue 29,
    # decision 3, 2026-11-10). Kit 9101 is a copy of kit 101 under an id the fixture cache lacks.
    profile = CacheProfile(cache)
    assert 9101 not in profile.kits
    rewrite_cache(cache, lambda parts: parts["kits"].update({9101: parts["kits"][101]}))
    assert profile.kits[9101].model_ids == profile.kits[101].model_ids


SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
needs_snapshot_430 = pytest.mark.skipif(
    not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder"
)


@needs_snapshot_430
def test_the_snapshot_430_cache_builds_the_default_male_body():
    # reference.json records 264 vertices and 476 faces for the male default look, from the revision 149 client.
    profile = CacheProfile(SNAPSHOT_430)
    preset = AppearancePreset(
        client_revision=149,
        snapshot_id=430,
        female=False,
        equipment=tuple(default_equipment(profile.kits)),
        colours=(0,) * 5,
    )
    body = profile.assemble(preset)
    assert (len(body.faces), len(body.vertices)) == (476, 264)


@needs_snapshot_430
@pytest.mark.parametrize(
    ("group", "decoder", "count"),
    [(3, decode_kit, 151), (8, decode_enum, 1725), (10, decode_item, 21392)],
    ids=["kits", "enums", "items"],
)
def test_every_snapshot_430_definition_of_a_config_group_decodes(group, decoder, count):
    # The counts are the raw config files in an export of snapshot 430 that the RuneLite cache library wrote, under its
    # configs/identkit, configs/enum and configs/item folders (counted on 2026-11-11). A decoder raises on an unknown
    # opcode or on bytes after the closing opcode.
    files = Js5Store(SNAPSHOT_430).files(2, group)
    assert len(files) == count
    for definition_id, data in files.items():
        decoder(definition_id, data)
