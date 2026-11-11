"""Texture coordinates that a texture triangle gives a face, following RuneLite's ModelDefinition."""

from collections.abc import Sequence

from .model import Model

type Vector = tuple[float, float, float]
type UV = tuple[float, float]


def texture_uvs(model: Model, face: int) -> tuple[UV, UV, UV] | None:
    """Return the UV of each corner of a textured face, or None for an untextured face.

    The texture triangle's P vertex maps to (0, 0), M to (1, 0) and N to (0, 1), and the face's corners are
    projected onto that plane. A textured face without a texture triangle uses its own corners as P, M and N.

    Eight Old School models (528, 2644, 2921, 3153 and 6277 to 6281 except 6279) give faces a texture triangle
    whose corners lie on one line, for which RuneLite computes NaN. The 2018 client's rasteriser
    (Graphics3D.rasterTextureAffineLine) samples texel (0, 0) wherever the projection's divisor is 0, so those
    faces get (0, 0) at every corner.
    """
    if model.face_textures[face] is None:
        return None
    triangle = model.face_texture_triangles[face]
    # The client ignores a texture triangle with the same corners as the face (ModelData.java line 1032 in the
    # 2018 client), which matters only when those corners lie on one line.
    if triangle is None or model.texture_triangles[triangle] == model.faces[face]:
        return (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)
    # The revision 170 client (ModelData.java lines 1559 to 1590, Model.java line 1370) copies only kind 0 records
    # into the drawable model and gives faces of the other kinds no texture triangle, so they use their own corners.
    # Revision 149 itself is not checked.
    if model.new_data is not None and model.new_data.texture_render_types[triangle] != 0:
        return (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)

    p, m, n = (model.vertices[i] for i in model.texture_triangles[triangle])
    a, b, c = (model.vertices[i] for i in model.faces[face])
    return projected_uvs((a, b, c), (p, m, n))


def projected_uvs(corners: tuple[Vector, Vector, Vector], pmn: tuple[Vector, Vector, Vector]) -> tuple[UV, UV, UV]:
    """Project a face's corners onto the plane of P, M and N, where P is (0, 0), M (1, 0) and N (0, 1)."""
    p, m, n = pmn
    pm, pn = _sub(m, p), _sub(n, p)
    normal = _cross(pm, pn)
    u_axis = _cross(pn, normal)
    u_scale = _dot(u_axis, pm)
    v_axis = _cross(pm, normal)
    v_scale = _dot(v_axis, pn)
    if u_scale == 0 or v_scale == 0:
        return (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)
    a, b, c = ((_dot(u_axis, x) / u_scale, _dot(v_axis, x) / v_scale) for x in (_sub(k, p) for k in corners))
    return a, b, c


def fit_triangle(
    corners: tuple[Vector, Vector, Vector], uvs: tuple[UV, UV, UV], like_original_exporter: bool = False
) -> tuple[Vector, Vector, Vector] | None:
    """Return the points on the face's plane where UV (0, 0), (1, 0) and (0, 1) fall, given its corners' UVs.

    This is how the original exporter turned a face's UVs into a texture triangle. It returns None when the face has
    no area or its UVs lie on one line, since either leaves nothing to fit to. With like_original_exporter, it
    refuses exactly the faces the original exporter refused: those whose UV determinant is 1e-6 or less, whatever
    the face's own area.
    """
    a, b, c = corners
    (ua, va), (ub, vb), (uc, vc) = uvs
    det = (ub - ua) * (vc - va) - (uc - ua) * (vb - va)
    ab, ac = _sub(b, a), _sub(c, a)
    normal = _cross(ab, ac)
    if like_original_exporter:
        if abs(det) <= 1e-6:
            return None
    elif abs(det) < 1e-9 or _dot(normal, normal) == 0:
        return None

    def point(u: float, v: float) -> Vector:
        s = ((vc - va) * (u - ua) - (uc - ua) * (v - va)) / det
        t = ((ub - ua) * (v - va) - (vb - va) * (u - ua)) / det
        return a[0] + s * ab[0] + t * ac[0], a[1] + s * ab[1] + t * ac[1], a[2] + s * ab[2] + t * ac[2]

    return point(0.0, 0.0), point(1.0, 0.0), point(0.0, 1.0)


def nearest_vertex(point: Vector, vertices: Sequence[Vector]) -> int:
    """The index of the vertex closest to the point, the lowest index among equally close ones."""
    return min(range(len(vertices)), key=lambda i: _dot(d := _sub(vertices[i], point), d))


def _sub(a: Vector, b: Vector) -> Vector:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _cross(a: Vector, b: Vector) -> Vector:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
