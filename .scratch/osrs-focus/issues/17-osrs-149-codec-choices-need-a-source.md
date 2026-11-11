# OSRS-149 codec choices need a client citation or the owner's decision

Status: ready-for-agent

The rules for writing hand-built models, and the input the codec rejects, are listed as unverified in [model formats](../../../docs/research/model-formats.md) under "Old School revision 149 in this add-on". None is checked against the revision 149 client. Each needs a client citation, or the owner's decision to keep it. Recorded 2026-11-06 ([plan 02](../plans/02-toolkit.md)).

## Decisions

The user chose on 2026-11-10, in a design interview:

1. All six rules are checked against the revision 149 client's new-format model decoder, read from the client jar with the decompiler already on this machine (the reference-source findings name the jar). The six are: one shared priority stored in the footer (0 for no faces); the render-type and alpha sections left out when all their values are 0; and the refusals of a texture index above 254, an opaque tail whose first byte is nonzero and that holds fewer than 11 bytes, texture kinds above 3, and footer flags other than 0 or 1.
2. Each rule the client confirms gets its client citation (class, method and offset or line) in the model formats note's "Old School revision 149 in this add-on" section, replacing "unverified". A rule the client contradicts comes back to the user before any code changes.
3. The work uses the research skill and is picked up later with the other ready work.

## Comments

- 2026-11-10, design interview with the user: decisions 1 to 3, ready-for-agent.
- 2026-11-10, agent: the spec is [.scratch/codec-rules-cited/spec.md](../../codec-rules-cited/spec.md) (ready-for-agent). The user agreed one test seam, the codec's decode and encode.
