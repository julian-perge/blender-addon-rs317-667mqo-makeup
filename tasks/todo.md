# Tasks

Spec: `spec/codec-rules-cited.md`. Plan: `plan.md` in this folder. Each task ends with `prek run --all-files`, a commit review, and one commit on `docs/codec-rules-cited`. Tick a task and write its result under it. Build the test parts with `test-driven-development` at one seam: the codec's public `decode` and `encode`. Use the `research` skill for T1.

## Phase 1: Read the client

- [ ] **T1 Settle the six rules against the client decoder** (S, no code change)
  - Description: Download the revision 149 client jar named in `.scratch/osrs-focus/evidence/reference-source-findings.md` (ask the user first), check its SHA-256, and run `javap -c -p` on `dv` (and the classes `dv.j` calls) into the scratchpad. Read the `FF FF` decoder `dv.j` for each rule. Write `.scratch/codec-rules-cited/evidence/client-rules.md` with one entry per rule: class, method, offsets, what the client does, and a verdict (confirmed, contradicted, not settled).
  - Accept:
    - [ ] The jar's SHA-256 equals `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd` before any reading.
    - [ ] Each of the six rules has an entry with offsets and a verdict. Rule 1 and 2: how the client reads the priority byte (255 versus a value) and the render-type and alpha flags. Rule 3: what the client does with a texture coordinate byte of 255. Rule 4: what the client reads from the tail, and how many bytes. Rule 5: what the client does with a texture kind above 3. Rule 6: what the client does with a flag byte other than 0 or 1 (per flag byte; the priority byte is separate).
    - [ ] The file names the jar by repository, commit and SHA-256. It holds no local path and no pasted decompiled source.
    - [ ] The result for rule 6 says whether the encode side gap (flags 2 to 254 accepted by `check`) matters.
  - Verify:
    - [ ] `rg -n "/Users|/private|/tmp" .scratch/codec-rules-cited/evidence/` finds nothing.
    - [ ] `prek run --all-files` passes.
    - [ ] Commit review with fixed point `HEAD`, spec `spec/codec-rules-cited.md`, standards `CODING_STANDARDS.md`.
  - Deps: none.
  - Files: `.scratch/codec-rules-cited/evidence/client-rules.md` (new).

## Checkpoint: Verdicts

- [ ] The user has read `client-rules.md`.
- [ ] Every contradicted or not-settled rule is put to the user with the client's behaviour and the options. T2 to T4 skip those rules until the user decides.
- [ ] The rule 6 gap (decode refuses what encode accepts) is put to the user as a separate decision.
- [ ] The user has answered the open questions in `plan.md` (branch type).

## Phase 2: Cite the confirmed rules

Each task does only the rules that T1 confirmed and the user approved. For a skipped rule, write "skipped, see checkpoint" under the task.

- [ ] **T2 Cite the two writing rules (1 and 2)** (M)
  - Description: Replace "unverified" for the shared priority rule and the omitted render-type and alpha sections with the T1 citation: in the comment block in `formats/new_format.py` (`encode`) and in the model formats note. Add tests at `encode` and `decode` for the two rules, with the citation in the test comment.
  - Accept:
    - [ ] A hand-built model (source `section_flags=None`) whose faces share one priority encodes with that priority in the footer and no priority section. The same model with two priorities writes a priority section and the footer byte 255. A model with no faces writes priority 0. (Each case only for a rule that T1 confirmed.)
    - [ ] A hand-built model with all render types and alphas 0 writes neither section and the footer flags 0. A model with a nonzero alpha writes the alpha section and its flag 1. The same for render types.
    - [ ] In each case `decode(encode(model))` equals the model.
    - [ ] The note, the code comment and the test comment carry the same citation, and "unverified" is gone for these rules.
    - [ ] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [ ] Mutation check: change the shared-priority condition, then the omission condition, in `new_format.py`; each new test fails. Restore the file.
    - [ ] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [ ] `prek run --all-files` passes.
    - [ ] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/new_format.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

