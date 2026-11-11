"""Which faces of a model the client leaves visible when faces stack exactly (see docs/research/render-priority.md)."""

from .model import Model


def visible_faces(model: Model) -> list[int]:
    """Indices of faces not painted over by an exactly stacked face.

    Two faces with the same corner positions in the same winding fall in one depth bucket, so the client draws them
    in priority order and, at equal priority, in face index order, and the last one drawn stays visible. Other
    overlaps, which need real depth ordering, are not handled.
    """
    winner: dict[tuple[tuple[int, int, int], ...], tuple[int, int]] = {}
    keys = []
    for i, face in enumerate(model.faces):
        corners = tuple(model.vertices[v] for v in face)
        start = corners.index(min(corners))
        key = corners[start:] + corners[:start]
        keys.append(key)
        priority = model.render_priorities[i]
        if key not in winner or (priority, i) > winner[key]:
            winner[key] = (priority, i)
    return [i for i, key in enumerate(keys) if winner[key][1] == i]
