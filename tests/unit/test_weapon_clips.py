from rsps_toolkit.animation.clip import load_clip_names
from rsps_toolkit.formats.item_wear import load_item_wear
from rsps_toolkit.formats.weapon_clips import load_weapon_clips

# The stance tuples come from the sample table in docs/research/weapon-stance-sets.md, section 4. The attack tuples
# were read by hand from Alter's bas_mappings.json at 9ddbbbe (sets bas.abyssal_whip, bas.2h_sword and
# bas.default_player), and the Boxing gloves from the plugin's data.json at 504f6bd (set "Boxing gloves").
TABLE = load_weapon_clips()
UNARMED_STANCE = (808, 823, 819, 820, 821, 822, 824)
STAFF_STANCE = (813, 1209, 1205, 1206, 1207, 1208, 1210)


def test_the_research_notes_sample_weapons_have_alters_stance_clips():
    assert {item: TABLE.clips(item).stance for item in (4151, 1333, 1319, 861, 9185, 11802, 4153, 4718)} == {
        4151: (808, 823, 1660, 1660, 1660, 1660, 1661),
        1333: UNARMED_STANCE,
        1319: (2561, 823, 2562, 2562, 2562, 2562, 2563),
        861: UNARMED_STANCE,
        9185: (4591, 823, 4226, 4227, 821, 822, 4228),
        11802: (7053, 7044, 7052, 7052, 7048, 7047, 7043),
        4153: (1662, 823, 1663, 1663, 1663, 1663, 1664),
        4718: (2065, 823, 2064, 2064, 2064, 2064, 824),
    }
    assert all(TABLE.clips(item).stance == STAFF_STANCE for item in (1381, 3204, 1249, 12926))


def test_attack_clips_follow_alters_fields_and_a_missing_one_is_none():
    assert TABLE.clips(4151).attack == (1658, 1658, -1, 1658, 1659)
    assert TABLE.clips(1319).attack == (407, 407, 406, 407, 410)
    assert TABLE.unarmed.attack == (422, 423, -1, 422, 424)


def test_a_weapon_neither_table_lists_gets_the_unarmed_clips():
    assert not TABLE.lists(4162)
    assert TABLE.clips(4162) == TABLE.unarmed
    assert TABLE.unarmed.stance == UNARMED_STANCE


def test_a_weapon_only_the_plugin_lists_has_its_stance_and_block_but_no_style_buttons():
    assert TABLE.lists(7671)
    assert TABLE.clips(7671).stance == (3677, 823, 3680, 3680, 3680, 3680, 824)
    assert TABLE.clips(7671).attack == (-1, -1, -1, -1, 3679)


def test_every_clip_a_weapon_gives_is_a_player_clip_of_snapshot_430_and_every_weapon_takes_the_weapon_slot():
    player_clips = set(load_clip_names())
    clips = {clip for weapon in TABLE.items.values() for clip in weapon.stance + weapon.attack if clip != -1}
    assert clips <= player_clips
    slots = load_item_wear().slot_of
    assert {slots.get(item) for item in TABLE.items} == {3}
