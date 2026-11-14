from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from runelite_json import load_locs

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.loc_definition import LocDefinition
from rsps_toolkit.formats.region_loc import pick_model, recolour_model, shown_loc_id

FIXTURES = Path(__file__).parent.parent / "fixtures"
LOCS = load_locs(FIXTURES / "region/locs.json")


def loc(**changes: Any) -> LocDefinition:
    """A loc with the defaults of the `ObjectComposition` constructor (lines 262 to 296), changed as given."""
    defaults: dict[str, Any] = {
        "models": (),
        "loc_types": None,
        "recolours": (),
        "retextures": (),
        "mirrored": False,
        "impostors": None,
        "impostor_varbit": -1,
        "impostor_varp": -1,
    }
    return replace(LOCS[83], **(defaults | changes))


def mirror_of(definition: LocDefinition, loc_type: int, rotation: int) -> bool:
    model = pick_model(definition, loc_type, rotation)
    assert model is not None
    return model.mirrored


def test_an_impostor_placement_shows_the_loc_that_the_impostor_list_gives_for_value_0():
    # ObjectComposition.java lines 830 to 845: value 0 picks impostorIds[0]. RuneLite's ObjectLoader gives loc 14908
    # varbit 2098 and the impostors 7102, -1, -1, ...
    assert LOCS[14908].impostors is not None
    assert LOCS[14908].impostor_varbit == 2098
    assert shown_loc_id(14908, LOCS) == 7102
    assert shown_loc_id(26813, LOCS) == 26797
    assert shown_loc_id(29008, LOCS) == 16018


def test_a_loc_without_impostors_shows_itself():
    assert LOCS[83].impostors is None
    assert shown_loc_id(83, LOCS) == 83


def test_an_impostor_id_of_minus_1_for_value_0_shows_nothing():
    # Line 845: an id of -1 gives null.
    locs = {1: loc(impostors=(-1, 5, -1), impostor_varbit=3)}
    assert shown_loc_id(1, locs) is None


def test_a_varp_impostor_reads_value_0_like_a_varbit():
    # Lines 832 to 835: a varp is read when there is no varbit.
    locs = {1: loc(impostors=(7, 8, -1), impostor_varp=4), 7: loc()}
    assert shown_loc_id(1, locs) == 7


def test_an_impostor_loc_with_no_varbit_and_no_varp_shows_the_last_id():
    # Lines 831 to 842: the value stays -1 without a varbit or a varp, so the last id is used.
    locs = {1: loc(impostors=(7, 8, 9)), 9: loc()}
    assert shown_loc_id(1, locs) == 9


def test_an_impostor_list_with_only_the_last_id_uses_it_for_value_0():
    # Line 839: value 0 is not below length - 1 = 0, so the last id is used.
    locs = {1: loc(impostors=(9,), impostor_varbit=3), 9: loc()}
    assert shown_loc_id(1, locs) == 9


def test_a_loc_with_models_of_loc_types_shows_the_model_of_the_requested_type():
    # Lines 742 to 752: the first index whose loc type equals the requested one. Loc 83 has types 0, 2, 4, 9 and 22.
    model = pick_model(LOCS[83], 4, 0)
    assert model is not None
    assert model.model_ids == (16239,)


def test_a_loc_with_models_of_loc_types_shows_nothing_for_a_type_it_lacks():
    # Lines 748 to 750.
    assert pick_model(LOCS[83], 10, 0) is None


def test_a_loc_with_loc_types_uses_the_first_model_of_a_repeated_type():
    definition = loc(models=(11, 12), loc_types=(2, 2))
    model = pick_model(definition, 2, 0)
    assert model is not None
    assert model.model_ids == (11,)


def test_a_loc_without_loc_types_shows_all_its_models_for_type_10_only():
    # Lines 694 to 701: with no loc types, any type other than 10 gives null. Loc 12684 has models 13534 and 13535.
    assert LOCS[12684].loc_types is None
    both = pick_model(LOCS[12684], 10, 0)
    assert both is not None
    assert both.model_ids == (13534, 13535)
    assert pick_model(LOCS[12684], 9, 0) is None


def test_a_loc_with_no_models_shows_nothing_for_any_type():
    # Lines 699 to 701: no object models gives null.
    nothing = loc()
    assert [pick_model(nothing, t, 0) for t in (0, 2, 10, 22)] == [None] * 4


def test_the_mirror_of_a_loc_with_loc_types_flips_for_rotations_above_3():
    # Lines 753 and 1380 to 1390: isRotated ^ (rotation > 3). Type 2 of a corner wall is asked for with rotation + 4.
    plain = loc(models=(11,), loc_types=(2,))
    mirrored = replace(plain, mirrored=True)
    assert [mirror_of(plain, 2, r) for r in (0, 3, 4, 7)] == [False, False, True, True]
    assert [mirror_of(mirrored, 2, r) for r in (0, 3, 4, 7)] == [True, True, False, False]


