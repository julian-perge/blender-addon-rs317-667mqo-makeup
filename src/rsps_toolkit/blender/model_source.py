"""Where the source fields of an OSRS-149 model live on a Blender mesh.

The mesh keeps a JSON custom property, SOURCE_PROPERTY, for the values that belong to the whole model (encoding,
texture records, opaque tail), and two face attributes for the values that belong to a face. Both attributes
store the value plus 1, so 0 means the face has no value, which differs from a stored value of 0. The names are
separate from the layers in rs_layers.py so those stay unchanged. Blender keeps the face attributes with their
faces, so deleting a face removes its row and a face added in Blender gets 0, which reads back as missing.

A mesh with no marker and no face attributes reads as an old-format model, so a mesh stripped of all three cannot
be told from one that never had source fields. write_source is meant for the importer; calling it again after an
edit would adopt the edited mesh as the original.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

import bmesh
import bpy

from ..formats import Model, ModelEncoding, ModelProfile, NewFormatData
from .rs_layers import Position, game_position

SOURCE_PROPERTY = "rs_model_source"
IMPORTED_PROPERTY = "rs_model_imported"
SOURCE_VERSION = 1
REIMPORT_ADVICE = "reimport the original DAT, or export with a preset instead"
FACE_COLOUR = "rs_source_face_colour"
RENDER_TYPE = "rs_source_render_type"


class SourceSchemaError(ValueError):
    """The stored source data is missing or unreadable; the model has to be imported again."""


@dataclass(frozen=True)
class MeshSource:
    encoding: ModelEncoding
    profile: ModelProfile | None
    new_data: NewFormatData
    signature: str


def geometry_signature(vertices: Sequence[Position], faces: Sequence[tuple[int, ...]]) -> str:
    """A hash of the game-space geometry, ignoring faces that repeat a vertex, which are kept apart from the mesh."""
    real_faces = [list(face) for face in faces if len(face) != 3 or len(set(face)) == 3]
    return hashlib.sha256(json.dumps([[list(v) for v in vertices], real_faces]).encode()).hexdigest()


def write_source(mesh: bpy.types.Mesh, model: Model) -> None:
    """Store the model's source fields, or remove stored ones when it has none (an old-format model)."""
    source = model.new_data
    if source is None:
        if SOURCE_PROPERTY in mesh:
            del mesh[SOURCE_PROPERTY]
        for name in (FACE_COLOUR, RENDER_TYPE):
            if name in mesh.attributes:
                mesh.attributes.remove(mesh.attributes[name])
        return
    for name, values in (
        ("textured face colours", source.textured_face_colours),
        ("render types", source.face_render_types),
    ):
        if len(values) != len(mesh.polygons):
            raise ValueError(f"{len(values)} {name} for {len(mesh.polygons)} faces; the mesh and model differ")
    mesh[SOURCE_PROPERTY] = json.dumps(
        {
            "version": SOURCE_VERSION,
            "signature": geometry_signature(model.vertices, model.faces),
            "encoding": model.encoding.value,
            "profile": model.profile,
            "texture_render_types": list(source.texture_render_types),
            "texture_parameters": [parameters.hex() for parameters in source.texture_parameters],
            "tail": source.tail.hex(),
            "section_flags": None if source.section_flags is None else list(source.section_flags),
        }
    )
    _write_face_attribute(mesh, FACE_COLOUR, [0 if c is None else c + 1 for c in source.textured_face_colours])
    _write_face_attribute(mesh, RENDER_TYPE, [value + 1 for value in source.face_render_types])


def _write_face_attribute(mesh: bpy.types.Mesh, name: str, values: list[int]) -> None:
    if name in mesh.attributes:
        mesh.attributes.remove(mesh.attributes[name])
    attribute = mesh.attributes.new(name, "INT", "FACE")
    attribute.data.foreach_set("value", values)


def mark_imported(mesh: bpy.types.Mesh, model: Model) -> None:
    """Record which encoding the mesh was built from, for every model, old format included.

    A mesh without this marker has lost its import data (or predates the marker), so Preserve Source refuses it
    instead of treating it as an old-format model.
    """
    mesh[IMPORTED_PROPERTY] = json.dumps({"version": SOURCE_VERSION, "encoding": model.encoding.value})


