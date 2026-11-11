"""The revision 149 client's per-vertex model lighting for untextured faces. Nothing here imports bpy.

This follows `ModelData.light` and `computeNormals` as read from RuneLite (revision 170), and it is checked against
lit models that the unchanged revision 149 client produced (see `tests/fixtures/appearance/reference.json`). The
branches the reference does not cover are refused instead of guessed. Flat-shaded faces are covered only by the
male cases (8 faces), and 32-bit overflow of the face normal is not modelled.
"""

import math
from dataclasses import dataclass

from .model import Model

# The ambient, contrast and light direction that the client passes when it lights a player body.
PLAYER_LIGHTING = (64, 850, -30, -50, -30)
# Face alpha values the client reads as signed bytes -2 and -1, which switch the face to special shading.
_HIDDEN_ALPHAS = (254, 255)


@dataclass(frozen=True)
class Shading:
    """One lit HSL colour per face corner, the way the client stores them."""

    corner_a: list[int]
    corner_b: list[int]
    corner_c: list[int]


def _divide(numerator: int, denominator: int) -> int:
    """Integer division that rounds toward zero, as in Java."""
    quotient = abs(numerator) // abs(denominator)
    return quotient if (numerator < 0) == (denominator < 0) else -quotient


def _face_normal(model: Model, face: tuple[int, int, int]) -> tuple[int, int, int]:
    a, b, c = (model.vertices[i] for i in face)
    bx, by, bz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    cx, cy, cz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    x, y, z = by * cz - cy * bz, bz * cx - cz * bx, bx * cy - cx * by
    while max(abs(x), abs(y), abs(z)) > 8192:
        x, y, z = x >> 1, y >> 1, z >> 1
    length = max(math.isqrt(x * x + y * y + z * z), 1)
    return _divide(x * 256, length), _divide(y * 256, length), _divide(z * 256, length)


def _shade(colour: int, intensity: int) -> int:
    intensity = (colour & 127) * intensity >> 7
    return (colour & 0xFF80) + min(max(intensity, 2), 126)


def light(model: Model, lighting: tuple[int, int, int, int, int] = PLAYER_LIGHTING) -> Shading:
    """Light an assembled model. Textured faces and the two special alpha values are not supported."""
    ambient, contrast, lx, ly, lz = lighting
    if any(t is not None for t in model.face_textures):
        raise ValueError("Lighting of textured faces is not verified against the client")
    if any(a in _HIDDEN_ALPHAS for a in model.face_alphas):
        raise ValueError("Lighting of faces with alpha 254 or 255 is not verified against the client")
    divisor = (math.isqrt(lx * lx + ly * ly + lz * lz) * contrast) >> 8
    sums = [[0, 0, 0, 0] for _ in model.vertices]
    face_normals: dict[int, tuple[int, int, int]] = {}
    for index, face in enumerate(model.faces):
        normal = _face_normal(model, face)
        if model.flat_shaded[index]:
            face_normals[index] = normal
            continue
        for vertex in face:
            total = sums[vertex]
            total[0] += normal[0]
            total[1] += normal[1]
            total[2] += normal[2]
            total[3] += 1
    corners: tuple[list[int], list[int], list[int]] = ([], [], [])
    for index, face in enumerate(model.faces):
        colour = model.face_colours[index]
        if colour is None:
            raise ValueError(f"Face {index} has no colour to light")
        if model.flat_shaded[index]:
            x, y, z = face_normals[index]
            value = _shade(colour, _divide(ly * y + lz * z + lx * x, divisor // 2 + divisor) + ambient)
            corners[0].append(value)
            # The client leaves the second corner at 0 and marks the third as -1 for a flat face.
            corners[1].append(0)
            corners[2].append(-1)
            continue
        for slot, vertex in enumerate(face):
            x, y, z, magnitude = sums[vertex]
            intensity = _divide(ly * y + lz * z + lx * x, divisor * magnitude) + ambient
            corners[slot].append(_shade(colour, intensity))
    return Shading(*corners)
