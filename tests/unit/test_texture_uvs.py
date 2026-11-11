import json
import math
from pathlib import Path

import pytest

from rsps_toolkit.formats import decode, texture_uvs
from rsps_toolkit.formats.texture_uvs import fit_triangle, nearest_vertex, projected_uvs

MODELS = Path(__file__).parent.parent / "fixtures" / "models"
OLD_FORMAT = sorted([*(MODELS / "osrs").glob("*.dat"), *(MODELS / "worn").glob("*.dat")])


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_texture_uvs_match_runelite(dat: Path):
    ref = json.loads(dat.with_suffix(".json").read_text())
    model = decode(dat.read_bytes())

    for face in range(len(model.faces)):
        u, v = ref["face_texture_u"][face], ref["face_texture_v"][face]
        uvs = texture_uvs(model, face)
        if u is None:
            assert uvs is None, f"face {face}"
        else:
            # RuneLite computes in 32-bit floats.
            assert uvs is not None, f"face {face}"
            flat = [c for uv in uvs for c in uv]
            expected = [c for uv in zip(u, v, strict=True) for c in uv]
            if any(math.isnan(c) for c in expected):
                # RuneLite divides by zero when the texture triangle's corners lie on one line. The client's
                # rasteriser (Graphics3D.rasterTextureAffineLine in the 2018 client) samples texel (0, 0) then.
                expected = [0.0] * 6
            assert flat == pytest.approx(expected, rel=1e-4, abs=1e-5), f"face {face}"


@pytest.mark.parametrize("dat", OLD_FORMAT, ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_a_triangle_fitted_to_runelites_uvs_gives_those_uvs_back(dat: Path):
    # Fitting finds where UV (0, 0), (1, 0) and (0, 1) fall on the face's plane, as the original exporter did.
    ref = json.loads(dat.with_suffix(".json").read_text())
    model = decode(dat.read_bytes())

    for face, corner_ids in enumerate(model.faces):
        u, v = ref["face_texture_u"][face], ref["face_texture_v"][face]
        if u is None or any(math.isnan(c) for c in [*u, *v]):
            continue
        a, b, c = (model.vertices[i] for i in corner_ids)
        corners = (a, b, c)
        uvs = ((u[0], v[0]), (u[1], v[1]), (u[2], v[2]))
        fitted = fit_triangle(corners, uvs)
        if fitted is None:
            # A face with no area, or whose UVs lie on one line, has no plane to fit to.
            continue

        got = projected_uvs(corners, fitted)
        flat = [c for uv in got for c in uv]
        expected = [c for uv in uvs for c in uv]
        assert flat == pytest.approx(expected, rel=1e-3, abs=1e-3), f"face {face}"


def test_nearest_vertex_picks_the_closest_and_the_first_of_equals():
    vertices = [(0, 0, 0), (10, 0, 0), (10, 0, 0), (0, 10, 0)]

    assert nearest_vertex((9.0, 1.0, 0.0), vertices) == 1
    assert nearest_vertex((1.0, 8.0, 0.0), vertices) == 3
