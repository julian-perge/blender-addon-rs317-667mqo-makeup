import json
from dataclasses import replace
from pathlib import Path

import pytest

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import assemble_body, load_items, load_kits, load_palette
from rsps_toolkit.formats.lighting import PLAYER_LIGHTING, _divide, light

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())
KITS = load_kits(FIXTURES / "KitDefinitions.json")
ITEMS = load_items(FIXTURES / "ItemDefinitions.json")
PALETTE = load_palette(FIXTURES / "revision149-palette.json")


def load_model(model_id: int) -> Model:
    return decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def test_player_lighting_is_what_the_client_passes():
    assert tuple(REFERENCE["lighting"]) == PLAYER_LIGHTING


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: f"{c.get('outfit')}-{c['female']}-{c['colours']}")
def test_lit_shades_match_the_unchanged_revision149_client(case):
    body = assemble_body(
        case["equipment"],
        KITS,
        load_model,
        case["colours"],
        PALETTE,
        ITEMS,
        female=case["female"],
    )
    shading = light(body)
    assert shading.corner_a == case["lit"]["shade_a"]
    assert shading.corner_b == case["lit"]["shade_b"]
    assert shading.corner_c == case["lit"]["shade_c"]


def test_division_rounds_toward_zero_like_java():
    assert [_divide(-7, 2), _divide(7, -2), _divide(-7, -2), _divide(7, 2)] == [-3, -3, 3, 3]


def test_unverified_faces_are_refused_not_lit():
    body = assemble_body(REFERENCE["equipment"], KITS, load_model, [0] * 5, PALETTE)
    textured = replace(body, face_textures=[5, *body.face_textures[1:]], face_colours=[None, *body.face_colours[1:]])
    with pytest.raises(ValueError, match="textured"):
        light(textured)
    with pytest.raises(ValueError, match="alpha"):
        light(replace(body, face_alphas=[255, *body.face_alphas[1:]]))
