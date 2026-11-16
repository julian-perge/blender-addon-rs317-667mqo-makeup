from pathlib import Path

import pytest
from runelite_json import load_kits

from rsps_toolkit.animation.bundle import FrameMap
from rsps_toolkit.animation.frames import decode_frame_map
from rsps_toolkit.formats import Model, decode
from rsps_toolkit.formats.appearance import assemble_body, default_equipment, load_palette
from rsps_toolkit.formats.appearance_rig import (
    BONE_LENGTH,
    JointSpec,
    derive_rig,
    frame_map_joint_specs,
    load_joint_specs,
)

FIXTURES = Path(__file__).parents[1] / "fixtures/appearance"
ANIMATION = Path(__file__).parents[1] / "fixtures/animation149"
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


# The tests from here to the end of the file check the joint rule that docs/adr/0025-an-npc-is-created-and-baked-only.md
# decides. A test names its source when it has another one.
def test_each_rotate_transform_gives_a_joint_named_by_its_transform_with_the_nearest_earlier_pivot():
    frame_map = FrameMap((0, 2, 0, 0, 2), ((1,), (1, 2), (9,), (2,), (2,)))
    assert frame_map_joint_specs(7, frame_map, {1, 2}) == (
        JointSpec("joint_1", 1, frozenset({1}), frozenset({1, 2})),
        JointSpec("joint_4", 4, frozenset({2}), frozenset({2})),
    )


def test_of_the_rotate_transforms_that_move_the_same_given_labels_only_the_earliest_is_a_joint():
    frame_map = FrameMap((0, 2, 0, 2, 0, 2), ((1,), (1, 2), (2,), (1, 2, 7), (1,), (2,)))
    assert [spec.rotate for spec in frame_map_joint_specs(7, frame_map, {1, 2})] == [1, 5]
    assert [spec.rotate for spec in frame_map_joint_specs(7, frame_map, {1, 2, 7})] == [1, 3, 5]


def test_a_joint_of_another_frame_map_gets_its_side_suffix_from_the_rig():
    specs = frame_map_joint_specs(7, FrameMap((0, 2), ((5,), (5, 9))), {5, 9})
    assert [joint.name for joint in derive_rig(small_model([5, 5, 5, 9]), specs).joints] == ["joint_1.L"]


def test_frame_map_0_gives_the_15_joints_of_the_player_table():
    frame_map = decode_frame_map((ANIMATION / "idle/maps/0.dat").read_bytes())
    specs = frame_map_joint_specs(0, frame_map, set(default_body().vertex_skins or ()))
    assert specs == load_joint_specs()
    assert len(specs) == 15


def test_a_frame_map_with_no_rotate_transform_gives_a_rig_with_label_bones_and_no_joints():
    specs = frame_map_joint_specs(7, FrameMap((0, 1, 3), ((5,), (5,), (9,))), {5, 9})
    assert specs == ()
    rig = derive_rig(small_model([5, 5, 5, 9]), specs)
    assert [bone.label for bone in rig.bones] == [5, 9]
    assert rig.joints == ()


def test_a_rotate_transform_whose_pivot_has_no_place_on_the_model_is_not_a_joint():
    # The owner's decision on issue 91: such a transform is skipped, and a later one that moves the same labels
    # is the joint. Transform 0 has no earlier pivot, and the pivot of transform 2 is on label 9, which the model
    # lacks. The client turns both around a point that no label gives (Model.java lines 676 to 678 and 772 to 780
    # of the 2018 client).
    frame_map = FrameMap((2, 0, 2, 0, 2), ((1,), (9,), (1,), (1,), (1,)))
    assert [spec.rotate for spec in frame_map_joint_specs(7, frame_map, {1})] == [4]


def test_two_rotate_transforms_after_one_pivot_transform_share_that_pivot():
    # The client keeps the pivot until the next pivot transform (Model.java lines 751 to 780 of the 2018 client
    # are the only code that sets it).
    frame_map = FrameMap((0, 2, 2), ((1,), (1, 2), (2,)))
    assert frame_map_joint_specs(7, frame_map, {1, 2}) == (
        JointSpec("joint_1", 1, frozenset({1}), frozenset({1, 2})),
        JointSpec("joint_2", 2, frozenset({1}), frozenset({2})),
    )


def test_a_joint_keeps_every_label_of_its_transforms_when_the_model_carries_only_some():
    # The client averages the pivot over the vertices that the model has (Model.java lines 757 to 770 of the 2018
    # client), so a pivot that is partly on the model has a place.
    frame_map = FrameMap((0, 2), ((1, 9), (1, 7)))
    assert frame_map_joint_specs(7, frame_map, {1}) == (JointSpec("joint_1", 1, frozenset({1, 9}), frozenset({1, 7})),)


def test_a_rotate_transform_that_moves_no_label_of_the_model_is_not_a_joint():
    # derive_joints gives such a spec no joint, so leaving it out changes no rig.
    frame_map = FrameMap((0, 2, 2), ((1,), (7,), (1,)))
    assert [spec.rotate for spec in frame_map_joint_specs(7, frame_map, {1})] == [2]
