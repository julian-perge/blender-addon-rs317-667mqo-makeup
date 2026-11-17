from rsps_toolkit.formats.repeated_faces import repeated_faces

# Issue 121: Blender's mesh validation removes a face that uses the same vertices as another face, so the RS Scene
# export gives such a face vertices of its own on the mesh copy. In the build of issue 142 on 2026-11-17 the owner chose
# that the first face of a group keeps its vertices, and that faces of any size match, not only triangles.


def test_faces_on_different_vertices_are_not_repeated():
    assert repeated_faces([(0, 1, 2), (1, 3, 2)]) == []


def test_a_later_face_on_the_same_three_vertices_is_repeated():
    assert repeated_faces([(0, 1, 2), (1, 3, 2), (0, 1, 2)]) == [2]


def test_the_winding_and_the_first_corner_do_not_matter():
    assert repeated_faces([(0, 1, 2), (2, 1, 0), (1, 2, 0)]) == [1, 2]


def test_faces_that_share_only_two_vertices_are_not_repeated():
    assert repeated_faces([(0, 1, 2), (0, 1, 3)]) == []


def test_a_quad_on_the_same_four_vertices_is_repeated():
    assert repeated_faces([(0, 1, 2, 3), (3, 2, 1, 0), (0, 1, 2)]) == [1]
