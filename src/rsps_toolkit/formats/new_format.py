"""OSRS revision-149 FF FF models, read into their raw source fields.

The field layout follows tests/fixtures/models/osrs149/README.md. Whether the client changes these fields
before rendering has not been checked against client code here.
"""

import struct

from ._stream import Reader, encode_faces, encode_vertices
from .model import Face, InvalidModelError, Model, ModelEncoding, NewFormatData, Vertex, check

_FOOTER = struct.Struct(">HHBBBBBBBHHHHH2s")


def decode(data: bytes) -> Model:
    try:
        return _decode(data)
    except (IndexError, struct.error) as error:
        raise InvalidModelError(f"Truncated OSRS-149 model: {error}") from error


def _decode(data: bytes) -> Model:
    footer_at = len(data) - _FOOTER.size
    if footer_at < 0:
        raise InvalidModelError("Truncated OSRS-149 footer")
    (
        vertex_count,
        face_count,
        texture_count,
        render,
        priority,
        alpha,
        face_skin,
        textures,
        vertex_skin,
        x_length,
        y_length,
        z_length,
        index_length,
        coord_length,
        marker,
    ) = _FOOTER.unpack_from(data, footer_at)
    if marker != b"\xff\xff":
        raise InvalidModelError("Missing OSRS FFFF marker")
    # The client treats any flag other than 1 as an absent section and refuses nothing. Refusing 2 to 255 is our own
    # stricter rule, kept by the owner. The priority byte is not one of these flags.
    # Evidence: docs/research/osrs-149-codec-client-rules.md, rule 6.
    if any(flag not in (0, 1) for flag in (render, alpha, face_skin, textures, vertex_skin)):
        raise InvalidModelError("Unsupported OSRS-149 footer flags")
    offset = 0

    def section(size: int) -> bytes:
        nonlocal offset
        end = offset + size
        if end > footer_at:
            raise InvalidModelError("OSRS-149 sections overlap the footer")
        result = data[offset:end]
        offset = end
        return result

    kinds = section(texture_count)
    # The kinds 0 to 3 are the client's. The client reads no bytes for a larger kind, so refusing it is our own
    # stricter rule, kept by the owner. Evidence: docs/research/osrs-149-codec-client-rules.md, rule 5.
    if any(kind > 3 for kind in kinds):
        raise InvalidModelError("Unsupported texture record kind")
    vertex_flags = section(vertex_count)
    render_types = section(face_count) if render else bytes(face_count)
    compression = section(face_count)
    priorities = section(face_count) if priority == 255 else bytes([priority]) * face_count
    face_skins = list(section(face_count)) if face_skin else None
    vertex_skins = list(section(vertex_count)) if vertex_skin else None
    alphas = section(face_count) if alpha else bytes(face_count)
    indices = Reader(section(index_length))
    texture_ids = struct.unpack(f">{face_count}H", section(face_count * 2)) if textures else (0,) * face_count
    coords = Reader(section(coord_length))
    face_coords = [coords.u8() - 1 if texture_count and texture else -1 for texture in texture_ids]
    if coords.remaining:
        raise InvalidModelError("Unused texture-coordinate bytes")
    colours = struct.unpack(f">{face_count}H", section(face_count * 2))
    xs, ys, zs = Reader(section(x_length)), Reader(section(y_length)), Reader(section(z_length))
    simple_count = kinds.count(0)
    complex_count = texture_count - simple_count
    simple = Reader(section(simple_count * 6))
    complex_words = Reader(section(complex_count * 6))
    scales = Reader(section(complex_count * 6))
    rotations = Reader(section(complex_count * 2))
    directions = Reader(section(complex_count))
    speeds = Reader(section(complex_count * 2 + kinds.count(2) * 2))
    triangles = []
    parameters = []
    for kind in kinds:
        words = simple if kind == 0 else complex_words
        triangles.append((words.u16(), words.u16(), words.u16()))
        parameters.append(
            b""
            if kind == 0
            else scales.take(6) + rotations.take(2) + directions.take(1) + speeds.take(4 if kind == 2 else 2)
        )
    # The 11 is the client's number, but the client checks no length. Refusing a shorter tail is our own stricter
    # rule, kept by the owner. Evidence: docs/research/osrs-149-codec-client-rules.md, rule 4.
    tail = data[offset:footer_at]
    if not tail or (tail[0] != 0 and len(tail) < 11):
        raise InvalidModelError("Truncated OSRS-149 opaque tail")
    vertices = _vertices(vertex_flags, xs, ys, zs)
    faces = _faces(compression, indices)
    return Model(
        vertices=vertices,
        faces=faces,
        face_colours=[colour if texture == 0 else None for colour, texture in zip(colours, texture_ids, strict=True)],
        face_textures=[None if texture == 0 else texture - 1 for texture in texture_ids],
        render_priorities=list(priorities),
        face_alphas=list(alphas),
        face_skins=face_skins,
        vertex_skins=vertex_skins,
        texture_triangles=triangles,
        face_texture_triangles=[None if coordinate == -1 else coordinate for coordinate in face_coords],
        flat_shaded=[kind in (1, 3) for kind in render_types],
        encoding=ModelEncoding.OSRS_FFFF,
        profile="osrs-149",
        new_data=NewFormatData(
            textured_face_colours=tuple(
                colour if texture else None for colour, texture in zip(colours, texture_ids, strict=True)
            ),
            face_render_types=tuple(render_types),
            texture_render_types=tuple(kinds),
            texture_parameters=tuple(parameters),
            tail=tail,
            section_flags=(render, priority, alpha, face_skin, textures, vertex_skin),
        ),
    )


