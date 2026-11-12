# Spec: Cite the revision 149 client for the six OSRS-149 codec rules

Status: done on 2026-11-11 on branch `docs/codec-rules-cited`. Results are in issue 17.

Written on 2026-11-11 from the scratch spec (deleted after the merge), which followed the decisions 1 to 3 in issue 17 (`git show 2a78edd:.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md`) (the user chose them on 2026-11-10). The scratch spec was written before the workflow in [docs/agents/workflow.md](../../docs/agents/workflow.md). This spec keeps its content and adds the six areas that the workflow needs. The code and test sites below were checked on 2026-11-11.

## Objective

A modeller who builds or edits an Old School revision 149 model in the new model format (`FF FF`) and exports it relies on rules that nobody has checked against the client. Two rules write the file. Four rules refuse input. The model formats note and the code mark all six "unverified", and [CODING_STANDARDS.md](../../CODING_STANDARDS.md) asks for a client citation or the owner's decision.

The six rules:

| # | Rule | Kind | Code site |
| --- | --- | --- | --- |
| 1 | A model whose faces share one render priority stores it once in the footer (0 for no faces). | Writes | `formats/new_format.py`, the comment before `flags = source.section_flags` in `encode` |
| 2 | The render-type and alpha sections are left out when all their values are 0. | Writes | the same comment in `formats/new_format.py` |
| 3 | A texture index above 254 is refused. | Refuses | `formats/model.py`, the comment before `limit = 254 if newer ...`; `tests/unit/test_osrs149_codec.py::test_encoder_rule_for_texture_coordinate_byte_limit` |
| 4 | An opaque tail whose first byte is nonzero and that holds fewer than 11 bytes is refused. | Refuses | `formats/new_format.py` (decode) and `formats/model.py` (encode validation), each with its own comment |
| 5 | Texture kinds above 3 are refused. | Refuses | `formats/new_format.py` (decode) and `formats/model.py` (encode validation) |
| 6 | Footer flags other than 0 or 1 are refused. | Refuses | `formats/new_format.py` (decode, the `Unsupported OSRS-149 footer flags` check) |

If the client reads a written file differently from the add-on, the exported model looks wrong or fails to load in game. If the add-on refuses a file that the client reads, a real cache model cannot be imported or edited.

The work reads the new-format model decoder of the revision 149 client and settles each rule against it. A rule that the client confirms gets its citation (class, method, and line or bytecode offset) in the model formats note, in the code comment that marks the rule, and in its test. A rule that the client contradicts goes back to the user before any code or test changes.

User: a modeller who edits Old School models in Blender, and the owner, who is the only maintainer.

### User stories

1. As a modeller, I want the shared priority rule checked against the client, so that a model I build with one priority loads with that priority in game.
2. As a modeller, I want the rule that leaves out all-zero render-type and alpha sections checked, so that my exported model reads the same in the client as in the add-on.
3. As a modeller, I want the refusal of texture indices above 254 checked, so that I know whether 255 means something to the client.
4. As a modeller, I want the opaque tail refusal checked, so that a cache model with an unusual tail is not refused wrongly.
5. As a modeller, I want the refusal of texture kinds above 3 checked, so that no real kind is refused.
6. As a modeller, I want the refusal of footer flags other than 0 or 1 checked, so that no real flag value is refused.
7. As the owner, I want each confirmed rule's citation in the model formats note, so that the note no longer says "unverified" for it.
8. As the owner, I want the code comment of each rule to cite the client line, so that a reader of the code sees the source.
9. As the owner, I want each confirmed rule covered by a test whose comment cites the client, so that the expected value has an outside source.
10. As the owner, I want any rule that the client contradicts brought to me before anything changes, so that I decide what the add-on does.
11. As the owner, I want the evidence (the decompiled method and the lines read) recorded where it can be checked again.
12. As the owner, I want issue 17 closed with the results, so that the open-questions list shrinks.

## Decisions

From issue 17 (user, 2026-11-10), unchanged:

- **Source.** The work reads the new-format decoder of the unchanged revision 149 client jar. It decompiles the jar with the decompiler already on this machine, as the earlier findings did. The jar and the decompiler are named in `docs/research/osrs-focus/reference-source-findings.md` and `reference-work-path.txt`. This spec holds no local paths, because the repo is public.
- **Method.** The work uses the research skill.
- **Per rule.** The work records the client method, the line or bytecode offset that shows how the client reads the field, and whether that matches the add-on's rule.
- **Confirmed rule.** The "unverified" marks are replaced with the citation in the model formats note section "Old School revision 149 in this add-on" and in the code comment.
- **Contradicted rule.** The work reports the client's behaviour and the options to the user. Nothing changes for that rule until the user decides.
- **Seam.** One test seam, agreed by the user: the codec's public `decode` and `encode`, in the existing OSRS-149 codec unit tests.

