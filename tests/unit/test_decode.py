import json
from pathlib import Path

import pytest

from rsps_toolkit.formats import decode

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
OLD_FORMAT = sorted((MODELS / "osrs").glob("*.dat"))


def reference(dat: Path) -> dict:
    return json.loads(dat.with_suffix(".json").read_text())


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_geometry_matches_runelite(dat: Path):
    ref = reference(dat)

    model = decode(dat.read_bytes())

    assert model.vertices == list(zip(ref["vertex_x"], ref["vertex_y"], ref["vertex_z"], strict=True))
    assert model.faces == list(zip(ref["face_a"], ref["face_b"], ref["face_c"], strict=True))


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_colours_and_textures_match_runelite(dat: Path):
    # RuneLite moves a textured face's stored value into face_textures and sets its colour to 127.
    ref = reference(dat)
    textures = ref["face_textures"] or [-1] * len(ref["face_colours"])

    model = decode(dat.read_bytes())

    assert model.face_textures == [None if t == -1 else t for t in textures]
    assert model.face_colours == [None if t != -1 else c for c, t in zip(ref["face_colours"], textures, strict=True)]


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_render_priorities_match_runelite(dat: Path):
    # A model stores either one priority per face or one priority for all faces; both decode to one per face.
    ref = reference(dat)
    expected = ref["face_render_priorities"] or [ref["model_priority"]] * len(ref["face_a"])

    model = decode(dat.read_bytes())

    assert model.render_priorities == expected


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_face_alphas_match_runelite(dat: Path):
    # A model without an alpha section is fully opaque, which is alpha 0.
    ref = reference(dat)
    expected = ref["face_alphas"] or [0] * len(ref["face_a"])

    model = decode(dat.read_bytes())

    assert model.face_alphas == expected


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_skins_match_runelite(dat: Path):
    ref = reference(dat)

    model = decode(dat.read_bytes())

    assert model.vertex_skins == ref["vertex_skins"]
    assert model.face_skins == ref["face_skins"]


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_texture_triangles_match_runelite(dat: Path):
    ref = reference(dat)
    triangles = list(zip(ref["texture_p"] or [], ref["texture_m"] or [], ref["texture_n"] or [], strict=True))

    model = decode(dat.read_bytes())

    assert model.texture_triangles == triangles
    ref_coords = ref["face_texture_coords"] or [-1] * len(ref["face_a"])
    for face, texture, triangle, ref_coord in zip(
        model.faces, model.face_textures, model.face_texture_triangles, ref_coords, strict=True
    ):
        if texture is None:
            assert triangle is None
        elif ref_coord == -1:
            # RuneLite drops the index when the texture triangle is the face itself.
            assert triangle is not None
            assert model.texture_triangles[triangle] == face
        else:
            assert triangle == ref_coord


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"osrs-{p.stem}")
def test_old_format_flat_shading_matches_runelite(dat: Path):
    # RuneLite calls the flat shading flag a face render type, 1 for flat and 0 for smooth.
    ref = reference(dat)
    expected = [t == 1 for t in ref["face_render_types"] or [0] * len(ref["face_a"])]

    model = decode(dat.read_bytes())

    assert model.flat_shaded == expected
