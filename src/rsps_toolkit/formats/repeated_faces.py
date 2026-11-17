"""Faces that use the same vertices as an earlier face. Nothing here imports bpy.

Blender's mesh validation removes such a face, and the stock glTF exporter validates each mesh that it exports
(`docs/research/82-gltf-export.md`, row 7). So the RS Scene export gives each of these faces vertices of its own on
the mesh copy first (issue 121)."""

from collections.abc import Iterable, Sequence


def repeated_faces(faces: Iterable[Sequence[int]]) -> list[int]:
    """The indices of the faces that use the same set of vertices as an earlier face, in face order. The winding and
    the first corner do not matter. The first face of each such group is not in the list."""
    seen: set[frozenset[int]] = set()
    repeated = []
    for index, face in enumerate(faces):
        key = frozenset(face)
        if key in seen:
            repeated.append(index)
        seen.add(key)
    return repeated
