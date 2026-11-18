# Named source of the revision 149 client

`build.sh` turns `gamepack-149.jar` into a Java source tree with real class, field and method names. Run it as:

```bash
scripts/named-client/build.sh --gamepack <path to gamepack-149.jar>
```

The May 2018 RuneLite tree (revision 170) holds a decompiled client whose members carry `@ObfuscatedName`. RuneLite's deobfuscator and `UpdateMappings` carry those names onto another revision. The evidence for how many names arrive is in [docs/research/runelite-name-mapping.md](../../docs/research/runelite-name-mapping.md).

## What the script needs

JDK 21, Maven, perl and `vineflower` (`brew install vineflower`) on the machine. The script reads three environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `NAMED_CLIENT_DIR` | `~/git/osrs-149-named` | The output folder. It holds `mapped-osrs-149.jar`, `names-osrs-149.tsv`, `map-osrs-149.log`, `src/` and `work/`. |
| `RUNELITE_TREE` | `~/git/runelite-master` | The read-only RuneLite tree. The script copies it into `work/runelite` and patches the copy. |
| `RUNELITE_JDK` | the `java` on the PATH | A JDK 21 home. The script stops when the Java in use is not 21. |

`names-osrs-149.tsv` has one row per class, field and method that has `@ObfuscatedName`: kind, obfuscated class, obfuscated member, descriptor and mapped name. `Dump.java` writes it. It runs as a single-file program on the deobfuscator classpath, which has ASM.

The script writes `docs/research/client-names.tsv` only when that file does not exist. After that, sessions edit it by hand.

## Why each patch

The tree does not build with Maven 3.10 on JDK 21 or 25 as it is. Evidence: the build errors on 2026-11-18.

- Lombok 1.16.20 fails on JDK 21 and newer. The build passes `-Dlombok.version=1.18.38`.
- The root `pom.xml` lists `http://` repositories, which Maven 3.10 blocks. `net.runelite:fernflower:20171017` is only on repo.runelite.net, which answers over https.
- `netscape.javascript.JSObject.getWindow(Applet)` is gone from JDK 21. The script replaces it with `null` in `Client`, `class41` and `class178`. It is browser code that mapping never runs.
- The deobfuscator's test dependencies `net.runelite.rs:client` and `vanilla` cannot be resolved. The script removes them.
- `UpdateMappings` exits when its annotation checker finds errors. From 170 to 149 it finds 48, so the script logs them in `map-osrs-149.log` and goes on. The errors flag 170 members that the checker could not confirm in 149. Some names are then absent from the TSV (`xteaKeys`), and others are in it on another class (`mapRegions` on `as`). Check a flagged name against `javap` before you use it.

When a patch does not apply, the script deletes its copy and stops with the name of the patch.

## Decompile step

`vineflower` reads only the classes of the root package. `net/runelite/rs/Opcodes.class` in the mapped jar is a 126-byte stub that makes vineflower stop with an `IndexOutOfBoundsException`. Evidence: the failure on 2026-11-18, and the same failure on the class alone.

## Runs can differ

Two runs on the same machine gave the same `names-osrs-149.tsv` row for row on 2026-11-18. A run on another day with JDK 21.0.13 differed from a run with JDK 21.0.12 in two rows: `moveTowardZoomTarget` moved from `ds.aw` to `ke.v`, and `shutdown` took `ds.aw`. The cause is a guess: the mapper picks between equal candidates, and the order of that choice depends on something other than the inputs. Check a name that matters against `javap`.
