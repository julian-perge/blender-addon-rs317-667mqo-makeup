"""The frames of travel: when an actor that walks or runs from point to point is at each point (ADR 0035). Nothing here
imports bpy.
"""

from collections.abc import Sequence

TILE_SIZE = 128
# A walk moves 1 tile in 0.6 seconds (the owner, issue 170), and a clip plays at 50 frames in a second.
WALK_FRAMES_PER_TILE = 30
# A run moves 2 tiles in 0.6 seconds. This is general knowledge of the game and is not checked in the client.
RUN_FRAMES_PER_TILE = 15


def travel_frames(points: Sequence[Sequence[float]], start: int, frames_per_tile: float) -> list[int]:
    """The frame of each point, for an actor that is at the first point on frame `start`. A point is x, y and an
    optional height in game units.

    A step takes `frames_per_tile` for each 128 game units of the longer of its x and y distances, so a step to a
    diagonal tile takes the time of a straight step, and a change of height takes no time. The whole distance to a
    point is rounded, not each step, so the parts of a frame do not add up."""
    if len(points) < 2:
        raise ValueError("Travel needs at least two points")
    frames = [start]
    distance = 0.0
    for before, after in zip(points, points[1:], strict=False):
        distance += max(abs(after[0] - before[0]), abs(after[1] - before[1]))
        frames.append(start + round(distance / TILE_SIZE * frames_per_tile))
    return frames
