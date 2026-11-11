# 02: Cite the client for the four refusals

**What to build:** a modeller importing a new-format (`FF FF`) Old School revision 149 model can trust that the add-on refuses only what the client cannot read. The work reads the revision 149 client's new-format model decoder and settles four refusals: a texture index above 254, an opaque tail whose first byte is nonzero and that holds fewer than 11 bytes, texture kinds above 3, and footer flags other than 0 or 1. See the [spec](../spec.md) and issue 17's decisions 1 and 2.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the codec's decode and encode in the existing OSRS-149 codec unit tests.
- [ ] The reference-source findings record, for each refusal, the client's method and line or bytecode offset and whether it matches.
- [ ] A confirmed refusal's "unverified" marks in the model formats note and the codec's comments are replaced with the citation.
- [ ] Each confirmed refusal has a test whose comment cites the client line; a refusal without one gets a test.
- [ ] A contradicted refusal is reported to the user with the client's behaviour, and nothing changes for it.
- [ ] prek and the unit tests pass; the work gets the two-axis review before its commit.
