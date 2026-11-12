"""Feedback tools for the sword flourish test: a contact sheet and a review video.

Run inside Blender. Both functions restore every render setting they change.

    contact_sheet("Player_rig", [1, 6, 11], "<folder>/sheet.png")
    review_video(["Player_rig", "Player.001_rig"], 1, 41, "<folder>/review.mp4")
"""

import os
import tempfile

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

# Each view is the direction from the player to the camera. A player from Create Player faces -Y.
VIEWS = {
    "front": Vector((0, -1, 0)),
    "back": Vector((0, 1, 0)),
    "right": Vector((-1, 0, 0)),
    "left": Vector((1, 0, 0)),
    "top": Vector((0, 0, 1)),
}

RENDER_ATTRS = (
    "resolution_x",
    "resolution_y",
    "resolution_percentage",
    "filepath",
    "use_border",
    "use_crop_to_border",
    "border_min_x",
    "border_max_x",
    "border_min_y",
    "border_max_y",
    "use_stamp",
    "stamp_font_size",
    "use_file_extension",
)


def _player_meshes(rig_name):
    rig = bpy.data.objects[rig_name]
    return [o for o in rig.children_recursive if o.type == "MESH"]


def _world_points(scene, meshes, frames):
    """Every vertex of the evaluated meshes, in world space, on every given frame."""
    points = []
    for frame in frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for mesh_object in meshes:
            evaluated = mesh_object.evaluated_get(depsgraph)
            matrix = evaluated.matrix_world
            points.extend(matrix @ v.co for v in evaluated.data.vertices)
    return points


class _RenderState:
    """Saves the render settings, the camera, the frame and the render visibility, and puts them back."""

    def __enter__(self):
        scene = bpy.context.scene
        render = scene.render
        self.scene = scene
        self.render = {name: getattr(render, name) for name in RENDER_ATTRS}
        self.stamps = {name: getattr(render, name) for name in dir(render) if name.startswith("use_stamp_")}
        settings = render.image_settings
        self.media_type = settings.media_type
        self.file_format = settings.file_format
        self.camera = scene.camera
        self.frame = scene.frame_current
        self.range = (scene.frame_start, scene.frame_end)
        self.hidden = {o.name: o.hide_render for o in scene.objects}
        return self

    def __exit__(self, *exc):
        scene = self.scene
        render = scene.render
        render.image_settings.media_type = self.media_type
        render.image_settings.file_format = self.file_format
        for name, value in {**self.render, **self.stamps}.items():
            setattr(render, name, value)
        scene.camera = self.camera
        scene.frame_start, scene.frame_end = self.range
        for name, value in self.hidden.items():
            bpy.data.objects[name].hide_render = value
        scene.frame_set(self.frame)
        return False


def _stamp_frame_only(render, font_size):
    for name in dir(render):
        if name.startswith("use_stamp_"):
            setattr(render, name, False)
    render.use_stamp = True
    render.use_stamp_frame = True
    render.stamp_font_size = font_size


def _ortho_camera(scene, direction, points, aspect):
    """An orthographic camera that looks against `direction` and holds all `points`."""
    data = bpy.data.cameras.new("Sheet Camera")
    data.type = "ORTHO"
    camera = bpy.data.objects.new("Sheet Camera", data)
    scene.collection.objects.link(camera)
    camera.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.update()
    inverse = camera.matrix_world.inverted()
    local = [inverse @ p for p in points]
    xs = [p.x for p in local]
    ys = [p.y for p in local]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    centre = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0))
    # ortho_scale is the size of the longer side of the image.
    if aspect >= 1:
        data.ortho_scale = max(width, height * aspect) * 1.1
    else:
        data.ortho_scale = max(height, width / aspect) * 1.1
    distance = max(p.length for p in points) + 1000
    camera.location = camera.matrix_world.to_3x3() @ centre + direction * distance
    data.clip_end = distance * 3
    return camera


def _read_pixels(path):
    image = bpy.data.images.load(path)
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    bpy.data.images.remove(image)
    return pixels.reshape(height, width, 4)


