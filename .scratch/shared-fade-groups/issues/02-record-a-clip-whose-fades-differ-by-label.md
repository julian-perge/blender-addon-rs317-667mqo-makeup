# 02: Record a clip whose fades differ by label

**What to build:** a clip fixture, with the unchanged revision 149 client's recorded poses and face alphas, in which different labels fade differently, so the multi-clip split in ticket 03 can be checked against the client. Pick it from the snapshot 430 player clips (frame map 0) with an alpha transform that changes faces of some labels and not others, reproducibly (a seeded sample, as the three alpha fixtures were picked), export it and record its poses for both bodies with the existing fixture scripts, and list it in the clip fixture README with how it was picked. See the [spec](../spec.md), Testing Decisions.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [ ] The clip is picked reproducibly, and the README says how.
- [ ] Its folder holds the exported clip files, the manifest with hashes, and the client's recorded male and female poses with face alphas.
- [ ] Baking it shows fade groups that differ by label (more than one distinct alpha curve), checked by a short script whose result goes in the README entry.
- [ ] prek passes.
