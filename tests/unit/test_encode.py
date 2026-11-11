from pathlib import Path

import pytest

from rsps_toolkit.formats import decode, encode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
OLD_FORMAT = sorted((MODELS / "osrs").glob("*.dat"))


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_encoding_a_decoded_model_keeps_everything(dat: Path):
    model = decode(dat.read_bytes())

    assert decode(encode(model)) == model
