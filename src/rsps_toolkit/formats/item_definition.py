"""Decodes an item definition from its raw bytes in the cache. Nothing here imports bpy.

The opcodes follow RuneLite's ItemLoader and EntityOpsLoader (cache/src/main/java/net/runelite/cache/definitions/
loaders/ at commit bb0fa42b3; both files are unchanged since commit 8f2aca1, which `scripts/generate-item-wear.py`
names). RuneLite's ConfigType gives ITEM as config group 10, which holds these definitions.
RuneLite skips an opcode that it does not know. This decoder refuses it, and it also refuses bytes after the closing
opcode 0, so a wrong parse cannot pass without notice. The decoder reads every opcode that RuneLite reads, so that
it can also decode the items of recent caches, such as cache 2757. It keeps only the worn-model fields
and the wear positions. Fields that no opcode sets keep RuneLite's defaults from ItemDefinition.java: the name "null",
-1 for models and wear positions, and 0 for offsets.
"""

from dataclasses import dataclass

from ._stream import Reader
from .appearance import WornItem


@dataclass(frozen=True)
class ItemDefinition:
    """The worn-model fields of an item, and its three wear positions (RuneLite's wearPos1 to wearPos3). Each wear
    position is an equipment slot: the first is the slot the item fills, and the other two are slots it empties.
    A wear position of -1 means none."""

    worn: WornItem
    wear_positions: tuple[int, int, int]


def decode_item(item_id: int, data: bytes) -> ItemDefinition:
    """Read one item. Colours and textures are read as unsigned 16-bit values, as the rest of the toolkit uses them."""
    reader = Reader(data)
    name = "null"
    male, female = [-1] * 3, [-1] * 3
    male_offset = female_offset = 0
    wear = [-1] * 3
    recolours: tuple[tuple[int, int], ...] = ()
    retextures: tuple[tuple[int, int], ...] = ()
    while (opcode := reader.u8()) != 0:
        if opcode in (1, 4, 5, 6, 7, 8, 75, 90, 91, 92, 93, 94, 95, 97, 98, 99, 110, 111, 112, 139, 140, 148, 149):
            reader.u16()
        elif opcode == 2:
            name = _string(reader)
        elif opcode in (3, 9) or 30 <= opcode < 40:
            _string(reader)
        elif opcode in (11, 15, 16, 65, 160, 251):
            pass
        elif opcode in (12, 44, 51, 52, 53, 54):
            reader.take(4)
        elif opcode == 13:
            wear[0] = _s8(reader)
        elif opcode == 14:
            wear[1] = _s8(reader)
        elif opcode == 27:
            wear[2] = _s8(reader)
        elif opcode == 23:
            male[0], male_offset = reader.u16(), reader.u8()
        elif opcode == 24:
            male[1] = reader.u16()
        elif opcode == 78:
            male[2] = reader.u16()
        elif opcode == 25:
            female[0], female_offset = reader.u16(), reader.u8()
        elif opcode == 26:
            female[1] = reader.u16()
        elif opcode == 79:
            female[2] = reader.u16()
        elif opcode == 45:
            male[0], male_offset = _s32(reader), reader.u8()
        elif opcode == 46:
            male[1] = _s32(reader)
        elif opcode == 47:
            male[2] = _s32(reader)
        elif opcode == 48:
            female[0], female_offset = _s32(reader), reader.u8()
        elif opcode == 49:
            female[1] = _s32(reader)
        elif opcode == 50:
            female[2] = _s32(reader)
        elif opcode == 40:
            recolours = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 41:
            retextures = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode in (42, 113, 114, 115):
            reader.u8()
        elif opcode == 43:
            reader.u8()
            while reader.u8() != 0:
                _string(reader)
        elif 100 <= opcode < 110:
            reader.take(4)
        elif opcode == 161:
            reader.take(2 * reader.u16())
        elif opcode == 200:
            reader.take(2)
            _string(reader)
        elif opcode == 201:
            reader.take(13)
            _string(reader)
        elif opcode == 202:
            reader.take(15)
            _string(reader)
        elif opcode == 249:
            for _ in range(reader.u8()):
                kind = reader.u8()
                reader.take(3)
                if kind == 1:
                    _string(reader)
                else:
                    reader.take(8 if kind == 2 else 4)
        else:
            raise ValueError(f"Item {item_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"Item {item_id} has {reader.remaining} byte(s) after its closing opcode")
    worn = WornItem(
        id=item_id,
        name=name,
        male_models=(male[0], male[1], male[2]),
        male_offset=male_offset,
        female_models=(female[0], female[1], female[2]),
        female_offset=female_offset,
        recolours=recolours,
        retextures=retextures,
    )
    return ItemDefinition(worn=worn, wear_positions=(wear[0], wear[1], wear[2]))


def _s8(reader: Reader) -> int:
    return int.from_bytes(reader.take(1), signed=True)


def _s32(reader: Reader) -> int:
    return int.from_bytes(reader.take(4), signed=True)


def _string(reader: Reader) -> str:
    """Read text that ends with a zero byte. RuneLite decodes it as Windows-1252."""
    text = bytearray()
    while (byte := reader.u8()) != 0:
        text.append(byte)
    return text.decode("cp1252", errors="replace")
