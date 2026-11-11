"""Least-squares fit of one rotation, uniform scale and translation per skin label, for playing a clip on label bones.

Within one frame the client moves every vertex of a label by the same translations, rotations and scales about
pivots that are fixed while the frame is applied (`poses.evaluate_frame`), so in real arithmetic each label moves by
one similarity transform. The client truncates coordinates to integers after each step, which the fit cannot follow.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Point = Sequence[float]
Quaternion = tuple[float, float, float, float]


@dataclass(frozen=True)
class LabelTransform:
    """Maps a rest point p to scale * rotation(p) + translation, in game axes (y points down)."""

    # A unit quaternion (w, x, y, z) with w >= 0.
    rotation: Quaternion
    scale: float
    translation: tuple[float, float, float]

    def apply(self, point: Point) -> tuple[float, float, float]:
        x, y, z = rotate(self.rotation, point)
        tx, ty, tz = self.translation
        return (self.scale * x + tx, self.scale * y + ty, self.scale * z + tz)

    def unapply(self, point: Point) -> tuple[float, float, float]:
        """The rest point this transform moves to `point`. The scale must not be 0."""
        w, x, y, z = self.rotation
        shifted = tuple((c - t) / self.scale for c, t in zip(point, self.translation, strict=True))
        return rotate((w, -x, -y, -z), shifted)  # pyrefly: ignore[bad-argument-type]


def rotate(q: Quaternion, point: Point) -> tuple[float, float, float]:
    w, x, y, z = q
    px, py, pz = point
    return (
        (1 - 2 * (y * y + z * z)) * px + 2 * (x * y - w * z) * py + 2 * (x * z + w * y) * pz,
        2 * (x * y + w * z) * px + (1 - 2 * (x * x + z * z)) * py + 2 * (y * z - w * x) * pz,
        2 * (x * z - w * y) * px + 2 * (y * z + w * x) * py + (1 - 2 * (x * x + y * y)) * pz,
    )


def fit_label(rest: Sequence[Point], posed: Sequence[Point]) -> LabelTransform:
    """The similarity transform with the least summed squared distance from the mapped rest points to the posed ones.

    The rotation is Horn's closed form (J. Opt. Soc. Am. A 4(4), 1987): the eigenvector of the largest eigenvalue of a
    symmetric 4x4 matrix built from the cross-covariance. A label whose rest points all coincide keeps the identity
    rotation and scale and only moves. A label whose rest points lie on one line takes the shortest turn from that
    line to the posed one, since any twist about the line fits it equally well.
    """
    if len(rest) != len(posed) or not rest:
        raise ValueError(f"A label needs as many posed points as rest points, got {len(rest)} and {len(posed)}")
    rest_centre, posed_centre = _centre(rest), _centre(posed)
    a = [[c - m for c, m in zip(p, rest_centre, strict=True)] for p in rest]
    b = [[c - m for c, m in zip(p, posed_centre, strict=True)] for p in posed]
    spread = sum(c * c for point in a for c in point)
    if spread == 0:
        (rx, ry, rz), (px, py, pz) = rest_centre, posed_centre
        return LabelTransform((1.0, 0.0, 0.0, 0.0), 1.0, (px - rx, py - ry, pz - rz))
    if _collinear(a, spread):
        return _along_line(a, b, spread, rest_centre, posed_centre)
    (xx, xy, xz), (yx, yy, yz), (zx, zy, zz) = (
        [sum(p[row] * q[column] for p, q in zip(a, b, strict=True)) for column in range(3)] for row in range(3)
    )
    horn = [
        [xx + yy + zz, yz - zy, zx - xz, xy - yx],
        [yz - zy, xx - yy - zz, xy + yx, zx + xz],
        [zx - xz, xy + yx, -xx + yy - zz, yz + zy],
        [xy - yx, zx + xz, yz + zy, -xx - yy + zz],
    ]
    value, vector = _largest_eigenpair(horn)
    length = math.sqrt(sum(c * c for c in vector))
    w, x, y, z = (c / length for c in vector)
    rotation = (w, x, y, z) if w >= 0 else (-w, -x, -y, -z)
    # The largest eigenvalue is the summed dot product of the rotated rest offsets with the posed offsets, so this is
    # the least-squares scale for the chosen rotation. It is 0 when the frame collapses the label onto one point.
    scale = max(value, 0.0) / spread
    turned = rotate(rotation, rest_centre)
    translation = (
        posed_centre[0] - scale * turned[0],
        posed_centre[1] - scale * turned[1],
        posed_centre[2] - scale * turned[2],
    )
    return LabelTransform(rotation, scale, translation)


def _collinear(offsets: list[list[float]], spread: float) -> bool:
    far = max(offsets, key=lambda p: sum(c * c for c in p))
    length = sum(c * c for c in far)
    return all(sum(c * c for c in _cross(p, far)) <= 1e-12 * spread * length for p in offsets)


def _along_line(a, b, spread: float, rest_centre, posed_centre) -> LabelTransform:
    """The shortest turn from the rest line to the posed one, with the least-squares scale and the matching move.

    The posed direction weighs each posed offset by how far along the rest line its point sits.
    """
    line = max(a, key=lambda p: sum(c * c for c in p))
    direction = [0.0, 0.0, 0.0]
    for p, q in zip(a, b, strict=True):
        along = sum(x * y for x, y in zip(p, line, strict=True))
        direction = [d + along * c for d, c in zip(direction, q, strict=True)]
    rotation = _shortest_arc(line, direction)
    matched = sum(sum(x * y for x, y in zip(rotate(rotation, p), q, strict=True)) for p, q in zip(a, b, strict=True))
    scale = max(matched, 0.0) / spread
    turned = rotate(rotation, rest_centre)
    translation = (
        posed_centre[0] - scale * turned[0],
        posed_centre[1] - scale * turned[1],
        posed_centre[2] - scale * turned[2],
    )
    return LabelTransform(rotation, scale, translation)


def _shortest_arc(u: Sequence[float], v: Sequence[float]) -> Quaternion:
    """The smallest rotation that turns direction u to direction v; the identity when v has no length."""
    lu, lv = math.sqrt(sum(c * c for c in u)), math.sqrt(sum(c * c for c in v))
    if lv == 0:
        return (1.0, 0.0, 0.0, 0.0)
    u, v = [c / lu for c in u], [c / lv for c in v]
    w = 1.0 + sum(x * y for x, y in zip(u, v, strict=True))
    axis = _cross(u, v)
    if w < 1e-9:
        # Opposite directions: half a turn about any axis across the line.
        axis = _cross(u, (1.0, 0.0, 0.0) if abs(u[0]) < 0.9 else (0.0, 1.0, 0.0))
        w = 0.0
    length = math.sqrt(w * w + sum(c * c for c in axis))
    return (w / length, axis[0] / length, axis[1] / length, axis[2] / length)


def _cross(p: Sequence[float], q: Sequence[float]) -> tuple[float, float, float]:
    return (p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0])


def fit_frame(rest: Sequence[Point], labels: Sequence[int], posed: Sequence[Point]) -> dict[int, LabelTransform]:
    """One fitted transform per label for a frame, given every vertex at rest and as the frame poses it."""
    if not len(rest) == len(labels) == len(posed):
        raise ValueError(f"Got {len(rest)} rest vertices, {len(labels)} labels and {len(posed)} posed vertices")
    groups: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        groups.setdefault(label, []).append(index)
    return {
        label: fit_label([rest[i] for i in members], [posed[i] for i in members]) for label, members in groups.items()
    }


def fitted_vertices(
    rest: Sequence[Point], labels: Sequence[int], transforms: Mapping[int, LabelTransform]
) -> tuple[tuple[float, float, float], ...]:
    """Every rest vertex moved by its label's transform, which is where a label bone with weight 1.0 puts it."""
    return tuple(transforms[label].apply(point) for point, label in zip(rest, labels, strict=True))


