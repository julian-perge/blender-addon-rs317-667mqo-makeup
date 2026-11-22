"""Chathead models (spec 183, section 5). Expected values come from RuneLite's decoding of snapshot 430
(fixtures/chathead, fixtures/npc/chathead-models.json, fixtures/appearance/KitDefinitions.json) and from `hu.s`, `ip.e`
and `hy.u` of gamepack 149 (docs/research/chatheads.md)."""

import json
from pathlib import Path

import pytest
from runelite_json import load_kits

from rsps_toolkit.formats.appearance import default_equipment, load_palette
from rsps_toolkit.formats.cache_profile import PALETTE_PATH
from rsps_toolkit.formats.chathead import WIDGET_LIGHTING, npc_head_model, player_head_model
from rsps_toolkit.formats.item_definition import decode_item
from rsps_toolkit.formats.model import Model
from rsps_toolkit.formats.npc_definition import decode_npc

FIXTURES = Path(__file__).parent.parent / "fixtures"
KITS = load_kits(FIXTURES / "appearance" / "KitDefinitions.json")
PALETTE = load_palette(PALETTE_PATH)
ITEM_ROWS = {row["id"]: row for row in json.loads((FIXTURES / "chathead" / "ItemDefinitions.json").read_text())}


def tagged(model_id: int) -> Model:
    """A one-face model whose face colour is its id, so a test can see which models a head joined, and in what order."""
    corner = model_id % 4000 * 3
    return Model(
        vertices=[(corner, 0, 0), (corner + 1, 0, 0), (corner, 1, 0)],
        faces=[(0, 1, 2)],
        face_colours=[model_id],
        face_textures=[None],
        render_priorities=[0],
        face_alphas=[0],
        face_texture_triangles=[None],
        flat_shaded=[False],
        vertex_skins=[1, 1, 1],
    )


@pytest.mark.parametrize("item_id", sorted(ITEM_ROWS))
def test_an_item_keeps_its_head_models_as_runelite_reads_them(item_id):
    row = ITEM_ROWS[item_id]
    worn = decode_item(item_id, (FIXTURES / "chathead" / f"item-{item_id}.dat").read_bytes()).worn

    assert worn.male_head_models == (row["maleHeadModel"], row["maleHeadModel2"])
    assert worn.female_head_models == (row["femaleHeadModel"], row["femaleHeadModel2"])


def test_man_keeps_his_chathead_model_53():
    # RuneLite's row of NPC 3078 in fixtures/npc/chathead-models.json.
    man = decode_npc(3078, (FIXTURES / "npc" / "3078.dat").read_bytes())
    assert man.chathead_models == (53,)


def test_the_male_default_head_joins_the_chathead_models_of_the_kits_in_slot_order():
    # hu.s joins the head of each slot in slot order. Of the male default kits, the hair kit 0 in slot 8 has chathead
    # model 63 and the jaw kit 10 in slot 11 has 81 (KitDefinitions.json); the others have none.
    equipment = default_equipment(KITS)
    head = player_head_model(equipment, KITS, {}, tagged, [0] * 5, PALETTE)
    assert head.face_colours == [63, 81]


def test_a_helmet_gives_its_two_male_head_models_and_the_kits_of_the_other_slots_theirs():
    # The Dragon med helm 1149 has the male head models 57 and 71 (RuneLite's row), which iz.o joins in that order.
    item = decode_item(1149, (FIXTURES / "chathead" / "item-1149.dat").read_bytes()).worn
    equipment = default_equipment(KITS)
    equipment[0] = 1149 + 512
    head = player_head_model(equipment, KITS, {1149: item}, tagged, [0] * 5, PALETTE)
    assert head.face_colours == [57, 71, 63, 81]


def test_the_head_is_recoloured_with_the_colour_choices_as_the_body_is():
    # hu.s recolours the joined head with hv.a and hv.j, then hv.n and hv.r, as hu.l does the body. The hair colour slot
    # 0 replaces its source colour with the row of the choice.
    equipment = default_equipment(KITS)
    source, shown = PALETTE.primary_sources[0], PALETTE.primary_choices[0][3]
    head = player_head_model(equipment, KITS, {}, lambda i: tagged(source), [3, 0, 0, 0, 0], PALETTE)
    assert set(head.face_colours) == {shown}


def test_equipment_with_no_head_model_is_refused():
    with pytest.raises(ValueError, match="no chathead model"):
        player_head_model([0] * 12, KITS, {}, tagged, [0] * 5, PALETTE)


def test_an_npc_head_is_its_chathead_models_recoloured_with_no_scale():
    # ip.e joins the chathead models and applies the NPC's recolours, with no width or height scale.
    man = decode_npc(3078, (FIXTURES / "npc" / "3078.dat").read_bytes())
    find, show = man.recolours[0]
    head = npc_head_model(man, lambda i: tagged(find))
    assert head.face_colours == [show]
    assert head.vertices == tagged(find).vertices


def test_an_npc_with_no_chathead_models_is_refused():
    cow = decode_npc(2805, (FIXTURES / "npc" / "2805.dat").read_bytes())
    with pytest.raises(ValueError, match="no chathead models"):
        npc_head_model(cow, tagged)


def test_the_widget_light_is_that_of_hy_u():
    assert WIDGET_LIGHTING == (64, 768, -50, -10, -50)
