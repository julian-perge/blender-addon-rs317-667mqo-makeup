# Tasks

Spec: `spec/codec-rules-cited.md`. Plan: `plan.md` in this folder. Each task ends with `prek run --all-files`, a commit review, and one commit on `docs/codec-rules-cited`. Tick a task and write its result under it. Build the test parts with `test-driven-development` at one seam: the codec's public `decode` and `encode`. Use the `research` skill for T1.

## Phase 1: Read the client

- [x] **T1 Settle the six rules against the client decoder** (S, no code change)
  - Result: [client-rules.md](../../../.scratch/codec-rules-cited/evidence/client-rules.md). The jar SHA-256 matched before reading. Rules 1, 2 and 3: confirmed. Rules 4, 5 and 6: not settled. The client has no refusal for them, and the add-on is stricter. The rule 6 encode gap does not exist for written files: `_encode` writes 0 or 1 for the five flags. Only `check` accepts flags that `decode` refuses. No decompiler was on the machine, so the reading uses `javap`. Two reviewers checked the offsets and the style, and their findings are fixed.
  - Description: Download the revision 149 client jar named in `.scratch/osrs-focus/evidence/reference-source-findings.md` (ask the user first), check its SHA-256, and run `javap -c -p` on `dv` (and the classes `dv.j` calls) into the scratchpad. Read the `FF FF` decoder `dv.j` for each rule. Write `.scratch/codec-rules-cited/evidence/client-rules.md` with one entry per rule: class, method, offsets, what the client does, and a verdict (confirmed, contradicted, not settled).
  - Accept:
    - [x] The jar's SHA-256 equals `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd` before any reading.
    - [x] Each of the six rules has an entry with offsets and a verdict. Rule 1 and 2: how the client reads the priority byte (255 versus a value) and the render-type and alpha flags. Rule 3: what the client does with a texture coordinate byte of 255. Rule 4: what the client reads from the tail, and how many bytes. Rule 5: what the client does with a texture kind above 3. Rule 6: what the client does with a flag byte other than 0 or 1 (per flag byte; the priority byte is separate).
    - [x] The file names the jar by repository, commit and SHA-256. It holds no local path and no pasted decompiled source.
    - [x] The result for rule 6 says whether the encode side gap (flags 2 to 254 accepted by `check`) matters.
  - Verify:
    - [x] `rg -n "/Users|/private|/tmp" .scratch/codec-rules-cited/evidence/` finds nothing.
    - [x] `prek run --all-files` passes.
    - [x] Commit review with fixed point `HEAD`, spec `spec/codec-rules-cited.md`, standards `CODING_STANDARDS.md`.
  - Deps: none.
  - Files: `.scratch/codec-rules-cited/evidence/client-rules.md` (new).

## Checkpoint: Verdicts

- [x] The user has read `client-rules.md`.
- [x] Every contradicted or not-settled rule is put to the user with the client's behaviour and the options. Decision on 2026-11-11: rules 4, 5 and 6 are kept and cited as "the constants are the client's, the refusal is the add-on's own, because the client reads such input differently". No code change. T3 and T4 use this wording for those rules.
- [x] The rule 6 gap is put to the user as a separate decision. Decision: only note it. `check` does not change. The gap is smaller than planned: `encode` writes 0 or 1 for the five flags, so only `check` accepts flags that `decode` refuses.
- [x] The user has answered the open questions in `plan.md`: branch `docs/`, jar download allowed.

## Phase 2: Cite the confirmed rules

Each task does only the rules that T1 confirmed and the user approved. For a skipped rule, write "skipped, see checkpoint" under the task.