def _centre(points: Sequence[Point]) -> tuple[float, float, float]:
    count = len(points)
    return (
        sum(p[0] for p in points) / count,
        sum(p[1] for p in points) / count,
        sum(p[2] for p in points) / count,
    )


def _largest_eigenpair(matrix: list[list[float]]) -> tuple[float, list[float]]:
    """The largest eigenvalue of a symmetric matrix and its eigenvector, by cyclic Jacobi rotations."""
    size = len(matrix)
    a = [row[:] for row in matrix]
    vectors = [[float(i == j) for j in range(size)] for i in range(size)]
    scale = sum(c * c for row in a for c in row)
    for _ in range(64):
        off = sum(a[i][j] ** 2 for i in range(size) for j in range(size) if i != j)
        if off <= 1e-30 * scale:
            break
        for p in range(size):
            for q in range(p + 1, size):
                if a[p][q] == 0:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for rows in (a, vectors):
                    for row in rows:
                        row[p], row[q] = c * row[p] - s * row[q], s * row[p] + c * row[q]
                for k in range(size):
                    a[p][k], a[q][k] = c * a[p][k] - s * a[q][k], s * a[p][k] + c * a[q][k]
    best = max(range(size), key=lambda i: a[i][i])
    return a[best][best], [vectors[k][best] for k in range(size)]
