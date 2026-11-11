# Gate 0 independent client source findings

Investigated November 6, 2026 with the Matt Pocock research skill. This is reference investigation only. No product code, fixture expectations or rasterizer patch was changed.

## Result

- An independently archived OSRS revision-149 client is identified by its actual initialization and handshake bytecode, beyond its filename or a 2017 date.
- Its model conversion retains only referenced type-0 texture triangles. Other texture records receive mapping index -1, and the renderer uses own-face mapping. This confirms the relevant May-2018 behavior in the identified revision-149 artifact.
- Its alpha-254 flat span performs the same incremented next-pixel read that fails in RuneLite cache 1.13.6. The reference client supplies no replacement value for a read past the framebuffer. A corrected last pixel remains a product decision, not a discovered reference pixel.

## Artifact identity and provenance limits

Primary artifact: [runetech/osrs-gamepacks, pinned osrs-149.jar](https://github.com/runetech/osrs-gamepacks/blob/2e92962075cfbc0df227cc783c37633d5e92f297/gamepacks/osrs-149.jar).

| Identity | Value |
| --- | --- |
| Repository commit used for download | `2e92962075cfbc0df227cc783c37633d5e92f297` |
| Git blob SHA-1 | `28a34a60c68a2518eb959b79f59be1d3fe813524` |
| Download size | 1,919,493 bytes |
| Observed SHA-256 | `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd` |
| Local research copy | `/private/tmp/osrs149-reference-gamepack.jar` |
| Addition commit | [`063bbc260a6f764b91e1fd2a161bc764a54ebd45`](https://github.com/runetech/osrs-gamepacks/commit/063bbc260a6f764b91e1fd2a161bc764a54ebd45) |
| Addition commit metadata | `2017-07-06T19:20:30Z`, message `Add osrs-149.jar` |
| ZIP member timestamps | July 6, 2017, 11:20, as printed by local `unzip -l` |

The archive's [pinned README](https://github.com/runetech/osrs-gamepacks/blob/2e92962075cfbc0df227cc783c37633d5e92f297/README.md) claims untouched gamepacks and describes compilation dates. These are archive claims. ZIP timestamps and Git commit dates do not prove publication time, authenticity, or an exact association to OpenRS2 snapshot 430. Signature files `META-INF/JAGEXLTD.SF` and `META-INF/JAGEXLTD.RSA` are present; certificate identity and signature verification were not performed. This investigation establishes a specifically identified revision-149 implementation, not an exact byte-for-byte client/cache pairing with snapshot 430.

GitHub MCP returned the blob identity and size before download. REA `open_binary` independently recognized a ZIP archive with the same SHA-256; the REA session was closed. Code observations below use existing `javap 25.0.4`, not a decompiler or a newly built client. No client was executed.

## Internal revision evidence

All offsets below are bytecode offsets inside the named method, not line numbers in a reconstructed Java source.

`client` contains initialization sequences passing `765`, `503`, `149` to `ai(IIII)V` (offsets 2120-2132). More decisively, its network initialization allocates `new fe(5)`, writes opcode 15 via `fe.j(II)V`, writes integer 149 via `fe.v(IS)V`, then passes exactly five bytes to `fq.v([BIII)V` (offsets 315-355). Another login write passes 149 through the inherited `ff.v(IS)V` (offsets 1047-1053 in the corresponding login method).

`fe.v(int, short)` writes the supplied integer in big-endian order. Its control flow writes shifts 24, 16, 8, then the low byte (offsets 0-27, 85-112, 31-57, 58-81). Thus the observed network sequence includes the revision integer, rather than merely an unrelated numeric 149. This identifies revision 149 independently of the artifact name.

## Mapping behavior in revision 149

The model-data class is `dv`; the lit drawable model is `ej`. Names below are artifact-local obfuscated identifiers. Their correspondence is established by decoder, conversion and renderer data flow, not by matching an identifier from another revision.

1. `dv(byte[])` selects `j(byte[])` for the final `FF FF` marker (offsets 23-64); other input goes to `r(byte[])`.
2. `dv.j(byte[])` stores the initial signed texture-record byte in `dv.o` (offsets 1613-1627), and later reads that byte unsigned while selecting the texture-record decode path (offsets 2019-2032). `dv.u` stores per-face texture-coordinate indices (offsets 1632-1665). The triangle arrays retained downstream are `dv.x`, `dv.f`, `dv.h`.
3. `dv.ae(IIIII)Lej;` counts per-record face references through `dv.u` (offsets 123-164 and 1618-1635). The retained-record count increases only when reference count is positive and `dv.o[index] == 0` (offsets 185-233 and 872-880).
4. The same conversion copies `dv.x/f/h` into `ej.i/d/b` only under that condition (offsets 287-383 and 517-535). Every other record receives remap value -1 (offsets 386-391). Per-face retained mapping `ej.x` receives that remap, or -1 when the source face has no mapping (offsets 428-461 and 551-559).
5. `ej.au(I)V` reads face corner indices from `ej.p/m/u` into locals 2/3/4. When `ej.x` is null or its face entry equals -1, it copies those face corners into mapping locals 5/6/7 (offsets 11-18, 422-432, 337-340, 32-35, 399-403). Otherwise it indexes retained arrays `ej.i/d/b` (offsets 407-419 and 346-371). Both textured shading branches pass the selected mapping corners to `ep.k` (offsets 91-201 and 435 onward).
6. A real definition-to-model path in `iz` invokes `dv.ae` with the characteristic item lighting inputs `64 + ambient`, `768 + contrast`, `-50`, `-10`, `-50` (offsets 511-542). Thus the conversion is used by client code; it is not only a dormant duplicate method.

This is static evidence for own-face mapping of non-type-0 references in this revision-149 implementation. The additional records must still be preserved as source data. Their existence does not establish cylindrical or cube projection in this client. It does not justify using RuneLite 1.13.6 UV results as the complex-record oracle.

The artifact includes duplicate obfuscated methods with altered constants: for example `dv.cu` and `ej.cy`. Do not substitute those for the verified `dv.ae` / `ej.au` path when recording expected behavior.

Visibility evidence: stored face render byte 2 leads to `ej.t[face] = -2` in `dv.ae` when alpha has not overridden that type. The untextured branch handles effective types 0, 1 and 3 separately and assigns -2 otherwise (offsets 675-680, 1036-1041, 1129-1135, 538-547); the textured branch handles types 0 and 1 and assigns -2 otherwise (offsets 1219-1223, 1606 onward, 1657-1666). Source render byte is loaded from `dv.w` at 860-867. The render loop `ej.ae(ZZZI)V` tests `ej.t[face] == -2` at offsets 104-116 and skips that face. Alpha bytes -1 and -2 override effective render type inside `dv.ae` (offsets 628-638, 719-725, 659-662). Consequently a fixture visibility contract must include those overrides and texture presence; do not generalize one Boolean flat-shading flag to all stored render bytes.

## Alpha-254 icon edge

Local RuneLite source artifact:

| Source | SHA-256 |
| --- | --- |
| `~/.m2/repository/net/runelite/cache/1.13.6/cache-1.13.6-sources.jar` | `c75985f35c891fc1dcbe9ee978032878d5e4b1c8a9b8dcf0496c498bb6b8b973` |
| Its `net/runelite/cache/item/Graphics3D.java` entry | `eaa644ba85f7a25b441cc4c26d33b920d63386fdac94f601af00e334d4d3453f` |

`Graphics3D.method2842` has an alpha-254 special case whose grouped and remainder loops both execute `var0[var1++] = var0[var1]`. Java evaluates the left array index before the right expression, so this copies the next pixel into the previous pixel. At destination index 1151 in a 1152-element buffer, its right-side read is index 1152 and throws before storing the destination. This explains the reported item-8283 failure; this research did not rerun its full resource closure.

The independent revision-149 implementation has the same behavior in the active flat span `ep.g([IIIIII)V`:

- `ep.v` is alpha: `ej.au` supplies `faceAlpha & 255` to it at offsets 68-78.
- `ep.g` checks `ep.v == 254` at offsets 171-177.
- Its four-pixel loop copies a next pixel at offsets 537-545, 200-208, 237-245 and 215-223. Each sequence saves the destination index, increments local 1, then loads array element at incremented local 1.
- Its remainder loop performs the identical read at offsets 249-257.
- Its clipping bounds the horizontal end to `ep.t` (offsets 55-63 and 528-533), but does not reserve a trailing framebuffer element. There is no last-element correction on the alpha-254 path.
- `ep.u(IIIIIII)V` calls `ep.g` repeatedly to fill flat spans. The duplicate methods `ep.ao/ay/ac` are unnecessary for this claim.

The reference therefore confirms the problematic operation, not a corrected pixel. A read beyond a Java array has a defined exception outcome; it has no color value to copy. We cannot freeze a claimed game-reference final pixel of zero, the previous destination value, or a clamped neighbor from this evidence.

Concrete decision before the icon patch: choose a documented repair rule for the missing neighbor. For example, skipping only that final out-of-bounds copy preserves the pixel already there; supplying a zero guard element makes it zero at that operation. Those are distinct policies whose final icon effect must be measured through outlines/shadows and later compositing. Neither is currently established as the original client result. Keeping a failing reference trace while accepting a separately named repair policy avoids presenting the chosen policy as source-correct game behavior.

## Reproduce the investigation

These commands download only the 1.9 MB client reference and write temporary inspection text. `/tmp` resolves to `/private/tmp` on this machine. They do not install, build or execute the client.

```bash
curl -fLsS https://raw.githubusercontent.com/runetech/osrs-gamepacks/2e92962075cfbc0df227cc783c37633d5e92f297/gamepacks/osrs-149.jar -o /private/tmp/osrs149-reference-gamepack.jar
shasum -a 256 /private/tmp/osrs149-reference-gamepack.jar
git hash-object /private/tmp/osrs149-reference-gamepack.jar
unzip -l /private/tmp/osrs149-reference-gamepack.jar
javap -version
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p client > /private/tmp/osrs149-reference-client.javap
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p fe > /private/tmp/osrs149-reference-fe.javap
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p dv > /private/tmp/osrs149-reference-dv.javap
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p ej > /private/tmp/osrs149-reference-ej.javap
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p ep > /private/tmp/osrs149-reference-ep.javap
javap -classpath /private/tmp/osrs149-reference-gamepack.jar -c -p iz > /private/tmp/osrs149-reference-iz.javap
unzip -p ~/.m2/repository/net/runelite/cache/1.13.6/cache-1.13.6-sources.jar net/runelite/cache/item/Graphics3D.java | shasum -a 256
```

## Search boundary and remaining work

GitHub MCP repository searches for `osrs 149` and `runescape gamepacks` located the archive. `Rune-Status/scape-tools-kotlin-osrs` describes a revision-149 reverse-engineering project, but its inspected root/data/lib were server-oriented and did not supply a matching client source. A bounded `runelite/runelite` history query for `runescape-client/src/main/java/Client.java` between July 1 and July 21, 2017 returned no commits. These negative searches are not claims that no other source exists.

The local May-2018 source remains useful corroboration, but is no longer the only evidence for mapping behavior. Its relevant source SHA-256 identities are `a5e0adefc71bad3fb8a9b6f2032de8f082351330e9594e6c373da2bd2cda657c` for `ModelData.java`, `b2365181c22b5823114d541e7870f206b4ad9138ff2b4fc4e4b1ffee2d2f3857` for `Model.java`, and `37275ec18ccb49be69b5796443528c6fbfbe51bf7f1441e48a1e89a6ecadf3c0` for `Graphics3D.java`, all beneath `<RuneLite May 2018 tree>/runescape-client/src/main/java/`. That directory has no Git metadata, so these are local file identities, not a verified upstream commit pin.

Still required for Gate 0: executable reference recording across the selected fixture closure, complete visibility cases including alpha overrides, exact raw field/tail preservation evidence, and a user-approved icon repair policy if the milestone requires successful icon output. This research does not claim a complete reference replay or an expected successful icon hash.
