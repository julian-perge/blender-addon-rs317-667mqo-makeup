"""Decodes an enum definition from its raw bytes in the cache. Nothing here imports bpy.

The opcodes follow RuneLite's EnumLoader (cache/src/main/java/net/runelite/cache/definitions/loaders/EnumLoader.java at
commit bb0fa42b3). RuneLite's ConfigType gives ENUM as config group 8, which holds these definitions. RuneLite skips
an opcode that it does not know. This decoder refuses it, and it also refuses bytes after the closing opcode 0, so a
wrong parse cannot pass without notice. RuneLite's opcodes 7 and 8, which hold long values, are left out on purpose:
no snapshot 430 enum uses them, so they are refused like any unknown opcode.
"""

from dataclasses import dataclass

from ._stream import Reader


@dataclass(frozen=True)
class EnumDefinition:
    """The keys of an enum and the value of each key. An enum holds either integer values or text values."""

    id: int
    keys: tuple[int, ...]
    int_values: tuple[int, ...]
    string_values: tuple[str, ...]


def decode_enum(enum_id: int, data: bytes) -> EnumDefinition:
    """Read one enum. The key type, value type and defaults are read and not kept, because nothing uses them."""
    reader = Reader(data)
    keys: tuple[int, ...] = ()
    int_values: tuple[int, ...] = ()
    string_values: tuple[str, ...] = ()
    while (opcode := reader.u8()) != 0:
        if opcode in (1, 2):
            reader.u8()
        elif opcode == 3:
            _string(reader)
        elif opcode == 4:
            reader.take(4)
        elif opcode == 5:
            pairs = [(_s32(reader), _string(reader)) for _ in range(reader.u16())]
            keys, string_values = tuple(k for k, _ in pairs), tuple(v for _, v in pairs)
        elif opcode == 6:
            pairs = [(_s32(reader), _s32(reader)) for _ in range(reader.u16())]
            keys, int_values = tuple(k for k, _ in pairs), tuple(v for _, v in pairs)
        else:
            raise ValueError(f"Enum {enum_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"Enum {enum_id} has {reader.remaining} byte(s) after its closing opcode")
    return EnumDefinition(id=enum_id, keys=keys, int_values=int_values, string_values=string_values)


def _s32(reader: Reader) -> int:
    return int.from_bytes(reader.take(4), signed=True)


def _string(reader: Reader) -> str:
    """Read text that ends with a zero byte. RuneLite decodes it as Windows-1252."""
    text = bytearray()
    while (byte := reader.u8()) != 0:
        text.append(byte)
    return text.decode("cp1252", errors="replace")
