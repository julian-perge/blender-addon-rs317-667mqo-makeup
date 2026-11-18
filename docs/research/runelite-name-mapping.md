# RuneLite names for gamepack 149

Measured on 2026-11-18. Evidence for the decision in
[named-client-source](../ideas/named-client-source.md): stay on revision 149 and take real names from RuneLite's
mapper. This note is the handoff for the next step, the named 149 source tree.

## Where the scripts are

The scripts live in the owner's notes, not in this repo: `<vault>/Tools/runelite-mapping/`. The note
`runelite-mapping.md` in that folder explains each script and each patch.

| Script | What it does |
| --- | --- |
| `map-names.fish` | Clones `<RuneLite May 2018 tree>`, patches it to build on JDK 21, then runs RuneLite's `Deob` and `UpdateMappings` for each gamepack. Writes `mapped-<name>.jar` and `names-<name>.tsv`. |
| `Dump.java` | Prints the `@ObfuscatedName` rows of a mapped jar: kind, obfuscated class, obfuscated member, descriptor, mapped name. `map-names.fish` runs it. |
| `check170.py` | Checks the tree's annotations against `osrs-170.jar`. Only needed for a new copy of the tree. |
| `relevant.txt` | The 25 tree classes that this repo cites. |

Run:

```fish
<vault>/Tools/runelite-mapping/map-names.fish <scratch folder> <path to gamepack-149.jar>
```

A second run on 2026-11-18 gave the same `names-osrs-149.tsv` as the first, row for row, in 35 seconds.

## What the output holds

- `mapped-osrs-149.jar`: gamepack 149 after RuneLite's deobfuscator, with the mapper's names applied. Each class and
  member keeps its 149 obfuscated name in an `@ObfuscatedName` annotation, so the next step can decompile it and
  still find `dv.ae`.
- `names-osrs-149.tsv`: 4,691 rows after the header. Rows whose mapped name is not a placeholder (`classNNN`,
  `fieldNNNN`, `methodNNNN`, `vmethodNNNN`) are the seed for the planned `names.tsv`. They number 2,067: 165 classes,
  1,380 fields and 522 methods.
- `map-osrs-149.log`: 48 annotation checker errors. 38 are "Missing IMPORTED field" (the mapper found no 149 member
  for a 170 field, such as `class58.xteaKeys`). 10 are "No other class ... which contains imported field" (such as
  `Name.name`). Some of these names are absent from the TSV (`xteaKeys`). Others are in it on another class
  (`mapRegions` is on `as`). Check a flagged name against `javap` before you use it.

## Result

| Target | Classes | Fields | Methods |
| --- | --- | --- | --- |
| 170 (the tree's own revision) | 186 | 1,487 | 585 |
| 149 | 165 (89%) | 1,380 (93%) | 522 (89%) |

On the 25 cited classes, 149 gets 415 real names and 170 gets 426. Every hand pairing in
[osrs-149-animation](osrs-149-animation.md), [deobfuscation-value](deobfuscation-value.md) and
[weapon-stance-sets](weapon-stance-sets.md) agrees with the mapper. `if` is `IndexDataBase` in the 2018 tree, the
class that the notes call `AbstractArchive`.

## Next step

Decompile `mapped-osrs-149.jar` with Vineflower into a git-ignored folder, and build the lookup in the one-pager.
The first open question there is still where that folder lives, so that every worktree reads the same copy.
