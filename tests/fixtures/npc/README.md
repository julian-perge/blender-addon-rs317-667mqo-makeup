# NPC fixtures

Inputs and expected values for the NPC tests of spec 13, all from OpenRS2 snapshot 430 (revision 149).

- `<id>.dat`: the raw definitions of the test NPCs (gnome 4233, ent 6594, cow 2805, green dragon 260, giant spider 2477 and Man 3078), the files of config group 9 of index 2.
- `models/<id>.dat`: the models that those NPCs name with opcode 1, file 0 of their groups in index 7.
- `npcs.json`: RuneLite's decoding of the definitions, written by `../NpcReference.java`.
- `lit.json`: the unchanged revision 149 client building the lit model of each NPC, written by `../NpcModelReference.java` and `../record_npc.py`. For each NPC it holds the vertex and face counts, the vertices after the client's scale (`e`, `l`, `s`), and the lit colours of the three corners of each face (`g`, `k`, `t`). A third colour of -1 marks a flat-shaded face.
- `clips/<sequence>/`: the stand and walk clips of the five test NPCs, as `../animation149/export_clip.py` writes a clip folder (README there).
- `poses.json`: the unchanged revision 149 client posing each of the five with every frame of its stand and walk clips, written by `../NpcModelReference.java` and `../record_npc.py --poses`. `clips` names the stand and walk sequence of each NPC from `npcs.json`. `npcs.<id>.<sequence>` holds one entry per frame with the vertex and face counts, the vertices after the client's scale (`e`, `l`, `s`) and the face alphas (`o`), as `../PoseReference.java` records them.

`scripts/extract-config-fixtures.py` copies the definitions and the models from the cache unchanged. It stops when an existing file has other bytes.

## Recording

Run from the repository root on macOS with uv and a JDK. The recorder checks the gamepack SHA-256 named in [the appearance README](../appearance/README.md) and needs a new output file.

```bash
uv run tests/fixtures/record_npc.py --client <reference work folder>/gamepack-149.jar --output <new file> \
  --poses <second new file>
cmp tests/fixtures/npc/lit.json <new file>
cmp tests/fixtures/npc/poses.json <second new file>
```

To export a clip folder again, for example the gnome's stand:

```bash
uv run tests/fixtures/animation149/export_clip.py --cache <path to cache> --sequence 195 \
  --output tests/fixtures/npc/clips/195
```

The harness loads the gamepack in its own class loader, as the appearance reference does. It puts the raw definitions into the config archive `ip.a` and the raw models into the model archive `gw.j`, and then calls the client's own `ip.m(id)` and `ip.v(null, 0, null, 0, guard)` for each NPC. For the poses it puts the frames of every clip into one frame archive `jg.j` and the frame maps into `ah.n`, and calls `ip.v(sequence, frame, null, 0, guard)` with a `jg` that holds the clip's packed frame ids. No Python of the add-on supplies an expected value. `NpcModelReference.java` names the bytecode offsets of each step.
