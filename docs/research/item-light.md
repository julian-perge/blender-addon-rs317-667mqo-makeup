# The item light in gamepack 149

Checked on 2026-11-20 with `javap -p -c` on the revision 149 gamepack (SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`, the jar that [the 149 fixtures](../../tests/fixtures/models/osrs149/README.md) name). The named source tree of `scripts/named-client/` was not on the machine, so the offsets below are bytecode offsets of the obfuscated classes. The real names come from [client-names.tsv](client-names.tsv).

## `iz.p(IB)Lej;` is `ItemComposition.getModel`

| Offsets | What the code does |
| --- | --- |
| 185 to 197 | `dv.a(iz.l, this.t, 0)`: load the model `inventoryModel` (`iz.t`) from the model index (`iz.l`). |
| 228 to 251 | `dv.h(this.ao, this.ac, this.af)`: scale by `resizeX`, `resizeY` and `resizeZ`, when one of them is not 128. |
| 332 to 436 | For each pair, `dv.c(this.o[i], this.x[i])` (`recolor` with `colourToReplace` and `colourToReplaceWith`), and `dv.o(this.f[i], this.h[i])` for the texture pairs. |
| 511 to 542 | `dv.ae(64 + this.bp, 768 + this.bi, -50, -10, -50)`: `ModelData.light` with `ambient` (`iz.bp`) and `contrast` (`iz.bi`). |

The two fields are read with their multipliers (`-385793045` for `bp` and `1880149473` for `bi`), which undo the multipliers of the decoder below.

`iz.at(I)Lej;` and `iz.al(I)Lej;` hold copies of the same call. `iz.al` has changed constants in place of 768 and the first -50. They are the duplicate methods that [reference-source-findings.md](osrs-focus/reference-source-findings.md) warns about, so this note uses `iz.p` only.

The row `iz.p` (`getModel`) of [client-names.tsv](client-names.tsv) links to this note for the item light: the mapper gave the name, and the offsets above confirm what the method does. The rows `dv.h` (`resize`) and `dv.o` (`retexture`) are new and link here too.

## `dv.h(III)V` is the resize

The decoder stores opcodes 110, 111 and 112 in `iz.ao`, `iz.ac` and `iz.af` (`resizeX`, `resizeY` and `resizeZ` of the mapper). The control flow of `iz.v` is scrambled, so this pairing is read from the order of the fields and from the mapper's names, and it is not proven from the jumps.


Offsets 7 to 72: for each vertex, `x = x * a / 128`, `y = y * b / 128` and `z = z * c / 128`, with Java's integer division, which rounds toward zero. `dv.j`, `dv.n` and `dv.r` are the x, y and z arrays.

## `iz.v(LBuffer;I)V` is the decoder

| Opcode | Offsets | What the code stores |
| --- | --- | --- |
| 113 | 1538 to 1549 | `bp = readByte() * 1832832195`. The getter's multiplier is its inverse modulo 2^32, so `ambient` is the signed byte. |
| 114 | 1576 to 1587 | `bi = readByte() * 1024003749`. That is 5 times the inverse of the getter's multiplier, so `contrast` is the signed byte times 5. |

RuneLite's JSON of snapshot 430 holds contrasts such as 7, 12 and 33, which are not multiples of 5. So that JSON holds the byte, and the client holds 5 times the byte.

## Conclusion

The client lights the inventory model of an item with `(ambient + 64, contrast + 768, -50, -10, -50)`. For an item with no opcode 113 or 114 this is `(64, 768, -50, -10, -50)`, the values that the icon harness of [model-formats.md](model-formats.md) already uses.
