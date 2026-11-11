import json

import pytest

from rsps_toolkit.formats.appearance_preset import AppearancePreset, dumps_preset, loads_preset

PRESET = AppearancePreset(149, 430, True, (0, 0, 0, 0, 312, 0, 317, 326, 301, 323, 335, 0), (1, 2, 3, 4, 5))


def test_preset_round_trips():
    assert loads_preset(dumps_preset(PRESET)) == PRESET


def test_unknown_schema_version_is_refused():
    data = json.loads(dumps_preset(PRESET)) | {"schema_version": 2}
    with pytest.raises(ValueError, match="schema version 2"):
        loads_preset(json.dumps(data))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"body_type": "other"}, "body type"),
        ({"equipment": [0] * 11}, "twelve"),
        ({"equipment": [0] * 11 + [-1]}, "twelve"),
        ({"colours": [0, 0, 0, 0]}, "five"),
        ({"colours": [0, 0, 0, 0, 1.5]}, "five"),
        ({"client_revision": "149"}, "client_revision"),
        ({"extra": 1}, "keys"),
    ],
)
def test_invalid_presets_are_refused(change, message):
    data = json.loads(dumps_preset(PRESET)) | change
    with pytest.raises(ValueError, match=message):
        loads_preset(json.dumps(data))


def test_missing_key_is_refused():
    data = json.loads(dumps_preset(PRESET))
    del data["colours"]
    with pytest.raises(ValueError, match="keys"):
        loads_preset(json.dumps(data))
