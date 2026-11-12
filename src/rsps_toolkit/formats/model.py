from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from ._stream import SMART_MAX, SMART_MIN

type Vertex = tuple[int, int, int]
type Face = tuple[int, int, int]
type ModelProfile = Literal["osrs-149"]


class ModelEncoding(StrEnum):
    OLD = "old"
    OSRS_FFFF = "osrs-ffff"


@dataclass(frozen=True)
class NewFormatData:
    textured_face_colours: tuple[int | None, ...]
    face_render_types: tuple[int, ...]
    texture_render_types: tuple[int, ...]
    texture_parameters: tuple[bytes, ...]
    tail: bytes
    # The footer's render, priority, alpha, face skin, texture and vertex skin values as read from the file,
    # so re-encoding an unedited model reproduces the same optional sections. None means a hand-built model.
    section_flags: tuple[int, int, int, int, int, int] | None = None


# The footer allows 65535 vertices, but each old-format face index is stored as its difference from the previous
# one in a smart value. Up to this many vertices every difference fits; the largest model in the Old School caches
# has 4991.
MAX_VERTICES = SMART_MAX + 1
# A face type byte holds the textured bit, the flat shading bit and the texture triangle index in its top 6 bits.
MAX_TEXTURE_TRIANGLE_INDEX = 63


class InvalidModelError(ValueError):
    """Model data cannot be represented by its declared encoding and profile."""


@dataclass
class Model:
    """A model as the game client stores it, in game coordinates where y points down.

    Construction checks field ranges and relationships. Encoding checks them again
    and verifies stream representability after lists have been edited in place.
    """

    vertices: list[Vertex] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)
    # Per face, exactly one of these is set: a face colour for an untextured face or a texture ID for a textured one.
    face_colours: list[int | None] = field(default_factory=list)
    face_textures: list[int | None] = field(default_factory=list)
    render_priorities: list[int] = field(default_factory=list)
    # 0 is opaque and 255 fully transparent.
    face_alphas: list[int] = field(default_factory=list)
    # None means the model has no labels of that kind, which differs from every label being 0.
    face_skins: list[int] | None = None
    vertex_skins: list[int] | None = None
    # Unverified against the client: only kind-zero records are treated as naming vertices; newer complex records
    # keep their source words at the same indices without being interpreted as vertices.
    texture_triangles: list[Face] = field(default_factory=list)
    face_texture_triangles: list[int | None] = field(default_factory=list)
    flat_shaded: list[bool] = field(default_factory=list)
    encoding: ModelEncoding = ModelEncoding.OLD
    profile: ModelProfile | None = None
    new_data: NewFormatData | None = None

    def __post_init__(self) -> None:
        check(self)


