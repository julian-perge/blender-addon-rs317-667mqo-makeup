import shutil
from pathlib import Path

import pytest

from rsps_toolkit.formats.appearance import assemble_body, default_equipment
from rsps_toolkit.formats.cache_profile import CacheProfile, MissingResourceError

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"


@pytest.fixture
def dump(tmp_path):
    (tmp_path / "kits").mkdir()
    (tmp_path / "items").mkdir()
    (tmp_path / "enums").mkdir()
    (tmp_path / "dump_index/models").mkdir(parents=True)
    shutil.copy(FIXTURES / "KitDefinitions.json", tmp_path / "kits/KitDefinitions.json")
    shutil.copy(FIXTURES / "ItemDefinitions.json", tmp_path / "items/ItemDefinitions.json")
    shutil.copy(FIXTURES / "KitStyleEnums.json", tmp_path / "enums/Enums.json")
    for model in FIXTURES.glob("*.dat"):
        shutil.copy(model, tmp_path / "dump_index/models" / model.name)
    return tmp_path


def test_profile_assembles_the_default_male_body(dump):
    profile = CacheProfile(dump)
    body = assemble_body(default_equipment(profile.kits), profile.kits, profile.load_model, [0] * 5, profile.palette)
    assert (len(body.faces), len(body.vertices)) == (476, 264)


def test_the_shipped_palette_is_the_fixture_palette():
    from rsps_toolkit.formats.cache_profile import PALETTE_PATH

    assert PALETTE_PATH.read_bytes() == (FIXTURES / "revision149-palette.json").read_bytes()


def test_a_missing_kit_catalog_names_the_path_and_the_fix(tmp_path):
    with pytest.raises(MissingResourceError, match=r"kits/KitDefinitions\.json.*kits"):
        CacheProfile(tmp_path).kits


def test_a_missing_model_is_an_error_not_a_skip(dump):
    (dump / "dump_index/models/230.dat").unlink()
    with pytest.raises(MissingResourceError, match="Model 230"):
        CacheProfile(dump).load_model(230)


def test_kit_names_come_from_the_dumps_enums(dump):
    assert CacheProfile(dump).kit_names[101] == "Leggings"
    (dump / "enums/Enums.json").unlink()
    with pytest.raises(MissingResourceError, match="enums"):
        CacheProfile(dump).kit_names
