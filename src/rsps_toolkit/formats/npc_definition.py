"""Decodes an NPC definition from its raw bytes in the cache. Nothing here imports bpy.

NPCs are config group 9 of index 2. The opcodes follow `NPCComposition.readNext` of the 2018 Old School client
(`NPCComposition.java` lines 251 to 368), and the tests check them against RuneLite's NpcLoader. The decoder reads
every opcode of `readNext`, so that each definition reads to its end, and keeps the fields that an NPC rig needs (spec
13). The client ignores an opcode that it does not know and reads no value for it. This decoder refuses it, and it
also refuses bytes after the closing opcode 0, so a wrong parse cannot pass without notice.

The client's `post` (lines 225 to 226) is empty, so the decoder has nothing to run after the opcodes.
"""

from dataclasses import dataclass

from ._stream import Reader
from .floor_definition import CONFIG_INDEX
from .js5 import Js5Store, NotInCacheError

NPC_GROUP = 9


@dataclass(frozen=True)
class NpcDefinition:
    """The fields of an NPC that an NPC rig needs. Fields that no opcode sets keep the defaults of the `NPCComposition`
    constructor (`NPCComposition.java` lines 192 to 217). Each sequence is a sequence id, or -1 for none. The client
    reads each sequence as an unsigned short and keeps 65535 as it is, so this decoder does too."""

    models: tuple[int, ...]
    """The model ids, in the order that the client merges them. Empty when no opcode gives models."""
    name: str
    stand: int
    walk: int
    """The walk sequence. Opcodes 14 and 17 both set it, and the later opcode wins."""
    turn_left: int
    """The sequence of opcode 15. The client names it `field3509`, and RuneLite names it `idleRotateLeftAnimation`."""
    turn_right: int
    """The sequence of opcode 16. The client names it `field3499`, and RuneLite names it `idleRotateRightAnimation`."""
    walk_back: int
    """The client's `rotate180Animation`."""
    walk_left: int
    """The third sequence of opcode 17. The 2018 client names it `rotate90RightAnimation`, but it copies it to the
    actor slot `field882` (`Frames.java` line 238), which is the walk left slot of a player (`Player.java` line 244,
    `docs/research/weapon-stance-sets.md` section 1). RuneLite names it `rotateLeftAnimation`."""
    walk_right: int
    """The fourth sequence of opcode 17. The 2018 client names it `rotate90LeftAnimation`, but it copies it to the
    actor slot `field893` (`Frames.java` line 239), which is the walk right slot of a player (`Player.java` line 249).
    RuneLite names it `rotateRightAnimation`."""
    recolours: tuple[tuple[int, int], ...]
    """Pairs of the face colour to find and the colour to show, as unsigned 16-bit values."""
    retextures: tuple[tuple[int, int], ...]
    """Pairs of the texture to find and the texture to show."""
    width_scale: int
    """The scale in game x and z. 128 is a scale of 1."""
    height_scale: int
    """The scale in game height. 128 is a scale of 1."""
    ambient: int
    contrast: int


def read_npc(store: Js5Store, npc_id: int) -> NpcDefinition:
    """The NPC of the cache with this id. An NPC id that the cache lacks is an error, as a loc id is for
    `loc_definition.read_locs`."""
    files = store.files(CONFIG_INDEX, NPC_GROUP)
    if npc_id not in files:
        raise NotInCacheError(f"Group {NPC_GROUP} of index {CONFIG_INDEX} of the cache has no NPC {npc_id}")
    return decode_npc(npc_id, files[npc_id])


def decode_npc(npc_id: int, data: bytes) -> NpcDefinition:
    """Read one NPC. The line numbers are those of `NPCComposition.java`."""
    reader = Reader(data)
    models: tuple[int, ...] = ()
    name = "null"
    stand = walk = turn_left = turn_right = walk_back = walk_left = walk_right = -1
    recolours: tuple[tuple[int, int], ...] = ()
    retextures: tuple[tuple[int, int], ...] = ()
    width_scale = height_scale = 128
    ambient = contrast = 0
    while (opcode := reader.u8()) != 0:
        if opcode == 1:
            models = tuple(reader.u16() for _ in range(reader.u8()))
        elif opcode == 2:
            name = _string(reader)
        elif opcode == 12:
            reader.u8()
        elif opcode == 13:
            stand = reader.u16()
        elif opcode == 14:
            walk = reader.u16()
        elif opcode == 15:
            turn_left = reader.u16()
        elif opcode == 16:
            turn_right = reader.u16()
        elif opcode == 17:
            # Lines 273 to 277 read the walk, walk back, walk left and walk right sequences, in that order.
            walk, walk_back, walk_left, walk_right = (reader.u16() for _ in range(4))
        elif 30 <= opcode < 35:
            _string(reader)
        elif opcode == 40:
            recolours = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 41:
            retextures = tuple((reader.u16(), reader.u16()) for _ in range(reader.u8()))
        elif opcode == 60:
            # Lines 301 to 307: the chat head models, which an NPC rig does not use.
            reader.take(2 * reader.u8())
        elif opcode in (93, 99, 107, 109, 111):
            # These opcodes read no value and set fields that an NPC rig does not keep.
            pass
        elif opcode in (95, 102, 103):
            reader.u16()
        elif opcode == 97:
            width_scale = reader.u16()
        elif opcode == 98:
            height_scale = reader.u16()
        elif opcode == 100:
            # Lines 318 to 321 read the ambient and the contrast with `readByte`, which is signed.
            ambient = _s8(reader)
        elif opcode == 101:
            contrast = _s8(reader)
        elif opcode in (106, 118):
            # Lines 326 to 366: the varbit and the varp, one more id for opcode 118, then a count and count + 1
            # impostor ids. Spec 13 does not keep impostors.
            reader.take(4)
            if opcode == 118:
                reader.u16()
            reader.take(2 * (reader.u8() + 1))
        elif opcode == 249:
            _parameters(reader)
        else:
            raise ValueError(f"NPC {npc_id} has unknown opcode {opcode}")
    if reader.remaining:
        raise ValueError(f"NPC {npc_id} has {reader.remaining} byte(s) after its closing opcode")
    return NpcDefinition(
        models=models,
        name=name,
        stand=stand,
        walk=walk,
        turn_left=turn_left,
        turn_right=turn_right,
        walk_back=walk_back,
        walk_left=walk_left,
        walk_right=walk_right,
        recolours=recolours,
        retextures=retextures,
        width_scale=width_scale,
        height_scale=height_scale,
        ambient=ambient,
        contrast=contrast,
    )


def _s8(reader: Reader) -> int:
    return int.from_bytes(reader.take(1), signed=True)


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


def _string(reader: Reader) -> str:
    """Read text that ends with a zero byte. RuneLite decodes it as Windows-1252, with "?" for the five bytes that
    Windows-1252 leaves undefined (InputStream.readString)."""
    text = bytearray()
    while (byte := reader.u8()) != 0:
        text.append(byte)
    return text.decode("cp1252", errors="replace").replace("\ufffd", "?")
