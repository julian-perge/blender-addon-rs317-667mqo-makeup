# Blender execution and packaging

Read this before running Blender, changing packaging or the manifest, or changing how tests reach Blender. For packaging decisions, read the [Blender extension packaging research](../research/blender-extension-packaging.md).

## Profile isolation

Use the throwaway profile so Blender runs leave the user's real preferences untouched:

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
export BLENDER_USER_RESOURCES="$PWD/.blender-test-profile"
```

## Source-based tests and dump round trips

Source-based runs load `src/` directly and do not require an installed extension. `--factory-startup` is allowed here; `scripts/test-blender.sh` already supplies it.

```bash
scripts/test-blender.sh
$B -b --factory-startup --python-exit-code 1 --python scripts/round-trip-dump.py -- <dump folder>
```

The round-trip script imports and exports every model in the dump folder.

## Build and installed-extension checks

Use the build and validation commands in [AGENTS.md](../../AGENTS.md). Textures never ship inside the build, for the licence reasons in [the fork comparison](../research/fork-or-own-copy.md); `texture_dump.zip` stays in the repo for setup.

Installed-extension checks need the extension enabled, so omit `--factory-startup` for these runs. After setting the throwaway profile above:

```bash
$B --command extension repo-add test_repo --directory "$PWD/.blender-test-profile/repo"
$B --command extension install-file -r test_repo -e dist/rsps_toolkit-VERSION.zip
$B -b --python-exit-code 1 --python <script.py>
```

Add `test_repo` only once. Replace `VERSION` with the version in `src/rsps_toolkit/blender_manifest.toml`. The installed package is `bl_ext.test_repo.rsps_toolkit`.

## Trying the panel by hand

The local scripts `<scratch folder 2026-11-07-blender-ui>/start.py`, which loads `src/` into a running Blender and sets the dump folder, and `reload.py`, which reloads after code changes, try the panel without installing the extension. Use `reload.py` in place of Blender's Reload Scripts. Both live outside the repo.
