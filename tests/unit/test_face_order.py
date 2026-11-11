from rsps_toolkit.formats import Model
from rsps_toolkit.formats.face_order import visible_faces


def model(faces, priorities):
    n = len(faces)
    return Model(
        vertices=[(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10)],
        faces=faces,
        face_colours=[1] * n,
        face_textures=[None] * n,
        render_priorities=priorities,
        face_alphas=[0] * n,
        face_texture_triangles=[None] * n,
        flat_shaded=[False] * n,
    )


def test_the_later_of_two_equal_priority_stacked_faces_stays():
    assert visible_faces(model([(0, 1, 2), (0, 1, 2)], [3, 3])) == [1]


def test_a_higher_priority_beats_a_later_face():
    assert visible_faces(model([(0, 1, 2), (0, 1, 2)], [5, 3])) == [0]


def test_rotated_corner_order_is_the_same_face():
    assert visible_faces(model([(0, 1, 2), (1, 2, 0)], [1, 1])) == [1]


def test_opposite_winding_is_a_different_face():
    assert visible_faces(model([(0, 1, 2), (0, 2, 1)], [1, 1])) == [0, 1]


def test_distinct_faces_all_stay():
    assert visible_faces(model([(0, 1, 2), (0, 1, 3)], [1, 1])) == [0, 1]
