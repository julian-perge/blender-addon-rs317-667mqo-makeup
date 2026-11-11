import json
from dataclasses import replace
from pathlib import Path

import pytest
from runelite_json import load_items, load_kits

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import (
    WornItem,
    assemble_body,
    default_equipment,
    item_model,
    items_for_slot,
    kit_model,
    load_palette,
    merge,
)

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"
KITS = load_kits(FIXTURES / "KitDefinitions.json")
PALETTE = load_palette(FIXTURES / "revision149-palette.json")
ITEMS = load_items(FIXTURES / "ItemDefinitions.json")
MALE_BODY_MODELS = [230, 249, 292, 151, 176, 254, 181]


def load_model(model_id: int) -> Model:
    return decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")


@pytest.mark.parametrize("female", [False, True])
def test_default_equipment_matches_the_array_the_client_builds_itself(female):
    reference = json.loads((FIXTURES / "reference.json").read_text())
    expected = reference["client_default_equipment"]["female" if female else "male"]
    assert default_equipment(KITS, female=female) == expected


def test_kit_catalog_has_every_identity_kit_with_unsigned_colours():
    assert len(KITS) == 151
    assert KITS[34].recolours == ((0xFFFF & -22464, 4550),)
    assert KITS[0].model_ids == (230,)


def test_palette_row_four_is_the_revision_149_row():
    assert PALETTE.primary_choices[4] == (4550, 4537, 5681, 5673, 5790, 6806, 8076, 4574, 17050, 0, 127)
    assert PALETTE.secondary_sources[0] == 0xFFFF & -10304


def test_merge_keeps_only_used_vertices_and_shares_equal_positions():
    a = load_model(230)
    merged = merge([a, a])
    assert len(merged.faces) == 2 * len(a.faces)
    assert len(merged.vertices) == len({a.vertices[v] for face in a.faces for v in face})
    assert merged.faces[: len(a.faces)] == merged.faces[len(a.faces) :]


def test_assembled_default_male_body_counts():
    body = assemble_body(default_equipment(KITS), KITS, load_model, [0, 0, 0, 0, 0], PALETTE)
    parts = [load_model(i) for i in MALE_BODY_MODELS]
    assert len(body.faces) == sum(len(p.faces) for p in parts) == 476
    assert len(body.vertices) == 264
    assert len(body.render_priorities) == len(body.faces)
    assert body.face_skins is not None and body.vertex_skins is not None


def test_kit_recolour_replaces_its_find_colour():
    source = load_model(KITS[34].model_ids[0])
    find, to = KITS[34].recolours[0]
    assert find in source.face_colours
    coloured = kit_model(KITS[34], load_model)
    assert find not in coloured.face_colours
    assert coloured.face_colours.count(to) >= source.face_colours.count(find)


def test_choice_past_the_end_of_a_row_changes_nothing():
    equipment = default_equipment(KITS)
    plain = assemble_body(equipment, KITS, load_model, [0, 0, 0, 0, 0], PALETTE)
    past = assemble_body(equipment, KITS, load_model, [99, 99, 99, 99, 99], PALETTE)
    assert past.face_colours == plain.face_colours


def test_kit_model_does_not_change_the_loaded_model():
    model = load_model(230)
    before = list(model.face_colours)
    kit_model(KITS[34], lambda _id: model)
    assert model.face_colours == before


def test_worn_items_and_unknown_kits_are_refused():
    equipment = default_equipment(KITS)
    with pytest.raises(ValueError, match="not in the item catalog"):
        assemble_body([*equipment[:11], 512 + 1127], KITS, load_model, [0] * 5, PALETTE)
    with pytest.raises(ValueError, match="does not exist"):
        assemble_body([*equipment[:11], 256 + 200], KITS, load_model, [0] * 5, PALETTE)


def test_bare_kit_ids_and_negative_values_are_refused_not_skipped():
    equipment = default_equipment(KITS)
    for bad in (18, 255, -1):
        with pytest.raises(ValueError, match="neither empty nor a kit entry"):
            assemble_body([*equipment[:11], bad], KITS, load_model, [0] * 5, PALETTE)


