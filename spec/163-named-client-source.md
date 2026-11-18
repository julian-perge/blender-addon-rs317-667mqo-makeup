Source: [issue 163](https://github.com/julian-perge/blender-addon-rs317-667mqo-makeup/issues/163) (a named source tree of the revision 149 client).

# Spec: A named client source and a lookup for it, V1

Status: proposed

This spec follows [docs/ideas/named-client-source.md](../docs/ideas/named-client-source.md). The evidence is in [docs/research/runelite-name-mapping.md](../docs/research/runelite-name-mapping.md). Commands, structure and code style are in [AGENTS.md](../AGENTS.md) and [CODING_STANDARDS.md](../CODING_STANDARDS.md). Terms follow [GLOSSARY.md](../GLOSSARY.md). The revision stays 149 ([ADR 0003](../docs/adr/0003-old-school-caches-come-first.md) and [ADR 0017](../docs/adr/0017-read-caches-directly-without-317-and-667-code.md)), so no new ADR is needed.

## Assumptions

Each item is a guess until the owner confirms it.

1. The owner has the RuneLite May 2018 tree at `~/git/runelite-master`, JDK 21 and Maven, as the mapping run of 2026-11-18 did.
2. `brew install vineflower` is a prerequisite. The scripts do not download a decompiler.
3. `gamepack-149.jar` is a local reference file that the owner already has. It is not in the repo.
4. The lookup finds callers and callees by text search of the decompiled source. It does not build a call graph.
5. `names.tsv` lives in `docs/research/client-names.tsv` (settled, see "Settled decisions").

## Objective

A session that asks "what does the client do with a model, a kit or a sequence" finds the answer by searching real names in Java source. It does not read `javap -p -c` output and does not pair obfuscated names by hand.

After this work, one command rebuilds a named source tree of gamepack 149. A second command takes a real name or an obfuscated name and prints where it is in that tree, what the research notes say about it, and the names it links to.

The user is the owner and the agent sessions of this repo. Success is in "Success criteria".

## Commands

```bash
# Rebuild the named 149 source. Needs JDK 21, Maven and vineflower on the PATH.
scripts/named-client/build.sh --gamepack <path to gamepack-149.jar>

# Look a name up. The argument is a real name, an obfuscated name such as dv.ae, or a class.member pair.
uv run scripts/lookup-client.py <name>

# The check of the repo, as for every task.
prek run --all-files
```

`build.sh` reads these environment variables. Each has a default.

| Variable | Default | Meaning |
| --- | --- | --- |
| `NAMED_CLIENT_DIR` | `~/git/osrs-149-named` | The output folder. It is outside the repo, so every worktree reads the same copy. |
| `RUNELITE_TREE` | `~/git/runelite-master` | The read-only RuneLite tree. The script copies it and patches the copy. |
| `RUNELITE_JDK` | the `java` on the PATH | A JDK 21 home. |

## Project structure

```
scripts/named-client/build.sh        Port of map-names.fish: clone, patch, build, Deob, UpdateMappings, Dump, Vineflower.
scripts/named-client/Dump.java       Moved from the vault. Prints one row per @ObfuscatedName.
scripts/named-client/README.md       Why each patch is needed. Moved from the vault note runelite-mapping.md.
scripts/lookup-client.py             The lookup. A PEP 723 script.
docs/research/client-names.tsv       names.tsv: obfuscated name, real name, evidence link. Tracked.
tests/unit/test_lookup_client.py     Tests of the lookup on a small fixture tree.
tests/fixtures/named_client/         A few decompiled classes and a small names TSV.
$NAMED_CLIENT_DIR/                   Git-ignored by location. Holds mapped-osrs-149.jar, names-osrs-149.tsv, map-osrs-149.log and src/.
```

The vault keeps `runelite-mapping.md` as the owner's note and points to the repo copy. `check170.py` and `relevant.txt` stay in the vault: only a new copy of the tree needs them.

## What to build

### 1. The rebuild script

`scripts/named-client/build.sh` does what `map-names.fish` does for one gamepack, in bash, then one more step.

1. Copy `RUNELITE_TREE` to a work folder with an APFS clone when possible, and apply the patches that the vault note lists. Stop with a clear message when a patch does not apply.
2. Build the tree on JDK 21, run RuneLite's `Deob` and `UpdateMappings` on the gamepack, and keep the annotation checker's errors in `map-osrs-149.log`.
3. Write `mapped-osrs-149.jar` and `names-osrs-149.tsv` with `Dump.java`.
4. Decompile `mapped-osrs-149.jar` with `vineflower` into `$NAMED_CLIENT_DIR/src/`, one `.java` file per class. Each member keeps its `@ObfuscatedName` annotation.
5. Print the counts of classes, fields and methods with real names.

A second run with the same inputs gives the same `names-osrs-149.tsv`, row for row (research note, "Where the scripts are").

### 2. `names.tsv`

`docs/research/client-names.tsv` has the columns `kind`, `obf_class`, `obf_member`, `descriptor`, `name`, `evidence`. It starts with the 2,067 rows of the mapper whose name is not a placeholder (`classNNN`, `fieldNNNN`, `methodNNNN`, `vmethodNNNN`). These rows have `runelite-mapper` in the `evidence` column. A session that names a placeholder adds a row and puts a link to the note or the commit that shows why in `evidence`.

The seed comes from the mapper, so a mapper row is a measured name, not a proven one. The research note records that the mapper agrees with every hand pairing in three notes, and that 48 annotation checker errors flag 170 names that the checker could not confirm in 149.

### 3. The lookup

`uv run scripts/lookup-client.py <name>` reads `names.tsv` and the source folder. It accepts a real name (`vertexSkins`), an obfuscated name (`dv.ae`) and a class and member pair (`Model.light`). For each match it prints:

- the kind, the real name, the obfuscated name and the descriptor;
- the file and the line range of the class or member in `$NAMED_CLIENT_DIR/src/`;
- the callers: the lines of other files that use the member name (a text search, so a name used by two classes shows both);
- the callees: the names of members that the body of a method uses and that are in `names.tsv`;
- the research notes, ADRs and specs in this repo that cite the real name or the obfuscated name.

A name with no match prints that, and prints the three closest names. The script exits with a non-zero code when `$NAMED_CLIENT_DIR/src/` does not exist, and its message gives the `build.sh` command.

### 4. The agent guide

`AGENTS.md` gets a "Read the doc that matches the task" line for the named client source: run the lookup before `javap`, and add a `names.tsv` row for every placeholder that a session names.

## Code style

The Python follows [CODING_STANDARDS.md](../CODING_STANDARDS.md). The script is a PEP 723 script with `uv run`, as the other scripts of `scripts/` are. The shell script is bash and falls back to POSIX features, as the global rule for git repos says.

## Testing strategy

- `tests/unit/test_lookup_client.py` runs `lookup-client.py` on `tests/fixtures/named_client/`: a real name, an obfuscated name, a class and member pair, a name with no match, a name with two matches, and a missing source folder. The fixture holds three small decompiled classes and a names TSV of about 20 rows.
- No test runs `build.sh`. It needs the RuneLite tree, Maven, a JDK and the 149 jar. The owner or the build task runs it once and records the counts (success criteria 1 to 3). The `prek` hooks do not run it.
- A test that the lookup reads each of the TSV columns uses the real `client-names.tsv` header, so a header change fails a test.

## Boundaries

- **Always:** keep each obfuscated name next to its real name. Link evidence for every row that a session adds. Run `prek run --all-files` before a commit.
- **Ask first:** adding a dependency to the add-on. Changing the 149 profile, the fixtures or the reference harnesses. Adding an MCP server.
- **Never:** commit the decompiled source, a gamepack jar or the RuneLite tree. Put a local path in a committed file instead of a placeholder such as `<path to gamepack-149.jar>`. Rename an obfuscated name in an existing fixture or note.

## Success criteria

Each item is checked once and recorded in the pull request.

1. `build.sh` ends with exit code 0 on this machine and writes `$NAMED_CLIENT_DIR/src/`.
2. The run gives 165 classes, 1,380 fields and 522 methods with real names, the counts of the research note. A difference is reported, not hidden.
3. A second run gives the same `names-osrs-149.tsv`.
4. `client-names.tsv` has 2,067 seed rows, and no row has a placeholder name.
5. `lookup-client.py dv.ae` and `lookup-client.py vertexSkins` print the same member, with a line range that opens the right lines in `$NAMED_CLIENT_DIR/src/`.
6. `lookup-client.py` on each of the 25 classes of `relevant.txt` finds the class and prints at least one research note that cites it, or says that none does.
7. The tests of the lookup pass, and `prek run --all-files` passes.
8. No file of the repo has a local path, and the repo does not track `$NAMED_CLIENT_DIR`.

## Out of scope (deferred)

- **An MCP front end** (dejared-mcp or Recaf MCP). It waits for the benchmark. The idea note says to add it only if an MCP beats the lookup.
- **A token benchmark of the lookup.** The 2026-11-18 `claude -p` benchmark design (6 jar questions, 4 conditions) is a follow-up issue, because it needs the lookup first.
- **Answers about the readability of the Vineflower output.** Whether sessions stop reading bytecode is tested after the tree exists (idea note, "Key Assumptions to Validate").
- **Decoded facts of `docs/research/` printed per line range**, as the urchin one-pager proposes. The lookup prints the notes that cite a name, not the facts of the notes.
- **Revision 170 as the evidence base.** A separate ADR.
- **A sample of other gamepacks.** The script takes one jar. `map-names.fish` takes many, and V1 does not need that.

## Settled decisions

The owner accepted these on 2026-11-18.

1. `names.tsv` lives at `docs/research/client-names.tsv`. It is evidence, each row links to a note, and the file is tracked, so every worktree reads the same copy.
2. The lookup finds callers in the decompiled source only. The line "research notes that cite it" covers the repo's docs. A text search of the repo's Python gives many false hits for short names.
3. The vault copy of `map-names.fish` stays until `build.sh` has run once and matches the counts of the research note. Then the vault note `runelite-mapping.md` becomes a short pointer to the repo script. `check170.py` and `relevant.txt` stay in the vault.

## Open questions

None.
