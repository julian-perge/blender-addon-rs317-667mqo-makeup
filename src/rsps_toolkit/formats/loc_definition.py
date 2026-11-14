"""Decodes a loc definition from its raw bytes in the cache. Nothing here imports bpy.

Locs are config group 6 of index 2. The opcodes follow `ObjectComposition.loadData` of the 2018 Old School client
(`ObjectComposition.java` lines 347 to 513), and the tests check them against RuneLite's ObjectLoader. The decoder reads
every opcode of `loadData`, so that each definition reads to its end, and keeps the fields that the region scenery
needs. The client skips an opcode that it does not know. This decoder refuses it, and it also refuses bytes after the
closing opcode 0, so a wrong parse cannot pass without notice.

The client also runs `post` (lines 304 to 322) after `loadData`. `post` sets only the interact flag and the item support
flag, which this decoder does not keep, so the decoder does not run it.
"""

from dataclasses import dataclass

from ._stream import Reader

_NONE = 0xFFFF
"""An unsigned short of 0xFFFF stands for -1 in the animation, the varbit, the varp and each impostor id."""


@dataclass(frozen=True)
class LocDefinition:
    """The fields of a loc that the region scenery needs. Fields that no opcode sets keep the defaults of the
    `ObjectComposition` constructor (`ObjectComposition.java` lines 262 to 296)."""

    models: tuple[int, ...]
    """The model ids. Empty when no opcode gives models."""
    loc_types: tuple[int, ...] | None
    """The loc type of each model (opcode 1), or None when the models come from opcode 5 or the loc has no models."""
    width: int
    length: int
    recolours: tuple[tuple[int, int], ...]
    """Pairs of the face colour to find and the colour to show, as unsigned 16-bit values."""
    retextures: tuple[tuple[int, int], ...]
    """Pairs of the texture to find and the texture to show."""
    scale: tuple[int, int, int]
    """The model scale in x, height and y. 128 is a scale of 1."""
    offset: tuple[int, int, int]
    """The model offset in x, height and y, as signed values."""
    mirrored: bool
    """The client's `isRotated` (opcode 62), which mirrors the model."""
    contoured_ground: int
    """-1 for a loc that is not contoured (see "Contoured loc" in `GLOSSARY.md`). Otherwise the value that
    `ObjectComposition.java` lines 600 to 606 pass to the contour of the model."""
    non_flat_shading: bool
    """The client's `nonFlatShading` (opcode 22), which changes how the client lights the model
    (`ObjectComposition.java` lines 584 and 596)."""
    animation: int
    """The animation id, or -1."""
    decor_displacement: int
    """The offset of a wall decoration from its wall, in game units (`PacketBuffer.java` line 295)."""
    casts_shadow: bool
    """The client's `clipped`, cleared by opcode 64. A loc with it writes loc shadows (`PacketBuffer.java` line 254)."""
    impostors: tuple[int, ...] | None
    """The impostor ids by varbit or varp value, then the id for any other value, or None for a loc with no impostors.
    -1 shows nothing (`ObjectComposition.java` lines 830 to 846)."""
    impostor_varbit: int
    """The varbit that picks the impostor, or -1. The client names it `varpId`."""
    impostor_varp: int
    """The varp that picks the impostor when there is no varbit, or -1. The client names it `configId`."""


