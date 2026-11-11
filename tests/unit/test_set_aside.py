from dataclasses import replace
from pathlib import Path

import pytest

from rsps_toolkit.formats import decode, restore_faces, set_aside_faces

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
OLD_FORMAT = sorted([*(MODELS / "osrs").glob("*.dat"), *(MODELS / "worn").glob("*.dat")])


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_restoring_the_set_aside_faces_gives_back_the_model(dat: Path):
    model = decode(dat.read_bytes())

    kept, aside = set_aside_faces(model)

    assert restore_faces(kept, aside) == model


def test_faces_that_repeat_a_vertex_are_set_aside_and_the_rest_kept():
    # The Old School model 6658 has faces such as (a, a, b), which have no area.
    model = decode((MODELS / "worn" / "6658.dat").read_bytes())
    repeating = [i for i, face in enumerate(model.faces) if len(set(face)) < 3]

    kept, aside = set_aside_faces(model)

    assert repeating
    assert [face.index for face in aside] == repeating
    assert kept.faces == [face for i, face in enumerate(model.faces) if i not in repeating]
    assert kept.vertices == model.vertices


def test_restoring_onto_a_model_without_face_skins_leaves_them_out():
    model = decode((MODELS / "worn" / "6658.dat").read_bytes())
    kept, aside = set_aside_faces(model)

    restored = restore_faces(replace(kept, face_skins=None), aside)

    assert restored == replace(model, face_skins=None)
