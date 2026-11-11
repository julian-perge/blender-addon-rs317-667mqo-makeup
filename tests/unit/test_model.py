"""The limits below are the old format's field widths, as the 317 client reads them (docs/research/model-formats.md)."""

from dataclasses import replace

import pytest

from rsps_toolkit.formats import InvalidModelError, Model, decode, encode, texture_uvs


def triangle(**changes) -> Model:
    model = Model(
        vertices=[(0, 0, 0), (100, 0, 0), (0, 100, 0)],
        faces=[(0, 1, 2)],
        face_colours=[1000],
        face_textures=[None],
        render_priorities=[0],
        face_alphas=[0],
        face_skins=[0],
        vertex_skins=[0, 0, 0],
        texture_triangles=[],
        face_texture_triangles=[None],
        flat_shaded=[False],
    )
    return replace(model, **changes)


def test_a_valid_model_constructs():
    triangle()


@pytest.mark.parametrize(
    "changes",
    [
        {"face_colours": [1000, 1000]},
        {"face_textures": []},
        {"render_priorities": []},
        {"face_alphas": [0, 0]},
        {"face_skins": []},
        {"vertex_skins": [0]},
        {"face_texture_triangles": []},
        {"flat_shaded": []},
    ],
    ids=lambda c: next(iter(c)),
)
def test_per_face_and_per_vertex_lists_match_the_counts(changes):
    with pytest.raises(InvalidModelError):
        triangle(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"faces": [(0, 1, 3)]},
        {"faces": [(-1, 1, 2)]},
        {"texture_triangles": [(0, 1, 3)]},
        {"face_textures": [5], "face_colours": [None], "face_texture_triangles": [0]},
    ],
    ids=["face vertex", "negative face vertex", "texture triangle vertex", "missing texture triangle"],
)
def test_indices_point_at_existing_vertices_and_texture_triangles(changes):
    with pytest.raises(InvalidModelError):
        triangle(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"face_colours": [None]},
        {"face_textures": [5]},
    ],
    ids=["neither", "both"],
)
def test_each_face_has_exactly_one_of_colour_and_texture(changes):
    with pytest.raises(InvalidModelError):
        triangle(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"face_alphas": [256]},
        {"render_priorities": [-1]},
        {"face_skins": [256]},
        {"vertex_skins": [0, 0, 256]},
        {"face_colours": [65536]},
        {"face_colours": [None], "face_textures": [65536]},
    ],
    ids=["alpha", "priority", "face skin", "vertex skin", "colour", "texture"],
)
def test_values_fit_their_fields(changes):
    with pytest.raises(InvalidModelError):
        triangle(**changes)


def test_vertex_deltas_fit_a_two_byte_smart_value():
    triangle(vertices=[(0, 0, 0), (16383, 0, 0), (0, 0, 0)])
    with pytest.raises(InvalidModelError, match="vertex 1"):
        triangle(vertices=[(0, 0, 0), (16384, 0, 0), (0, 0, 0)])
    with pytest.raises(InvalidModelError, match="vertex 2"):
        triangle(vertices=[(0, 0, 0), (10000, 0, 0), (-10000, 0, 0)])


def test_a_face_type_byte_holds_texture_triangle_indices_up_to_63():
    corners = [(0, 1, 2)] * 65
    textured = {"face_colours": [None], "face_textures": [5], "texture_triangles": corners}
    triangle(**textured, face_texture_triangles=[63])
    with pytest.raises(InvalidModelError):
        triangle(**textured, face_texture_triangles=[64])


def test_a_model_has_at_most_16384_vertices_so_face_index_differences_fit():
    # Face indices are stored as differences in two-byte smart values, which hold -16384 to 16383.
    vertices = [(0, 0, 0)] * 16385
    with pytest.raises(InvalidModelError, match="16385 vertices"):
        triangle(vertices=vertices, vertex_skins=None)


def test_textured_faces_without_texture_triangles_fit_the_63_index_limit():
    # 64 texture triangles fill indices 0 to 63, so a face needing its own triangle would get index 64.
    others = [(0, 2, 1)] * 64
    textured = {"face_colours": [None], "face_textures": [5], "texture_triangles": others}
    with pytest.raises(InvalidModelError, match="texture triangle 64"):
        triangle(**textured)
    triangle(**textured, faces=[(0, 2, 1)])


def test_encode_checks_a_model_changed_in_place():
    model = triangle()
    model.face_alphas[0] = 300
    with pytest.raises(InvalidModelError):
        encode(model)


def test_invalid_model_is_a_value_error():
    assert issubclass(InvalidModelError, ValueError)


def test_textured_face_without_texture_triangle_survives_encoding():
    model = triangle(face_colours=[None], face_textures=[5])

    decoded = decode(encode(model))

    # The client ignores a texture triangle with the face's own corners (ModelData.java line 1032 in the 2018
    # client), and RuneLite then gives the face UVs (0, 0), (1, 0) and (0, 1).
    assert decoded.face_textures == [5]
    triangle_index = decoded.face_texture_triangles[0]
    assert triangle_index is not None
    assert decoded.texture_triangles[triangle_index] == (0, 1, 2)
    assert texture_uvs(decoded, 0) == ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
