"""The spot effect decoder (spec 183, section 3). Expected values come from RuneLite's decoding of snapshot 430 in
fixtures/spot_effects and from `ii.v` of gamepack 149 (docs/research/spot-effects.md)."""

import json
from pathlib import Path

import pytest

from rsps_toolkit.formats.model import Model
from rsps_toolkit.formats.spot_effect import (
    decode_spot_effect,
    spot_effect_lighting,
    spot_effect_model,
    spot_effect_scale,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "spot_effects"
ROWS = {row["id"]: row for row in json.loads((FIXTURES / "SpotAnimDefinitions.json").read_text())}


def decoded(spot_effect_id: int):
    return decode_spot_effect(spot_effect_id, (FIXTURES / f"{spot_effect_id}.dat").read_bytes())


@pytest.mark.parametrize("spot_effect_id", sorted(ROWS))
def test_a_spot_effect_has_the_values_of_runelite(spot_effect_id):
    row = ROWS[spot_effect_id]
    effect = decoded(spot_effect_id)

    assert (effect.model, effect.sequence) == (row["modelId"], row["animationId"])
    assert (effect.resize_width, effect.resize_height, effect.rotation) == (row["resizeX"], row["resizeY"], row["rotaton"])
    assert (effect.ambient, effect.contrast) == (row["ambient"], row["contrast"])
    finds, shows = row.get("recolorToFind", []), row.get("recolorToReplace", [])
    assert effect.recolours == tuple(zip(finds, shows, strict=True))


def test_the_ambient_is_an_unsigned_byte():
    # Spot effect 314 stores the ambient byte 0xC0, which RuneLite reads as 192 and ii.r with readUnsignedByte.
    assert decoded(314).ambient == 192


def test_an_unknown_opcode_and_bytes_after_the_end_are_refused():
    with pytest.raises(ValueError, match="unknown opcode 3"):
        decode_spot_effect(1, bytes([3, 0]))
    with pytest.raises(ValueError, match="1 byte"):
        decode_spot_effect(1, bytes([0, 0]))


def test_the_light_adds_64_and_850_with_the_direction_of_ii_v():
    # ii.v offsets 226 to 255: dv.ae(64 + ambient, 850 + contrast, -30, -50, -30). Spot effect 931 has 60 and 60.
    assert spot_effect_lighting(decoded(931)) == (124, 910, -30, -50, -30)


def test_the_scale_is_the_width_in_x_and_z_and_the_height_in_y():
    # ej.i(width, height, width) at ii.v offsets 351 to 374. Spot effect 188 has width 256 and height 128.
    assert spot_effect_scale(decoded(188)) == (2.0, 1.0, 2.0)


def test_the_model_is_recoloured_as_the_spot_effect_says():
    # Spot effect 9 shows 33 in place of 57 and 61 (RuneLite's row).
    model = Model(
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2), (0, 2, 1), (1, 0, 2)],
        face_colours=[57, 61, 5],
        face_textures=[None, None, None],
        render_priorities=[0, 0, 0],
        face_alphas=[0, 0, 0],
        face_texture_triangles=[None, None, None],
        flat_shaded=[False, False, False],
    )
    effect = decoded(9)

    assert spot_effect_model(effect, {effect.model: model}.__getitem__).face_colours == [33, 33, 5]
