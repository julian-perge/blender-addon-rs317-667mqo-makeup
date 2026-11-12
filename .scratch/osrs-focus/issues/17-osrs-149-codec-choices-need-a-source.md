# OSRS-149 codec choices need a client citation or the owner's decision

Status: resolved

The rules for writing hand-built models, and the input the codec rejects, are listed as unverified in [model formats](../../../docs/research/model-formats.md) under "Old School revision 149 in this add-on". None is checked against the revision 149 client. Each needs a client citation, or the owner's decision to keep it. Recorded 2026-11-06 ([plan 02](../plans/02-toolkit.md)).

## Decisions

The user chose on 2026-11-10, in a design interview:

1. All six rules are checked against the revision 149 client's new-format model decoder, read from the client jar with the decompiler already on this machine (the reference-source findings name the jar). The six are: one shared priority stored in the footer (0 for no faces); the render-type and alpha sections left out when all their values are 0; and the refusals of a texture index above 254, an opaque tail whose first byte is nonzero and that holds fewer than 11 bytes, texture kinds above 3, and footer flags other than 0 or 1.
2. Each rule the client confirms gets its client citation (class, method and offset or line) in the model formats note's "Old School revision 149 in this add-on" section, replacing "unverified". A rule the client contradicts comes back to the user before any code changes.
3. The work uses the research skill and is picked up later with the other ready work.

The user chose on 2026-11-11, when the client result was in:

4. The client has no refusal for rules 4, 5 and 6, and the add-on is stricter. Keep the three refusals. Cite them as: the constants (11 bytes, kinds 0 to 3, flags 0 and 1) are the client's, and the refusal is the add-on's own stricter rule. No code change.
5. Rule 6 on the encode side: leave `check` as it is. Only note the gap in the model formats note.

## Results

The evidence is in [client-rules.md](../../codec-rules-cited/evidence/client-rules.md). It reads the jar from `runetech/osrs-gamepacks`, commit `2e92962075cfbc0df227cc783c37633d5e92f297`, with SHA-256 `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`. The reading uses `javap` bytecode offsets, because no decompiler was on the machine.

| # | Rule | Result |
| --- | --- | --- |
| 1 | One shared priority in the footer (0 for no faces) | Confirmed. The client reads 255 as per-face priorities and any other byte as the shared one. The 0 for no faces is the add-on's choice. |
| 2 | Render-type and alpha sections left out when all values are 0 | Confirmed. A missing section reads as 0, and each section is read only when its flag is 1. |
| 3 | Texture index above 254 refused | Confirmed. The file byte holds the index plus 1, so 254 is the highest index. The client has no check of its own. |
| 4 | Short opaque tail refused | Not settled by the client. The client reads 11 bytes when the first tail byte is nonzero and checks no length. Kept as a stricter rule (decision 4). |
| 5 | Texture kinds above 3 refused | Not settled by the client. The client reads kinds 0 to 3 and skips any other kind. Kept as a stricter rule (decision 4). |
| 6 | Footer flags other than 0 or 1 refused | Not settled by the client. The client compares each flag with 1 only. Kept as a stricter rule (decision 4). |

Rule 6 on the encode side: `encode` builds the five flags from the data and writes only 0 or 1, so no written file is refused by `decode`. Only `check` accepts source flags of 0 to 255. It stays as it is (decision 5).

The existing test case `bad-footer-flag` set the priority byte, not a flag, so it never tested rule 6. It is now named `wrong-priority-byte`. The new test covers each of the five flag bytes. The "unverified" marks are gone for the six rules in the note and the code. The codec behaviour did not change: the diff in `src/` is comments only.

## Comments

- 2026-11-10, design interview with the user: decisions 1 to 3, ready-for-agent.
- 2026-11-10, agent: the spec is [.scratch/codec-rules-cited/spec.md](../../codec-rules-cited/spec.md) (ready-for-agent). The user agreed one test seam, the codec's decode and encode.
- 2026-11-11, agent: resolved by [spec/codec-rules-cited.md](../../../spec/codec-rules-cited.md) on branch `docs/codec-rules-cited`. Results and decisions 4 and 5 are above.
