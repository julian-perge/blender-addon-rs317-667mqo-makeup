# OSRS revision-149 static references

The 180 DAT files come from OpenRS2 snapshot 430. The selected closure covers
all 139 observed new-format footer combinations, all 13 actively referenced
complex-record models, all 22 render-type-2 models, both models using record
indices above 63, both nonzero tail patterns, and selected old-format edges.
The complete dataset has 33,196 models: 27,798 old and 5,398 FF FF.
`inventory.json` records the reproducible full-dataset audit; `coverage.json`
pins every selected DAT and JSON. These are source data, not generated models.

Read [the field contract](contract.md) before consuming these fixtures.
[Source findings](../../../../.scratch/osrs-focus/evidence/reference-source-findings.md)
give artifact provenance, exact bytecode paths, offsets and limitations.
The model harness runs the unchanged constructor and lighting method; it does
not start the game client or connect to a game server.

## Reference identities

- RuneLite cache 1.13.6 source JAR SHA-256:
  `c75985f35c891fc1dcbe9ee978032878d5e4b1c8a9b8dcf0496c498bb6b8b973`.
- Its ModelLoader.java SHA-256:
  `83d0bb23d91cf1e91a6b4466a47b469d9df2614ad119994dc210497d09f4df73`.
- The unmodified bundled library used for recording is the dumper JAR at
  companion commit `2e331e13d8648cefb9b573ff127338bb3453c7d2`, SHA-256
  `c71c4db7830d3828d15a96420e76cb24fe3f864f755799d5b3d618f09a15d623`.
- Independent [revision-149 gamepack](https://github.com/runetech/osrs-gamepacks/blob/2e92962075cfbc0df227cc783c37633d5e92f297/gamepacks/osrs-149.jar)
  SHA-256: `19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd`.

Internal initialization and network-handshake bytecode identify revision 149.
Neither archive dates nor this evidence prove an exact binary pairing with
snapshot 430. Certificate verification was not performed. The gamepack and
library JARs remain external inputs; the fixture manifest pins their identities.
Rebuilt shaded JARs can differ in ZIP metadata; use the recorded input artifact
when replaying hashes. No production Python codec or patched rasterizer supplies
expected values.

## Record models

Run from the repository root with Java 25 and uv. Paths below identify the
recorded local inputs; outputs must be new directories.

```bash
OSRS430_ROOT=<data workspace>
OSRS149_CLIENT=<reference work folder>/gamepack-149.jar
OSRS149_LIBRARY=<reference work folder>/reference-library.jar
uv run tests/fixtures/record_osrs149.py \
  --models "$OSRS430_ROOT/exports/osrs/openrs2-430/dump/dump_index/models" \
  --inventory .scratch/osrs-focus/evidence/cache430_field_audit.json \
  --client "$OSRS149_CLIENT" --library "$OSRS149_LIBRARY" \
  --output /private/tmp/osrs149-new-recording
diff -qr tests/fixtures/models/osrs149 /private/tmp/osrs149-new-recording
```

The final diff reports the documentation and `icons/` only. Every numbered JSON,
DAT, inventory and coverage file must match exactly. Selection takes the first
numeric model for each footer combination/tail pattern, plus required edge IDs;
the script verifies the complete dataset digest before recording.

To replay only the selected model closure, compile the Java harness and compare
its new JSONs directly:

```bash
mkdir -p /private/tmp/osrs149-reference-classes
javac -cp "$OSRS149_LIBRARY" -d /private/tmp/osrs149-reference-classes tests/fixtures/Osrs149Reference.java
java -Djava.awt.headless=true -cp "/private/tmp/osrs149-reference-classes:$OSRS149_LIBRARY" \
  Osrs149Reference --input tests/fixtures/models/osrs149 \
  --output /private/tmp/osrs149-selected-replay --client "$OSRS149_CLIENT"
uv run python - <<'PY'
from pathlib import Path
reference = Path('tests/fixtures/models/osrs149')
for replay in Path('/private/tmp/osrs149-selected-replay').glob('*.json'):
    assert replay.read_bytes() == (reference / replay.name).read_bytes(), replay.name
PY
```

## Record and replay icons

The guard policy is approved in [ADR 0002](../../../../docs/adr/0002-icon-buffer-edge-policy.md).
The recorder pins the original source and binary hashes. It creates a temporary
copy of the cache because RuneLite opens disk files with write access. Actual
providers capture each requested item/model/sprite file and the texture table.
The three selected items require no template linking. This harness is scoped to
those unlinked examples rather than a replacement item manager.

```bash
OSRS149_SOURCES=<reference work folder>/cache-1.13.6-sources.jar
uv run tests/fixtures/record_osrs149_icons.py \
  --cache "$OSRS430_ROOT/caches/osrs/openrs2-430/cache" \
  --sources "$OSRS149_SOURCES" --library "$OSRS149_LIBRARY" \
  --output /private/tmp/osrs149-new-icons
uv run tests/fixtures/record_osrs149_icons.py \
  --closure tests/fixtures/models/osrs149/icons \
  --sources "$OSRS149_SOURCES" --library "$OSRS149_LIBRARY" \
  --output /private/tmp/osrs149-replayed-icons
diff -qr tests/fixtures/models/osrs149/icons /private/tmp/osrs149-replayed-icons
uv run pytest tests/unit/test_osrs149_reference.py -q
```

The cache-free replay must match every resource, PNG, original exception trace
and manifest. Source code retains its RuneLite license in the extracted factory;
the script makes only the documented class-name and allocation substitutions.
The icon resource closure totals approximately 13 KB.
