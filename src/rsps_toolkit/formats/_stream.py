SMART_MIN, SMART_MAX = -16384, 16383


def smart(value: int) -> bytes:
    """The inverse of Reader.smart: one byte for -64 to 63, two bytes for SMART_MIN to SMART_MAX."""
    if -64 <= value < 64:
        return bytes([value + 64])
    if not SMART_MIN <= value <= SMART_MAX:
        raise ValueError(f"{value} does not fit in a two-byte smart value")
    return (value + 0xC000).to_bytes(2)


class Reader:
    """Reads big-endian values from one section of a model file, raising IndexError past its end."""

    def __init__(self, data: bytes, offset: int = 0) -> None:
        self._data = data
        self._offset = offset

    def u8(self) -> int:
        value = self._data[self._offset]
        self._offset += 1
        return value

    @property
    def remaining(self) -> int:
        return len(self._data) - self._offset

    def take(self, size: int) -> bytes:
        end = self._offset + size
        if size < 0 or end > len(self._data):
            raise IndexError("Read beyond stream section")
        result = self._data[self._offset : end]
        self._offset = end
        return result

    def u16(self) -> int:
        value = self._data[self._offset] << 8 | self._data[self._offset + 1]
        self._offset += 2
        return value

    def smart(self) -> int:
        """A signed value stored in one byte (-64 to 63) or, when the top bit is set, two bytes."""
        first = self._data[self._offset]
        if first < 0x80:
            self._offset += 1
            return first - 64
        return self.u16() - 0xC000


def encode_vertices(vertices: list[tuple[int, int, int]]) -> tuple[bytes, bytes, bytes, bytes]:
    flags, xs, ys, zs = bytearray(), bytearray(), bytearray(), bytearray()
    last = (0, 0, 0)
    for vertex in vertices:
        dx, dy, dz = (v - p for v, p in zip(vertex, last, strict=True))
        flags.append((dx != 0) | (dy != 0) << 1 | (dz != 0) << 2)
        if dx:
            xs += smart(dx)
        if dy:
            ys += smart(dy)
        if dz:
            zs += smart(dz)
        last = vertex
    return bytes(flags), bytes(xs), bytes(ys), bytes(zs)


def encode_faces(faces: list[tuple[int, int, int]]) -> tuple[bytes, bytes]:
    # The inverse of _faces: pick the kind that reuses the most vertices of the previous face.
    kinds, indices = bytearray(), bytearray()
    a = b = c = last = 0
    for fa, fb, fc in faces:
        if (fa, fb) == (b, a):
            kinds.append(4)
            new = [fc]
        elif (fa, fb) == (c, b):
            kinds.append(3)
            new = [fc]
        elif (fa, fb) == (a, c):
            kinds.append(2)
            new = [fc]
        else:
            kinds.append(1)
            new = [fa, fb, fc]
        for index in new:
            indices += smart(index - last)
            last = index
        a, b, c = fa, fb, fc
    return bytes(kinds), bytes(indices)
