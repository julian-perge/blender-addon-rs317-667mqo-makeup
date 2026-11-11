"""Model files as bytes, decoded to a plain Model and encoded back. Nothing here imports bpy."""

import struct
from dataclasses import replace

from . import new_format, old_format
from .colour import face_colour_to_rgb
from .model import InvalidModelError, Model, ModelEncoding, ModelProfile, NewFormatData
from .set_aside import SetAsideFace, restore_faces, set_aside_faces
from .texture_uvs import texture_uvs

__all__ = [
    "InvalidModelError",
    "Model",
    "ModelEncoding",
    "ModelProfile",
    "NewFormatData",
    "SetAsideFace",
    "decode",
    "encode",
    "face_colour_to_rgb",
    "restore_faces",
    "set_aside_faces",
    "texture_uvs",
]


def decode(data: bytes, *, profile: ModelProfile | None = None) -> Model:
    if profile not in (None, "osrs-149"):
        raise InvalidModelError(f"Unsupported model profile {profile!r}")
    if data[-2:] == b"\xff\xff":
        if profile != "osrs-149":
            raise InvalidModelError("FFFF models require an explicit osrs-149 profile")
        return new_format.decode(data)
    if data[-2:] in (b"\xff\xfd", b"\xff\xfe"):
        raise InvalidModelError(f"Unsupported model marker {data[-2:].hex()}")
    try:
        return replace(old_format.decode(data), profile=profile)
    except (IndexError, struct.error) as error:
        raise InvalidModelError(f"Truncated old-format model: {error}") from error


def encode(model: Model) -> bytes:
    if model.encoding is ModelEncoding.OSRS_FFFF:
        return new_format.encode(model)
    return old_format.encode(model)
