import gzip
from pathlib import Path

import bpy
import pytest
from js5_builder import REGION_FIXTURES

from rsps_toolkit.blender.face_materials import face_material, texture_image
from rsps_toolkit.formats.sprite import decode_sprites
from rsps_toolkit.formats.texture import SIZE, decode_texture, texture_pixels

# The client starts at brightness 0.8 (`GameCanvas.java` line 445 of the 2018 client).
BRIGHTNESS = 0.8


def reference_pixels(texture_id: int) -> tuple[int, ...]:
    """RuneLite's pixels of one texture at brightness 0.8, row by row from the top, from the reference file that
    `tests/fixtures/TextureReference.java` writes."""
    lines = iter(gzip.decompress((REGION_FIXTURES / "textures.txt.gz").read_bytes()).decode().splitlines())
    for header in lines:
        _, texture, _, _ = header.split()
        for _ in range(4):
            _, brightness = next(lines).split()
            rows = [next(lines) for _ in range(SIZE)]
            if int(texture) == texture_id and float(brightness) == BRIGHTNESS:
                return tuple(int(pixel, 16) for row in rows for pixel in row.split())
    raise LookupError(texture_id)


def decoded_image(texture_id: int) -> bpy.types.Image:
    texture = decode_texture(texture_id, (REGION_FIXTURES / "textures" / f"{texture_id}.dat").read_bytes())
    sprites = {
        sprite_id: decode_sprites(sprite_id, (REGION_FIXTURES / "sprites" / f"{sprite_id}.dat").read_bytes())
        for sprite_id in texture.sprites
    }
    return texture_image(texture_id, texture_pixels(texture, sprites, BRIGHTNESS), texture.opaque)


def rgba_from_the_top(image: bpy.types.Image) -> list[tuple[int, ...]]:
    """The image's pixels as 0 to 255 channels, row by row from the top. Blender's rows start at the bottom."""
    flat = [0.0] * (SIZE * SIZE * 4)
    image.pixels.foreach_get(flat)
    channels = [round(value * 255) for value in flat]
    rows = [channels[row * SIZE * 4 : (row + 1) * SIZE * 4] for row in range(SIZE)]
    return [tuple(row[i : i + 4]) for row in reversed(rows) for i in range(0, SIZE * 4, 4)]


@pytest.fixture(autouse=True)
def no_images():
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)
    yield


def test_the_image_of_an_opaque_texture_holds_runelites_pixels_and_no_transparent_texel():
    # Texture 16 is opaque (flag 1, `Texture.java` line 41), so the client draws every texel.
    image = decoded_image(16)

    size = [0, 0]
    image.size.foreach_get(size)
    assert size == [SIZE, SIZE]
    expected = [(pixel >> 16, pixel >> 8 & 0xFF, pixel & 0xFF, 255) for pixel in reference_pixels(16)]
    assert rgba_from_the_top(image) == expected


def test_a_texel_of_value_0_in_a_texture_that_is_not_opaque_is_transparent():
    # Texture 7 is not opaque, and 6,984 of its texels are 0 at brightness 0.8. The client skips a texel of value 0
    # when the texture is not opaque (`Graphics3D.java` lines 2182 to 2190, and the opaque flag at line 2480).
    image = decoded_image(7)

    expected = [
        (pixel >> 16, pixel >> 8 & 0xFF, pixel & 0xFF, 0 if pixel == 0 else 255) for pixel in reference_pixels(7)
    ]
    assert rgba_from_the_top(image) == expected


def test_a_texel_of_value_0_in_an_opaque_texture_is_drawn_black():
    # No opaque texture of snapshot 430 has a texel of value 0, so the pixels are made for the test. The client draws
    # every texel of an opaque texture, 0 included (`Graphics3D.java` line 2116).
    image = texture_image(0, [0] * (SIZE * SIZE), opaque=True)

    assert rgba_from_the_top(image) == [(0, 0, 0, 255)] * (SIZE * SIZE)


def test_the_image_is_packed_so_a_blend_file_holds_its_pixels(tmp_path: Path):
    image = decoded_image(16)
    expected = rgba_from_the_top(image)

    assert image.packed_file is not None
    assert not image.filepath or not Path(bpy.path.abspath(image.filepath)).exists()
    library = tmp_path / "textures.blend"
    bpy.data.libraries.write(str(library), {image})
    bpy.data.images.remove(image)
    with bpy.data.libraries.load(str(library)) as (source, target):  # pyrefly: ignore[bad-context-manager]
        target.images = source.images
    (loaded,) = bpy.data.images
    assert loaded.packed_file is not None
    assert rgba_from_the_top(loaded) == expected


def test_a_material_with_the_image_source_shows_the_image_without_filtering():
    image = decoded_image(16)

    material = face_material(None, 16, 0, lambda texture: image)

    assert material["rs_texture_id"] == 16
    tree = material.node_tree
    assert tree is not None
    nodes = [node for node in tree.nodes if isinstance(node, bpy.types.ShaderNodeTexImage)]
    assert [node.image for node in nodes] == [image]
    assert nodes[0].interpolation == "Closest"
    bsdf = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    links = {
        (link.from_node, link.from_socket.name, link.to_node, link.to_socket.name)
        for link in tree.links
        if link.from_socket is not None and link.to_socket is not None
    }
    assert (nodes[0], "Color", bsdf, "Base Color") in links
    assert (nodes[0], "Alpha", bsdf, "Alpha") in links