def test_negative_colour_choice_is_refused():
    with pytest.raises(ValueError, match="negative"):
        assemble_body(default_equipment(KITS), KITS, load_model, [0, 0, -1, 0, 0], PALETTE)


def test_merge_offsets_texture_triangle_references_per_model():
    a = load_model(230)
    b = replace(
        a,
        texture_triangles=[(0, 1, 2)],
        face_texture_triangles=[0, *a.face_texture_triangles[1:]],
        face_textures=[5, *a.face_textures[1:]],
        face_colours=[None, *a.face_colours[1:]],
    )
    merged = merge([b, b])
    assert merged.face_texture_triangles[len(a.faces)] == 1
    assert len(merged.texture_triangles) == 2


@pytest.mark.parametrize("female", [False, True])
@pytest.mark.parametrize("colours", [[0, 0, 0, 0, 0], [1, 2, 3, 4, 5]])
def test_assembled_body_matches_unchanged_revision149_client(colours, female):
    reference = json.loads((FIXTURES / "reference.json").read_text())
    case = next(c for c in reference["cases"] if c["colours"] == colours and c["female"] == female)
    equipment = reference["female_equipment"] if female else reference["equipment"]
    body = assemble_body(equipment, KITS, load_model, colours, PALETTE)
    actual = {
        "vertex_count": len(body.vertices),
        "face_count": len(body.faces),
        "vertices": [list(vertex) for vertex in body.vertices],
        "faces": [list(face) for face in body.faces],
        "face_colours": body.face_colours,
        "face_alphas": body.face_alphas,
        "render_priorities": body.render_priorities,
        "face_skins": body.face_skins,
        "vertex_skins": body.vertex_skins,
        "face_textures": body.face_textures,
        "face_texture_triangles": body.face_texture_triangles,
        "texture_triangles": [list(triangle) for triangle in body.texture_triangles],
        "flat_shaded": body.flat_shaded,
    }
    assert actual.keys() == case["before_lighting"].keys()
    for field, values in actual.items():
        assert values == case["before_lighting"][field], field
    # The counts are the client's own: 264 vertices and 476 faces male, 260 and 477 female (reference.json).
    expected_counts = (477, 260) if female else (476, 264)
    assert (actual["face_count"], actual["vertex_count"]) == expected_counts


def stand_in_models(model_id: int) -> Model:
    return load_model({1: 230, 2: 249, 3: 292}[model_id])


def worn(male_models, male_offset=0, recolours=()):
    return WornItem(1, "Test item", male_models, male_offset, (-1, -1, -1), 0, recolours, ())


# Worn model ids and recolours below are read from RuneLite's ItemDefinitions.json for snapshot 430; the client decoder
# agrees with them in test_item_catalog_matches_what_the_client_decoded.
def test_item_catalog_reads_the_sample_items_with_unsigned_colours():
    assert ITEMS[2653].male_models == (3379, 164, 3381)
    assert ITEMS[2653].female_models == (3383, 344, 3381)
    assert ITEMS[2653].recolours[0] == (61, 0xFFFF & -29403)
    assert ITEMS[4087].male_models == (5024, -1, -1)


def test_item_model_joins_up_to_three_pieces():
    sizes = [len(stand_in_models(i).faces) for i in (1, 2, 3)]
    assert len(item_model(worn((1, -1, -1)), False, stand_in_models).faces) == sizes[0]
    assert len(item_model(worn((1, 2, -1)), False, stand_in_models).faces) == sizes[0] + sizes[1]
    assert len(item_model(worn((1, 2, 3)), False, stand_in_models).faces) == sum(sizes)


def test_third_piece_is_ignored_without_a_second_piece():
    assert len(item_model(worn((1, -1, 3)), False, stand_in_models).faces) == len(stand_in_models(1).faces)


def test_offset_moves_every_vertex_down_by_the_offset_only_in_y():
    base = item_model(worn((1, -1, -1)), False, stand_in_models)
    moved = item_model(worn((1, -1, -1), male_offset=6), False, stand_in_models)
    assert moved.vertices == [(x, y + 6, z) for x, y, z in base.vertices]


