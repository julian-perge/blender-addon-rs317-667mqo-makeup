import struct

from ._stream import Reader
from ._stream import encode_faces as _encode_faces
from ._stream import encode_vertices as _encode_vertices
from .model import Face, InvalidModelError, Model, ModelEncoding, Vertex, check, own_corner_triangles

_FOOTER = struct.Struct(">HHBBBBBBHHHH")


def decode(data: bytes) -> Model:
    (
        vertex_count,
        face_count,
        texture_triangle_count,
        has_textures,
        priority,
        has_alphas,
        has_face_skins,
        has_vertex_skins,
        x_length,
        y_length,
        z_length,
        face_index_length,
    ) = _FOOTER.unpack_from(data, len(data) - _FOOTER.size)

    vertex_flags = 0
    face_compression = vertex_flags + vertex_count
    offset = face_compression + face_count
    face_priorities = offset
    if priority == 255:
        offset += face_count
    face_skins = offset
    if has_face_skins:
        offset += face_count
    face_types = offset
    if has_textures:
        offset += face_count
    vertex_skins = offset
    if has_vertex_skins:
        offset += vertex_count
    face_alphas = offset
    if has_alphas:
        offset += face_count
    face_indices = offset
    offset += face_index_length
    face_colours = offset
    offset += face_count * 2
    texture_triangles = offset
    offset += texture_triangle_count * 6
    x_data = offset
    y_data = x_data + x_length
    z_data = y_data + y_length
    if z_data + z_length != len(data) - _FOOTER.size:
        raise InvalidModelError("Old-format sections do not match the footer boundary")

    colours = list(struct.unpack_from(f">{face_count}H", data, face_colours))
    types = list(data[face_types : face_types + face_count]) if has_textures else [0] * face_count
    textured = [bool(t & 2) for t in types]
    triangle_ids = struct.unpack_from(f">{texture_triangle_count * 3}H", data, texture_triangles)
    return Model(
        vertices=_vertices(data, vertex_count, vertex_flags, x_data, y_data, z_data),
        faces=_faces(data, face_count, face_compression, face_indices),
        face_colours=[None if t else c for c, t in zip(colours, textured, strict=True)],
        face_textures=[c if t else None for c, t in zip(colours, textured, strict=True)],
        render_priorities=(
            list(data[face_priorities : face_priorities + face_count]) if priority == 255 else [priority] * face_count
        ),
        face_alphas=list(data[face_alphas : face_alphas + face_count]) if has_alphas else [0] * face_count,
        face_skins=list(data[face_skins : face_skins + face_count]) if has_face_skins else None,
        vertex_skins=list(data[vertex_skins : vertex_skins + vertex_count]) if has_vertex_skins else None,
        texture_triangles=list(zip(triangle_ids[0::3], triangle_ids[1::3], triangle_ids[2::3], strict=True)),
        face_texture_triangles=[t >> 2 if t & 2 else None for t in types],
        flat_shaded=[bool(t & 1) for t in types],
    )


def _vertices(data: bytes, count: int, flags_at: int, x_at: int, y_at: int, z_at: int) -> list[Vertex]:
    xs, ys, zs = Reader(data, x_at), Reader(data, y_at), Reader(data, z_at)
    x = y = z = 0
    vertices = []
    for flags in data[flags_at : flags_at + count]:
        if flags & 1:
            x += xs.smart()
        if flags & 2:
            y += ys.smart()
        if flags & 4:
            z += zs.smart()
        vertices.append((x, y, z))
    return vertices


def _faces(data: bytes, count: int, compression_at: int, indices_at: int) -> list[Face]:
    # Each face reuses vertices of the previous face where it can, so most faces store one new index.
    indices = Reader(data, indices_at)
    a = b = c = last = 0
    faces = []
    for kind in data[compression_at : compression_at + count]:
        if kind == 1:
            a = last = indices.smart() + last
            b = last = indices.smart() + last
            c = last = indices.smart() + last
        elif kind == 2:
            b = c
            c = last = indices.smart() + last
        elif kind == 3:
            a = c
            c = last = indices.smart() + last
        elif kind == 4:
            a, b = b, a
            c = last = indices.smart() + last
        faces.append((a, b, c))
    return faces


def encode(model: Model) -> bytes:
    check(model)
    if model.encoding is not ModelEncoding.OLD:
        raise InvalidModelError("The old encoder cannot convert a newer-format model")
    vertex_count, face_count = len(model.vertices), len(model.faces)
    texture_triangles, face_texture_triangles = own_corner_triangles(model)
    textured = any(t is not None for t in model.face_textures)
    has_face_types = textured or any(model.flat_shaded)
    priorities = set(model.render_priorities)
    shared_priority = priorities.pop() if len(priorities) == 1 and 255 not in priorities else None
    if face_count == 0:
        shared_priority = 0
    has_alphas = any(model.face_alphas)

    vertex_flags, xs, ys, zs = _encode_vertices(model.vertices)
    compression, face_indices = _encode_faces(model.faces)
    face_types = bytes(
        (2 | triangle << 2 if triangle is not None else 0) | flat
        for triangle, flat in zip(face_texture_triangles, model.flat_shaded, strict=True)
    )
    colours = [t if t is not None else c for c, t in zip(model.face_colours, model.face_textures, strict=True)]

    sections = [vertex_flags, compression]
    if shared_priority is None:
        sections.append(bytes(model.render_priorities))
    if model.face_skins is not None:
        sections.append(bytes(model.face_skins))
    if has_face_types:
        sections.append(face_types)
    if model.vertex_skins is not None:
        sections.append(bytes(model.vertex_skins))
    if has_alphas:
        sections.append(bytes(model.face_alphas))
    sections += [
        face_indices,
        struct.pack(f">{face_count}H", *colours),
        struct.pack(f">{len(texture_triangles) * 3}H", *(i for t in texture_triangles for i in t)),
        xs,
        ys,
        zs,
    ]
    footer = _FOOTER.pack(
        vertex_count,
        face_count,
        len(texture_triangles),
        has_face_types,
        255 if shared_priority is None else shared_priority,
        has_alphas,
        model.face_skins is not None,
        model.vertex_skins is not None,
        len(xs),
        len(ys),
        len(zs),
        len(face_indices),
    )
    return b"".join(sections) + footer
