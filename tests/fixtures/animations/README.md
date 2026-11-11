# Revision-1 animation references

Recorded November 6, 2026 from the February 22, 2013 cache, OpenRS2 archive 241. These are outside-source expectations for future animation tests, not output from RSPS Toolkit's evaluator.

## Sources and independence

`../AnimationReference.java` compiles against the unmodified [revision-1 client](https://github.com/Shadowrs/osrs-refactor-revision-1/tree/b0fdcde9c8bbbc75cd2ea4a3cd87461d1a62641b). The client's own `Looks`, model, sequence, frame and frame-map classes perform assembly, decoding and transforms. RuneLite cache 1.13.6 supplies only cache-container/file access; Gson serializes the result. No new toolkit pose code or animation dumper normalization code is used.

The harness can also replay the decompressed `2013/raw/` payloads directly. In that mode RuneLite does not unpack a cache. Packed-cache and raw-payload runs produced byte-identical `reference.json` files after canonical key ordering. The client source compiled with `javac --release 8`; the harness ran with Java 25.0.4. No Applet, game network connection or Blender process is launched.

`source.json` records original cache hashes, client commit and critical source hashes, harness hash, reference hash and the existing shaded dumper JAR hash. It also records the two existing-dump PNG hashes/dimensions. The original cache was never opened by the reference: a temporary copy was used, and its relevant file hashes still match the original after both runs.

The name-to-ID source is RuneLite's generated [AnimationID](https://github.com/runelite/runelite/blob/8f2aca162a5ddd3765dd0166aea5de86522bc785/runelite-api/src/main/java/net/runelite/api/gameval/AnimationID.java): `SLAYER_ABYSSAL_WHIP_ATTACK = 1658`, distinct from its special attack. That is a later generated name source, not a recovered 2013 server. The local 2013 sequence/frame/model content is independently checked by this fixture; no claim is made that the client itself selects an attack based on item 4151.

## What is recorded

- `reference.json`: all 15 poses of sequence 1658, all 364 assembled vertices and 652 face alphas per pose, rest topology/labels/colors, the eight source parts and exact correspondence back to assembled vertices, sequence/frame/map data, and both actor-clock traces.
- `raw/<index>/<group>/<file>.dat`: 305 exact decompressed payloads actually requested by the client. Full frame group 300 is present because the original client builds the entire frame group. This is a compact dependency closure, not the full cache.
- `textures/8.png` and `34.png`: existing dumper PNGs from the same 2013 dump. They are display resources, not an assertion of pixel-identical client rasterization or lighting.
- `request.json`: explicit version-1 extraction request derived from the recorded default appearance, parts, recolors and source hashes. The opt-in dumper target consumes it.

- `bundle-manifest.json`: version-1 producer output from `osrs-cache-dumper` commit `c9fcc12` (reader `0d27b2b`, RuneLite cache 1.13.6, Java 25). Its SHA-256 is `1ad34289b442bcf35aa2775d0e8ad934576291fe943198c10a486c66dea956cb`. A fresh temporary-cache extraction produced records and resource bytes matching the client fixture exactly. This is a wire-format fixture, not a second source of game pose expectations. Tests copy the existing raw model/PNG bytes into the manifest's declared dump paths. The toolkit loader currently accepts the producer's non-interlaced 8-bit RGBA PNG encoding and refuses other encodings explicitly.

The default male equipment selected by `Looks.render(null, ...)` contains kits 18, 26, 36, 0, 33, 42 and 10. The whip replaces equipment slot 3 with item 4151, using worn model 5409. The parts' model IDs in equipment order are 5409, 292, 151, 254, 230, 176, 181 and 249. All original part vertices have an assembled correspondence. A coordinate shared across parts is animated through the client's assembled labels and pivot, not a separately calculated part pivot.

Magic Tree object 1306 selects model 7978 and no object sequence. Its texture 34 has direction 1 and speed 2; texture 8 is stationary. `Class104_Sub19.method558` was invoked on numbered pixels at 128 by 128, recording exact wrapped row samples at ticks 0, 1, 2, 63, 64 and 65. The client defaults to high-memory mode and uses 128-pixel textures; its low-memory 64-pixel path is not the selected presentation mode.

## Timing origin and arithmetic

The actor trace includes its initialization state at tick 0. This is not the first displayed sample. `client.method943` processes player updates before `Widget.method537`, which advances actors through `Class30.method144` and `Class84.method381`. `Applet_Sub1` renders afterward. Therefore `rendered_actor_clock` begins at the state after the first logic update, with `elapsed_tick = 0`.

For this clip, rendered transitions are at ticks 0, 4, 7, 9, 10, 11, 15, 17, 19, 27, 28, 30, 32, 35 and 37. The sequence ends at rendered tick 39: 780,000,000 ns at the client's 20 ms tick. The initialization trace ends at tick 40 and is retained to expose the phase distinction. Do not add that initialization tick to the displayed clip.

`Class104_Sub18_Sub16_Sub4.method817` supplies transform order and Java integer arithmetic. Pivot averages and scale divisions truncate toward zero; rotation uses the client's sine/cosine tables and signed integer shifts. Tests compare exact integer game coordinates. No floating tolerance was selected to conceal a mismatch.

The selected clip exercises transform types 0, 1, 2 and 3. Face alphas are preserved at 0 or 240; this clip does not change them. Additional `transform-cases.json` captures now exercise type-5 alpha clamping and absent face labels directly through the same client, independently of the whip clip. Texture updates are performed for textures used by the client renderer; the planned deterministic presentation clock does not simulate offscreen texture scheduling.

## Reproduce from the compact fixture

Run from the repository root with a built RuneLite-1.13.6 dumper JAR available. Use a fresh directory; do not overwrite the fixture with the output.

```bash
set -e
animation_ref_work=$(mktemp -d)
curl -L --fail https://api.github.com/repos/Shadowrs/osrs-refactor-revision-1/tarball/b0fdcde9c8bbbc75cd2ea4a3cd87461d1a62641b -o "$animation_ref_work/client.tar.gz"
mkdir "$animation_ref_work/client" "$animation_ref_work/classes"
tar -xzf "$animation_ref_work/client.tar.gz" -C "$animation_ref_work/client" --strip-components=1
javac --release 8 -d "$animation_ref_work/classes" "$animation_ref_work/client/source/"*.java
animation_ref_jar="<data workspace>/osrs-cache-dumper/target/osrs-cache-dumper.jar"
javac -cp "$animation_ref_work/classes:$animation_ref_jar" -d "$animation_ref_work/classes" tests/fixtures/AnimationReference.java
java -Djava.awt.headless=true -cp "$animation_ref_work/classes:$animation_ref_jar" AnimationReference tests/fixtures/animations/2013 "$animation_ref_work/replayed" 1658
cmp tests/fixtures/animations/2013/reference.json "$animation_ref_work/replayed/reference.json"
```

Expected: `sequence=1658 frames=15 vertices=364 faces=652 parts=8 resources=305`, then `cmp` exits 0 with no output. Java 25 warns that release 8 is obsolete; those warnings do not mean source compilation failed.

To record again from the packed cache, replace the fixture input argument with a temporary copy of `oldschool-live-en-b1-2013-02-22-00-00-00-openrs2_241`. Run the same comparison before replacing any fixture. Preserve the source hashes and primary-source provenance; never regenerate expectations from the toolkit evaluator or its future dumper normalization output.

## Additional transform references

`AnimationTransformReference.java` invokes the pinned client's `method817` with
explicit input arrays and resets its pivot before each case, as `method815` does.
Its six cases cover ordered transforms, duplicate and absent labels, pivot reset,
negative integer division, signed-32-bit overflow, rotation-table order and alpha
clamping, including initially identical alpha values in distinct face groups. These inputs are arithmetic probes, not additional in-game clips.
`transform-cases.json` records both inputs and client-produced outputs. The
fixture is never generated by the Python evaluator.

After compiling the pinned client using the command above:

```bash
javac -cp "$animation_ref_work/classes:$animation_ref_jar" -d "$animation_ref_work/classes" tests/fixtures/AnimationTransformReference.java
java -cp "$animation_ref_work/classes:$animation_ref_jar" AnimationTransformReference > "$animation_ref_work/transform-cases.json"
cmp tests/fixtures/animations/2013/transform-cases.json "$animation_ref_work/transform-cases.json"
```

Harness SHA-256: `73ab85e3316b5a0df6cdf579f056f9f2559f4e0238f74d2f7d4b8f095ed8e66b`.

Transform fixture SHA-256: `4820f3550290de38a78e8d85b187ab97486073ba621003732a24c558f8eb9b3b`.