def _vertices(flags: bytes, xs: Reader, ys: Reader, zs: Reader) -> list[Vertex]:
    x = y = z = 0
    result = []
    for flag in flags:
        if flag > 7:
            raise InvalidModelError(f"Unsupported vertex flags {flag}")
        x += xs.smart() if flag & 1 else 0
        y += ys.smart() if flag & 2 else 0
        z += zs.smart() if flag & 4 else 0
        result.append((x, y, z))
    if xs.remaining or ys.remaining or zs.remaining:
        raise InvalidModelError("Unused vertex coordinate bytes")
    return result


def _faces(kinds: bytes, indices: Reader) -> list[Face]:
    a = b = c = last = 0
    result = []
    for kind in kinds:
        if kind == 1:
            a = last = last + indices.smart()
            b = last = last + indices.smart()
            c = last = last + indices.smart()
        elif kind == 2:
            b = c
            c = last = last + indices.smart()
        elif kind == 3:
            a = c
            c = last = last + indices.smart()
        elif kind == 4:
            a, b = b, a
            c = last = last + indices.smart()
        else:
            raise InvalidModelError(f"Invalid face compression kind {kind}")
        result.append((a, b, c))
    if indices.remaining:
        raise InvalidModelError("Unused face index bytes")
    return result


def encode(model: Model) -> bytes:
    try:
        check(model)
        if model.encoding is not ModelEncoding.OSRS_FFFF:
            raise InvalidModelError("The OSRS-149 encoder requires OSRS FFFF encoding")
        return _encode(model)
    except InvalidModelError:
        raise
    except (TypeError, ValueError, OverflowError, struct.error) as error:
        raise InvalidModelError(f"Cannot encode OSRS-149 model: {error}") from error


def _encode(model: Model) -> bytes:
    source = model.new_data
    assert source is not None
    vertex_count, face_count = len(model.vertices), len(model.faces)
    vertex_flags, xs, ys, zs = encode_vertices(model.vertices)
    compression, indices = encode_faces(model.faces)
    colours = []
    for colour, texture, independent in zip(
        model.face_colours, model.face_textures, source.textured_face_colours, strict=True
    ):
        value = colour if texture is None else independent
        assert value is not None
        colours.append(value)
    textures = any(texture is not None for texture in model.face_textures)
    coordinates = (
        bytes(
            0 if coordinate is None else coordinate + 1
            for texture, coordinate in zip(model.face_textures, model.face_texture_triangles, strict=True)
            if texture is not None
        )
        if model.texture_triangles
        else b""
    )
    for name, stream in {
        "X": xs,
        "Y": ys,
        "Z": zs,
        "face indices": indices,
        "texture coordinates": coordinates,
    }.items():
        if len(stream) > 0xFFFF:
            raise InvalidModelError(f"{name} stream has {len(stream)} bytes, over 65535")
    # The source footer's choices are kept while the edited model still agrees with them. Only when it no longer
    # does, or for a hand-built model, are the choices computed: a single shared priority is stored once in the
    # footer (0 for no faces), and the render type and alpha sections are omitted when every value is 0.
    # The client reads both: a priority byte below 255 is one shared priority, and a section whose flag is not 1 reads
    # as 0. The 0 for no faces is our own choice. Evidence: docs/research/osrs-149-codec-client-rules.md,
    # rules 1 and 2.
    flags = source.section_flags
    priorities = set(model.render_priorities)
    shared = next(iter(priorities)) if len(priorities) == 1 and 255 not in priorities else None
    if face_count == 0:
        shared = 0
    has_render = any(source.face_render_types)
    has_alpha = any(model.face_alphas)
    if flags is not None:
        render_flag, priority_flag, alpha_flag, _, texture_flag, _ = flags
        has_render = has_render or render_flag == 1
        has_alpha = has_alpha or alpha_flag == 1
        textures = textures or texture_flag == 1
        if priority_flag == 255:
            shared = None
        elif priorities <= {priority_flag}:
            shared = priority_flag
    simple, complex_words, scales, rotations, directions, speeds = (bytearray() for _ in range(6))
    for kind, words, parameters in zip(
        source.texture_render_types, model.texture_triangles, source.texture_parameters, strict=True
    ):
        packed = struct.pack(">HHH", *words)
        if kind == 0:
            simple += packed
        else:
            complex_words += packed
            scales += parameters[:6]
            rotations += parameters[6:8]
            directions += parameters[8:9]
            speeds += parameters[9:]
    sections = [bytes(source.texture_render_types), vertex_flags]
    if has_render:
        sections.append(bytes(source.face_render_types))
    sections.append(compression)
    if shared is None:
        sections.append(bytes(model.render_priorities))
    if model.face_skins is not None:
        sections.append(bytes(model.face_skins))
    if model.vertex_skins is not None:
        sections.append(bytes(model.vertex_skins))
    if has_alpha:
        sections.append(bytes(model.face_alphas))
    sections.append(indices)
    if textures:
        sections.append(
            struct.pack(f">{face_count}H", *(0 if texture is None else texture + 1 for texture in model.face_textures))
        )
    sections.extend(
        [
            coordinates,
            struct.pack(f">{face_count}H", *colours),
            xs,
            ys,
            zs,
            bytes(simple),
            bytes(complex_words),
            bytes(scales),
            bytes(rotations),
            bytes(directions),
            bytes(speeds),
            source.tail,
        ]
    )
    footer = _FOOTER.pack(
        vertex_count,
        face_count,
        len(model.texture_triangles),
        has_render,
        255 if shared is None else shared,
        has_alpha,
        model.face_skins is not None,
        textures,
        model.vertex_skins is not None,
        len(xs),
        len(ys),
        len(zs),
        len(indices),
        len(coordinates),
        b"\xff\xff",
    )
    return b"".join(sections) + footer