def test_item_recolours_run_in_order_and_do_not_change_the_loaded_model():
    source = stand_in_models(1)
    find = source.face_colours[0]
    item = worn((1, -1, -1), recolours=((find, 7), (7, 9)))
    result = item_model(item, False, lambda _id: source)
    assert find not in result.face_colours and 9 in result.face_colours and 7 not in result.face_colours
    assert find in source.face_colours


def test_item_without_a_worn_model_for_the_body_type_is_an_error():
    with pytest.raises(ValueError, match="no worn model for the female body"):
        item_model(worn((1, -1, -1)), True, stand_in_models)


def test_item_namespace_is_not_the_kit_namespace():
    equipment = default_equipment(KITS)
    with pytest.raises(ValueError, match="not in the item catalog"):
        assemble_body([*equipment[:11], 512 + 18], KITS, load_model, [0] * 5, PALETTE, ITEMS)


OUTFIT_CASES = [
    (c["outfit"], c["female"], c["colours"])
    for c in json.loads((FIXTURES / "reference.json").read_text())["cases"]
    if c.get("outfit")
]


@pytest.mark.parametrize(("outfit", "female", "colours"), OUTFIT_CASES)
def test_worn_outfit_matches_unchanged_revision149_client(outfit, female, colours):
    reference = json.loads((FIXTURES / "reference.json").read_text())
    case = next(
        c for c in reference["cases"] if (c.get("outfit"), c["female"], c["colours"]) == (outfit, female, colours)
    )
    body = assemble_body(case["equipment"], KITS, load_model, colours, PALETTE, ITEMS, female=female)
    expected = case["before_lighting"]
    assert len(body.faces) == expected["face_count"]
    assert len(body.vertices) == expected["vertex_count"]
    assert [list(v) for v in body.vertices] == expected["vertices"]
    assert [list(f) for f in body.faces] == expected["faces"]
    assert body.face_colours == expected["face_colours"]
    assert body.face_textures == expected["face_textures"]
    assert body.face_alphas == expected["face_alphas"]
    assert body.render_priorities == expected["render_priorities"]
    assert body.face_skins == expected["face_skins"]
    assert body.vertex_skins == expected["vertex_skins"]


def test_item_catalog_matches_what_the_client_decoded():
    reference = json.loads((FIXTURES / "reference.json").read_text())
    for item_id, decoded in reference["items"].items():
        item = ITEMS[int(item_id)]
        raw = decoded["client_raw"]
        assert [*item.recolours] == [
            (a & 0xFFFF, b & 0xFFFF) for a, b in zip(raw["o"] or (), raw["x"] or (), strict=True)
        ]


def test_a_body_part_without_a_selectable_kit_leaves_its_slot_empty():
    without_torso = {k: v for k, v in KITS.items() if v.body_part != 2}
    assert default_equipment(without_torso)[4] == 0


def test_merging_a_new_format_model_gives_an_old_encoding_model_without_its_extra_source_data():
    newer = load_model(3383)
    assert newer.new_data is not None
    merged = merge([newer, load_model(344)])
    assert merged.new_data is None and merged.encoding.value == "old"


SLOT_OF = {1149: 0, 2653: 4, 3140: 4, 4087: 7}


def test_the_items_of_a_slot_are_those_the_slot_table_places_there_by_name():
    assert [i.id for i in items_for_slot(ITEMS, False, SLOT_OF, 4)] == [3140, 2653]
    assert [i.id for i in items_for_slot(ITEMS, False, SLOT_OF, 7)] == [4087]
    assert items_for_slot(ITEMS, False, SLOT_OF, 2) == []


def test_the_items_of_a_slot_need_a_worn_model_for_the_body_type():
    male_only = {**ITEMS, 3140: replace(ITEMS[3140], female_models=(-1, -1, -1))}
    assert [i.id for i in items_for_slot(male_only, True, SLOT_OF, 4)] == [2653]
    assert [i.id for i in items_for_slot(male_only, False, SLOT_OF, 4)] == [3140, 2653]


def test_an_equipment_array_with_no_kit_or_item_is_refused_not_assembled_empty():
    with pytest.raises(ValueError, match="nothing to assemble"):
        assemble_body([0] * 12, KITS, load_model, [0] * 5, PALETTE)
