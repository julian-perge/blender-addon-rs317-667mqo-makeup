"""Expected poses come from the unmodified pinned client, including transform edge cases."""

import json
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from rsps_toolkit.animation.bundle import Frame, FrameMap, PartRecipe, Recipe, load_bundle
from rsps_toolkit.animation.poses import compile_asset, evaluate_frame, sample_pose, texture_offset
from rsps_toolkit.formats import decode, encode

FIXTURE = Path(__file__).parents[1] / "fixtures/animations/2013"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
CASES = json.loads((FIXTURE / "transform-cases.json").read_text())


def expected_parts(pose):
    result = []
    face = 0
    for part in REFERENCE["parts"]:
        count = part["face_count"]
        result.append(
            (
                part["key"],
                tuple(tuple(pose["vertices"][i]) for i in part["assembled_vertex_indices"]),
                tuple(pose["face_alphas"][face : face + count]),
            )
        )
        face += count
    return tuple(result)


def test_entire_whip_clip_matches_client(bundle_root):
    bundle = load_bundle(bundle_root)
    unchanged = {key: model.data for key, model in bundle.models.items()}
    asset = compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"])
    assert asset.vertices == tuple(tuple(v) for v in REFERENCE["rest_vertices"])
    assert asset.vertex_skins == tuple(REFERENCE["assembled_model_data"]["vertex_skins"])
    assert asset.face_skins == tuple(REFERENCE["assembled_model_data"]["face_skins"])
    assert asset.duration_ns == REFERENCE["rendered_actor_clock"][-1]["elapsed_tick"] * REFERENCE["tick_ns"]
    for actual, expected in zip(asset.parts, REFERENCE["parts"], strict=True):
        assert actual.key == expected["key"]
        assert actual.assembled_indices == tuple(expected["assembled_vertex_indices"])
    assert [colour for part in asset.parts for model in part.models for colour in model.face_colours] == REFERENCE[
        "assembled_model_data"
    ]["face_colours"]
    initial_models = deepcopy(tuple(part.models for part in asset.parts))
    samples = REFERENCE["rendered_actor_clock"][:-1]
    for row in [*samples, *reversed(samples)]:
        expected = expected_parts(REFERENCE["poses"][row["frame_index"]])
        for fractional_tick in (0, REFERENCE["tick_ns"] - 1):
            pose = sample_pose(asset, row["elapsed_tick"] * REFERENCE["tick_ns"] + fractional_tick)
            assert tuple((p.key, p.vertices, p.face_alphas) for p in pose.parts) == expected
    assert {key: model.data for key, model in bundle.models.items()} == unchanged
    assert tuple(part.models for part in asset.parts) == initial_models


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_transform_arithmetic_matches_client(case):
    transforms = case["transforms"]
    frame = Frame(
        0,
        tuple(t[0] for t in transforms),
        tuple(t[1] for t in transforms),
        tuple(t[2] for t in transforms),
        tuple(t[3] for t in transforms),
    )
    frame_map = FrameMap(tuple(case["types"]), tuple(tuple(labels) for labels in case["labels"]))
    vertices, alphas = evaluate_frame(
        tuple(tuple(v) for v in case["vertices"]),
        tuple(case["vertex_skins"]),
        tuple(case["face_alphas"]),
        None if case["face_skins"] is None else tuple(case["face_skins"]),
        frame,
        frame_map,
    )
    assert vertices == tuple(tuple(v) for v in case["expected_vertices"])
    assert alphas == tuple(case["expected_face_alphas"])


def test_parts_with_multiple_raw_models_match_client_assembly(bundle_root):
    bundle = load_bundle(bundle_root)
    original = bundle.recipes["default-male-whip"]
    merged = PartRecipe("merged", tuple(i for part in original.parts for i in part.model_ids), (0, 0, 0), (), ())
    bundle = replace(bundle, recipes={"merged": Recipe((merged,), original.recolours, original.sequence_ids)})
    asset = compile_asset(bundle, "merged", REFERENCE["sequence_id"])
    assert asset.vertices == tuple(tuple(v) for v in REFERENCE["rest_vertices"])
    tick = 0
    for expected, duration in zip(REFERENCE["poses"], REFERENCE["durations"], strict=True):
        pose = sample_pose(asset, tick * REFERENCE["tick_ns"]).parts[0]
        assert pose.vertices == tuple(tuple(v) for v in expected["vertices"])
        assert pose.face_alphas == tuple(expected["face_alphas"])
        tick += duration


