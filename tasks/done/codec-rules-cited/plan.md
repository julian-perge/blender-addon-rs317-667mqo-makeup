Spec: spec/codec-rules-cited.md

# Implementation Plan: Cite the revision 149 client for the six OSRS-149 codec rules

Branch: `docs/codec-rules-cited`. One commit per task. Tasks are in `tasks/todo.md`. Issue: [issue 17](../../../.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md).

## Overview

Six rules of the new-format (`FF FF`) codec are marked "unverified". Two rules write the file and four rules refuse input. This plan reads the new-format model decoder of the revision 149 client once, settles all six rules in one evidence file, and then puts the citation of each confirmed rule in three places: the model formats note, the code comment and the test. No codec behaviour changes. A rule that the client contradicts, or does not settle, goes to the user and stays as it is.

## What the code reading found

- The six code sites match the spec table. Checked on 2026-11-11:
  - Rules 1 and 2: one comment block in `formats/new_format.py` (`encode`, before `flags = source.section_flags`).
  - Rule 3: the comment before `limit = 254 if newer ...` in `formats/model.py`.
  - Rule 4: a comment at the tail check in `formats/new_format.py` (`_decode`, "Truncated OSRS-149 opaque tail") and one in `formats/model.py` (`check`, "OSRS-149 source tail is truncated").
  - Rule 5: `any(kind > 3 for kind in kinds)` in `_decode`, and `kind in (0, 1, 2, 3)` in `check`. Neither site has a comment that says "unverified". The word is in the model formats note only.
  - Rule 6: `_decode` checks `render`, `alpha`, `face_skin`, `textures` and `vertex_skin`. It does not check the priority byte, because 255 means "per-face priorities follow". So rule 6 is about five of the six footer flag bytes. `check` accepts six bytes of 0 to 255.
- Existing tests in `tests/unit/test_osrs149_codec.py`:
  - Rule 3: `test_encoder_rule_for_texture_coordinate_byte_limit`, with an "Unverified" comment.
  - Rule 5: the case `texture-kind-4` of `test_decode_refuses_mutated_source_bytes`.
  - Rule 6: the case `bad-footer-flag` of `test_malformed_new_format_footers_are_refused` (sets the face skin flag to 2).
  - Rules 1, 2 and 4: a search for "priorit", "shared" and "tail" found no test of the rule itself. `test_unused_texture_records_and_tails_survive_decode_and_encode` only checks that a long tail survives. T2 and T3 add these tests.
- The client evidence exists in part. `.scratch/osrs-focus/evidence/reference-source-findings.md` shows that class `dv` is the model data class and `dv.j(byte[])` is the `FF FF` decoder. It records offsets 1613 to 1665 of `dv.j` (the texture byte and `dv.u`). It does not read the footer flags, the priority byte, the render-type and alpha sections, the tail or the texture kinds. T1 reads those.
- The research copy of the jar is gone (`/private/tmp` no longer holds it). The findings file gives the source, the commit, the SHA-256 and the `javap` commands. T1 downloads it again (about 1.9 MB) and checks the SHA-256 before it reads anything. The download needs the user's yes. `javap` is on the machine. No other decompiler was found on PATH, so the evidence is bytecode offsets, as in the earlier findings.
- The two scratch tickets in `.scratch/codec-rules-cited/issues/` (writing rules, refusals) are older than the workflow. This plan keeps their split for T2 and T3, and it puts the shared reading first, because both tickets need the same decoder.

## Dependency graph

```
T1 evidence: read the client decoder, one verdict per rule
 |
 +-- checkpoint: user reads the verdicts, decides on contradicted or unsettled rules
      |
      +-- T2 cite rules 1 and 2 (writing rules)
      +-- T3 cite rules 3 and 4 (texture index, opaque tail)
      +-- T4 cite rules 5 and 6 (texture kinds, footer flags)
           |
           T5 close issue 17, archive the plan
```

T2, T3 and T4 depend on T1 only. They touch different rules but share `new_format.py`, `model.py`, the test file and the note, so they run one after another, not in parallel.

## Architecture decisions

- **One evidence file** for all six rules: `.scratch/codec-rules-cited/evidence/client-rules.md`. It links the earlier findings and does not repeat them. Each rule has a heading with: the client class and method, the offsets, what the client does, and one verdict (confirmed, contradicted, or not settled).
- **Three verdicts, not two.** The spec names two results. The client may be silent on a rule (for example a size check that the client never makes). Then the rule stays, and the plan reports it to the user, as the spec's "Ask first" says.
- **Citation form** is the spec's form: obfuscated class, method, offsets, and one sentence of what the client does. The same text goes into the note, the code comment and the test comment.
- **No decompiled source in the repo.** The `javap` output stays in the scratchpad. The evidence file holds only offsets, short descriptions and the jar identity. No local path appears in it.
- **No behaviour change.** A task changes comments, the note and tests. If a verdict needs a code change, the task stops for the user.
- **Tests are pins, not new behaviour.** A rule that has no test gets one at the public `decode` and `encode`. Such a test passes on its first run, because the code already does this. The proof that it can fail is a mutation check: change the rule in the code, see the test fail, restore the code from the working copy (not with `git checkout` of a file with other edits).
- **Rule 6 gap.** `encode` takes flag bytes of 0 to 255 and `decode` refuses 2 to 254 for five of them. If T1 confirms 0 and 1, the add-on can write a file that it refuses to read. This is a behaviour change, so the plan reports it at the checkpoint and does not fix it (spec, open question 2).

## Task list

See `tasks/todo.md`. Five tasks and one checkpoint.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The jar cannot be downloaded again, or its SHA-256 differs from the findings file | High | Stop at T1 and ask. Do not use a different jar. The earlier findings tie every offset to this one jar. |
| `javap` bytecode is hard to read for the footer flags and the tail, so a verdict is a guess | High | A verdict needs the offsets that show the read. If the bytecode does not settle a rule, the verdict is "not settled" and the user decides. No citation is written for it. |
| The client contradicts a writing rule (for example it reads the priority byte as "per-face if nonzero") | High | The checkpoint stops T2 to T4 for that rule. The user decides what the add-on does. |
| A citation names the wrong method because of the duplicate obfuscated methods (`dv.cu`, `ej.cy`) | Med | The findings file warns about them. T1 names the entry point `dv.j` by its `FF FF` check (offsets 23 to 64) and follows calls from there. |
| A new characterization test passes for the wrong reason | Med | The mutation check of each new test (see above). |
| The note text for rule 5 or 6 drifts from the code comment | Low | Success criterion 2: the same citation in all three places. The review compares them. |

## Open questions

- **Download.** The jar is 1.9 MB from the GitHub repository named in the findings. T1 asks for the user's yes before the download.
- **Branch type.** The plan uses `docs/` because the change is comments, a note and tests. Say if it should be `chore/`.
- **Rule 6 gap and any contradicted rule** wait for T1's result.