def record_source_hash(mesh: bpy.types.Mesh, sha256: str) -> None:
    """Remember the SHA-256 of the file the model was decoded from; it identifies the file, not its profile."""
    marker = _imported(mesh)
    if marker is None:
        return
    marker["source_sha256"] = sha256
    mesh[IMPORTED_PROPERTY] = json.dumps(marker)


def stored_hash(mesh: bpy.types.Mesh) -> str | None:
    """The recorded SHA-256 of the source file, or None when there is none."""
    marker = _imported(mesh)
    return None if marker is None else marker.get("source_sha256")


def _imported(mesh: bpy.types.Mesh) -> dict | None:
    stored = mesh.get(IMPORTED_PROPERTY)
    if stored is None:
        return None
    try:
        marker = json.loads(stored)
        marker["encoding"]
    except (ValueError, KeyError, TypeError) as error:
        raise SourceSchemaError(f"The import marker is damaged ({error}); {REIMPORT_ADVICE}") from error
    return marker


def assert_preservable(obj: bpy.types.Object, final_model: Model) -> None:
    """Raise ValueError unless the import marker agrees with the encoding the final model would be written in.

    This is what tells a stripped new-format mesh from an old-format one, since neither has source fields.
    """
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return
    marker = _imported(mesh)
    if marker is None:
        raise ValueError(
            f"{obj.name!r} has no import marker, so Preserve Source cannot tell what format it came from; "
            f"{REIMPORT_ADVICE}"
        )
    if marker["encoding"] != final_model.encoding.value:
        raise ValueError(
            f"{obj.name!r} was imported as {marker['encoding']!r} but its stored source fields now read as "
            f"{final_model.encoding.value!r}; {REIMPORT_ADVICE}"
        )


def stored_signature(mesh: bpy.types.Mesh) -> str | None:
    """The geometry signature stored at import, None for a mesh without source fields, or raise SourceSchemaError.

    This reads only the stored marker, so it also works in Edit Mode, where the mesh's own face data is not current.
    """
    record = _record(mesh)
    return None if record is None else _field(record, "signature")


def _field(record: dict, name: str):
    try:
        return record[name]
    except KeyError as error:
        raise SourceSchemaError(f"The stored source data is damaged ({error}); reimport the original DAT") from error


def _record(mesh: bpy.types.Mesh) -> dict | None:
    stored = mesh.get(SOURCE_PROPERTY)
    if stored is None:
        if FACE_COLOUR in mesh.attributes or RENDER_TYPE in mesh.attributes:
            raise SourceSchemaError("The source marker is missing; reimport the original DAT")
        return None
    try:
        record = json.loads(stored)
        version = record["version"]
    except (ValueError, KeyError, TypeError) as error:
        raise SourceSchemaError(f"The stored source data is damaged ({error}); reimport the original DAT") from error
    if version != SOURCE_VERSION:
        raise SourceSchemaError(f"Unknown source version {version}; reimport the original DAT")
    return record


def read_source(mesh: bpy.types.Mesh) -> MeshSource | None:
    """Return the stored source fields, None for a mesh that never had any, or raise SourceSchemaError."""
    record = _record(mesh)
    if record is None:
        return None
    try:
        colours = _read_face_attribute(mesh, FACE_COLOUR)
        render_types = _read_face_attribute(mesh, RENDER_TYPE)
        flags = record["section_flags"]
        new_data = NewFormatData(
            textured_face_colours=tuple(None if c == 0 else c - 1 for c in colours),
            face_render_types=tuple(value - 1 for value in render_types),
            texture_render_types=tuple(record["texture_render_types"]),
            texture_parameters=tuple(bytes.fromhex(parameters) for parameters in record["texture_parameters"]),
            tail=bytes.fromhex(record["tail"]),
            section_flags=None if flags is None else tuple(flags),
        )
        return MeshSource(
            encoding=ModelEncoding(record["encoding"]),
            profile=record["profile"],
            new_data=new_data,
            signature=record["signature"],
        )
    except (ValueError, KeyError, TypeError) as error:
        raise SourceSchemaError(f"The stored source data is damaged ({error}); reimport the original DAT") from error


