from pathlib import Path

import pytest
from js5_builder import build_cache
from runelite_json import load_npcs

from rsps_toolkit.formats.js5 import Js5Store, NotInCacheError
from rsps_toolkit.formats.npc_definition import decode_npc, read_npc

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


@pytest.mark.parametrize("opcode", [3, 18, 42, 61, 74, 114, 122])
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
