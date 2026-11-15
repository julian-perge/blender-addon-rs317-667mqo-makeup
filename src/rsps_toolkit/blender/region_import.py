"""The File > Import entry for one region of the cache: its level 0 terrain and scenery, in a collection of its own."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

import bpy

from ..formats import decode
from ..formats.appearance import merge
from ..formats.cache_profile import MODEL_INDEX, SET_CACHE_FOLDER
from ..formats.floor_definition import Overlay, Underlay, read_overlays, read_underlays
from ..formats.js5 import Js5Store, NotInCacheError
from ..formats.loc_definition import LocDefinition, read_locs
from ..formats.model import Model, Vertex
from ..formats.region import REGION_SIZE, Terrain, bridge_tiles, load_landscape, load_terrain
from ..formats.region_colours import BLEND_AHEAD, BLEND_BEHIND
from ..formats.region_light import loc_shadows
from ..formats.region_loc import LocModel, recolour_model
from ..formats.region_placement import PlacedLoc, place_scenery
from ..formats.texture import read_textures, texture_pixels
from . import preferences
from .face_materials import texture_image
from .region_scenery import MeshKey, SceneryCounts, mesh_key, scenery_objects
from .region_terrain import drawn_tiles, terrain_object

REGION_MAX = 255


class RefusalError(Exception):
    """The import cannot run, and the message names the cause."""


@dataclass(frozen=True)
class RegionReport:
    """What one import made."""

    tiles: int
    """The terrain tiles that have at least one face. A tile with no underlay and no overlay has none, and neither has a
    tile whose parts are all hidden. The owner chose this meaning on 2026-11-14 (spec 35, guess 6)."""
    scenery: SceneryCounts
    bridge_tiles: tuple[tuple[int, int], ...]
    """The bridge tiles of the region as world tiles, which the import leaves out (`formats.region.bridge_tiles`)."""
    has_key: bool
    """False when the keys folder has no key file for the region, so the region has no scenery."""


class RS_OT_import_region(bpy.types.Operator):
    """Import the level 0 terrain of a region from the cache"""

    bl_idname = "import_scene.rs_region"
    bl_label = "Import RS Region"
    bl_options = {"REGISTER", "UNDO"}

    region_x: bpy.props.IntProperty(  # pyrefly: ignore[bad-assignment]
        name="Region X", description="The x number of the region", min=0, max=REGION_MAX, default=48
    )
    region_y: bpy.props.IntProperty(  # pyrefly: ignore[bad-assignment]
        name="Region Y", description="The y number of the region", min=0, max=REGION_MAX, default=50
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        x, y = self.region_x, self.region_y
        try:
            folder = preferences.cache_folder()
            if folder is None:
                raise RefusalError(SET_CACHE_FOLDER)
            region, report = import_region(context.scene.collection, folder, x, y, preferences.brightness())
        except (RefusalError, FileNotFoundError, NotInCacheError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        terrain = region.objects[0]
        for obj in context.view_layer.objects:
            obj.select_set(False)
        terrain.select_set(True)
        context.view_layer.objects.active = terrain
        self.report({"INFO"}, report_text(x, y, report))
        return {"FINISHED"}


def report_text(x: int, y: int, report: RegionReport) -> str:
    """The sentence that the operator reports: the numbers of the report, whether the region had a key, and the bridge
    tiles that the import leaves out, if there are any."""
    scenery = report.scenery
    text = (
        f"Imported region {x}_{y}: {report.tiles} tiles, {scenery.placements_made} placements made as {scenery.objects} "
        f"objects, {scenery.shared_meshes} shared meshes, {scenery.own_meshes} own meshes, {scenery.shown_nothing} "
        f"placements that showed nothing, the region had {'a key' if report.has_key else 'no key'}"
    )
    if report.bridge_tiles:
        text += f". {len(report.bridge_tiles)} bridge tiles are left out: {bridge_text(report.bridge_tiles)}"
    return text


def bridge_text(tiles: Sequence[tuple[int, int]]) -> str:
    """The tiles as ranges, such as `x 3112 to 3115, y 3200 to 3206`. Each column has its runs of consecutive y, and the
    next columns that hold the same run join its x range. Pieces are joined with `; `. The owner chose this format on
    2026-11-14 (spec 35, guess 7)."""
    columns = {x: _runs(sorted(y for column, y in tiles if column == x)) for x in sorted({x for x, _ in tiles})}
    pieces = []
    for x, runs in columns.items():
        for run in runs:
            if run in columns.get(x - 1, ()):
                continue
            last = x
            while run in columns.get(last + 1, ()):
                last += 1
            pieces.append(f"{_span('x', x, last)}, {_span('y', *run)}")
    return "; ".join(pieces)


def _runs(values: Sequence[int]) -> list[tuple[int, int]]:
    """The runs of consecutive numbers in the sorted `values`, each as its first and last number."""
    runs = []
    for _, group in groupby(enumerate(values), key=lambda item: item[1] - item[0]):
        numbers = [number for _, number in group]
        runs.append((numbers[0], numbers[-1]))
    return runs


def _span(axis: str, first: int, last: int) -> str:
    return f"{axis} {first}" if first == last else f"{axis} {first} to {last}"


def import_region(
    parent: bpy.types.Collection, folder: Path, x: int, y: int, brightness: float
) -> tuple[bpy.types.Collection, RegionReport]:
    """A new collection `Region <x>_<y>` in `parent`, with the object `Terrain <x>_<y>` and a child collection
    `Scenery <x>_<y>` of the level 0 placements (`region_scenery`), and the report of what it made. Everything is read
    from the cache first, so a read that fails makes nothing. A failure while building removes what was made so far and
    passes on.

    The scenery is made before the terrain, because the terrain light needs the loc shadows of the placements
    (`region_light.loc_shadows`). A region with no key file has no placements, so its terrain has no shadows.

    A loc or a model that the cache lacks stops the import, as a texture does. The owner chose this on 2026-11-14 (issue
    49, Decisions).

    A region whose own terrain group the cache lacks is refused, and the name of the scenery collection is as above,
    which the owner chose on 2026-11-14 (issue 47, Decisions)."""
    store = Js5Store(folder)
    terrain = load_terrain(store, x, y)
    if (x, y) in terrain.missing:
        raise RefusalError(f"The cache has no terrain for region {x}_{y}")
    underlays, overlays = read_underlays(store), read_overlays(store)
    _check_floors(terrain, underlays, overlays)
    landscape = load_landscape(store, x, y)
    placements = [placement for placement in landscape.placements if placement.level == 0]
    locs = read_locs(store, {placement.loc for placement in placements})

    def height(corner_x: int, corner_y: int) -> int:
        return terrain.tile(0, corner_x, corner_y).height

    placed = place_scenery(placements, locs, height)
    models = _loc_models(store, placed, locs)
    model_textures = {texture for model in models.values() for texture in model.face_textures if texture is not None}
    textures = read_textures(store, sorted(_textures(terrain, overlays) | model_textures))
    shadows = loc_shadows(placed, locs, _model_vertices(models))
    collections, objects, meshes = set(bpy.data.collections), set(bpy.data.objects), set(bpy.data.meshes)
    materials, images_before = set(bpy.data.materials), set(bpy.data.images)
    try:
        images = {
            texture_id: texture_image(texture_id, texture_pixels(texture, sprites, brightness), texture.opaque)
            for texture_id, (texture, sprites) in textures.items()
        }
        region = bpy.data.collections.new(f"Region {x}_{y}")
        scenery = bpy.data.collections.new(f"Scenery {x}_{y}")
        region.children.link(scenery)
        counts = scenery_objects(scenery, placed, locs, models, images, height, brightness)
        terrain_obj = terrain_object(f"Terrain {x}_{y}", terrain, underlays, overlays, images, brightness, shadows)
        region.objects.link(terrain_obj)
        parent.children.link(region)
    except Exception:
        for collection in set(bpy.data.collections) - collections:
            bpy.data.collections.remove(collection)
        for obj in set(bpy.data.objects) - objects:
            bpy.data.objects.remove(obj)
        for mesh in set(bpy.data.meshes) - meshes:
            bpy.data.meshes.remove(mesh)
        for material in set(bpy.data.materials) - materials:
            bpy.data.materials.remove(material)
        for image in set(bpy.data.images) - images_before:
            bpy.data.images.remove(image)
        raise
    bridges = tuple((x * REGION_SIZE + tile_x, y * REGION_SIZE + tile_y) for tile_x, tile_y in bridge_tiles(terrain))
    return region, RegionReport(drawn_tiles(terrain_obj), counts, bridges, landscape.has_key)


def _model_vertices(models: Mapping[MeshKey, Model]) -> Callable[[LocModel], Sequence[Vertex]]:
    """The vertices that `loc_shadows` asks for, as the cache stores them with the cache models of a part joined. They
    come from the models of `_loc_models`, whose recolours and retextures leave the vertices alone. Every part that
    `loc_shadows` asks for is in `models`, because it asks only for the placements that show their own loc."""
    by_ids = {key[0]: model.vertices for key, model in models.items()}
    return lambda loc_model: by_ids[loc_model.model_ids]


def _loc_models(store: Js5Store, placed: list[PlacedLoc], locs: dict[int, LocDefinition]) -> dict[MeshKey, Model]:
    """The model of each part of the placements, by its `mesh_key`. The cache models of a part are joined as the client
    joins them (`ObjectComposition.java` lines 728 to 733), and then recoloured and retextured as the loc says. The join
    gives an old-format model, so a recolour of 127 on it is refused, which the owner accepted on 2026-11-14 (issue 49,
    Decisions)."""
    decoded: dict[int, Model] = {}

    def cache_model(model_id: int) -> Model:
        if model_id not in decoded:
            decoded[model_id] = decode(store.container(MODEL_INDEX, model_id), profile="osrs-149")
        return decoded[model_id]

    models: dict[MeshKey, Model] = {}
    for placed_loc in placed:
        if placed_loc.shown_id is None:
            continue
        shown = locs[placed_loc.shown_id]
        for part in placed_loc.parts:
            key = mesh_key(part, shown)
            if key in models:
                continue
            parts = [cache_model(model_id) for model_id in part.model.model_ids]
            joined = parts[0] if len(parts) == 1 else merge(parts)
            models[key] = recolour_model(joined, shown.recolours, shown.retextures)
    return models


def _check_floors(terrain: Terrain, underlays: Mapping[int, Underlay], overlays: Mapping[int, Overlay]) -> None:
    """Refuse a terrain that names a floor definition the cache lacks, before anything is made. The blend of the
    region's tiles reads the underlays from 4 tiles west and south of the region to 5 tiles east and north of it, and
    only the region's own tiles read their overlays (`region_colours`)."""
    for x in range(-BLEND_BEHIND, REGION_SIZE + BLEND_AHEAD):
        for y in range(-BLEND_BEHIND, REGION_SIZE + BLEND_AHEAD):
            tile = terrain.tile(0, x, y)
            if tile.underlay and tile.underlay - 1 not in underlays:
                raise RefusalError(f"The cache has no underlay {tile.underlay - 1}, which tile ({x}, {y}) names")
            inside = 0 <= x < REGION_SIZE and 0 <= y < REGION_SIZE
            if inside and tile.overlay and tile.overlay - 1 not in overlays:
                raise RefusalError(f"The cache has no overlay {tile.overlay - 1}, which tile ({x}, {y}) names")


def _textures(terrain: Terrain, overlays: Mapping[int, Overlay]) -> set[int]:
    """The textures of the overlays on the level 0 tiles of the terrain's region."""
    found = set()
    for x in range(REGION_SIZE):
        for y in range(REGION_SIZE):
            overlay = terrain.tile(0, x, y).overlay
            if overlay and overlays[overlay - 1].texture >= 0:
                found.add(overlays[overlay - 1].texture)
    return found


def menu_entry(self, context):
    self.layout.operator(RS_OT_import_region.bl_idname, text="RS Region (from cache)")


classes = (RS_OT_import_region,)