def _read_face_attribute(mesh: bpy.types.Mesh, name: str) -> list[int]:
    attribute = mesh.attributes.get(name)
    if attribute is None:
        raise ValueError(f"face attribute {name} is missing")
    values = [0] * len(mesh.polygons)
    attribute.data.foreach_get("value", values)
    return values


def mesh_geometry(mesh: bpy.types.Mesh, editing: bool) -> tuple[list[Position], list[tuple[int, ...]]]:
    """The mesh's game-space vertices and faces, read from the edit BMesh while the object is in Edit Mode."""
    if editing:
        bm = bmesh.from_edit_mesh(mesh)
        return [game_position(v.co) for v in bm.verts], [tuple(v.index for v in face.verts) for face in bm.faces]
    vertices = [game_position(v.co) for v in mesh.vertices]
    faces = [tuple(mesh.loops[p.loop_start + i].vertex_index for i in range(p.loop_total)) for p in mesh.polygons]
    return vertices, faces


def source_warning(obj: bpy.types.Object) -> str | None:
    """Why the stored source fields no longer fit the object's mesh, or None when they do or there are none."""
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return None
    try:
        signature = stored_signature(mesh)
    except SourceSchemaError as error:
        return str(error)
    if signature is None:
        return None
    vertices, faces = mesh_geometry(mesh, obj.mode == "EDIT")
    if geometry_signature(vertices, faces) != signature:
        return f"The mesh changed after import, so its source fields no longer match its faces; {REIMPORT_ADVICE}"
    return None


def assert_source_exportable(obj: bpy.types.Object, final_model: Model) -> None:
    """Raise ValueError unless the final game-space model has the geometry the source fields were stored for.

    The final model is what would be written, after modifiers and the object's transform, so a change made
    there is caught as well as a change to the mesh itself.
    """
    mesh = obj.data
    if not isinstance(mesh, bpy.types.Mesh):
        return
    signature = stored_signature(mesh)
    if signature is None:
        return
    if geometry_signature(final_model.vertices, final_model.faces) != signature:
        raise ValueError(f"{obj.name!r} no longer matches its stored source fields; {REIMPORT_ADVICE}")


VERTEX_RECORD = 0


def has_source(mesh: bpy.types.Mesh) -> bool:
    """Whether the mesh carries the source fields of a newer-format model."""
    return _record(mesh) is not None


def names_vertices(kinds: tuple[int, ...] | None, record: int) -> bool:
    """Whether the texture record holds vertex numbers; every record does on a mesh without source fields.

    Unverified: only kind 0 records are taken to hold vertex numbers, from the Gate 0 reference reader. The other kinds
    hold raw parameter words, and no client line has been cited for what they mean.
    """
    return kinds is None or kinds[record] == VERTEX_RECORD


def texture_record_kinds(mesh: bpy.types.Mesh) -> tuple[int, ...] | None:
    """The kind of each stored texture record (0 names vertices, see names_vertices); None without source fields."""
    record = _record(mesh)
    return None if record is None else tuple(_field(record, "texture_render_types"))


def append_vertex_record(mesh: bpy.types.Mesh) -> None:
    """Add the source entry for one new texture record that names vertices, kind 0 with no extra parameters."""
    record = _record(mesh)
    if record is None:
        return
    record["texture_render_types"].append(0)
    record["texture_parameters"].append("")
    mesh[SOURCE_PROPERTY] = json.dumps(record)


def refuse_complex_records(mesh: bpy.types.Mesh, used_by: Sequence[int | None], action: str) -> None:
    """Raise ValueError when any of the given texture record indices is a kind whose projection is not understood.

    Those records hold raw parameter words, not vertex numbers, so a tool that would replace or recompute the record
    a face uses would lose the projection the face has.
    """
    kinds = texture_record_kinds(mesh)
    if kinds is None:
        return
    for record in used_by:
        if record is not None and record < len(kinds) and not names_vertices(kinds, record):
            raise ValueError(
                f"{action} is not available for a face whose texture record {record} is kind {kinds[record]}; "
                "its projection is kept as imported and cannot be edited here"
            )
