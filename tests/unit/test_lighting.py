import json
from dataclasses import replace
from pathlib import Path

import pytest
from runelite_json import load_items, load_kits

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import assemble_body, load_palette, merge
from rsps_toolkit.formats.lighting import PLAYER_LIGHTING, _divide, joined_render_types, light
from rsps_toolkit.formats.model import ModelEncoding, NewFormatData

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


def test_a_joined_player_lights_a_textured_face_and_alpha_254_and_255_instead_of_refusing_them():
    # Issue 103: dv.ae of gamepack 149 lights a textured face with light values and hides a face of alpha 255
    # (docs/research/textured-light.md, section 1). The face keeps the light value that the colour formula scales: a
    # light value is the clamped intensity, and the untextured shade is (colour & 0xFF80) + (lightness * intensity >> 7).
    body = assemble_body(REFERENCE["equipment"], KITS, load_model, [0] * 5, PALETTE)
    textured = replace(body, face_textures=[5, *body.face_textures[1:]], face_colours=[None, *body.face_colours[1:]])
    hidden = replace(body, face_alphas=[255, *body.face_alphas[1:]])

    lit = light(textured, PLAYER_LIGHTING)
    gone = light(hidden, PLAYER_LIGHTING)

    assert lit.light_values[0] and not any(lit.light_values[1:])
    assert all(2 <= value <= 126 for value in (lit.corner_a[0], lit.corner_b[0], lit.corner_c[0]))
    assert (gone.corner_a[0], gone.corner_b[0], gone.corner_c[0]) == (0, 0, -2)