- [x] **T2 Cite the two writing rules (1 and 2)** (M)
  - Result: both rules were confirmed in T1, except the value 0 for a model with no faces: the client accepts any byte below 255, so 0 is the add-on's choice, and the comment and note say so. The citation is in the encode comment block, in the note and in three new tests (shared, mixed and all-255 priorities; no faces; all-zero, alpha-only and render-type-only sections). The tests passed on their first run. Five mutation checks (shared-priority condition, 255 guard, no-face value, alpha omission, render type omission) each failed the matching test, and the file was restored. `git diff HEAD -- src` shows comment changes only. `prek run --all-files` passes.
  - Description: Replace "unverified" for the shared priority rule and the omitted render-type and alpha sections with the T1 citation: in the comment block in `formats/new_format.py` (`encode`) and in the model formats note. Add tests at `encode` and `decode` for the two rules, with the citation in the test comment.
  - Accept:
    - [x] A hand-built model (source `section_flags=None`) whose faces share one priority encodes with that priority in the footer and no priority section. The same model with two priorities writes a priority section and the footer byte 255. A model with no faces writes priority 0. (Each case only for a rule that T1 confirmed.)
    - [x] A hand-built model with all render types and alphas 0 writes neither section and the footer flags 0. A model with a nonzero alpha writes the alpha section and its flag 1. The same for render types.
    - [x] In each case `decode(encode(model))` equals the model.
    - [x] The note, the code comment and the test comment carry the same citation, and "unverified" is gone for these rules.
    - [x] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [x] Mutation check: change the shared-priority condition, then the omission condition, in `new_format.py`; each new test fails. Restore the file.
    - [x] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/new_format.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

- [x] **T3 Cite the texture index and opaque tail refusals (3 and 4)** (M)
  - Result: rule 3 is cited as confirmed. Rule 4 is cited as decided at the checkpoint: the 11 is the client's number and the refusal is our own stricter rule. The citation is in `model.py` (limit and tail), `new_format.py` (tail), the note, the evidence file and the tests. New test: `test_opaque_tail_with_a_nonzero_first_byte_needs_11_bytes` (four tails, at `decode` and `encode`). `test_encoder_rule_for_texture_coordinate_byte_limit` now cites the client, and it also pins the 255-triangle cap. Mutation checks: `>= 10` in `model.py` fails the encode case, `>= 10` and `< 10` together fail the decode case, and `0x100` for the triangle cap fails the index test. Two mutations survive because their guards cannot be reached alone: `< 10` in `new_format.py` (the `Model` check refuses the same tail) and `limit = 255` (index 255 is already a missing triangle). Both are reported in the evidence file. No code change.
  - Description: Replace the "Unverified" comments at the texture index limit (`formats/model.py`, `check`; the test `test_encoder_rule_for_texture_coordinate_byte_limit`) and at the two opaque tail checks (`formats/new_format.py` decode, `formats/model.py` encode validation) with the T1 citation. Update the note. Add a test for the tail rule at `decode` and `encode`.
  - Accept:
    - [x] The comment of `test_encoder_rule_for_texture_coordinate_byte_limit` cites the client instead of saying "Unverified", and the test still passes unchanged in what it checks (254 stores, 255 is refused).
    - [x] A source whose tail starts with a nonzero byte and holds fewer than 11 bytes is refused by `decode` and by `encode`. A tail of exactly 11 bytes with a nonzero first byte, and a short tail with first byte 0, are accepted. (Only as far as T1 confirmed the rule.)
    - [x] The note, both code comments and the test comments carry the same citation for each rule.
    - [x] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [x] Mutation check: change `11` to `10` at each tail site, and `254` to `255` for the index limit; each corresponding test fails. Restore the files.
    - [x] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/model.py`, `src/rsps_toolkit/formats/new_format.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