def contact_sheet(rig_name, frames, out_path, views=("front", "right"), cell=(320, 480)):
    """Render one player on each frame of `frames`, from each view, into one PNG.

    The sheet has one row per view and one column per frame, in the order given.
    Every cell of a row has the same camera, and each cell shows its frame number.
    """
    scene = bpy.context.scene
    meshes = _player_meshes(rig_name)
    keep = {o.name for o in meshes}
    cell_w, cell_h = cell
    sheet = np.zeros((cell_h * len(views), cell_w * len(frames), 4), dtype=np.float32)
    cameras = []
    with _RenderState(), tempfile.TemporaryDirectory() as folder:
        render = scene.render
        try:
            points = _world_points(scene, meshes, frames)
            for o in scene.objects:
                if o.type == "MESH" and o.name not in keep:
                    o.hide_render = True
            render.image_settings.media_type = "IMAGE"
            render.image_settings.file_format = "PNG"
            render.resolution_x, render.resolution_y = cell_w, cell_h
            render.resolution_percentage = 100
            render.use_border = False
            _stamp_frame_only(render, 22)
            for row, view in enumerate(views):
                camera = _ortho_camera(scene, VIEWS[view], points, cell_w / cell_h)
                cameras.append(camera)
                scene.camera = camera
                for column, frame in enumerate(frames):
                    scene.frame_set(frame)
                    render.filepath = os.path.join(folder, f"{view}-{frame}.png")
                    bpy.ops.render.render(write_still=True)
                    pixels = _read_pixels(render.filepath)
                    # Image rows run from the bottom up, so the first view goes in the last rows.
                    y = (len(views) - 1 - row) * cell_h
                    x = column * cell_w
                    sheet[y : y + cell_h, x : x + cell_w] = pixels
        finally:
            for camera in cameras:
                data = camera.data
                bpy.data.objects.remove(camera)
                bpy.data.cameras.remove(data)
    image = bpy.data.images.new("Contact Sheet", sheet.shape[1], sheet.shape[0], alpha=True)
    image.pixels.foreach_set(sheet.ravel())
    image.filepath_raw = out_path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
    return {"path": out_path, "size": [sheet.shape[1], sheet.shape[0]], "frames": list(frames), "views": list(views)}


def review_video(rig_names, frame_start, frame_end, out_path, scale=150):
    """Render the frame range from the scene camera as an H.264 MP4 at the scene's frame rate.

    The image is cut to the players named in `rig_names`, so they fill the video.
    Each video frame shows its scene frame number.
    """
    scene = bpy.context.scene
    camera = scene.camera
    meshes = [m for name in rig_names for m in _player_meshes(name)]
    with _RenderState():
        render = scene.render
        render.resolution_percentage = scale
        width = render.resolution_x * scale // 100
        height = render.resolution_y * scale // 100
        points = _world_points(scene, meshes, range(frame_start, frame_end + 1))
        projected = [world_to_camera_view(scene, camera, p) for p in points]
        xs = [p.x for p in projected]
        ys = [p.y for p in projected]
        pad = 0.04

        def pixel_span(low, high, size):
            """A whole-pixel span with an even length, because H.264 needs even sides."""
            first = max(0, int((low - pad) * size))
            last = min(size, int((high + pad) * size) + 1)
            if (last - first) % 2:
                last -= 1
            return first, last

        x0, x1 = pixel_span(min(xs), max(xs), width)
        y0, y1 = pixel_span(min(ys), max(ys), height)
        render.use_border = True
        render.use_crop_to_border = True
        # Blender stores the border as 32-bit fractions and cuts them back to whole pixels, so a fraction that is
        # exactly on a pixel edge can lose one pixel. A small part of a pixel is added to stay on the wanted pixel.
        render.border_min_x, render.border_max_x = (x0 + 0.01) / width, (x1 + 0.01) / width
        render.border_min_y, render.border_max_y = (y0 + 0.01) / height, (y1 + 0.01) / height
        _stamp_frame_only(render, 18)
        # The media type must be VIDEO before FFMPEG is a valid file format.
        render.image_settings.media_type = "VIDEO"
        render.image_settings.file_format = "FFMPEG"
        render.ffmpeg.format = "MPEG4"
        render.ffmpeg.codec = "H264"
        render.ffmpeg.constant_rate_factor = "HIGH"
        render.ffmpeg.audio_codec = "NONE"
        render.use_file_extension = False
        render.filepath = out_path
        scene.frame_start, scene.frame_end = frame_start, frame_end
        bpy.ops.render.render(animation=True)
    return {
        "path": out_path,
        "size": [x1 - x0, y1 - y0],
        "crop": {"x": x0, "y_from_bottom": y0, "of": [width, height]},
        "frames": [frame_start, frame_end],
        "fps": scene.render.fps,
    }
