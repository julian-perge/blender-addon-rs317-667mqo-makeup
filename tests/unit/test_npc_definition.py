import json
from dataclasses import replace
from pathlib import Path

import pytest
from js5_builder import build_cache
from runelite_json import load_npcs

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.js5 import Js5Store, NotInCacheError
from rsps_toolkit.formats.lighting import light
from rsps_toolkit.formats.npc_definition import (
    NpcDefinition,
    decode_npc,
    npc_lighting,
    npc_model,
    npc_scale,
    read_npc,
)

NPC_FIXTURES = Path(__file__).parent.parent / "fixtures/npc"


def test_the_six_test_npcs_equal_runelites_npc_loader():
    decoded = {int(path.stem): decode_npc(int(path.stem), path.read_bytes()) for path in NPC_FIXTURES.glob("*.dat")}
    assert sorted(decoded) == [260, 2477, 2805, 3078, 4233, 6594]
    assert decoded == load_npcs(NPC_FIXTURES / "npcs.json")


def test_the_gnome_keeps_its_models_sequences_and_recolours():
    # docs/research/13-npc-rigs.md: the gnome has models 9433, 2909 and 2915, four recolours, and stand and walk
    # sequences 195 and 189.
    gnome = decode_npc(4233, (NPC_FIXTURES / "4233.dat").read_bytes())
    assert (gnome.models, gnome.stand, gnome.walk, len(gnome.recolours)) == ((9433, 2909, 2915), 195, 189, 4)


def test_man_walks_with_the_unarmed_player_sequences():
    # docs/research/weapon-stance-sets.md section 1: the unarmed player walks with 819 HUMAN_WALK_F, 820 HUMAN_WALK_B,
    # 821 HUMAN_WALK_L and 822 HUMAN_WALK_R.
    man = decode_npc(3078, (NPC_FIXTURES / "3078.dat").read_bytes())
    assert (man.walk, man.walk_back, man.walk_left, man.walk_right) == (819, 820, 821, 822)


def test_an_npc_that_uses_every_opcode_of_read_next_reads_to_its_end():
    # Each opcode below is one branch of NPCComposition.readNext (lines 251 to 368), with the values that the branch
    # reads. The expected values follow the lines named beside them. Opcode 118 is covered below.
    data = b"".join(
        [
            bytes([1, 2, 0x01, 0x02, 0x03, 0x04]),  # 254 to 260: two models
            bytes([2]) + b"Gnome\0",  # 261 to 262: name
            bytes([12, 1]),  # 263 to 264: size
            bytes([13, 0x00, 0xC3]),  # 265 to 266: stand 195
            bytes([14, 0x00, 0x01]),  # 267 to 268: walk 1, replaced by opcode 17
            bytes([15, 0x00, 0x0F, 16, 0x00, 0x10]),  # 269 to 272: turn left 15, turn right 16
            bytes([17, 0x00, 0xBD, 0x00, 0xBE, 0x00, 0xBF, 0x00, 0xC0]),  # 273 to 277: walk 189, back, left, right
            bytes([30]) + b"Talk-to\0" + bytes([34]) + b"Hidden\0",  # 278 to 282: actions
            bytes([40, 1, 0x12, 0x34, 0xFF, 0xFE]),  # 283 to 291: one recolour
            bytes([41, 1, 0x00, 0x05, 0x00, 0x06]),  # 292 to 300: one retexture
            bytes([60, 2, 0x00, 0x07, 0x00, 0x08]),  # 301 to 307: two chat head models
            bytes([93, 95, 0x00, 0x03]),  # 308 to 311: hidden on the minimap, combat level 3
            bytes([97, 0x00, 0x6E, 98, 0x00, 0x8C, 99]),  # 312 to 317: width 110, height 140, visible
            bytes([100, 0xFB, 101, 0x05]),  # 318 to 321: ambient -5 and contrast 5, signed bytes
            bytes([102, 0x00, 0x01, 103, 0x00, 0x20]),  # 322 to 325: head icon, rotation
            bytes([106, 0x00, 0x05, 0xFF, 0xFF, 1, 0x00, 0x0A, 0xFF, 0xFF]),  # 326 to 366: varbit 5, two impostors
            bytes([107, 109, 111]),  # 327 to 332
            bytes([249, 2, 1, 0, 0, 1]) + b"text\0" + bytes([0, 0, 0, 2, 0, 0, 0, 7]),  # 333 to 334: parameters
            bytes([0]),
        ]
    )
    npc = decode_npc(1, data)
    assert (npc.models, npc.name) == ((0x0102, 0x0304), "Gnome")
    # Lines 265 to 277: opcode 17 sets the walk sequence again, then walk back, walk left and walk right. Frames.java
    # lines 238 and 239 copy the third and fourth to the walk left and walk right slots of a player (Player.java lines
    # 244 and 249).
    assert (npc.stand, npc.walk, npc.turn_left, npc.turn_right) == (195, 189, 15, 16)
    assert (npc.walk_back, npc.walk_left, npc.walk_right) == (190, 191, 192)
    assert npc.recolours == ((0x1234, 0xFFFE),)
    assert npc.retextures == ((5, 6),)
    assert (npc.width_scale, npc.height_scale) == (110, 140)
    # Lines 318 to 321 read the ambient and the contrast with `readByte`, which is signed.
    assert (npc.ambient, npc.contrast) == (-5, 5)


