import pytest

from rsps_toolkit.formats.appearance import load_palette
from rsps_toolkit.formats.appearance_colours import colour_choices
from rsps_toolkit.formats.cache_profile import PALETTE_PATH
from rsps_toolkit.formats.colour import face_colour_to_rgb

PALETTE = load_palette(PALETTE_PATH)


def rgb(colour):
    return face_colour_to_rgb(colour, 1.0)


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b), strict=True))


@pytest.mark.parametrize("slot", range(5))
def test_every_choice_of_the_palette_is_listed_once(slot):
    choices = colour_choices(PALETTE, slot)
    assert sorted(c.index for c in choices) == list(range(len(PALETTE.primary_choices[slot])))
    assert all(c.colour == PALETTE.primary_choices[slot][c.index] for c in choices)


def test_a_legs_colour_has_the_name_of_the_torso_colour_it_looks_like():
    torso = colour_choices(PALETTE, 1)
    for choice in colour_choices(PALETTE, 2):
        nearest = min(torso, key=lambda t: distance(t.colour, choice.colour))
        assert choice.name == nearest.name


def test_legs_keep_the_clients_order_with_emerald_first():
    assert [c.name for c in colour_choices(PALETTE, 2)][:3] == ["Emerald", "Khaki", "Charcoal"]


def test_hair_colours_shared_with_clothing_are_the_same_colours():
    hair, torso = colour_choices(PALETTE, 0), colour_choices(PALETTE, 1)
    assert [c.colour for c in hair[12:]] == [c.colour for c in torso[16:]]
    assert (hair[0].name, hair[12].name) == ("Dark brown", "Black")


def test_skin_tones_run_from_lightest_to_darkest_then_green_black_and_white():
    skin = colour_choices(PALETTE, 4)
    tones = skin[:8]
    assert [c.name for c in tones] == [f"Tone {n}" for n in range(1, 9)]
    lightness = [sum(rgb(c.colour)) for c in tones]
    assert lightness == sorted(lightness, reverse=True)
    green, black, white = (rgb(c.colour) for c in skin[8:])
    assert [c.name for c in skin[8:]] == ["Green", "Black", "White"]
    assert green[1] > green[0] and green[1] > green[2]
    assert max(black) < 16 and min(white) > 240


def test_shoe_colours_carry_the_wikis_names():
    assert [c.name for c in colour_choices(PALETTE, 3)] == ["Brown", "Khaki", "Ashen", "Dark", "Terracotta", "Grey"]