def decode_loc(loc_id: int, data: bytes) -> LocDefinition:
    """Read one loc. The line numbers are those of `ObjectComposition.java`."""
    reader = Reader(data)
    models: tuple[int, ...] | None = None
    loc_types: tuple[int, ...] | None = None
    width = length = 1
    recolours: tuple[tuple[int, int], ...] = ()
    retextures: tuple[tuple[int, int], ...] = ()
    scale = [128, 128, 128]
    offset = [0, 0, 0]
    mirrored = non_flat_shading = False
    casts_shadow = True
    contoured_ground = animation = -1
    decor_displacement = 16
    impostors: tuple[int, ...] | None = None
    varbit = varp = -1
    while (opcode := reader.u8()) != 0:
        if opcode in (1, 5):
            # Lines 350 to 380. The client sets low detail mode from its low memory mode (`GameCanvas.java` line 295,
            # `KitDefinition.java` line 252), and it only ever sets low memory mode to false (`Client.java` line 1214,
            # `AbstractSoundSystem.java` line 503). So once a loc has models, a later list is skipped. A count of 0 reads
            # nothing.
            count = reader.u8()
            if count == 0:
                continue
            if models is not None:
                reader.take((3 if opcode == 1 else 2) * count)
            elif opcode == 1:
                pairs = [(reader.u16(), reader.u8()) for _ in range(count)]
                models, loc_types = tuple(m for m, _ in pairs), tuple(t for _, t in pairs)
            else:
                models, loc_types = tuple(reader.u16() for _ in range(count)), None
        elif opcode == 2 or 30 <= opcode < 35:
            _string(reader)
        elif opcode == 14:
            width = reader.u8()
        elif opcode == 15:
            length = reader.u8()
        elif opcode in (17, 18, 23, 27, 73, 74):
            # These opcodes read no value and set fields that the scenery does not keep.
            pass
        elif opcode == 21:
            contoured_ground = 0
        elif opcode == 22:
            non_flat_shading = True
        elif opcode == 24:
            animation = _or_none(reader.u16())
        elif opcode == 28:
            decor_displacement = reader.u8()
        elif opcode in (19, 29, 39, 69, 75):
            reader.u8()
        elif opcode == 40:
            recolours = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 41:
            retextures = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 62:
            mirrored = True
        elif opcode == 64:
            casts_shadow = False
        elif 65 <= opcode <= 67:
            scale[opcode - 65] = reader.u16()
        elif opcode in (68, 82):
            reader.u16()
        elif 70 <= opcode <= 72:
            # Lines 448 to 453 read the offsets as signed shorts, where RuneLite's ObjectLoader reads unsigned ones.
            offset[opcode - 70] = int.from_bytes(reader.take(2), signed=True)
        elif opcode == 78:
            reader.take(3)
        elif opcode == 79:
            reader.take(5)
            reader.take(2 * reader.u8())
        elif opcode == 81:
            contoured_ground = reader.u8() * 256
        elif opcode in (77, 92):
            # Lines 481 to 510. The impostor list has count + 1 ids, then the id for any other value: -1 for opcode 77,
            # and one more id, read before the count, for opcode 92.
            varbit, varp = _or_none(reader.u16()), _or_none(reader.u16())
            default = _or_none(reader.u16()) if opcode == 92 else -1
            ids = tuple(_or_none(reader.u16()) for _ in range(reader.u8() + 1))
            impostors = (*ids, default)
        elif opcode == 249:
            _parameters(reader)
        else:
            raise ValueError(f"Loc {loc_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"Loc {loc_id} has {reader.remaining} byte(s) after its closing opcode")
    return LocDefinition(
        models=models or (),
        loc_types=loc_types,
        width=width,
        length=length,
        recolours=recolours,
        retextures=retextures,
        scale=(scale[0], scale[1], scale[2]),
        offset=(offset[0], offset[1], offset[2]),
        mirrored=mirrored,
        contoured_ground=contoured_ground,
        non_flat_shading=non_flat_shading,
        animation=animation,
        decor_displacement=decor_displacement,
        casts_shadow=casts_shadow,
        impostors=impostors,
        impostor_varbit=varbit,
        impostor_varp=varp,
    )


def _or_none(value: int) -> int:
    return -1 if value == _NONE else value


def _parameters(reader: Reader) -> None:
    """Skip the parameters of opcode 249 (`CacheFile.java` lines 388 to 410): a count, then for each a flag byte, a 24-bit
    key, and text when the flag is 1 or a 32-bit number otherwise."""
    for _ in range(reader.u8()):
        is_text = reader.u8() == 1
        reader.take(3)
        if is_text:
            _string(reader)
        else:
            reader.take(4)


def _string(reader: Reader) -> None:
    """Skip text that ends with a zero byte (`Buffer.readString`)."""
    while reader.u8() != 0:
        pass