def test_opcode_118_reads_its_default_impostor():
    # NPCComposition.java lines 348 to 353: opcode 118 reads one more id than opcode 106, before the count.
    npc = decode_npc(1, bytes([118, 0xFF, 0xFF, 0x00, 0x03, 0x00, 0x2A, 0, 0x00, 0x0B, 13, 0x00, 0x07, 0]))
    assert npc.stand == 7


def test_fields_that_no_opcode_sets_keep_the_constructor_defaults():
    # NPCComposition.java lines 192 to 217: the name "null", -1 for each sequence, a scale of 128, and 0 for the
    # ambient and the contrast. `models` has no default in the constructor, so an NPC without opcode 1 has no models.
    npc = decode_npc(1, bytes([0]))
    assert (npc.models, npc.name, npc.recolours, npc.retextures) == ((), "null", (), ())
    assert (npc.stand, npc.walk, npc.turn_left, npc.turn_right) == (-1, -1, -1, -1)
    assert (npc.walk_back, npc.walk_right, npc.walk_left) == (-1, -1, -1)
    assert (npc.width_scale, npc.height_scale, npc.ambient, npc.contrast) == (128, 128, 0, 0)


READ_NEXT_OPCODES = {1, 2, *range(12, 18), *range(30, 35), 40, 41, 60, 93, 95, *range(97, 104), 106, 107, 109, 111}
READ_NEXT_OPCODES |= {118, 249}
"""The opcodes that NPCComposition.readNext reads, from the branches of lines 254 to 366. Opcode 0 ends a definition."""


@pytest.mark.parametrize("opcode", sorted(set(range(1, 256)) - READ_NEXT_OPCODES))
def test_an_npc_with_an_opcode_that_decode_does_not_read_is_refused(opcode):
    with pytest.raises(ValueError, match=f"unknown opcode {opcode}"):
        decode_npc(1, bytes([opcode, 0]))


def test_an_npc_with_bytes_after_its_end_is_refused():
    with pytest.raises(ValueError, match="after its closing opcode"):
        decode_npc(1, bytes([12, 2, 0, 0]))


def _npc_cache(folder: Path) -> Js5Store:
    build_cache(folder, npcs={npc: (NPC_FIXTURES / f"{npc}.dat").read_bytes() for npc in (260, 4233)})
    return Js5Store(folder)


def test_read_npc_reads_one_npc_by_id(tmp_path):
    reference = load_npcs(NPC_FIXTURES / "npcs.json")
    assert read_npc(_npc_cache(tmp_path), 4233) == reference[4233]


def test_read_npc_refuses_an_npc_that_the_cache_lacks(tmp_path):
    with pytest.raises(NotInCacheError, match="Group 9 of index 2 of the cache has no NPC 2805"):
        read_npc(_npc_cache(tmp_path), 2805)


LIT = json.loads((NPC_FIXTURES / "lit.json").read_text())["npcs"]