- [ ] **T3 Cite the texture index and opaque tail refusals (3 and 4)** (M)
  - Description: Replace the "Unverified" comments at the texture index limit (`formats/model.py`, `check`; the test `test_encoder_rule_for_texture_coordinate_byte_limit`) and at the two opaque tail checks (`formats/new_format.py` decode, `formats/model.py` encode validation) with the T1 citation. Update the note. Add a test for the tail rule at `decode` and `encode`.
  - Accept:
    - [ ] The comment of `test_encoder_rule_for_texture_coordinate_byte_limit` cites the client instead of saying "Unverified", and the test still passes unchanged in what it checks (254 stores, 255 is refused).
    - [ ] A source whose tail starts with a nonzero byte and holds fewer than 11 bytes is refused by `decode` and by `encode`. A tail of exactly 11 bytes with a nonzero first byte, and a short tail with first byte 0, are accepted. (Only as far as T1 confirmed the rule.)
    - [ ] The note, both code comments and the test comments carry the same citation for each rule.
    - [ ] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [ ] Mutation check: change `11` to `10` at each tail site, and `254` to `255` for the index limit; each corresponding test fails. Restore the files.
    - [ ] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [ ] `prek run --all-files` passes.
    - [ ] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/model.py`, `src/rsps_toolkit/formats/new_format.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

- [ ] **T4 Cite the texture kind and footer flag refusals (5 and 6)** (M)
  - Description: Put the T1 citation on the texture kind check (`new_format.py` decode, `model.py` `check`) and on the footer flag check (`new_format.py` decode). Rule 5 has no comment at either site today, so add one that passes the three comment tests. Update the note. Name the existing tests (`texture-kind-4`, `bad-footer-flag`) in the evidence file, and add a test for each case that they leave out: kind 4 at `encode` (through `check`), and each of the five flag bytes with a value of 2 at `decode`.
  - Accept:
    - [ ] `decode` refuses texture kind 4 and `encode` refuses a source with kind 4. Kinds 0 to 3 are accepted.
    - [ ] `decode` refuses a value of 2 in each of the five flag bytes (render, alpha, face skin, textures, vertex skin). The priority byte is not refused for any value. (Only as far as T1 confirmed the rule.)
    - [ ] The note, the code comments and the test comments carry the same citation. The rule 6 gap is stated as it was decided at the checkpoint, in the note, and the code does not change.
    - [ ] `git diff HEAD -- src` shows comment changes only.
  - Verify:
    - [ ] Mutation check: change `kind > 3` to `kind > 4`, and `(0, 1)` to `(0, 1, 2)` at the flag check; each corresponding test fails. Restore the files.
    - [ ] `uv run pytest tests/unit/test_osrs149_codec.py` passes.
    - [ ] `prek run --all-files` passes.
    - [ ] Commit review as in T1.
  - Deps: T1 and the checkpoint.
  - Files: `src/rsps_toolkit/formats/new_format.py`, `src/rsps_toolkit/formats/model.py`, `docs/research/model-formats.md`, `tests/unit/test_osrs149_codec.py`, `.scratch/codec-rules-cited/evidence/client-rules.md`.

## Checkpoint: Rules cited

- [ ] `prek run --all-files` passes on the branch.
- [ ] `git diff main -- src` shows comment changes only (success criterion 4).
- [ ] `rg -n -i unverified docs/research/model-formats.md src/rsps_toolkit/formats` shows the word only for rules that the checkpoint left open, and for the unrelated claims named as out of scope.
- [ ] Every skipped rule is listed for the user with the client's behaviour.

## Phase 3: Close

- [ ] **T5 Close issue 17 and archive the plan** (S)
  - Description: Write the results into issue 17 and mark it closed, as the earlier issues in `.scratch/osrs-focus/issues/` were. Update the two scratch tickets in `.scratch/codec-rules-cited/issues/` and the scratch spec status. Move `tasks/plan.md` and `tasks/todo.md` to `tasks/done/codec-rules-cited/`.
  - Accept:
    - [ ] Issue 17 lists the six rules with their verdicts and links the evidence file. A rule left open says so and names the decision it waits for.
    - [ ] The scratch tickets and spec carry the new status.
    - [ ] `tasks/` holds only `done/` after the move.
  - Verify:
    - [ ] `prek run --all-files` passes.
    - [ ] Commit review as in T1.
    - [ ] Open the pull request and stop. The user merges.
  - Deps: T2, T3, T4.
  - Files: `.scratch/osrs-focus/issues/17-osrs-149-codec-choices-need-a-source.md`, `.scratch/codec-rules-cited/issues/01-cite-the-client-for-the-two-writing-rules.md`, `.scratch/codec-rules-cited/issues/02-cite-the-client-for-the-four-refusals.md`, `.scratch/codec-rules-cited/spec.md`, `tasks/plan.md`, `tasks/todo.md`.