def test_the_mirror_of_a_loc_without_loc_types_ignores_the_rotation():
    # Lines 703 to 706: var4 = isRotated, and its type 2 test never holds because the type is 10.
    plain = loc(models=(11,))
    assert [mirror_of(plain, 10, r) for r in (0, 4)] == [False, False]
    assert [mirror_of(replace(plain, mirrored=True), 10, r) for r in (0, 4)] == [True, True]


def test_a_rotation_above_7_is_refused():
    with pytest.raises(ValueError, match="rotation"):
        pick_model(LOCS[83], 0, 8)


def triangles(**changes) -> Model:
    model = Model(
        vertices=[(0, 0, 0), (100, 0, 0), (0, 100, 0), (100, 100, 0)],
        faces=[(0, 1, 2), (1, 3, 2), (0, 1, 3), (0, 3, 2)],
        face_colours=[10, 20, None, 10],
        face_textures=[None, None, 5, None],
        render_priorities=[0, 0, 0, 0],
        face_alphas=[0, 0, 0, 0],
        face_texture_triangles=[None, None, 0, None],
        texture_triangles=[(0, 1, 2)],
        flat_shaded=[False] * 4,
    )
    return replace(model, **changes)


def test_a_recolour_changes_exactly_the_faces_that_have_the_colour_to_find():
    # ModelData.java lines 1358 to 1365. The textured face has no colour, so it stays as it is.
    assert recolour_model(triangles(), ((10, 99),), ()).face_colours == [99, 20, None, 99]


def test_recolours_apply_in_order_so_a_later_pair_sees_an_earlier_change():
    # Lines 801 to 805 of ObjectComposition.java loop over the pairs, and each pass reads the colours that the pass
    # before it left.
    assert recolour_model(triangles(), ((10, 20), (20, 30)), ()).face_colours == [30, 30, None, 30]


def test_a_retexture_changes_exactly_the_faces_that_have_the_texture_to_find():
    # ModelData.java lines 1368 to 1376.
    model = triangles(face_textures=[None, 5, 5, None], face_colours=[10, None, None, 10])
    model = replace(model, face_texture_triangles=[None, 0, 0, None])
    result = recolour_model(model, (), ((5, 7), (9, 1)))
    assert result.face_textures == [None, 7, 7, None]
    assert result.face_colours == [10, None, None, 10]


def test_retextures_apply_in_order_so_a_later_pair_sees_an_earlier_change():
    # Lines 806 to 811 of ObjectComposition.java loop over the pairs like the recolours.
    model = triangles(face_textures=[None, 5, 7, None], face_colours=[10, None, None, 10])
    model = replace(model, face_texture_triangles=[None, 0, 0, None])
    assert recolour_model(model, (), ((5, 7), (7, 9))).face_textures == [None, 9, 9, None]


def test_a_retexture_leaves_a_model_without_textures_as_it_is():
    plain = triangles(face_textures=[None] * 4, face_colours=[10, 20, 30, 10], face_texture_triangles=[None] * 4)
    assert recolour_model(plain, (), ((5, 7),)) == plain


def test_the_input_model_is_not_changed():
    model = triangles()
    recolour_model(model, ((10, 99),), ((5, 7),))
    assert model == triangles()


def test_a_recolour_also_changes_the_colour_that_a_textured_face_keeps():
    # ModelData.java line 636: a model of the new format reads a colour for every face, textured or not, and recolor
    # (line 1360) compares them all. Model 2269 has texture 16 with the colour 127 on its textured faces, and 9096 on
    # its untextured ones.
    model = decode((FIXTURES / "models/osrs149/2269.dat").read_bytes(), profile="osrs-149")
    assert model.new_data is not None
    textured = [i for i, texture in enumerate(model.face_textures) if texture is not None]
    assert {model.new_data.textured_face_colours[i] for i in textured} == {127}
    result = recolour_model(model, ((127, 500), (9096, 600)), ())
    assert result.new_data is not None
    assert {result.new_data.textured_face_colours[i] for i in textured} == {500}
    # Untextured faces can have the colour 127 too, and they change as well. Of the 79 faces, 50 have 9096 and 12 have
    # 127 (from the fixture's RuneLite decoding), 16 have no colour and 1 has 0.
    assert Counter(result.face_colours) == {600: 50, None: 16, 500: 12, 0: 1}
    assert result.face_textures == model.face_textures


def test_a_retexture_to_the_value_65535_is_refused():
    # The client then sets the face texture to -1 (a short), which Model cannot hold with the colour of the face.
    with pytest.raises(ValueError, match="65535"):
        recolour_model(triangles(), (), ((5, 0xFFFF),))


def test_a_recolour_of_127_on_an_old_format_model_with_a_textured_face_is_refused():
    # ModelData.java line 943: the client gives a textured face of an old-format model the colour 127, and Model does not
    # store it, so the recolour would miss that face.
    with pytest.raises(ValueError, match="127"):
        recolour_model(triangles(), ((127, 500),), ())


def test_a_recolour_of_127_on_an_old_format_model_without_textured_faces_changes_its_faces():
    plain = triangles(face_textures=[None] * 4, face_colours=[127, 20, 127, 10], face_texture_triangles=[None] * 4)
    assert recolour_model(plain, ((127, 500),), ()).face_colours == [500, 20, 500, 10]