def load_model(model_id: int) -> Model:
    return decode((NPC_FIXTURES / "models" / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def fixture_npc(npc_id: int) -> NpcDefinition:
    return decode_npc(npc_id, (NPC_FIXTURES / f"{npc_id}.dat").read_bytes())


@pytest.mark.parametrize("npc_id", sorted(map(int, LIT)))
def test_each_test_npc_has_the_merged_model_and_lit_colours_of_the_revision_149_client(npc_id):
    # tests/fixtures/npc/lit.json: the unchanged revision 149 client's getModel (NpcModelReference.java).
    client = LIT[str(npc_id)]
    npc = fixture_npc(npc_id)
    model = npc_model(npc, load_model)
    shading = light(model, npc_lighting(npc))
    assert (len(model.vertices), len(model.faces)) == (client["vertex_count"], client["face_count"])
    assert (shading.corner_a, shading.corner_b, shading.corner_c) == (client["g"], client["k"], client["t"])


@pytest.mark.parametrize("npc_id", sorted(map(int, LIT)))
def test_the_scale_of_each_test_npc_gives_the_scaled_vertices_of_the_revision_149_client(npc_id):
    # The client scales with whole game units (ej.i), so a scaled vertex may differ from the client's by less than 1.
    client = LIT[str(npc_id)]
    npc = fixture_npc(npc_id)
    scale = npc_scale(npc)
    scaled = [tuple(c * s for c, s in zip(v, scale, strict=True)) for v in npc_model(npc, load_model).vertices]
    expected = list(zip(client["e"], client["l"], client["s"], strict=True))
    assert all(abs(a - b) < 1 for v, w in zip(scaled, expected, strict=True) for a, b in zip(v, w, strict=True))


def test_the_green_dragon_is_scaled_by_its_width_and_height_over_128():
    # docs/research/13-npc-rigs.md: the green dragon has width and height scale 110.
    assert npc_scale(fixture_npc(260)) == (110 / 128, 110 / 128, 110 / 128)


def test_an_npc_is_lit_with_its_ambient_plus_64_and_five_times_its_contrast_plus_850():
    # Revision 149 `ip.v` offsets 418-449 light with `64 + ambient` and `contrast field + 850`, and `ip.r` offsets
    # 896-906 store opcode 101's byte so that the contrast field reads as five times it (the two field multipliers
    # 646696543 and -1450163173 multiply to 5 in 32 bits). The 2018 client's NPCComposition.getModel line 421 agrees.
    npc = replace(fixture_npc(2805), ambient=7, contrast=-3)
    assert npc_lighting(npc) == (71, 835, -30, -50, -30)


def test_the_recolours_of_an_npc_apply_in_definition_order_and_its_retextures_apply_too():
    # NPCComposition.getModel lines 409 to 419 apply every recolour in order, then every retexture. A recolour and a
    # retexture change different fields, so this test cannot see the order between the two kinds.
    npc = replace(fixture_npc(2805), recolours=((1, 2), (2, 3)), retextures=((4, 5),))
    base = load_model(23889)
    base.face_colours = [1, 2, None, *base.face_colours[3:]]
    base.face_textures = [None, None, 4, *base.face_textures[3:]]
    model = npc_model(npc, lambda _: base)
    assert (model.face_colours[:3], model.face_textures[:3]) == ([3, 3, None], [None, None, 5])


def test_an_npc_with_a_model_without_vertex_skins_is_refused_with_the_model_ids():
    npc = fixture_npc(2477)
    with pytest.raises(ValueError, match="without vertex skins.*: 20310$"):
        npc_model(
            npc,
            lambda model_id: (
                replace(load_model(model_id), vertex_skins=None) if model_id == 20310 else load_model(model_id)
            ),
        )


def test_an_npc_with_no_models_is_refused():
    with pytest.raises(ValueError, match="has no models"):
        npc_model(replace(fixture_npc(2477), models=()), load_model)


def test_the_width_scale_goes_on_game_x_and_z_and_the_height_scale_on_game_height():
    # NPCComposition.getModel lines 436 to 437 scale x and z by widthScale and height by heightScale, over 128.
    assert npc_scale(replace(fixture_npc(2805), width_scale=64, height_scale=256)) == (0.5, 2.0, 0.5)
