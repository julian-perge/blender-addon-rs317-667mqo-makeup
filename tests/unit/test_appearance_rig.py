from pathlib import Path

import pytest

from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import assemble_body, default_equipment, load_kits, load_palette
from rsps_toolkit.formats.appearance_rig import BONE_LENGTH, derive_rig

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"
KITS = load_kits(FIXTURES / "KitDefinitions.json")
PALETTE = load_palette(FIXTURES / "revision149-palette.json")


def load_model(model_id: int) -> Model:
    return decode((FIXTURES / f"{model_id}.dat").read_bytes(), profile="osrs-149")


def default_body() -> Model:
    return assemble_body(default_equipment(KITS), KITS, load_model, [0, 0, 0, 0, 0], PALETTE)


def small_model(skins: list[int] | None) -> Model:
    return Model(
        vertices=[(0, 0, 0), (30, 0, 0), (0, 30, 0), (0, 0, 60)],
        faces=[(0, 1, 2), (0, 1, 3)],
        face_colours=[1, 1],
        face_textures=[None, None],
        render_priorities=[0, 0],
        face_alphas=[0, 0],
        face_texture_triangles=[None, None],
        flat_shaded=[False, False],
        vertex_skins=skins,
    )


def test_one_bone_per_label_with_head_at_the_vertex_centroid():
    rig = derive_rig(small_model([5, 5, 5, 9]))
    assert [bone.label for bone in rig.bones] == [5, 9]
    assert rig.bones[0].head == (10.0, 10.0, 0.0)
    assert rig.bones[1].head == (0.0, 0.0, 60.0)


def test_tail_is_a_fixed_length_straight_up_in_game_axes():
    # Game y points down, so "up" is minus y.
    bone = derive_rig(small_model([5, 5, 5, 9])).bones[0]
    assert bone.tail == (bone.head[0], bone.head[1] - BONE_LENGTH, bone.head[2])


def test_label_zero_is_a_normal_bone():
    rig = derive_rig(small_model([0, 0, 0, 0]))
    assert [bone.label for bone in rig.bones] == [0]


def test_a_model_without_vertex_skins_is_refused():
    with pytest.raises(ValueError, match="vertex skins"):
        derive_rig(small_model(None))


def test_every_vertex_has_weight_one_on_its_cache_label():
    body = default_body()
    assert body.vertex_skins is not None
    rig = derive_rig(body)
    assert rig.vertex_labels == tuple(body.vertex_skins)
    assert {bone.label for bone in rig.bones} == set(body.vertex_skins)


def test_bones_are_sorted_by_label():
    labels = [bone.label for bone in derive_rig(default_body()).bones]
    assert labels == sorted(labels)


def test_two_different_bodies_give_different_rigs():
    female = assemble_body(
        default_equipment(KITS, female=True), KITS, load_model, [0, 0, 0, 0, 0], PALETTE, female=True
    )
    assert derive_rig(female) != derive_rig(default_body())


def centre(body: Model, labels: set[int]) -> tuple[float, ...]:
    points = [v for v, label in zip(body.vertices, body.vertex_skins or (), strict=True) if label in labels]
    return tuple(sum(p[axis] for p in points) / len(points) for axis in range(3))


def test_the_joints_of_the_default_body_form_the_frame_maps_skeleton():
    rig = derive_rig(default_body())
    parents = {joint.name: joint.parent for joint in rig.joints}
    assert parents == {
        "root": None,
        "spine": "root",
        "head": "spine",
        "upper_arm.L": "spine",
        "forearm.L": "upper_arm.L",
        "hand.L": "forearm.L",
        "upper_arm.R": "spine",
        "forearm.R": "upper_arm.R",
        "hand.R": "forearm.R",
        "thigh.L": "root",
        "shin.L": "thigh.L",
        "foot.L": "shin.L",
        "thigh.R": "root",
        "shin.R": "thigh.R",
        "foot.R": "shin.R",
    }
    names = [joint.name for joint in rig.joints]
    assert all(names.index(parent) < names.index(name) for name, parent in parents.items() if parent)


def test_the_head_turns_labels_1_and_3_about_the_neck_and_each_label_has_its_deepest_joint():
    body = default_body()
    rig = derive_rig(body)
    head = next(joint for joint in rig.joints if joint.name == "head")
    assert head.owned == (1, 3)
    assert head.head == pytest.approx(centre(body, {2, 3}))
    assert (rig.owner(28), rig.owner(22), rig.owner(41), rig.owner(0)) == ("hand.L", "forearm.L", "root", None)


def test_left_joints_sit_on_the_positive_x_side():
    rig = derive_rig(default_body())
    for joint in rig.joints:
        if joint.name.endswith(".L"):
            assert joint.head[0] > 0
        if joint.name.endswith(".R"):
            assert joint.head[0] < 0


def test_a_model_without_the_frame_maps_pivot_labels_gets_no_joints():
    assert derive_rig(small_model([5, 5, 5, 9])).joints == ()
