# What the revision 149 client does for the six OSRS-149 codec rules

Read on 2026-11-11 for [spec/codec-rules-cited.md](../../../spec/codec-rules-cited.md), task T1. This is a reading of bytecode. No client code was run.

## Jar

The earlier findings in [reference-source-findings.md](../../osrs-focus/evidence/reference-source-findings.md) give the download command and the provenance limits. The SHA-256 below was checked before any reading.

| Identity | Value |
| --- | --- |
| Repository | `runetech/osrs-gamepacks`, file `gamepacks/osrs-149.jar` |
| Commit | `2e92962075cfbc0df227cc783c37633d5e92f297` |
| Size | 1,919,493 bytes |
| SHA-256 | `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd` |

The spec says to use the decompiler on this machine. No decompiler was found on the PATH, so this reading uses `javap -c -p` on the classes `dv`, `fe` and `el`, as the earlier findings did. This is a small deviation from the spec. All offsets are bytecode offsets inside the named method. The class and method names are the obfuscated names of this jar.

## Classes and methods

- `dv.j(byte[])` is the `FF FF` decoder. The constructor `dv(byte[])` calls it at offset 64. The method has no `athrow` and no exception table. It has no validation of its own. Only the reader class `fe` can throw, when a read goes past the end of the array.
- `fe` is the byte reader. `fe.z` reads one unsigned byte. `fe.i` reads one signed byte. `fe.d` reads an unsigned 16-bit big-endian value (2 bytes). `fe.au` reads a 32-bit big-endian value (4 bytes). The sizes come from the position step in each method.
- `dv.ae(IIIII)Lej;` converts the decoded data to the lit model `ej`. The earlier findings verified it. `dv.cu` is a duplicate with changed constants, and this reading does not use it.

## The footer in `dv.j`

The method sets the reader to the array length minus 23 (offsets 72 to 81) and reads these fields in this order:

| Read | Offsets | Field |
| --- | --- | --- |
| `fe.d` | 392 to 399 | vertex count |
| `fe.d` | 792 to 799 | face count |
| `fe.z` | 111 to 116 | texture count |
| `fe.z` | 640 to 645 | render type flag |
| `fe.z` | 133 to 138 | priority byte |
| `fe.z` | 1223 to 1228 | alpha flag |
| `fe.z` | 1018 to 1023 | face skin flag |
| `fe.z` | 162 to 167 | texture flag |
| `fe.z` | 1798 to 1803 | vertex skin flag |
| `fe.d` x5 | 628, 196, 2588, 219, 228 | X, Y, Z, face index and texture coordinate lengths |

The add-on's footer has the same order. The layout steps in `dv.j` also match the add-on's section order from the texture kinds to the texture coordinates: texture kinds, vertex flags, render types, face compression, priorities, face skins, vertex skins, alphas, face indices, texture ids, texture coordinates.

## Rule 1: one shared priority in the footer

Verdict: **confirmed**.

- Anchor: class `dv`, method `j`, offsets 2235 to 2240 and 965 to 969. A priority byte of 255 allocates a per-face priority array `dv.p`. Any other value is stored as one shared priority `dv.t`.
- Also: offsets 404 to 412 and 1537 to 1558 step over and read a per-face priority section only for 255. Class `dv`, method `ae`, offsets 197 to 203 copy `dv.p` to `ej.c`, and offsets 1804 to 1810 copy `dv.t` to `ej.h`.
- The client has no special case for a model with no faces. A byte of 0 is a shared priority like any value below 255. So "0 for no faces" is valid for the client. The value 0 is the add-on's choice.

## Rule 2: render type and alpha sections left out when all values are 0

Verdict: **confirmed**.

- Anchor: class `dv`, method `ae`, offsets 1192 to 1199 and 1706 to 1709 (render types) and 563 to 570 and 1488 to 1491 (alphas). When the array `dv.w` or `dv.m` is null, the value is 0.
- Also, in `dv.j`: the render type flag (local 12) allocates `dv.w` (offsets 1582 to 1588 and 457 to 462), steps over the section (offsets 2635 to 2641) and reads it (offsets 1516 to 1522 and 650 to 659), all only when the flag equals 1. The alpha flag (local 14) does the same: allocation at offsets 1364 to 1370 and 934 to 939, layout step at offsets 472 to 485, read at offsets 1559 to 1579.
- A file without these sections reads the same as a file with sections of zeros. The add-on writes the flag as 0 or 1 to match.

## Rule 3: a texture index above 254 is refused

Verdict: **confirmed**. The limit is the size of the field. The client has no check of its own.

- Anchor: class `dv`, method `j`, offsets 1632 to 1665. For a face that has a texture, the method reads one unsigned byte with `fe.z`, subtracts 1 and stores the result in `dv.u` as a byte.
- Also: the method reads this byte only when `dv.u` exists (the texture flag is 1 and the texture count is above 0, offsets 975 to 981, 2143 to 2148 and 994 to 999). Class `dv`, method `ae`, offsets 428 to 436: a stored -1 (file byte 0) means no texture triangle. Offsets 449 to 459 and 1618 to 1630 use the stored byte as an index after `& 255`.
- A file byte of 255 reads as index 254. This is the highest index. An index of 255 needs a file byte of 256, which does not fit in one byte. The add-on refuses it because it cannot write it.