@pytest.mark.parametrize("case", REFERENCE["cases"][:2], ids=lambda c: f"{c.get('outfit')}-{c['female']}")
def test_the_player_and_npc_light_gives_the_client_shades_of_a_player(case):
    body = assemble_body(case["equipment"], KITS, load_model, case["colours"], PALETTE, ITEMS, female=case["female"])
    shading = light(body, PLAYER_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == (
        case["lit"]["shade_a"],
        case["lit"]["shade_b"],
        case["lit"]["shade_c"],
    )


# Hand-made models for the loc light. The client lights a loc with (ambient + 64, contrast + 768, -50, -10, -50)
# (ObjectComposition.java line 585). With ambient 16 and contrast 50 the lighting is (80, 818, -50, -10, -50), and
# ModelData.java lines 1540 and 1541 give the divisor sqrt(50 * 50 + 10 * 10 + 50 * 50) = 71, times 818, >> 8 = 226.
LOC_LIGHTING = (16 + 64, 50 + 768, -50, -10, -50)
# The colour of each untextured face: hue 10, saturation 3 and lightness 100, so 10724 & 0xFF80 is 10624.
COLOUR = (10 << 10) | (3 << 7) | 100
# The vertices of the tilted face (0, 1, 3) and the level face (0, 1, 2). By ModelData.java lines 1421 to 1443, the
# tilted face has the cross product (0, -16384, -8192), halved once to (0, -8192, -4096), of length 9158, so its
# normal is (0, -228, -114). The level face has the cross product (0, -16384, 0) and the normal (0, -256, 0).
VERTICES = [(0, 0, 0), (128, 0, 0), (0, 0, 128), (0, -64, 128)]
TILTED = (0, 1, 3)
LEVEL = (0, 1, 2)


def old_model(faces, colours, textures, alphas, flat) -> Model:
    return Model(
        vertices=VERTICES,
        faces=faces,
        face_colours=colours,
        face_textures=textures,
        render_priorities=[0] * len(faces),
        face_alphas=alphas,
        face_texture_triangles=[None] * len(faces),
        flat_shaded=flat,
    )


def test_a_plain_face_gives_the_client_corner_colours_with_the_loc_lighting():
    # ModelData.java lines 1639 to 1663: (-10 * -228 + -50 * -114) / (226 * 1) + 80 = 7980 / 226 + 80 = 115 at each corner.
    # method2639 (lines 1818 to 1827): (100 * 115) >> 7 = 89, so each corner is 10624 + 89 = 10713.
    shading = light(old_model([TILTED], [COLOUR], [None], [0], [False]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([10713], [10713], [10713])
    assert shading.light_values == [False]


def test_a_textured_face_gives_the_client_light_value_per_corner():
    # ModelData.java lines 1674 to 1698: each corner gets method2676 of 115 (lines 1830 to 1838), which keeps a value
    # from 2 to 126, so 115.
    shading = light(old_model([TILTED], [None], [5], [0], [False]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([115], [115], [115])
    assert shading.light_values == [True]


def test_a_textured_face_keeps_its_light_value_at_most_126():
    # With ambient 120 the intensity is 7980 / 226 + 120 + 64 = 219, and method2676 (lines 1830 to 1838) gives 126.
    shading = light(old_model([TILTED], [None], [5], [0], [False]), (120 + 64, 50 + 768, -50, -10, -50))
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([126], [126], [126])


def test_a_textured_face_keeps_its_light_value_at_least_2():
    # With ambient -128, the lowest signed byte, the intensity is 7980 / 226 - 128 + 64 = -29, and method2676
    # (lines 1830 to 1838) gives 2.
    shading = light(old_model([TILTED], [None], [5], [0], [False]), (-128 + 64, 50 + 768, -50, -10, -50))
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([2], [2], [2])


def test_a_flat_textured_face_gives_one_light_value():
    # ModelData.java lines 1666 to 1670: (-10 * -228 + -50 * -114) / (226 / 2 + 226) + 80 = 7980 / 339 + 80 = 103,
    # method2676 keeps 103, and the third corner is -1. The second corner is never written, so it stays 0.
    shading = light(old_model([TILTED], [None], [5], [0], [True]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([103], [0], [-1])
    assert shading.light_values == [True]


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_an_untextured_face_with_alpha_254_gives_colour_128_and_the_flat_mark(flat):
    # ModelData.java lines 1614 to 1616 make alpha -2 (254) render type 3, and lines 1632 to 1634 give 128 and -1.
    shading = light(old_model([TILTED], [COLOUR], [None], [254], [flat]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([128], [0], [-1])


@pytest.mark.parametrize(
    ("textures", "alpha"),
    [([None], 255), ([5], 254), ([5], 255)],
    ids=["untextured alpha 255", "textured alpha 254", "textured alpha 255"],
)
def test_a_face_with_alpha_255_or_a_textured_face_with_alpha_254_is_hidden(textures, alpha):
    # ModelData.java lines 1614 to 1620 make alpha -2 (254) render type 3 and alpha -1 (255) render type 2. Lines 1635
    # and 1636 give an untextured face of render type 2 the third corner -2, and lines 1671 and 1672 give a textured face
    # of render type 2 or 3 the same. The other two corners are never written, so they stay 0.
    colours = [None] if textures[0] is not None else [COLOUR]
    shading = light(old_model([TILTED], colours, textures, [alpha], [False]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([0], [0], [-2])


def test_a_face_with_alpha_255_still_adds_its_normal_to_its_corners():
    # computeNormals (ModelData.java lines 1444 to 1466) reads the stored render type, not the alpha, so the hidden
    # level face adds (0, -256, 0) to vertices 0 and 1. Their sums are (0, -484, -114) with magnitude 2, so
    # (-10 * -484 + -50 * -114) / (226 * 2) + 80 = 10540 / 452 + 80 = 103 and (100 * 103) >> 7 = 80: 10624 + 80.
    # Vertex 3 keeps the tilted face's 10713.
    model = old_model([LEVEL, TILTED], [COLOUR, COLOUR], [None, None], [255, 0], [False, False])
    shading = light(model, LOC_LIGHTING)
    assert (shading.corner_a[1], shading.corner_b[1], shading.corner_c[1]) == (10704, 10704, 10713)


def new_model(render_types) -> Model:
    return Model(
        vertices=VERTICES,
        faces=[LEVEL, TILTED],
        face_colours=[COLOUR, COLOUR],
        face_textures=[None, None],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[kind in (1, 3) for kind in render_types],
        encoding=ModelEncoding.OSRS_FFFF,
        profile="osrs-149",
        new_data=NewFormatData(
            textured_face_colours=(None, None),
            face_render_types=tuple(render_types),
            texture_render_types=(),
            texture_parameters=(),
            tail=b"\0",
        ),
    )


def test_a_new_format_face_of_render_type_2_is_hidden_and_adds_no_normal():
    # ModelData.java line 638 keeps the stored byte. computeNormals (lines 1444 to 1476) adds a normal only for render
    # types 0 and 1, and light gives an untextured face of render type 2 the third corner -2 (lines 1635 and 1636).
    # So the tilted face lights alone and keeps 10713 at every corner.
    shading = light(new_model([2, 0]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([0, 10713], [0, 10713], [-2, 10713])


def test_a_new_format_face_of_render_type_4_is_hidden_and_adds_no_normal():
    # computeNormals (ModelData.java lines 1444 to 1476) adds a normal only for render types 0 and 1, and light hides an
    # untextured face of any render type other than 0, 1 and 3 (lines 1635 and 1636). So the tilted face keeps 10713.
    shading = light(new_model([4, 0]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([0, 10713], [0, 10713], [-2, 10713])


def test_a_new_format_face_of_render_type_3_gives_colour_128_and_adds_no_normal():
    # computeNormals (ModelData.java lines 1444 to 1476) adds no normal for render type 3, and light gives an untextured
    # face of render type 3 the colour 128 and the third corner -1 (lines 1632 to 1634). The tilted face keeps 10713.
    shading = light(new_model([3, 0]), LOC_LIGHTING)
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == ([128, 10713], [0, 10713], [-1, 10713])


def test_a_joined_model_keeps_the_stored_render_type_of_each_part():
    # The client's join (ModelData.java lines 192, 207 to 209, 255 and 256) copies the stored render type of each face of
    # each part. A part without render types stores 0, and an old-format part stores 1 for a flat face (lines 932 to 938).
    parts = [
        new_model([2, 0]),
        old_model([LEVEL], [COLOUR], [None], [0], [True]),
        old_model([LEVEL], [COLOUR], [None], [0], [False]),
    ]
    assert joined_render_types(parts) == [2, 0, 1, 0]


def test_a_joined_model_is_lit_with_the_render_types_that_it_is_given():
    # appearance.merge gives an old-format model, so without the render types the face of render type 2 would be lit
    # as a smooth face (test_the_player_and_npc_light_lights_a_face_of_render_type_2_as_a_smooth_face).
    part = new_model([2, 0])
    joined = merge([part])
    assert light(joined, LOC_LIGHTING, joined_render_types([part])) == light(part, LOC_LIGHTING)
    assert light(joined, LOC_LIGHTING) != light(part, LOC_LIGHTING)
