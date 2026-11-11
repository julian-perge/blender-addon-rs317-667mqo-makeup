import json
from pathlib import Path

import pytest

from rsps_toolkit.formats import face_colour_to_rgb
from rsps_toolkit.formats.colour import original_exporter_colour

COLOURS = json.loads((Path(__file__).parent.parent / "fixtures" / "colours.json").read_text())


@pytest.mark.parametrize("brightness", [0.9, 0.8, 0.7, 0.6])
def test_face_colours_match_the_client_palette(brightness: float):
    rows = [row for row in COLOURS if row[1] == brightness]

    actual = [(colour, *face_colour_to_rgb(colour, brightness)) for colour, _, *_ in rows]

    assert actual == [(colour, r, g, b) for colour, _, r, g, b in rows]


def test_the_original_exporters_colour_conversion():
    # The original exporter (dat_exporter.py at 547a2aa, rgb_to_rune_hsl) wrote faces 0 and 1 of
    # tests/fixtures/pmn/5412.json in this colour, converted from Blender's default Base Color (0.8, 0.8, 0.8).
    recorded = json.loads((Path(__file__).parent.parent / "fixtures" / "pmn" / "5412.json").read_text())

    assert original_exporter_colour(0.8, 0.8, 0.8) == recorded["face_colours"][0]
