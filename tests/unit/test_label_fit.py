import json
import math
from pathlib import Path

import pytest
from runelite_json import load_kits

from rsps_toolkit.animation.clip import pose_vertices
from rsps_toolkit.animation.label_fit import LabelTransform, fit_frame, fit_label, fitted_vertices
from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import assemble_body, default_equipment, load_palette

APPEARANCE = Path(__file__).parents[1] / "fixtures/appearance"
CLIPS = Path(__file__).parents[1] / "fixtures/animation149"
REST = ((0, 0, 0), (10, 0, 0), (0, 20, 0), (0, 0, 30), (7, -3, 11))
# The largest and the mean distance, in game units, between the fitted label transforms and the client's recorded
# vertices, measured on 2026-11-07 and rounded up to 0.01. The client truncates every rotated and scaled coordinate
# to an integer, so no smooth transform of a label can meet its vertices exactly; see "Bone rig clip" in
# docs/research/osrs-149-animation.md.
ERROR_BOUNDS = {
    ("walk", "male"): (1.77, 0.39),
    ("walk", "female"): (1.45, 0.40),
    ("idle", "male"): (1.47, 0.30),
    ("idle", "female"): (1.21, 0.29),
    ("run", "male"): (2.02, 0.54),
    ("run", "female"): (1.85, 0.50),
    ("loop", "male"): (1.56, 0.33),
}


def body(clip: str, kind: str) -> Model:
    """The default body the client recorded the clip on, assembled as test_pose_149 does."""
    recorded = json.loads((CLIPS / clip / f"pose-{kind}.json").read_text())
    kits = load_kits(APPEARANCE / "KitDefinitions.json")
    female = kind == "female"
    equipment = default_equipment(kits, female=female)
    assert equipment == recorded["equipment"]

    def load_model(model_id: int) -> Model:
        return decode((APPEARANCE / f"{model_id}.dat").read_bytes(), profile="osrs-149")

    palette = load_palette(APPEARANCE / "revision149-palette.json")
    return assemble_body(equipment, kits, load_model, recorded["colours"], palette, female=female)


def rotate(axis, angle, point):
    """Rodrigues' rotation formula, written out independently of the quaternion code under test."""
    ux, uy, uz = axis
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    dot = ux * x + uy * y + uz * z
    cross = (uy * z - uz * y, uz * x - ux * z, ux * y - uy * x)
    return tuple(p * c + k * s + u * dot * (1 - c) for p, k, u in zip(point, cross, axis, strict=True))


def test_a_rotated_scaled_and_moved_label_is_recovered():
    axis = (2 / 3, -1 / 3, 2 / 3)
    angle = 1.1
    posed = [tuple(0.75 * c + t for c, t in zip(rotate(axis, angle, p), (5, -8, 13), strict=True)) for p in REST]
    fit = fit_label(REST, posed)
    half = angle / 2
    expected = (math.cos(half), *(u * math.sin(half) for u in axis))
    assert fit.rotation == pytest.approx(expected, abs=1e-9)
    assert fit.scale == pytest.approx(0.75, abs=1e-9)
    assert fit.translation == pytest.approx((5, -8, 13), abs=1e-9)


def test_an_unmoved_label_fits_the_identity():
    fit = fit_label(REST, REST)
    assert fit.rotation == pytest.approx((1, 0, 0, 0), abs=1e-9)
    assert fit.scale == pytest.approx(1, abs=1e-9)
    assert fit.translation == pytest.approx((0, 0, 0), abs=1e-9)


def test_a_one_vertex_label_is_moved_onto_its_posed_vertex():
    fit = fit_label(((4, 5, 6),), ((-1, 2, 9),))
    assert fit.apply((4, 5, 6)) == pytest.approx((-1, 2, 9))
    assert fit.rotation == (1.0, 0.0, 0.0, 0.0) and fit.scale == 1.0


def test_a_label_scaled_to_nothing_collapses_onto_one_point():
    # A type 3 transform with scale 0, as sequence 1499 uses, puts every vertex of the label on its pivot.
    fit = fit_label(REST, [(3, 3, 3)] * len(REST))
    assert fit.scale == 0
    for point in REST:
        assert fit.apply(point) == pytest.approx((3, 3, 3))


def test_the_rotation_has_a_nonnegative_real_part():
    posed = [rotate((0, 0, 1), 3.0, p) for p in REST]
    assert fit_label(REST, posed).rotation[0] >= 0


def test_fit_frame_fits_each_label_on_its_own():
    labels = (1, 1, 1, 2, 2)
    posed = [(x + 4, y, z) for x, y, z in REST[:3]] + [(x, y - 7, z) for x, y, z in REST[3:]]
    transforms = fit_frame(REST, labels, posed)
    assert set(transforms) == {1, 2}
    for fitted, expected in zip(fitted_vertices(REST, labels, transforms), posed, strict=True):
        assert fitted == pytest.approx(expected)


def test_fitted_vertices_apply_each_vertexs_own_label():
    move = LabelTransform((1.0, 0.0, 0.0, 0.0), 2.0, (1.0, 0.0, 0.0))
    still = LabelTransform((1.0, 0.0, 0.0, 0.0), 1.0, (0.0, 0.0, 0.0))
    assert fitted_vertices(((1, 1, 1), (1, 1, 1)), (5, 6), {5: move, 6: still}) == ((3, 2, 2), (1, 1, 1))


@pytest.mark.parametrize(("clip", "kind"), list(ERROR_BOUNDS))
def test_the_fitted_labels_stay_within_the_measured_distance_of_the_clients_vertices(clip, kind):
    model = body(clip, kind)
    assert model.vertex_skins is not None
    rest, labels = tuple(model.vertices), tuple(model.vertex_skins)
    client = json.loads((CLIPS / clip / f"pose-{kind}.json").read_text())["frames"]
    errors = []
    for frame, recorded in zip(pose_vertices(rest, labels, CLIPS / clip), client, strict=True):
        fitted = fitted_vertices(rest, labels, fit_frame(rest, labels, frame.vertices))
        exact = zip(recorded["e"], recorded["l"], recorded["s"], strict=True)
        errors += [math.dist(a, b) for a, b in zip(fitted, exact, strict=True)]
    largest, mean = ERROR_BOUNDS[clip, kind]
    assert max(errors) <= largest
    assert sum(errors) / len(errors) <= mean


def test_a_label_on_one_line_takes_the_shortest_turn_and_lands_exactly():
    rest = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
    posed = [(5.0, 5.0, 0.0), (5.0, 15.0, 0.0), (5.0, 25.0, 0.0)]
    fit = fit_label(rest, posed)
    w = fit.rotation[0]
    assert math.degrees(2 * math.acos(min(1.0, w))) == pytest.approx(90.0)
    for point, target in zip(rest, posed, strict=True):
        assert fit.apply(point) == pytest.approx(target)


def test_a_label_on_one_line_that_does_not_move_keeps_the_identity_rotation():
    rest = [(1.0, 2.0, 3.0), (1.0, 12.0, 3.0)]
    fit = fit_label(rest, rest)
    assert fit.rotation == pytest.approx((1.0, 0.0, 0.0, 0.0))


def test_unapply_undoes_apply():
    fit = fit_label(
        [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 7.0, 0.0)], [(3.0, 1.0, 2.0), (3.0, 21.0, 2.0), (-11.0, 1.0, 2.0)]
    )
    for point in ((1.0, 2.0, 3.0), (-4.0, 0.5, 9.0)):
        assert fit.unapply(fit.apply(point)) == pytest.approx(point)