## Rule 4: an opaque tail with a nonzero first byte and fewer than 11 bytes is refused

Verdict: **not settled**. The number 11 is the client's. The refusal is the add-on's own, and the client has no check for it.

- Anchor: class `dv`, method `j`, offsets 2689 to 2694 and 1901 to 1903. After the last texture section, the method reads one byte with `fe.z` from the end of the sections. If it is 0, the method returns.
- Also: otherwise (offsets 2709 to 2725, 2423 to 2431, 2740 to 2748, 172 to 180) the method creates an `el` object, reads 2, 2 and 2 bytes with `fe.d` and 4 bytes with `fe.au`, and does not use the values. The total is 1 + 2 + 2 + 2 + 4 = 11 bytes.
- The method does not check how many bytes remain. For a tail shorter than 11 bytes, the reads cover the footer bytes that follow, and no error occurs. For an empty tail, the first footer byte is read as the tail flag.
- `decode` refuses a tail that is empty (`not tail`) or that has a nonzero first byte and fewer than 11 bytes. This is stricter than the client.
- The reason for the refusal is a guess, not evidence: it probably stops a tail from overlapping the footer. The client states no reason.

## Rule 5: texture kinds above 3 are refused

Verdict: **not settled**. The values 0 to 3 are the client's. The refusal is the add-on's own, and the client has no check for it.

- Anchor: class `dv`, method `j`, offsets 2578 to 2585 and 2019 to 2032. Each kind byte is read as an unsigned byte. There is one read path for each of 0 (offsets 1999 to 2004), 1 (2261 to 2264), 2 (2407 to 2410) and 3 (2539 to 2542). For any other value the method reads nothing for that record and continues (offsets 2674 to 2677).
- Also: offsets 1613 to 1629 store each kind byte in `dv.o` and read it as a signed byte. Offsets 295 to 330 count the kinds: 0 is a simple record, 1 to 3 is a complex record, and 2 is also a record with 4 speed bytes.
- A record with a larger kind is in no count, takes no bytes, and keeps the value 0 in its triangle words.
- The add-on counts a record of kind 4 or more as complex (`complex_count = texture_count - simple_count` in `formats/new_format.py`). It would then read bytes that the client does not read. This follows from the two code readings. It is not a statement of the client.

## Rule 6: footer flags other than 0 or 1 are refused

Verdict: **not settled**. The values 0 and 1 are the client's. The refusal is the add-on's own, and the client has no check for it.

- Anchor: class `dv`, method `j`. The render, alpha, face skin, texture and vertex skin flags are only compared with 1. Render: offsets 1516 to 1519, 1582 to 1585, 2635 to 2638. Alpha: 1364 to 1367, 1559 to 1562, 472 to 475. Face skin: 426 to 429, 942 to 945. Texture: 975 to 978, 1604 to 1607, 526 to 529. Vertex skin: 448 to 451, 1774 to 1777.
- A value of 2 to 255 in one of these bytes means the same as 0: the section is absent. The client does not refuse it.
- The priority byte is compared with 255 only (rule 1). It is not a flag of 0 or 1, and `decode` does not check it.
- `decode` refuses a value of 2 to 255 in the five flag bytes. For such a file, the client reads no section, and the add-on would read bytes that the client does not read. This follows from the two code readings.

## The encode side of rule 6

The plan expected that `encode` could write a file that `decode` refuses, because `check` accepts six flag bytes of 0 to 255 (`formats/model.py`, `check`, the `section_flags` test). Reading `_encode` in `formats/new_format.py` shows that this cannot happen.

- The footer is built by the `_FOOTER.pack` call at the end of `_encode`. It passes booleans for the five flags, so the file has 0 or 1 in each.
- The render, alpha and texture flags come from the data (`has_render`, `has_alpha`, `textures`). A source flag equal to 1 only keeps a section that is otherwise empty. A source flag of 2 or more has no effect, so it gives 0 in the file when the data has no such section. The client does the same with it.
- The face skin and vertex skin flags come from `model.face_skins is not None` and `model.vertex_skins is not None`. The source flags for them are not used.

So no written file can fail to read in `decode`. The only gap is that `check` accepts source flags that `decode` refuses. These flags can come only from a hand-built model, because `decode` refuses them. The files are not affected. It is the user's decision whether `check` should refuse the same flags. That decision is a change of codec behaviour.

## Summary

| # | Rule | Verdict | What the client has |
| --- | --- | --- | --- |
| 1 | Shared priority in the footer | confirmed | 255 means per-face priorities, any other byte is the shared one |
| 2 | Render type and alpha sections left out | confirmed | flag 1 means present, else the values are 0 |
| 3 | Texture index above 254 refused | confirmed | one byte holds index plus 1, so 254 is the highest index |
| 4 | Short opaque tail refused | not settled | reads 11 bytes for a nonzero first byte, no length check |
| 5 | Texture kinds above 3 refused | not settled | handles 0 to 3, skips any other kind |
| 6 | Footer flags other than 0 or 1 refused | not settled | tests `== 1`, treats any other value as absent |

For rules 4 to 6, the client reads bad input without an error, and it reads it in a different way from the add-on. The add-on is stricter than the client. The user decides whether to keep the stricter refusal and to cite it in that form.