Changed or added on 2026-11-11 to fit the current layout (the user approved the spec with these on 2026-11-11):

- **Evidence folder.** The evidence is in [docs/research/osrs-149-codec-client-rules.md](../../docs/research/osrs-149-codec-client-rules.md), as [docs/agents/workflow.md](../../docs/agents/workflow.md) says. The earlier findings stay where they are, and the new file links to them.
- **Review.** The commit review in the workflow replaces the "two-axis review" in the scratch tickets.

## Tech stack

Python 3.13, uv, pytest, ruff, pyrefly, prek. No new dependency. The decompiler is a local tool and is not part of the repo. `formats/` stays pure (no `bpy`).

## Commands

See [AGENTS.md](../../AGENTS.md). The commands this work uses:

```bash
prek run --all-files
uv run pytest tests/unit/test_osrs149_codec.py
```

## Project structure

| Path | Role in this work |
| --- | --- |
| `src/rsps_toolkit/formats/new_format.py` | Decode and encode of the `FF FF` footer. Comments of rules 1, 2, 4, 5 and 6 change. |
| `src/rsps_toolkit/formats/model.py` | Encode validation. Comments of rules 3, 4 and 5 change. |
| `tests/unit/test_osrs149_codec.py` | The test seam. Test comments get the citation. A rule without a test gets one. |
| `docs/research/model-formats.md` | Section "Old School revision 149 in this add-on". Each confirmed rule gets its citation. |
| `docs/research/osrs-149-codec-client-rules.md` | The decompiled methods and the lines read. |
| `.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md` | Closed with the results. |

## Code style

A comment that carries a client citation names the class, the method and the offset or line, and says what the client does. The revision 149 client is obfuscated, so the class and method names are the obfuscated ones. A sketch of the form:

```python
# Client rev 149, class dv, method j, offsets 1613 to 1627: the footer byte is read as one shared priority.
# 255 means that a priority byte follows for every face.
```

The real citations come from the decompiled client. The sketch above is not a finding.

## Testing strategy

- One seam: the codec's public `decode` and `encode`. A good test checks what `decode` accepts or refuses and what `encode` writes. It never checks the codec's internals.
- Expected values come from the client's decoder ([CODING_STANDARDS.md](../../CODING_STANDARDS.md): "a line of a game client's code, named in a comment as file and line").
- A confirmed rule gets a test whose comment cites the client method and line. If the rule has no test, add one. The existing test `test_encoder_rule_for_texture_coordinate_byte_limit` carries an "Unverified" comment for rule 3. That comment is replaced when the client confirms the rule.
- Prior art: the OSRS-149 codec unit tests (refusals of malformed footers and invalid source fields, the computed footer layout of hand-built models) and the existing client citations in the model formats note.
- No test changes for a contradicted rule until the user decides.

## Boundaries

- Always: read the client decoder before editing a rule. Name the evidence file for each rule. Run `prek run --all-files` before each commit. Run the commit review of the workflow before each commit.
- Ask first: any rule that the client contradicts (report it with the client's behaviour and the options). Any change to the codec's behaviour. Any rule that the client neither confirms nor contradicts, where the user must decide to keep it.
- Never: change the codec's behaviour as part of this spec. Write a local path, a personal detail or a decompiled client source file into a commit. Replace "unverified" with a citation that the client does not support.

## Success criteria

1. Each of the six rules has one of two results, recorded in the evidence file: the client confirms it with a citation, or the client contradicts it and the user has the details.
2. For each confirmed rule, the model formats note, the code comment and the test comment carry the same citation, and the word "unverified" is gone from that rule.
3. A confirmed rule has a test in `tests/unit/test_osrs149_codec.py`.
4. No code behaviour changed. `git diff` for `src/` shows comment changes only.
5. `prek run --all-files` passes.
6. Issue 17 is closed with the results.

## Out of scope

- Changing the codec for a rule that the client contradicts (this waits for the user).
- The render-level Gate 0 comparison of plan 02.
- Other "unverified" claims in the model formats note, such as render types 1 and 3 being flat, and the texture tools' rules in [ADR 0012](../../docs/adr/0012-newer-models-refuse-unestablished-edits.md).
- Revisions 317 and 667.

## Open questions

Both were answered by the approval on 2026-11-11:

1. The two changes under "Changed or added on 2026-11-11" (the evidence folder, the review step) are accepted.
2. Rule 6 has a decode site only. The `encode` validation takes six flag bytes of 0 to 255 and does not check for 0 or 1. If the client confirms that only 0 and 1 are valid, the encode side accepts a value that the decode side refuses. The approval did not name this gap. It is therefore treated as a change to the codec's behaviour: it stays out of scope, and the plan reports it to the user when the client result is in. The user decides then.
