import json
from pathlib import Path

import pytest

from rsps_toolkit.formats import decode
from rsps_toolkit.presets import BODY_PARTS, MIRRORED_LABELS, PRESETS, apply_preset, detect_model_type

FIXTURES = Path(__file__).parent.parent / "fixtures"
WORN = sorted((FIXTURES / "models" / "worn").glob("*.dat"))

# The original exporter read labels back from Blender's 32-bit vertex group weights with int(weight * 100),
# which truncates some labels by one (8 became 7), so it detected these three models wrongly. The expected
# types here are what its rules give for the true labels.
DETECTED_WITH_TRUE_LABELS = {"7122": "NECKLACE", "16010": "BOOTS", "19830": "BODY"}


def recorded(dat: Path) -> dict:
    return json.loads((FIXTURES / "presets" / f"{dat.stem}.json").read_text())


@pytest.mark.parametrize("dat", WORN, ids=lambda p: p.stem)
def test_detected_type_matches_the_original_exporter(dat: Path):
    model = decode(dat.read_bytes())

    expected = DETECTED_WITH_TRUE_LABELS.get(dat.stem, recorded(dat)["detected"])
    assert detect_model_type(model.vertex_skins or []) == expected


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("dat", WORN, ids=lambda p: p.stem)
def test_preset_matches_the_original_exporter(dat: Path, preset: str):
    expected = recorded(dat)[preset]
    model = decode(dat.read_bytes())

    result = apply_preset(model, preset)

    assert result.render_priorities == expected["render_priorities"]
    assert result.face_skins == (expected["face_skins"] or [0] * len(model.faces))


def weighter_reference() -> dict:
    return json.loads((FIXTURES / "weighter_reference.json").read_text())


def test_body_parts_are_the_original_weighters_buttons_in_panel_order():
    # The original weighter stored each body part's label as a vertex group weight of label / 100.
    reference = weighter_reference()
    by_operator = {b["operator"]: b for b in reference["buttons"]}
    expected = [(by_operator[op]["button"], round(by_operator[op]["weight"] * 100)) for op in reference["panel_order"]]

    assert [(part.name, part.label) for part in BODY_PARTS] == expected


def test_each_body_part_mirrors_as_the_original_weighters_mirror_map_says():
    mirror = {round(float(a) * 100): round(float(b) * 100) for a, b in weighter_reference()["mirror_weights"].items()}

    assert [part.mirrored for part in BODY_PARTS] == [mirror.get(part.label) for part in BODY_PARTS]
    assert MIRRORED_LABELS == mirror
