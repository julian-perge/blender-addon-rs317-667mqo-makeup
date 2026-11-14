"""The contact sheet of a player: one PNG with one column per frame and one row per view.

The layout and the defaults are those the owner accepted in the sword flourish test of issue 12
(docs/research/sword-flourish-test/feedback.py, ADR 0019).
"""

import os
import tempfile
from array import array
from collections.abc import Sequence

import bpy
from mathutils import Vector

from . import appearance_preview

# Each view is the direction from the player to the camera. A player from Create Player faces -Y.
VIEWS = {
    "front": Vector((0, -1, 0)),
    "back": Vector((0, 1, 0)),
    "right": Vector((-1, 0, 0)),
    "left": Vector((1, 0, 0)),
    "top": Vector((0, 0, 1)),
}
DEFAULT_VIEWS = "front,right"
DEFAULT_CELL = (320, 480)
STAMP_FONT_SIZE = 22
# The size of a cell divided by the size of the player in it, on the side where the player fits most closely.
MARGIN = 1.1

RENDER_SETTINGS = (
    "resolution_x",
    "resolution_y",
    "resolution_percentage",
    "filepath",
    "use_border",
    "use_stamp",
    "stamp_font_size",
)


def parse_frames(text: str) -> list[int]:
    """The scene frames of a text such as `1,6,11`."""
    if not text.strip():
        raise ValueError("The frames are empty. Give scene frames separated by commas, such as 1,6,11")
    frames = []
    for part in text.split(","):
        try:
            frames.append(int(part.strip()))
        except ValueError:
            raise ValueError(f"The frames {text!r} hold {part.strip()!r}, which is not a whole number") from None
    return frames


def parse_views(text: str) -> list[str]:
    """The view names of a text such as `front,right`."""
    if not text.strip():
        raise ValueError(f"The views are empty. Give view names separated by commas, from {', '.join(VIEWS)}")
    views = [part.strip() for part in text.split(",")]
    for view in views:
        if view not in VIEWS:
            raise ValueError(f"The views {text!r} hold {view!r}, which is not one of {', '.join(VIEWS)}")
    return views


def render_cell(path: str) -> None:
    """Render the scene's current frame from the scene camera into a PNG."""
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def contact_sheet(
    player: bpy.types.Collection, frames: Sequence[int], views: Sequence[str], cell: tuple[int, int], path: str
) -> tuple[int, int]:
    """Render the player on each frame from each view into one PNG at `path`, and return the PNG's width and height.

    The sheet has one row per view and one column per frame, in the order given, and each cell shows its frame number.
    Every cell of a row has the same camera, which holds the player on all the frames. Only the player's meshes are
    rendered, also those that are hidden for renders. Every setting this changes is put back, also when a render fails, and no camera or image stays.
    """
    if not path:
        raise ValueError("The file path of the contact sheet is empty")
    meshes = [obj for obj in player.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError(f"{player.name} has no mesh to render")
    scene = bpy.context.scene
    assert scene is not None
    render = scene.render
    width, height = cell
    sheet_width, sheet_height = width * len(frames), height * len(views)
    sheet = array("f", bytes(4 * 4 * sheet_width * sheet_height))

    settings = {name: getattr(render, name) for name in RENDER_SETTINGS}
    stamps = {name: getattr(render, name) for name in dir(render) if name.startswith("use_stamp_")}
    media_type, file_format = render.image_settings.media_type, render.image_settings.file_format
    scene_camera, frame_before, subframe_before = scene.camera, scene.frame_current, scene.frame_subframe
    hidden = {obj: obj.hide_render for obj in scene.objects}
    images_before = set(bpy.data.images)
    cameras = []
    try:
        with tempfile.TemporaryDirectory() as folder:
            points = _world_points(scene, meshes, frames)
            if not points:
                raise ValueError(f"{player.name} has no vertex to render")
            for obj in scene.objects:
                if obj.type == "MESH":
                    obj.hide_render = obj not in meshes
            render.image_settings.media_type = "IMAGE"
            render.image_settings.file_format = "PNG"
            render.resolution_x, render.resolution_y = width, height
            render.resolution_percentage = 100
            render.use_border = False
            for name in stamps:
                setattr(render, name, False)
            render.use_stamp = True
            render.use_stamp_frame = True
            render.stamp_font_size = STAMP_FONT_SIZE
            for row, view in enumerate(views):
                camera = _camera(scene, VIEWS[view], points, width / height)
                cameras.append(camera)
                scene.camera = camera
                for column, frame in enumerate(frames):
                    scene.frame_set(frame)
                    cell_path = os.path.join(folder, f"{row}-{column}.png")
                    render_cell(cell_path)
                    pixels = _read_pixels(cell_path, width, height)
                    # Image rows run from the bottom up, so the first view goes in the last rows.
                    first_row = (len(views) - 1 - row) * height
                    for y in range(height):
                        start = 4 * ((first_row + y) * sheet_width + column * width)
                        sheet[start : start + 4 * width] = pixels[4 * y * width : 4 * (y + 1) * width]
    finally:
        for camera in cameras:
            data = camera.data
            bpy.data.objects.remove(camera)
            bpy.data.cameras.remove(data)  # pyrefly: ignore[bad-argument-type]
        # A render makes the image "Render Result" when the file has none.
        for image in set(bpy.data.images) - images_before:
            bpy.data.images.remove(image)
        render.image_settings.media_type = media_type
        render.image_settings.file_format = file_format
        for name, value in {**settings, **stamps}.items():
            setattr(render, name, value)
        scene.camera = scene_camera
        for obj, value in hidden.items():
            obj.hide_render = value
        scene.frame_set(frame_before, subframe=subframe_before)

    image = bpy.data.images.new("Contact Sheet", sheet_width, sheet_height, alpha=True)
    try:
        image.pixels.foreach_set(sheet)
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)
    return sheet_width, sheet_height


