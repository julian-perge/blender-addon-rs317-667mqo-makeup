"""A rest-pose rig derived from a model's vertex skin labels and the player frame map's joints.

Label bones carry the vertices, one per skin label. Joint bones come from `data/player_joints.json`, the rotate
transforms of frame map 0 with their pivots (`scripts/generate-player-joints.py`): each joint the body uses is placed
at the rest centre of its pivot labels and parented by how the label sets it moves nest, and each label bone hangs
under the deepest joint that moves it.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .model import Model

# The cache stores no bone direction or length, so the owner chose that each label bone points up a fixed distance
# from its head, in game units (issue 20).
BONE_LENGTH = 8.0
JOINTS_PATH = Path(__file__).parent.parent / "data" / "player_joints.json"


@dataclass(frozen=True)
class JointSpec:
    """One rotate transform of the player frame map, with the labels of its pivot and every label it moves."""

    name: str
    rotate: int
    pivot_labels: frozenset[int]
    labels: frozenset[int]


@dataclass(frozen=True)
class Joint:
    """A joint the body uses. Head and tail are in game coordinates; `owned` lists the labels no deeper joint moves."""

    name: str
    rotate: int
    head: tuple[float, float, float]
    tail: tuple[float, float, float]
    parent: str | None
    owned: tuple[int, ...]


def load_joint_specs(path: Path = JOINTS_PATH) -> tuple[JointSpec, ...]:
    return tuple(
        JointSpec(j["name"], j["rotate"], frozenset(j["pivot_labels"]), frozenset(j["labels"]))
        for j in json.loads(path.read_text())["joints"]
    )


@dataclass(frozen=True)
class Bone:
    """One skin label. Head and tail are in game coordinates (y points down)."""

    label: int
    head: tuple[float, float, float]
    tail: tuple[float, float, float]


@dataclass(frozen=True)
class Rig:
    bones: tuple[Bone, ...]
    # The label of every vertex, in vertex order. Each vertex has weight 1.0 on exactly this label's bone.
    vertex_labels: tuple[int, ...]
    # Parents before children.
    joints: tuple[Joint, ...] = ()

    def owner(self, label: int) -> str | None:
        """The deepest joint that moves the label, or None for a label no joint moves."""
        return next((joint.name for joint in reversed(self.joints) if label in joint.owned), None)


def derive_rig(model: Model, specs: tuple[JointSpec, ...] | None = None) -> Rig:
    """One bone per vertex skin label, headed at the centroid of that label's vertices, sorted by label, and the
    joints of `specs` (the player frame map's by default) that move and pivot on labels the model carries."""
    if model.vertex_skins is None:
        raise ValueError("The model has no vertex skins, so there are no labels to build bones from")
    sums: dict[int, list[float]] = {}
    for (x, y, z), label in zip(model.vertices, model.vertex_skins, strict=True):
        total = sums.setdefault(label, [0.0, 0.0, 0.0, 0.0])
        total[0] += x
        total[1] += y
        total[2] += z
        total[3] += 1
    bones = []
    for label in sorted(sums):
        x, y, z, count = sums[label]
        head = (x / count, y / count, z / count)
        bones.append(Bone(label, head, (head[0], head[1] - BONE_LENGTH, head[2])))
    joints = derive_joints(sums, load_joint_specs() if specs is None else specs)
    return Rig(tuple(bones), tuple(model.vertex_skins), joints)


def derive_joints(sums: dict[int, list[float]], specs: tuple[JointSpec, ...]) -> tuple[Joint, ...]:
    """The joints whose pivot and moved labels the body carries, parents first.

    A joint's parent is the joint that moves the smallest set of the body's labels holding all of its own; of two
    joints moving the same labels, the earlier transform is the parent, as the client applies it first. A label is
    owned by the deepest joint that moves it. A side suffix, .L for game x above 0, tells mirrored joints apart.
    """
    body = set(sums)
    present = [spec for spec in specs if spec.labels & body and spec.pivot_labels & body]
    moved = {spec.rotate: frozenset(spec.labels & body) for spec in present}

    def depth_key(spec: JointSpec) -> tuple[int, int]:
        return (-len(moved[spec.rotate]), spec.rotate)

    ordered = sorted(present, key=depth_key)
    parents: dict[int, int | None] = {}
    for spec in ordered:
        holders = [
            other
            for other in ordered
            if other.rotate != spec.rotate
            and moved[other.rotate] >= moved[spec.rotate]
            and depth_key(other) < depth_key(spec)
        ]
        parents[spec.rotate] = holders[-1].rotate if holders else None
    owners: dict[int, int] = {}
    for spec in ordered:
        for label in moved[spec.rotate]:
            owners[label] = spec.rotate
    names = _names(ordered, sums)
    joints = []
    for spec in ordered:
        pivot = [sums[label] for label in spec.pivot_labels & body]
        count = sum(total[3] for total in pivot)
        head = tuple(sum(total[axis] for total in pivot) / count for axis in range(3))
        parent = parents[spec.rotate]
        joints.append(
            Joint(
                names[spec.rotate],
                spec.rotate,
                head,  # pyrefly: ignore[bad-argument-type]
                (head[0], head[1] - BONE_LENGTH, head[2]),
                None if parent is None else names[parent],
                tuple(sorted(label for label, owner in owners.items() if owner == spec.rotate)),
            )
        )
    return tuple(joints)


def _names(specs: list[JointSpec], sums: dict[int, list[float]]) -> dict[int, str]:
    """Each joint's name with a side suffix where its pivot sits off the middle, unique by its transform if not."""
    names: dict[int, str] = {}
    for spec in specs:
        pivot = [sums[label] for label in spec.pivot_labels if label in sums]
        x = sum(total[0] for total in pivot) / sum(total[3] for total in pivot)
        name = spec.name if abs(x) < 1 else f"{spec.name}.{'L' if x > 0 else 'R'}"
        names[spec.rotate] = name if name not in names.values() else f"{name}_{spec.rotate}"
    return names
