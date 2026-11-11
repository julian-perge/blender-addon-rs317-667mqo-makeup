# 01: Cite the client for the two writing rules

**What to build:** a modeller exporting a hand-built or edited new-format (`FF FF`) Old School revision 149 model can trust that the client reads it as written. The work reads the revision 149 client's new-format model decoder and settles two writing rules: a model whose faces share one render priority stores it once in the footer (0 when there are no faces), and the render-type and face alpha sections are left out when all their values are 0. See the [spec](../spec.md) and issue 17's decisions 1 and 2.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Agree the test seam with the user first: the codec's decode and encode in the existing OSRS-149 codec unit tests.
- [ ] The reference-source findings record, for each rule, the client's method and line or bytecode offset and whether it matches.
- [ ] A confirmed rule's "unverified" marks in the model formats note and the codec's comments are replaced with the citation.
- [ ] Each confirmed rule has a test whose comment cites the client line; a rule without one gets a test.
- [ ] A contradicted rule is reported to the user with the client's behaviour, and nothing changes for it.
- [ ] prek and the unit tests pass; the work gets the two-axis review before its commit.
