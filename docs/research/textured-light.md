# Textured faces and alpha 254 and 255 in gamepack 149

Checked on 2026-11-22 with `javap -p -c` on the revision 149 gamepack (SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`, the jar that [item-light.md](item-light.md) names). The offsets below are bytecode offsets of the obfuscated classes. The real names come from [client-names.tsv](client-names.tsv), with the rows that this note adds. The control flow of every method is scrambled with `goto`, so each table follows the jumps, not the order of the offsets.

## Which copies the client uses

`dv` has five methods of the shape `(IIIII)Lej;`: `ae`, `cu`, `cy`, `cn` and `ck`. Only `dv.ae` has callers (56 call sites in `em`, `hu`, `hy`, `ii`, `im`, `iz` and `ip`). The other four have no caller in the jar. Evidence.

`hu` has three copies of the player model method: `l(jg, int, jg, int, byte)`, `au` and `ak`. Only `hu.l` has callers (4 call sites). Evidence. This note uses `dv.ae`, `dv.z` and `hu.l` only.

## `dv.z()V` is `computeNormals`

| Offsets | What the code does |
| --- | --- |
| 0 to 4, 285 | If `am` (`normals`) is not null, return. |
| 37 to 89 | `am = new eq[a]` and one new `eq` (`VertexNormal`) for each vertex. |
| 704, 440, 135, 773, 210 | For face i: vertices a = `e[i]`, b = `l[i]`, c = `s[i]`. Edges b - a and c - a from `j`, `n`, `r` (x, y, z). |
| 300, 256 | `nx = by*cz - cy*bz`, `ny = bz*cx - cz*bx`, `nz = bx*cy - cx*by`. |
| 415, 535, 105, 316, 62, 618 to 599 | While a component is above 8192 or below -8192, shift all three right by 1. |
| 10 to 34, 340, 409 | `length = (int) Math.sqrt(nx*nx + ny*ny + nz*nz)`, and 1 when it is 0 or less. |
| 286, 426, 450 | Each component becomes `component * 256 / length` (Java division). |
| 662, 470, 464 | The kind is `w[i]` (`faceRenderType`), or 0 when `w` is null. The alpha `m` is not read here. |
| 478, 51 to 685 | Kind 0: add the normal to `am[a]`, `am[b]` and `am[c]`, and add 1 to the magnitude of each. |
| 688 to 764 | Kind 1: `ar[i] = new eu(nx, ny, nz)` (`faceNormals`). |
| 688 | Any other kind adds nothing. |

The write multipliers are the inverses of the read multipliers in `dv.ae`: for example `-723763511 * -1493288071 = 1` mod 2^32 for `eq.a`. I checked all seven pairs (`eq.a`, `eq.j`, `eq.n`, `eq.r`, `eu.a`, `eu.j`, `eu.n`). So the fields hold the plain values. Evidence.

Conclusion: this is the arithmetic of `_face_normal` and of the first loop of `_light` in `src/rsps_toolkit/formats/lighting.py`. Evidence.

## `dv.ae(IIIII)Lej;` is `ModelData.light(ambient, contrast, x, y, z)`

Locals: 1 ambient, 2 contrast, 3 x, 4 y, 5 z, 7 the divisor, 9 the face, 10 the kind, 11 the alpha, 12 the texture, 14 the light, 15 the colour.

### Set-up

| Offsets | What the code does |
| --- | --- |
| 0 to 1 | `this.z()` (`computeNormals`). |
| 68 to 88 | `magnitude = (int) Math.sqrt(x*x + y*y + z*z)`. |
| 25 to 32 | `divisor = contrast * magnitude >> 8`. |
| 34 to 62, 1592 to 1600 | `new ej`, and `ej.g`, `ej.k`, `ej.t` = `new int[faceCount]`. |

### Texture coordinates (before the face loop)

| Offsets | What the code does |
| --- | --- |
| 1385 to 109 | Only when `dv.c` (the count of texture triangles) is above 0 and `u` (`textureCoords`) is not null. Otherwise `ej.x`, `ej.i`, `ej.d`, `ej.b` stay null. |
| 112 to 164, 1618 | Count how many faces use each texture triangle (`u[face] & 255`, -1 is none). |
| 167 to 233 | `ej.z` = the number of texture triangles that are used and have `o[t] == 0` (`textureRenderTypes`, so a plain P, M, N triangle). |
| 236 to 269 | `ej.i`, `ej.d`, `ej.b` = `new int[ej.z]`. |
| 287 to 392, 517 | For each such triangle in order: `ej.i = x[t] & 0xFFFF`, `ej.d = f[t] & 0xFFFF`, `ej.b = h[t] & 0xFFFF` (`texTriangleX`, `Y`, `Z`: the P, M, N vertex indices). A triangle that is not used or has another render type gets -1 in the remap table. |
| 405 to 560 | `ej.x = new byte[faceCount]`. `ej.x[face]` = the new index of its triangle, or -1. |

### The face loop

| Offsets | What the code does |
| --- | --- |
| 1192, 860, 1706 | kind = `w[face]`, or 0 when `w` is null. |
| 563, 585, 1488 | alpha = `m[face]` as a signed byte, or 0 when `m` is null. |
| 745, 619, 1412 | texture = `k[face]` (`faceTextures`), or -1 when `k` is null. |
| 628 to 638 | alpha -2 (254): kind = 3. |
| 719, 659 | alpha -1 (255): kind = 2. |
| 176 | texture -1: untextured branch (675). Else textured branch (1219). |

Untextured face (colour = `g[face] & 0xFFFF`, `faceColor`, at 146):

| Kind | Offsets | What `ej` stores |
| --- | --- | --- |
| 0 | 146 to 382 | For each corner: `light = ambient + (x*n.x + y*n.y + z*n.z) / (divisor * n.magnitude)`, with n the vertex normal. `g`, `k`, `t` = `dv.au(colour, light)`. |
| 1 | 1036 to 1126, 1680 | `light = ambient + (x*f.x + y*f.y + z*f.z) / (divisor + divisor / 2)`, with f = `ar[face]`. `g = dv.au(colour, light)`, `t = -1`. `k` is not written, so it stays 0. |
| 3 | 1129, 1022 to 102 | `g = 128`, `t = -1`. `k` stays 0. |
| 2 or any other | 1129, 538 | `t = -2`. `g` and `k` stay 0. |

Textured face (no colour is read):

| Kind | Offsets | What `ej` stores |
| --- | --- | --- |
| 0 | 1219 to 7, 356, 1138 to 1615 | The same three lights as the untextured kind 0. `g`, `k`, `t` = `dv.ak(light)`. |
| 1 | 1606, 1010, 1244 to 1654 | The same flat light. `g = dv.ak(light)`, `t = -1`. `k` stays 0. |
| 2, 3 or any other | 1606, 1657 | `t = -2`. `g` and `k` stay 0. So a textured face with alpha 254 is hidden, not given 128. |

The vertex normal is `aw[v]` when the array `aw` and that entry are not null, else `am[v]` (for example 1234, 1786, 728, 1311). `aw` is written only by the copy constructor `dv(dv, boolean, boolean, boolean, boolean)`, by `be`, `i`, `bx` and by the static methods `ai`, `cx`, `cs`, `ct` (signature `(dv, dv, int, int, int, boolean)`). `hu.l` and `iz.p` call none of them. Evidence. That `aw` is the shared-normal table that scenery merging fills is a Guess.

### The two clamps

| Method | Offsets | What it does |
| --- | --- | --- |
| `dv.au(II)I` | 0 to 42 | `l = light * (hsl & 127) >> 7`, clamped to 2..126, returns `(hsl & 0xFF80) + l`. For an untextured face. |
| `dv.ak(I)I` | 0 to 24 | Returns `light` clamped to 2..126. For a textured face. |

### What the lit `ej` keeps

| Offsets | Field of `ej` | From `dv` |
| --- | --- | --- |
| 883 to 1763 | `v`, `e`, `l`, `s` (vertex count and x, y, z) | `a`, `j`, `n`, `r` |
| 1730 to 1763 | `w`, `p`, `m`, `u` (face count and the three vertex indices) | `v`, `e`, `l`, `s` |
| 197 to 203 | `c` (priorities) | `p` |
| 913 to 919 | `o` (alphas, as stored, 254 and 255 included) | `m` |
| 1804 to 1810 | `h` (model priority) | `t` |
| 1813 to 1828 | `q`, `y` (vertex and face groups) | `ak`, `ap` |
| 1831 to 1837 | `f` (`faceTextures`, the texture id of each face, -1 is none) | `k` |
| above | `g`, `k`, `t` (the three corner values), `x`, `z`, `i`, `d`, `b` | computed |

`ej` does not keep `faceColor`. For a textured face `g`, `k`, `t` hold light values of 2 to 126, not HSL. Evidence. `dv.s()` (`computeAnimationTables`) runs after the loop (1673).

Conclusion: every branch of `_light` in `lighting.py` matches `dv.ae` in gamepack 149, including the textured branches, the forced kinds 3 and 2 for alpha 254 and 255, the value 128 for an untextured kind 3, the hidden row (0, 0, -2) and the 2..126 clamp of `method2676`. Evidence. Two small notes: `lighting.py` does not model `aw`, and it computes `divisor // 2` with floor division where Java truncates. They differ only for a negative divisor, which needs a negative contrast. Evidence for the arithmetic, Guess that no caller passes such a contrast.

## Drawing a face

The call graph: the draw methods of `ej` call `ej.ae(ZZZI)V`, which calls `ej.au(I)V` for each face. `ej.au` calls `ej.ak(I)V` for a face that crosses the near plane. Evidence.

### `ej.ae(ZZZI)V` skips hidden faces

Offsets 104 to 116 and 315 to 328: when `t[face] == -2`, jump to the next face (1036 and 1882 are `iinc` of the face counter). So a face of kind 2, and a textured face of kind 3, is never drawn. Evidence.

### `ej.au(I)V`

| Offsets | What the code does |
| --- | --- |
| 0 to 8, 551 | If `az[face]` is set, call `ej.ak(face)` (the clipped path) and return. |
| 46 to 51 | `ep.a` (`rasterClipEnable`) = `ad[face]`. |
| 54 to 78 | `ep.v` (`rasterAlpha`) = `o[face] & 255`, or 0 when `o` is null. This runs for every face, textured or not. |
| 81 to 88, 311 to 321 | If `f` is null or `f[face] == -1`: untextured (376). |
| 11 to 18, 422 to 432, 337 to 403 | Texture triangle: if `x` is null or `x[face] == -1`, P, M, N are the three vertices of the face. |
| 407 to 373 | Else P, M, N = `i[x[face]]`, `d[x[face]]`, `b[x[face]]`. |
| 324 to 331, 435 to 545 | `t[face] != -1`: `ep.k(..., g, k, t, ..., f[face])` (`rasterTextureAffine`) with the three corner lights. |
| 91 to 201 | `t[face] == -1`: `ep.k(..., g, g, g, ..., f[face])`: a flat textured face uses `g` at all three corners. |
| 376 to 386, 207 to 257 | Untextured, `t != -1`: `ep.p(..., g, k, t)` (`rasterGouraud`). |
| 263 to 305 | Untextured, `t == -1`: `ep.u(..., bt[g])` (`rasterFlat`). `ej.bt` is `ep.i` (`colorPalette`), set in the static initialiser of `ej`. |

So an untextured kind 3 face (`g = 128`, `t = -1`) is drawn flat in `ep.i[128]`, the palette colour of HSL 128 (hue 0, saturation 1, lightness 0, near black), with the face alpha. Evidence. `ej.ak` also sets `ep.v` from `o` (1172, 2214) and draws textured faces with `ep.k` (399, 560, 1642, 1735, 2198, 2339). Evidence.

### `ep.k` (`rasterTextureAffine`) and `ep.c` (`rasterTextureAffineLine`)

| Offsets | What the code does |
| --- | --- |
| `ep.k` 0 to 12 | `texels = ep.d.j(texture)` (`textureLoader.load`). |
| `ep.k` 27 to 41, 2271 to 2303 | When `texels` is null: `avg = ep.d.n(texture)` (`getAverageTextureRGB`), then `ep.p(..., ep.h(avg, g), ep.h(avg, k), ep.h(avg, t))`. `ep.h` is the same arithmetic as `dv.au` (offsets 0 to 42 of `ep.h`). So a texture that is not loaded is drawn as a Gouraud face of its average HSL colour lit by the light values. |
| `ep.k` 448 to 460 | `ep.j = ep.d.r(texture)`. `da.r` returns `eo.e`, a flag of the `Texture`. |
| `ep.k` 546 to 559 | The shade starts at `light << 9` (plus a step term). |
| `ep.c` 9 to 14 | `s = shade >> 8`, so `s` is about `2 * light`. |
| `ep.c` 40 to 67 and 480 to 510 | `pixel = ((texel & 0xFF00FF) * s & 0xFF00FF00) + ((texel & 0xFF00) * s & 0xFF0000) >> 8`. |
| `ep.c` 456, 462 to 510 | When `ep.j` is true, every texel is written. |
| `ep.c` 2968, 2976 to 2990 | When `ep.j` is false, a texel of value 0 is skipped (the pixel stays). |

Each colour channel becomes `texel * s / 256`, about `texel * light / 128`. A light value of 126 gives about 0.98 of the texel and 64 gives 0.5. Evidence for the arithmetic. The name and the decoder of `eo.e` were not checked. That it marks a texture without transparent texels is a Guess.

`ep.v` (`rasterAlpha`) is read only by `ep.g` (`rasterFlatLine`), `ep.m` (`rasterGouraudLine`) and their duplicate copies (`ao`, `al`, `ab`, `at`, `ah`, `ay`, `ac`). It is not read by `ep.k`, `ep.c`, `ep.o` or `ep.x`. Evidence. So the face alpha is not applied to a textured face, as in 2018, except in the fallback above, where `ep.p` calls `ep.m` and the alpha applies. `ep.p` calls only `ep.m`, and `ep.u` calls only `ep.g`. Evidence.

`ep.g` offsets 171 to 177: when `ep.v == 254`, the line does `pixel[i] = pixel[i + 1]` (200 to 208) and does not write the face colour. So an untextured face with alpha 254 (kind 3, colour 128) leaves the image as it was, shifted by at most one pixel. Other non-zero alphas blend (9 to 36). `ep.m` has no 254 case. Evidence. Alpha 254 therefore reaches `ep.g` only for an untextured face, because the light makes every alpha-254 face flat (`t = -1`) or hidden.

## The player body: `hu.l(jg, int, jg, int, byte)Lej;`

| Offsets | What the code does |
| --- | --- |
| 928 | `it.e` (`KitDefinition.getModelData`) for a body kit. `it.e` calls `dv.o` (`retexture`) at its offset 265. |
| 779 | `iz.k` (`ItemComposition.getWornModelData`) for a worn item. `iz.k` calls `dv.o` at its offset 28 with `iz.f` and `iz.h`. |
| 820 to 831 | `new dv(parts, count)`: the join. It allocates `k` (`faceTextures`), `u` (`textureCoords`), `o`, `x`, `f`, `h` (offsets 87, 577, 605, 824, 623, 1201 of the constructor). |
| 352, 858 | `dv.c` (`recolor`) for the body colours. |
| 279 to 292 | `dv.ae(64, 850, -30, -50, -30)`. |

The only methods of `dv` that `hu.l` calls are the constructor, `c` and `ae`. No call removes or changes textures between the join and the light. Evidence. So the player model goes through the same `dv.ae`, and its textured faces keep their texture and get light values. Evidence.

## Data check: snapshot 430 dump

From `<data workspace>/exports/osrs/openrs2-430/dump/items/ItemDefinitions.json` (RuneLite JSON):

- Fire cape (6570): inventory model 9631, male worn model 9638, female worn model 9640, no other worn models. No recolours and no retextures. Resize 128, ambient 0, contrast 0.
- Vial of water (227): inventory model 2789, resize 128 on all axes, ambient 0, contrast 0, recolour 61 to -23206 (42330).

From `dump/models_obj` (OBJ and MTL files, material names `hsl<colour>_a<alpha>` or `tex<id>`):

- 2789 has 104 faces. Faces 102 and 103 use `hsl38119_a254`: alpha 254. No face has alpha 255. The other faces have alpha 0 (22 faces), 128 (48 faces) and 32 (32 faces, colour 61). The face numbers are the order of the OBJ file. That it is the cache order is a Guess.
- 9638 and 9640 (63 faces each) use texture 40 on 24 faces (OBJ faces 14 to 37). The other faces are colours 6032, 924 and 0. 9631 (35 faces) uses texture 40 on 25 faces.

## Conclusion

In gamepack 149, `dv.ae` lights textured faces and faces of alpha 254 and 255 the way `_light` in `lighting.py` does, for the player body (`hu.l`, light `(64, 850, -30, -50, -30)`) and for the inventory model (`iz.p`, see [item-light.md](item-light.md)). A textured face stores light values of 2 to 126. The rasterizer multiplies each texel channel by about `light / 128` and does not apply the face alpha. A face of alpha 255, and a textured face of alpha 254, is not drawn. An untextured face of alpha 254 is drawn with colour 128 and alpha 254, and `ep.g` leaves the pixels as they were.