- [x] **T4 Cite the texture kind and footer flag refusals (5 and 6)** (M)
  - Result: both rules are cited as decided at the checkpoint: the constants (kinds 0 to 3, flags 0 and 1) are the client's, and the refusal is our own stricter rule. The citation is in `new_format.py` (kind and flag checks), `model.py` (kind check), the note, the evidence file and three new tests (kinds 0 to 3 accepted and kind 4 refused at `decode` and `encode`; a flag of 2 refused in each of the five flag bytes while the priority byte is read as a shared priority; `encode` writes only 0 or 1 for the flags). The rule 6 gap is stated in the note: `check` is unchanged by decision. Finding: the existing case `bad-footer-flag` sets the priority byte, not a flag, so it never tested rule 6. Mutation checks: `kind > 4`, `(0, 1, 2, 3, 4)`, `(0, 1, 2)` for the flags and `render_flag >= 1` each fail the matching test, and the files were restored. `git diff HEAD -- src` shows comment changes only.
  - Description: Put the T1 citation on the texture kind check (`new_format.py` decode, `model.py` `check`) and on the footer flag check (`new_format.py` decode). Rule 5 has no comment at either site today, so add one that passes the three comment tests. Update the note. Name the existing tests (`texture-kind-4`, `bad-footer-flag`) in the evidence file, and add a test for each case that they leave out: kind 4 at `encode` (through `check`), and each of the five flag bytes with a value of 2 at `decode`.
  - Accept:
    - [x] `decode` refuses texture kind 4 and `encode` refuses a source with kind 4. Kinds 0 to 3 are accepted.
    - [x] `decode` refuses a value of 2 in each of the five flag bytes (render, alpha, face skin, textures, vertex skin). The priority byte is not refused for any value. (Only as far as T1 confirmed the rule.)
    - [x] The note, the code comments and the test comments carry the same citation. The rule 6 gap is stated as it was decided at the checkpoint, in the note, and the code does not change.
    - [x] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [x] Mutation check: change `kind > 3` to `kind > 4`, and `(0, 1)` to `(0, 1, 2)` at the flag check; each corresponding test fails. Restore the files.
    - [x] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/new_format.py`, `src/rsps_toolkit/formats/model.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

## Checkpoint: Rules cited

- [x] `prek run --all-files` passes on the branch.
- [x] `git diff main -- src` shows comment changes only (success criterion 4).
- [x] `rg -n -i unverified docs/research/model-formats.md src/rsps_toolkit/formats` shows the word only for rules that the checkpoint left open, and for the unrelated claims named as out of scope.
- [x] Every skipped rule is listed for the user with the client's behaviour.

## Phase 3: Close

- [x] **T5 Close issue 17 and archive the plan** (S)
  - Result: issue 17 is resolved, with decisions 4 and 5 and a results table. The two scratch tickets and the scratch spec are resolved, and the spec status says done. This plan moved to `tasks/done/codec-rules-cited/`. Remaining "unverified" marks in the note and in `formats/` are out of scope: render types 1 and 3, the texture tools' rules, kind-zero vertex records, the preview of other record kinds in `texture_triangles.py`, and the kit name order. Skipped rules: none. Rules 4, 5 and 6 are cited as stricter rules by decision.
  - Description: Write the results into issue 17 and mark it closed, as the earlier issues in `.scratch/osrs-focus/issues/` were. Update the two scratch tickets in `.scratch/codec-rules-cited/issues/` and the scratch spec status. Move `tasks/plan.md` and `tasks/todo.md` to `tasks/done/codec-rules-cited/`.
  - Accept:
    - [x] Issue 17 lists the six rules with their verdicts and links the evidence file. A rule left open says so and names the decision it waits for.
    - [x] The scratch tickets and spec carry the new status.
    - [x] `tasks/` holds only `done/` after the move.
  - Verify:
    - [x] `prek run --all-files` passes.
    - [x] Commit review as in T1.
    - [ ] Open the pull request and stop. The user merges.
  - Deps: T2, T3, T4.
  - Files: `.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md`, `.scratch/codec-rules-cited/issues/01-cite-the-client-for-the-two-writing-rules.md`, `.scratch/codec-rules-cited/issues/02-cite-the-client-for-the-four-refusals.md`, `.scratch/codec-rules-cited/spec.md`, `tasks/plan.md`, `tasks/todo.md`.
