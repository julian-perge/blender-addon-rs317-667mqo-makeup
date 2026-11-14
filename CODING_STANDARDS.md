# Coding standards

Rules a reviewer checks on every diff. Formatting, lint rules and types are enforced by `prek`, so they are not repeated here.

## Every expected value has an outside source

A test's expected value must come from outside our own code, so that a test can never pass just because the code agrees with itself. Each expected value traces to one of:

- a reference file in `tests/fixtures/` written by a second implementation (`ModelReference.java` for RuneLite, `preset_reference.py` for the original exporter);
- a line of a game client's code, named in a comment as file and line (the clients are listed in `docs/research/model-formats.md`), or named in an evidence file in `docs/research/` that the comment points to by file and rule;
- real game output, such as an item icon or an OSRS Wiki recording;
- a decision the user made, recorded in an ADR in `docs/adr/` or in the Decisions block of the plan or ticket where it was made.

Look hardest where the outside reference has a gap: a NaN, a missing section, a crash, or a field the reference does not decode. Those are the places where a value invented by the implementer slips in. A comment such as "so that import never fails" justifies behaviour, not an expected value; ask for the source.

A round-trip test (`decode(encode(m)) == m`) needs no outside source, because it checks the code against itself on purpose.

## Unverified claims stay marked

A claim about how the game behaves, in code comments or docs, says where it was checked. A claim from general knowledge says it is unverified, as `GLOSSARY.md` does, until a client or game output confirms it.

## Stored data survives the user's edits

Data the add-on stores that names vertices or faces by index (texture triangles, faces kept beside the mesh, vertex groups), or that depends on their positions (UV previews, signatures), breaks quietly when the user edits the mesh after import. A diff that adds or changes such data needs tests for what happens after the user moves, deletes or merges vertices, adds faces, runs the same operator again, mirrors with the weighter, or undoes. Each case either keeps the data right, or is refused or warned about where the user sees it. A missing case is a finding, even when the code is correct for a model just imported.

## Choices the inputs do not decide are the user's

Code that picks an output value its inputs do not determine (a default for a missing field, a reading of an ambiguous name, a fallback when a reference has a gap, a tie-break) must cite a decision the user made (an ADR in `docs/adr/`, or the Decisions block of its plan or ticket), or an outside source as in the first section. Otherwise report it as a finding marked "needs the user's decision", even when the choice looks reasonable: the implementer filling in a blank is the failure this rule exists to catch.
