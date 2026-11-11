"""The change of axes between game coordinates and Blender coordinates."""

from mathutils import Matrix

# Game y points down, so a game point (x, y, z) is the Blender point (x, z, -y).
GAME_TO_BLENDER = Matrix(((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)))


def game_to_blender(point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (x, z, -y)