def check(model: Model) -> None:
    """Raise InvalidModelError when fields contradict their encoding or profile."""
    _require(isinstance(model.encoding, ModelEncoding), f"Unsupported model encoding {model.encoding!r}")
    _require(model.profile in (None, "osrs-149"), f"Unsupported model profile {model.profile!r}")
    newer = model.encoding is ModelEncoding.OSRS_FFFF
    if newer:
        _require(model.profile == "osrs-149", "OSRS FFFF models require the osrs-149 profile")
        _require(isinstance(model.new_data, NewFormatData), "OSRS FFFF source data is missing")
    else:
        _require(model.new_data is None, "Old encoding cannot carry newer-format source data")
    vertex_count, face_count = len(model.vertices), len(model.faces)
    maximum = 0xFFFF if newer else MAX_VERTICES
    _require(vertex_count <= maximum, f"{vertex_count} vertices, more than {maximum}")
    _require(face_count <= 0xFFFF, f"{face_count} faces, more than the format's 65535")
    _require(len(model.texture_triangles) <= 0xFF, f"{len(model.texture_triangles)} texture triangles, over 255")

    per_face = {
        "face_colours": model.face_colours,
        "face_textures": model.face_textures,
        "render_priorities": model.render_priorities,
        "face_alphas": model.face_alphas,
        "face_skins": model.face_skins,
        "face_texture_triangles": model.face_texture_triangles,
        "flat_shaded": model.flat_shaded,
    }
    for name, values in per_face.items():
        if values is not None:
            _require(len(values) == face_count, f"{name} has {len(values)} entries for {face_count} faces")
    if model.vertex_skins is not None:
        count = len(model.vertex_skins)
        _require(count == vertex_count, f"vertex_skins has {count} entries for {vertex_count} vertices")
    source = model.new_data
    if source is not None:
        _check_new_types(model, source)
        _require(len(source.textured_face_colours) == face_count, "Independent face colour count mismatch")
        _require(len(source.face_render_types) == face_count, "Face render type count mismatch")
        _require(len(source.texture_render_types) == len(model.texture_triangles), "Texture kind count mismatch")
        _require(len(source.texture_parameters) == len(model.texture_triangles), "Texture parameter count mismatch")
        _require(bool(source.tail), "OSRS-149 source tail is missing")
        flags = source.section_flags
        _require(
            flags is None or (len(flags) == 6 and all(isinstance(flag, int) and 0 <= flag <= 255 for flag in flags)),
            "OSRS-149 section flags must be six bytes",
        )
        # Client rev 149, class dv, method j, offsets 2689 to 2694, 1901 to 1903, 2709 to 2725, 2423 to 2431,
        # 2740 to 2748 and 172 to 180: when the first tail byte is nonzero, the client reads 11 bytes (1, 2, 2, 2 and
        # 4) and ignores them. It checks no length, so a shorter tail makes it read the footer. The 11 is the
        # client's number, and refusing a shorter tail is our own stricter rule. The owner decided on 2026-11-11 to
        # keep it (issue 17).
        # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 4.
        _require(source.tail[0] == 0 or len(source.tail) >= 11, "OSRS-149 source tail is truncated")
        for i, (kind, parameters) in enumerate(
            zip(source.texture_render_types, source.texture_parameters, strict=True)
        ):
            # Client rev 149, class dv, method j, offsets 295 to 330, 1999 to 2004, 2261 to 2264, 2407 to 2410,
            # 2539 to 2542 and 2674 to 2677: the client reads each texture record by its kind, 0, 1, 2 or 3. For
            # any other kind it reads no bytes for that record and continues, and the record keeps zero triangle
            # words. The values 0 to 3 are the client's. Refusing a larger kind is our own stricter rule, because
            # we would read bytes that the client does not read. The owner decided on 2026-11-11 to keep it
            # (issue 17).
            # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 5.
            _require(kind in (0, 1, 2, 3), f"Texture record {i} has unsupported kind {kind}")
            size = 0 if kind == 0 else 13 if kind == 2 else 11
            _require(len(parameters) == size, f"Texture record {i} needs {size} parameter bytes")
        for i, (colour, texture, render_type, flat) in enumerate(
            zip(
                source.textured_face_colours,
                model.face_textures,
                source.face_render_types,
                model.flat_shaded,
                strict=True,
            )
        ):
            _require(0 <= render_type <= 255, f"Face {i} render type is not an unsigned byte")
            _require(flat == (render_type in (1, 3)), f"Face {i} flat shading contradicts its render type")
            _require(
                colour is None if texture is None else colour is not None and 0 <= colour <= 0xFFFF,
                f"Face {i} independent colour contradicts its texture",
            )

    for i, (face, colour, texture, triangle) in enumerate(
        zip(model.faces, model.face_colours, model.face_textures, model.face_texture_triangles, strict=True)
    ):
        _require(all(0 <= v < vertex_count for v in face), f"face {i} uses a vertex that does not exist: {face}")
        _require((colour is None) != (texture is None), f"face {i} needs exactly one of a face colour or texture")
        _require(colour is None or 0 <= colour <= 0xFFFF, f"face {i} colour {colour} is not a 16-bit value")
        _require(texture is None or 0 <= texture <= 0xFFFF, f"face {i} texture {texture} is not a 16-bit value")
        if triangle is not None:
            _require(texture is not None, f"face {i} has a texture triangle but no texture")
            _require(0 <= triangle < len(model.texture_triangles), f"face {i} uses missing texture triangle {triangle}")
            # Client rev 149, class dv, method j, offsets 1632 to 1665: a face's texture coordinate is one file byte
            # that holds the index plus 1. Class dv, method ae, offsets 428 to 436 and 449 to 459: file byte 0 means
            # no texture triangle, and any other byte is used as an unsigned index, so 254 is the highest index. The
            # client has no check of its own. We refuse 255 because it does not fit in the byte. A model has at most
            # 255 texture triangles, so the checks above refuse index 255 first and this limit is a second guard.
            # Evidence: .scratch/codec-rules-cited/evidence/client-rules.md, rule 3.
            limit = 254 if newer else MAX_TEXTURE_TRIANGLE_INDEX
            _require(triangle <= limit, f"face {i} uses texture triangle {triangle}, over {limit}")
    for i, corners in enumerate(model.texture_triangles):
        if source is not None and source.texture_render_types[i] != 0:
            _require(all(0 <= word <= 0xFFFF for word in corners), f"Texture record {i} has non-16-bit words")
        else:
            _require(all(0 <= v < vertex_count for v in corners), f"texture triangle {i} uses a missing vertex")

    for name, values in {
        "face_alphas": model.face_alphas,
        "render_priorities": model.render_priorities,
        "face_skins": model.face_skins,
        "vertex_skins": model.vertex_skins,
    }.items():
        for i, value in enumerate(values or []):
            _require(0 <= value <= 0xFF, f"{name}[{i}] is {value}, outside 0 to 255")

    last = (0, 0, 0)
    for i, vertex in enumerate(model.vertices):
        previous = f"vertex {i - 1} at {last}" if i else "the origin, which the first vertex is measured from"
        _require(
            all(SMART_MIN <= v - p <= SMART_MAX for v, p in zip(vertex, last, strict=True)),
            f"vertex {i} at {vertex} is too far from {previous}; each axis can differ by {SMART_MIN} to {SMART_MAX}",
        )
        last = vertex
    if not newer:
        own_corner_triangles(model)


