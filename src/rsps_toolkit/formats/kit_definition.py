"""Decodes an identity kit definition from its raw bytes in the cache. Nothing here imports bpy.

The opcodes follow RuneLite's KitLoader (cache/src/main/java/net/runelite/cache/definitions/loaders/KitLoader.java at
commit bb0fa42b3). RuneLite's ConfigType gives IDENTKIT as config group 3, which holds these definitions. RuneLite
skips an opcode that it does not know. This decoder refuses it, and it also refuses bytes after the closing opcode 0,
so a wrong parse cannot pass without notice. RuneLite's opcodes 5 and 70 to 74, which store model ids in four bytes,
are left out on purpose: no snapshot 430 kit uses them, so they are refused like any unknown opcode. RuneLite reads
opcodes 60 to 69 as chathead models, but its KitDefinition holds only five, so opcodes 65 to 69 fail there too. This
decoder refuses them.
"""

from ._stream import Reader
from .appearance import Kit

CHATHEAD_SLOTS = 5


def decode_kit(kit_id: int, data: bytes) -> Kit:
    """Read one kit. Colours and textures are read as unsigned 16-bit values, as the rest of the toolkit uses them."""
    reader = Reader(data)
    body_part, non_selectable = -1, False
    model_ids: tuple[int, ...] = ()
    chathead_models = [-1] * CHATHEAD_SLOTS
    recolours: tuple[tuple[int, int], ...] = ()
    retextures: tuple[tuple[int, int], ...] = ()
    while (opcode := reader.u8()) != 0:
        if opcode == 1:
            body_part = reader.u8()
        elif opcode == 2:
            model_ids = tuple(reader.u16() for _ in range(reader.u8()))
        elif opcode == 3:
            non_selectable = True
        elif opcode == 40:
            recolours = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 41:
            retextures = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif 60 <= opcode < 60 + CHATHEAD_SLOTS:
            chathead_models[opcode - 60] = reader.u16()
        else:
            raise ValueError(f"Kit {kit_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"Kit {kit_id} has {reader.remaining} byte(s) after its closing opcode")
    return Kit(
        id=kit_id,
        body_part=body_part,
        model_ids=model_ids,
        chathead_models=tuple(chathead_models),
        non_selectable=non_selectable,
        recolours=recolours,
        retextures=retextures,
    )
