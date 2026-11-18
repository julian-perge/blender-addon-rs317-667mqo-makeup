# A named client source tree

## Problem Statement

How might we let a session find what the client does with a model, a kit or a sequence by searching real names in
source, instead of reading `javap -p -c` bytecode of `gamepack-149.jar` and pairing obfuscated names by hand?

## Measurements

All Evidence unless marked Guess.

- Read-type calls on the jar or on decompiled Java, 2026-11-04 to 2026-11-18: about 300, in bursts (100 on
  2026-11-14, 39 on 11-16). Counted by a transcript-count script in `<scratch folder 2026-11-18-read-reduction>`.
  The addon's own Python and tests take about 1,950 of the read-type calls, and the 2026-11-18 benchmark found that
  plain `rg` already answers those well.
- Sessions read 149 with `javap`, because no decompiler is installed
  ([osrs-149-codec-client-rules](../research/osrs-149-codec-client-rules.md)). Every 149 name pairing was made by
  hand ([deobfuscation-value](../research/deobfuscation-value.md) section 1), and that note records two slips that
  came from it.
- The `runescape-client` module of `<RuneLite May 2018 tree>` is revision 170. Of its 321 classes, 319 carry
  `@ObfuscatedName`, with 5,086 annotations in total. So the tree maps every class and annotated member to its
  obfuscated name in `osrs-170.jar`. 133 classes are still placeholders (`classNNN`), and many members are
  `methodNNNN` or `fieldNNNN`. `ModelData`, `Model`, `KitDefinition` and `Graphics3D` carry real names for part of
  their members.
- `runetech/osrs-gamepacks` serves `osrs-170.jar`, and OpenRS2 archive 34 is the build-170 cache already downloaded
  ([revision-170-cache](../research/revision-170-cache.md)). That the tree is the decompile of the archive-34 gamepack
  is a Guess, because the tree has no gamepack hash.

## Recommended Direction

Run one experiment that picks the revision, then build a lookup on the winner.

**Experiment: which revision gets closer to full names.** At 170, the names come from the tree's annotations with no
mapper: check that each annotated class, field and method exists in `osrs-170.jar` with the same descriptor, and
count the share that has a real name. At 149, run RuneLite's `deobfuscator/.../mapping/Mapper` from the annotated
170 jar to `gamepack-149.jar` and count the share it maps. The revision with the larger share of real names on the
classes this addon reads (models, kits, sequences, frames, the rasterizer) wins. This can go against the 2026-11-06
choice of 149 in [ADR 0003](../adr/0003-old-school-caches-come-first.md), so a 170 result needs a new ADR, and the
149 reference harnesses (`Osrs149Reference`, `PoseReference`) and fixtures keep their 149 evidence until it is moved.

### Result, 2026-11-18

All Evidence. How to rerun it: [runelite-name-mapping](../research/runelite-name-mapping.md).

- `osrs-170.jar` (git blob `007ea69c`, SHA-256 `1162c729...caf4`) matches the tree. All 319 annotated classes and
  4,708 of 4,710 member annotations exist in the jar, 4,567 of them with the same descriptor. The 2 misses are a
  parser slip in the check script (`java.awt.Frame` read as the client's `Frame`).
- The mapper runs. RuneLite's `UpdateMappings` (compiled runescape-client to the `Deob` output of each jar), with the
  annotation checker's exit removed, renamed:

| Target | Classes | Fields | Methods |
| --- | --- | --- | --- |
| 170 (ceiling: the tree's own revision) | 186 | 1,487 | 585 |
| 149 | 165 (89%) | 1,380 (93%) | 522 (89%) |

- On the 25 tree classes that this repo's docs, specs and source cite, 170 has 426 members with a real name and 149
  has 415 (97% of 170). The 4 cited classes that 149 does not map (`class24`, `class50`, `class264`, `class16`) are
  placeholders, so no real name is lost.
- The mapper agrees with every hand pairing in [osrs-149-animation](../research/osrs-149-animation.md),
  [deobfuscation-value](../research/deobfuscation-value.md) and [weapon-stance-sets](../research/weapon-stance-sets.md):
  13 of 14 classes by name, and `if`, which the notes call `AbstractArchive`, is the same class under its 2018 name
  `IndexDataBase`. The members checked agree too: `ej.e/l/s` are `verticesX/Y/Z`, `ej.q` is `vertexGroups`,
  `dv.ae` is `vertexSkins` and `dv.ae(IIIII)` is `light`, `eg.v` is `skin`, `eb.j/n/r` are `count/types/list`,
  `jg.e` is `frameIDs`, and `hu.l(jg,int,jg,int)` is `getModel`.

**Decision:** 170 has 11 more real names on the cited classes, which is not enough to move the evidence base. Stay on
149, as ADR 0003 decided, and take the names from the mapper. No new ADR is needed.

**Build on 149.**

1. Decompile the mapped 149 jar once with Vineflower into a git-ignored folder, so the source carries the mapper
   names and keeps each obfuscated name in its `@ObfuscatedName` annotation.
2. Keep `names.tsv` in the repo: obfuscated name, real name, and the evidence link. Sessions add a row when they
   name a placeholder, so the next session finds it by name.
3. Add a lookup recipe in the shape of urchin's `just as-lookup`: a name or an obfuscated name gives the class and
   line range, the callers, the callees, the obfuscated name, and the research notes and ADRs that cite it.
4. Put dejared-mcp or Recaf MCP on top only if the benchmark shows that an MCP beats the lookup.

## Key Assumptions to Validate

- [x] `osrs-170.jar` from `runetech/osrs-gamepacks` matches the tree's annotations. Result: 4,708 of 4,710.
- [x] RuneLite's `Mapper` runs on 170 to 149. Result: it took one session, with the build fixes in the repo's
  papercut "RuneLite 2018 tree does not build on JDK 21+ with Maven 3.10".
- [x] Names on the cited classes decide, not total coverage. Result: 415 at 149 against 426 at 170.
- [ ] Vineflower output with names applied is readable enough that sessions stop reading bytecode. Test: answer 3
  questions from the research notes with the tree and count the reads.
- [ ] A lookup cuts tokens on jar questions. Test: the `claude -p` benchmark from 2026-11-18, with 6 jar questions,
  conditions `javap` only, named tree with `rg`, named tree with the lookup, and dejared-mcp.

## MVP Scope

In: a script that rebuilds the mapped 149 jar (the revision experiment is done), the Vineflower decompile of it,
`names.tsv` seeded from the mapper's 2,067 real names, and a lookup by name and by obfuscated name. Out: any change
to the addon's 149 profile, fixtures or reference harnesses.

## Not Doing (and Why)

- A general code-graph MCP for the addon's Python. It lost the 2026-11-18 benchmark, and `rg` already answers those
  questions in one or two calls.
- An MCP front end before names exist. Without names, dejared or Recaf only shows `dv.ae` with more steps.
- Deobfuscating the whole client by hand. Only the classes that this addon reads need real names.
- Moving the addon to 170 as part of this work. The experiment picks the source tree for reading. Moving the
  addon's evidence base is a separate ADR.

## Open Questions

- Where does the git-ignored decompile live, so every worktree reads the same copy? An environment variable, as
  urchin's `URCHIN_SWF_DIR` does, is one option.
- Does the lookup also print the decoded facts from `docs/research/` for a range, as the urchin one-pager proposes
  for `DECODED_ALGORITHMS.md`?
