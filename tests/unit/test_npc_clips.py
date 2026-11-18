import json
import os
from pathlib import Path

import pytest

from rsps_toolkit.animation.clip import CONFIG_INDEX, FRAME_INDEX, SEQUENCE_GROUP, frame_map_id
from rsps_toolkit.animation.frames import decode_sequence
from rsps_toolkit.formats.js5 import Js5Store
from rsps_toolkit.formats.npc_clips import NpcClip, load_npc_clips
from rsps_toolkit.formats.npc_definition import NPC_GROUP, decode_npc

# The expected clips were read by hand from the source.json files of the AnotherScape models mod 1.0.0, in the folders
# that "Sample NPCs" of docs/research/160-npc-clips.md names, after the rules of spec/160-npc-clips.md.
TABLE = load_npc_clips()


def clips(npc_id: int) -> list[tuple[str, int, str | None]]:
    return [(clip.key, clip.sequence, clip.runelite_name) for clip in TABLE.clips(npc_id)]


def test_the_green_dragon_has_attack_flinch_and_death_with_no_melee_key_and_no_runelite_name():
    # green_dragon_260/source.json gives melee 91 and attack 91, so the repeat rule (answer 1) keeps only attack. Its
    # labels are the plain words melee, flinch and death, so no clip has a RuneLite name (answer 5).
    assert clips(260) == [("attack", 91, None), ("flinch", 89, None), ("death", 92, None)]


def test_the_giant_spider_has_attack_mage_flinch_and_death_with_their_runelite_names():
    assert clips(2477) == [
        ("attack", 5319, "SPIDER_UPDATE_ATTACK_LARGE"),
        ("mage", 5322, "SPIDER_UPDATE_CASTING_LARGE"),
        ("flinch", 5320, "SPIDER_UPDATE_DEFEND_LARGE"),
        ("death", 5321, "SPIDER_UPDATE_DEATH_LARGE"),
    ]


def test_the_elf_warrior_keeps_its_clips_because_names_are_compared_with_case_ignored():
    # elf_warrior/source.json says "Elf Warrior", and snapshot 430 says "Elf warrior" (answer 3).
    assert TABLE.names[5293] == "Elf Warrior"
    assert clips(5293) == [
        ("range", 2728, "WANTED_RANGER_READY"),
        ("mage", 1364, "POH_SMASH_MAGIC_TABLET_SPELL"),
        ("flinch", 378, "HUMAN_DDAGGER_BLOCK"),
        ("death", 836, "HUMAN_DEATH"),
    ]


def test_the_flesh_crawler_has_no_walk_key():
    # flesh_crawler/source.json marks its walk 1184 cache_same_rig_verified. The table holds no walk key (answer 2).
    assert clips(2498) == [
        ("attack", 1184, "KALPHITE_ATTACK_MANDIBLES"),
        ("flinch", 1186, "KALPHITE_BLOCK"),
        ("death", 1190, "KALPHITE_DEATH"),
    ]


def test_an_npc_id_in_two_folders_has_one_entry_with_the_clips_of_the_folder_that_has_them():
    # aberrant_spectre and aberrant_spectre_clean both give NPC 2, and king_black_dragon and echo_king_black_dragon
    # both give NPC 239 (rule 7).
    assert clips(2) == [("attack", 1507, "SPECTER_ATTACK"), ("death", 1508, "SPECTER_DEATH")]
    assert clips(239) == [
        ("attack", 80, "DRAGON_ATTACK"),
        ("flinch", 89, "DRAGON_BLOCK"),
        ("death", 92, "DRAGON_DEATH"),
    ]


def test_the_abyssal_demon_has_no_entry_because_its_clips_have_another_mark():
    # abyssal_demon/source.json marks its clips runelite_model_dumper_baked_obj (answer 4).
    assert 415 not in TABLE.rows
    assert TABLE.clips(415) == ()


@pytest.mark.parametrize("npc_id", [2805, 4233, 6594, 3078])
def test_an_npc_that_the_mod_does_not_list_has_no_clips(npc_id):
    # No source.json of the mod has the NPC id of the cow, the gnome, the ent or Man (research note).
    assert npc_id not in TABLE.rows
    assert TABLE.clips(npc_id) == ()


def test_the_header_names_the_mod_version_the_snapshot_the_generator_and_the_unverified_note():
    # The version is in META-INF/neoforge.mods.toml of the jar, and the unverified mark is ADR 0030. The SHA-256 of the
    # jar is in "Source" of docs/research/160-npc-clips.md.
    header = TABLE.header
    assert (header["mod"]["mod_id"], header["mod"]["version"]) == ("anotherscape_models", "1.0.0")
    assert header["mod"]["sha256"] == "ce0f9535c74a3f2910a3981d999093d5e64b6dfa016e66f5d95c76229df8df7c"
    assert header["snapshot"] == 430
    assert header["generator"] == "scripts/generate-npc-clips.py"
    assert header["research"] == "docs/research/160-npc-clips.md"
    assert "unverified" in header["note"]
    # This compares the file with itself on purpose: no test asserts the count of the file (answer 7).
    assert header["counts"] == {"npcs": len(TABLE.rows), "clips": sum(len(row) for row in TABLE.rows.values())}


def test_the_buttons_follow_attack_melee_range_mage_flinch_death_then_other_keys_by_name(tmp_path):
    # Design decision 6 of issue 160.
    path = tmp_path / "npc_clips.json"
    keys = ("swipe", "death", "flinch", "mage", "range", "melee", "attack", "phase_in")
    row = {"name": "Test", "clips": {key: {"sequence": number} for number, key in enumerate(keys)}}
    path.write_text(json.dumps({"npcs": {"7": row}}))
    table = load_npc_clips(path)
    assert [clip.key for clip in table.clips(7)] == [
        "attack",
        "melee",
        "range",
        "mage",
        "flinch",
        "death",
        "phase_in",
        "swipe",
    ]
    assert table.clips(7)[0] == NpcClip("attack", 6, None)


SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()


@pytest.mark.skipif(
    not ("RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()),
    reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder",
)
def test_every_npc_has_its_name_in_snapshot_430_and_every_frame_of_its_clips_is_on_its_stand_frame_map():
    # Rules 2 and 5 of the spec, and the fit rule of the NPC bake, which checks every frame (spec 13). The stored name
    # and the sequence ids come from the mod.
    assert_fits_snapshot_430(TABLE)


def assert_fits_snapshot_430(table) -> None:
    store = Js5Store(SNAPSHOT_430)
    npcs = store.files(CONFIG_INDEX, NPC_GROUP)
    sequences = store.files(CONFIG_INDEX, SEQUENCE_GROUP)
    groups: dict[int, dict[int, bytes]] = {}

    def frame_maps(sequence_id: int) -> list[int]:
        maps = []
        for group, file in decode_sequence(sequences[sequence_id]).frames:
            if group not in groups:
                groups[group] = store.files(FRAME_INDEX, group)
            maps.append(frame_map_id(groups[group][file]))
        return maps

    for npc_id, row in table.rows.items():
        npc = decode_npc(npc_id, npcs[npc_id])
        assert npc.name.casefold() == table.names[npc_id].casefold(), npc_id
        stand_map = frame_maps(npc.stand)[0]
        for clip in row:
            assert set(frame_maps(clip.sequence)) == {stand_map}, (npc_id, clip.key)