def test_tree_is_static_and_texture_motion_matches_client(bundle_root):
    bundle = load_bundle(bundle_root)
    asset = compile_asset(bundle, "magic-tree", None)
    assert asset.duration_ns is None
    expected = tuple(tuple(v) for v in REFERENCE["tree"]["vertices"])
    assert sample_pose(asset, 0).parts[0].vertices == expected
    assert sample_pose(asset, 10**18).parts[0].vertices == expected
    for texture in REFERENCE["texture_references"]:
        motion = bundle.textures[texture["id"]]
        for row in texture["samples_128"]:
            source_row = row["first_pixels"][0] // motion.sampling_size
            expected_v = Fraction((-source_row) % motion.sampling_size, motion.sampling_size)
            for fractional_tick in (0, motion.tick_ns - 1):
                assert texture_offset(motion, row["ticks"] * motion.tick_ns + fractional_tick) == (
                    Fraction(0),
                    expected_v,
                )


def test_sampling_rejects_times_outside_its_domain(bundle_root):
    bundle = load_bundle(bundle_root)
    asset = compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"])
    assert asset.duration_ns is not None
    for value in (-1, asset.duration_ns, asset.duration_ns + 1, True, 1.0):
        with pytest.raises(ValueError):
            sample_pose(asset, cast(int, value))
    static = compile_asset(bundle, "magic-tree", None)
    for value in (-1, True, 1.0):
        with pytest.raises(ValueError):
            sample_pose(static, cast(int, value))
        with pytest.raises(ValueError):
            texture_offset(bundle.textures[34], cast(int, value))


def test_refuses_unselected_recipes_or_sequences(bundle_root):
    bundle = load_bundle(bundle_root)
    with pytest.raises(ValueError, match="recipe"):
        compile_asset(bundle, "missing", None)
    with pytest.raises(ValueError, match="sequence"):
        compile_asset(bundle, "magic-tree", REFERENCE["sequence_id"])


def test_animated_unreferenced_vertices_do_not_get_guessed_positions(bundle_root):
    bundle = load_bundle(bundle_root)
    model = decode(bundle.models[5409].data)
    model.vertices.append((123, 456, 789))
    assert model.vertex_skins is not None
    model.vertex_skins.append(0)
    models = dict(bundle.models)
    models[5409] = replace(models[5409], data=encode(model))
    bundle = replace(bundle, models=models)
    with pytest.raises(ValueError, match="unreferenced|correspondence"):
        compile_asset(bundle, "default-male-whip", REFERENCE["sequence_id"])


def test_retexturing_requires_the_effective_texture_resource(bundle_root):
    path = bundle_root / "animations/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["recipes"]["magic-tree"]["parts"][0]["retextures"] = [[34, 999]]
    path.write_text(json.dumps(manifest))
    bundle = load_bundle(bundle_root)
    with pytest.raises(ValueError, match="magic-tree.*tree.*999"):
        compile_asset(bundle, "magic-tree", None)


def test_retexture_replacements_apply_in_declared_order(bundle_root):
    bundle = load_bundle(bundle_root)
    recipe = bundle.recipes["magic-tree"]
    part = replace(recipe.parts[0], retextures=((34, 999), (999, 8)))
    bundle = replace(bundle, recipes={"magic-tree": replace(recipe, parts=(part,))})
    asset = compile_asset(bundle, "magic-tree", None)
    # Class104_Sub18_Sub16_Sub5.java:1424-1429 replaces each matching texture before the next pair runs.
    expected = [8 if value == 34 else value for value in decode(bundle.models[7978].data).face_textures]
    assert asset.parts[0].models[0].face_textures == expected