def _world_points(scene: bpy.types.Scene, meshes: list[bpy.types.Object], frames: Sequence[int]) -> list[Vector]:
    """Every vertex of the evaluated meshes, in world space, on every given frame."""
    points = []
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in meshes:
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.data
            assert isinstance(mesh, bpy.types.Mesh)
            matrix = evaluated.matrix_world.copy()
            points.extend(matrix @ vertex.co for vertex in mesh.vertices)
    return points


def _camera(scene: bpy.types.Scene, direction: Vector, points: list[Vector], aspect: float) -> bpy.types.Object:
    """An orthographic camera that looks against `direction` and holds all `points`."""
    data = bpy.data.cameras.new("Contact Sheet Camera")
    data.type = "ORTHO"
    camera = bpy.data.objects.new("Contact Sheet Camera", data)
    scene.collection.objects.link(camera)
    # A camera looks down its own -Z axis, so its Z axis points from the player to the camera.
    rotation = direction.to_track_quat("Z", "Y")
    camera.rotation_euler = rotation.to_euler()
    to_camera = rotation.inverted()
    seen = [to_camera @ point for point in points]
    xs, ys = [point.x for point in seen], [point.y for point in seen]
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    # ortho_scale is the size of the longer side of the image.
    if aspect >= 1:
        data.ortho_scale = max(span_x, span_y * aspect) * MARGIN
    else:
        data.ortho_scale = max(span_y, span_x / aspect) * MARGIN
    distance = max(point.length for point in points) + 1000
    centre = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0))
    camera.location = rotation @ centre + direction * distance
    data.clip_end = distance * 3
    return camera


def _read_pixels(path: str, width: int, height: int) -> array:
    """The red, green, blue and alpha of each pixel of an image of the given size, in rows from the bottom up."""
    image = bpy.data.images.load(path)
    try:
        pixels = array("f", bytes(4 * 4 * width * height))
        image.pixels.foreach_get(pixels)
    finally:
        bpy.data.images.remove(image)
    return pixels


class RSPS_OT_contact_sheet(bpy.types.Operator):
    bl_idname = "rsps.contact_sheet"
    bl_label = "Contact Sheet"
    bl_description = (
        "Render the active player on the given frames from the given views into one PNG, "
        "with one column per frame and one row per view"
    )
    # The operator puts back everything it changes in the scene, so it is not an undo step.
    # Only a Python call can give the frames and the file path, so the operator is hidden from the operator search (docs/adr/0020).
    bl_options = {"REGISTER", "INTERNAL"}

    filepath: bpy.props.StringProperty(name="File Path", description="Where the PNG goes", subtype="FILE_PATH")  # pyrefly: ignore[bad-assignment]
    frames: bpy.props.StringProperty(name="Frames", description="Scene frames, separated by commas, such as 1,6,11")  # pyrefly: ignore[bad-assignment]
    views: bpy.props.StringProperty(  # pyrefly: ignore[bad-assignment]
        name="Views",
        description=f"View names, separated by commas, from {', '.join(VIEWS)}",
        default=DEFAULT_VIEWS,
    )
    cell_width: bpy.props.IntProperty(  # pyrefly: ignore[bad-assignment]
        name="Cell Width", description="The width of one cell, in pixels", default=DEFAULT_CELL[0], min=1
    )
    cell_height: bpy.props.IntProperty(  # pyrefly: ignore[bad-assignment]
        name="Cell Height", description="The height of one cell, in pixels", default=DEFAULT_CELL[1], min=1
    )

    @classmethod
    def poll(cls, context):
        return appearance_preview.collection_of(context.active_object) is not None

    def execute(self, context):
        player = appearance_preview.collection_of(context.active_object)
        assert player is not None
        path = bpy.path.abspath(self.filepath)
        try:
            frames, views = parse_frames(self.frames), parse_views(self.views)
            width, height = contact_sheet(player, frames, views, (self.cell_width, self.cell_height), path)
        except (ValueError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Wrote the contact sheet {path} ({width} x {height} pixels)")
        return {"FINISHED"}


classes = (RSPS_OT_contact_sheet,)