def _check_new_types(model: Model, source: NewFormatData) -> None:
    for name, rows in {
        "vertices": model.vertices,
        "faces": model.faces,
        "texture records": model.texture_triangles,
    }.items():
        for i, row in enumerate(rows):
            _require(
                len(row) == 3 and all(isinstance(value, int) for value in row), f"{name}[{i}] needs three integers"
            )
    nullable = {"face_colours", "face_textures", "face_texture_triangles", "independent colours"}
    for name, values in {
        "face_colours": model.face_colours,
        "face_textures": model.face_textures,
        "face_texture_triangles": model.face_texture_triangles,
        "render_priorities": model.render_priorities,
        "face_alphas": model.face_alphas,
        "face_skins": model.face_skins,
        "vertex_skins": model.vertex_skins,
        "independent colours": source.textured_face_colours,
        "render types": source.face_render_types,
        "texture kinds": source.texture_render_types,
    }.items():
        for i, value in enumerate(values or []):
            _require(isinstance(value, int) or (value is None and name in nullable), f"{name}[{i}] must be an integer")
    _require(all(isinstance(value, bool) for value in model.flat_shaded), "Flat-shading flags must be boolean")
    _require(isinstance(source.tail, bytes), "OSRS-149 source tail must be bytes")
    _require(all(isinstance(value, bytes) for value in source.texture_parameters), "Texture parameters must be bytes")


def own_corner_triangles(model: Model) -> tuple[list[Face], list[int | None]]:
    """Return the texture triangles and per-face indices with a triangle for every textured face.

    The old format can only mark a face textured together with a texture triangle index, so a textured face without
    one gets a texture triangle made of its own corners, reusing one with exactly those corners if it exists. The
    client ignores such a triangle (ModelData.java line 1032 in the 2018 client), so the face draws the same.
    """
    triangles = list(model.texture_triangles)
    index_of = {corners: i for i, corners in reversed(list(enumerate(triangles)))}
    face_triangles = list(model.face_texture_triangles)
    for i, (face, texture, triangle) in enumerate(zip(model.faces, model.face_textures, face_triangles, strict=True)):
        if texture is None or triangle is not None:
            continue
        if face not in index_of:
            index_of[face] = len(triangles)
            triangles.append(face)
        own = index_of[face]
        _require(
            own <= MAX_TEXTURE_TRIANGLE_INDEX, f"face {i} needs texture triangle {own}, but a face can use 0 to 63"
        )
        face_triangles[i] = own
    return triangles, face_triangles


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidModelError(message)
