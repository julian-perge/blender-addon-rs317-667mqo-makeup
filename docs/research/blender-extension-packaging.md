# Blender 5.2 extension packaging: research

Researched 2026-11-04 against Blender 5.2.3 LTS (`/Applications/Blender.app`, bundled Python 3.13.13). Sources are the Blender 5.2 LTS manual, the Blender developer handbook, Blender's own bundled Python sources, the fake-bpy-module repo and PyPI, and the pytest docs. "Verified locally" means a command was run against a toy project in `<scratch folder 2026-11-04-blender-ext-research>/toy/` (not in this repo); the output is quoted where it matters.

Abbreviations used below:

- `$B` = `/Applications/Blender.app/Contents/MacOS/Blender`
- `$S` = `/Applications/Blender.app/Contents/Resources/5.2/scripts`
- `blender_ext.py` = `$S/addons_core/bl_pkg/cli/blender_ext.py` (the code behind `--command extension`)
- Manual = <https://docs.blender.org/manual/en/latest/advanced/extensions/> (page header: "Blender 5.2 LTS Manual")

## Recommendations for this repo

### Layout

The extension package is `src/rsps_toolkit/`. It holds `blender_manifest.toml` and `__init__.py`, because Blender requires both at the root of whatever it builds or loads (see Q3). Everything outside that folder (pyproject, tests, fixtures, docs) is never zipped, with no exclude rules needed.

```text
pyproject.toml            # uv project, package = false, dev tools only
.python-version           # 3.13
uv.lock
src/rsps_toolkit/         # = the extension; build with --source-dir src/rsps_toolkit
  blender_manifest.toml
  __init__.py             # register()/unregister() only; imports bpy code lazily
  formats/                # pure Python: bytes <-> plain data model, never imports bpy
    __init__.py
    model_317.py
    model_667.py
    dat_writer.py
  blender/                # everything that imports bpy/bmesh/gpu/mathutils
    __init__.py           # register()/unregister() for all classes
    preferences.py        # AddonPreferences, bl_idname = base package
    importers.py, exporter.py, weighter.py, priorities.py, ...
tests/
  unit/                   # plain `uv run pytest`, imports rsps_toolkit.formats only
  blender/                # run inside Blender (bpy available)
  fixtures/               # real .dat models from the 317 cache and OSRS dump
```

The extension id `rsps_toolkit` is a suggestion; it must be a valid Python identifier with no leading/trailing or double underscore (`pkg_idname_is_valid_or_error`, `blender_ext.py` line 1517).

### Top-level `__init__.py`

Import the `bpy` layer inside `register()`/`unregister()`, so that `import rsps_toolkit.formats.model_317` works in plain CPython. Verified locally: with `import bpy` at the top of the package `__init__.py`, plain pytest fails at collection with `ModuleNotFoundError: No module named 'bpy'`, even with `fake-bpy-module-5.2` installed (it only ships `bpy-stubs`). With the lazy form below, `uv run pytest` passes.

```python
def register():
    from . import blender

    blender.register()


def unregister():
    from . import blender

    blender.unregister()
```

Trade-off: the handbook's "Reload Scripts" pattern (`_needs_reload = "bpy" in locals()` plus `importlib.reload`) assumes module-level imports in `__init__.py` (<https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/>). With lazy imports, "Reload Scripts" will not reload submodules unless `register()` reloads them itself. Unconfirmed whether that matters for this workflow; restarting Blender always works.

### Manifest draft

```toml
schema_version = "1.0.0"

id = "rsps_toolkit"
version = "7.7.0"
name = "RSPS Toolkit"
tagline = "Import, weight, texture and export RuneScape 317 and 667 models"
maintainer = "Julian Perge"
type = "add-on"

blender_version_min = "5.2.0"

license = ["SPDX:MIT"]

[permissions]
files = "Import and export RuneScape model and texture files"

[build]
paths_exclude_pattern = [
  "__pycache__/",
  ".*",
  "/*.zip",
  "*.blend[1-9]",
]
```

- `tagline`: max 64 characters, must end with an alphanumeric character or a closing bracket (`TERSE_DESCRIPTION_MAX_LENGTH = 64` and `pkg_manifest_validate_terse_description_or_error`, `blender_ext.py` lines 141 and 1529). The draft above is 63 characters.
- `license`: the README says MIT (`README.md` line 250), and `LICENSE` holds the MIT text since `6b8a07b`. The built zip leaves it out (`docs/research/fork-or-own-copy.md`, Licences).
- `[build]` repeats the 5.2 source defaults explicitly (see Q1 for why the manual's list differs).
- No `wheels` or `platforms`: the add-on has no third-party dependencies.

### Commands

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender

# validate and build (output: dist/rsps_toolkit-7.7.0.zip)
$B --command extension validate src/rsps_toolkit
mkdir -p dist   # build fails with "No such file or directory" if the output folder is missing
$B --command extension build --source-dir src/rsps_toolkit --output-dir dist

# install the zip into the default user repo and enable it
$B --command extension install-file -r user_default -e dist/rsps_toolkit-7.7.0.zip

# development without rebuilding: a local repo that symlinks the package
$B --command extension repo-add dev --directory ~/blender-dev-extensions
ln -s "$PWD/src/rsps_toolkit" ~/blender-dev-extensions/rsps_toolkit

# pure-Python tests
uv run pytest

# tests inside Blender, in a throwaway profile so real preferences are untouched
export BLENDER_USER_RESOURCES="$PWD/.blender-test-profile"
$B --command extension repo-add test_repo --directory "$PWD/.blender-test-profile/repo"
$B --command extension install-file -r test_repo -e dist/rsps_toolkit-7.7.0.zip
PYTHONPATH="$PWD/.venv/lib/python3.13/site-packages" \
  $B -b --python-use-system-env --python-exit-code 1 \
  --python-expr "import sys, pytest; sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', 'tests/blender']))"
```

Inside Blender the package is importable as `bl_ext.test_repo.rsps_toolkit` (verified locally, see Q7). Do not pass `--factory-startup` for the in-Blender run: it skips the user preferences, so installed extensions are not enabled (verified locally, see Q7).

### Textures

Replace the three different `texture_dump` lookups (`importer_317.py` line 75 uses the add-on folder, `pmn_texturing.py` line 86 uses the add-on folder or the .blend folder, `importer_667.py` line 74 uses `%APPDATA%` and a hard-coded `polyforge_mqo_exporter` folder) with one function: an add-on preference `texture_dir` (`subtype="DIR_PATH"`), falling back to `bpy.utils.extension_path_user(base_package, path="texture_dump", create=True)`. Verified locally that this resolves to `<user>/extensions/.user/<repo>/<id>/texture_dump`. See Q5.

### Type checking

Dev dependency `fake-bpy-module-5.2` (matches the installed Blender). Verified locally with pyright and mypy: both resolve `bpy` from the stubs, and both reject the Blender property-annotation idiom `prop: bpy.props.StringProperty(...)` (pyright `reportInvalidTypeForm`, mypy `valid-type`) and flag `__package__` as `str | None`. Plan per-line ignores or a narrower checker config for the `blender/` layer. See Q6.

## Q1. `blender_manifest.toml` fields (Blender 5.2)

Source of truth is the validator table `pkg_manifest_known_keys_and_types` in `blender_ext.py` (lines 1963 to 1992), which is commented "Required" (implicit) and "Optional". Manual: <https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html#manifest>.

Required (all strings unless noted):

| Field | Rule | Source |
| --- | --- | --- |
| `schema_version` | `"1.0.0"` | Manual, `blender_ext.py` 1974 |
| `id` | Python identifier, no `__`, no leading/trailing `_` | `blender_ext.py` 1517 to 1526 |
| `version` | semantic version | Manual |
| `name` | non-empty, no control characters | `blender_ext.py` 1975 |
| `tagline` | up to 64 characters, no trailing punctuation | Manual, `blender_ext.py` 141, 1529 |
| `maintainer` | non-empty | Manual |
| `type` | `"add-on"` or `"theme"` | `PKG_MANIFEST_TYPE_SUPPORTED`, `blender_ext.py` 76 |
| `license` | list of SPDX ids with `SPDX:` prefix | Manual, <https://docs.blender.org/manual/en/latest/advanced/extensions/licenses.html> |
| `blender_version_min` | strict validation wants 3 numbers `X.Y.Z` | `blender_ext.py` 1740 to 1753 |

Optional: `blender_version_max` (first unsupported version), `website`, `copyright` (list of `"Year Name"` or `"Year-Year Name"`), `tags`, `platforms` (`windows-x64`, `windows-arm64`, `macos-x64`, `macos-arm64`, `linux-x64`), `wheels` (list of relative `./wheels/*.whl` paths), `permissions`. Manual, same page; `blender_ext.py` 1983 to 1991.

`permissions` is a table whose keys must be one of `files`, `network`, `clipboard`, `camera`, `microphone`; each value is a reason up to 64 characters without trailing punctuation (`pkg_manifest_validate_field_permissions`, `blender_ext.py` 1803 to 1856). A list form is still accepted when not strict, "for old files" (same function).

`[build]` (only read by `extension build`):

- `paths`: explicit list of files relative to the manifest.
- `paths_exclude_pattern`: gitignore-style patterns.
- Declaring both is an error: `[build]: declaring both "paths" and "paths_exclude_pattern" is not supported` (`blender_ext.py` 358 to 359).
- `[build.generated]` is reserved and must not be written by hand (Manual).
- Every value present must be non-empty; omit an optional field instead of leaving it empty (Manual, note under "Reserved").

Default exclude list: the manual shows `["__pycache__/", ".git", "*.zip"]` in one place and `["__pycache__/", "/.git/", "/*.zip"]` in the example manifest. The 5.2.3 source uses `["__pycache__/", ".*", "/*.zip", "*.blend[1-9]"]` (`blender_ext.py` around line 4659). The source is what runs. Declaring `paths_exclude_pattern` replaces the default list entirely (the default is only built when `[build]` is absent, same block), so copy the defaults in when adding patterns.

Which apply to this add-on:

- All required fields.
- `permissions.files`: the add-on reads `.dat` models and PNG textures and writes `.dat` exports (`ui.py` line 44 onwards). The manual says `files` is "for access of any filesystem operations".
- Not `network`, `clipboard`, `camera`, `microphone`.
- Not `wheels` / `platforms`: only Blender built-ins are imported. Without `platforms` the extension is available on all systems (Manual).
- `blender_version_max`: leave out (Manual: "This can be omitted and defined later").

## Q2. `extension build` / `validate` / `install-file`

Flags, from `$B --command extension <sub> --help` (5.2.3) and <https://docs.blender.org/manual/en/latest/advanced/command_line/extension_arguments.html>:

- `build [--source-dir DIR] [--output-dir DIR] [--output-filepath FILE] [--valid-tags JSON] [--split-platforms] [--verbose]`
  - `--source-dir`: "The package source directory containing a `blender_manifest.toml` manifest. Defaults to the current directory."
  - `--output-filepath`: defaults to `{id}-{version}.zip`.
  - `--valid-tags ""` disables tag validation; a JSON file can supply custom tags.
  - `--split-platforms`: one zip per entry in `platforms`, suffixed e.g. `-macos_arm64`; only useful with platform-specific wheels (<https://docs.blender.org/manual/en/latest/advanced/extensions/python_wheels.html#platform-builds>).
- `validate [--valid-tags JSON] [SOURCE_PATH]`: SOURCE_PATH is a directory or a built zip.
- `install-file -r REPO [-e] [--no-prefs] FILE`: `-e` enables after install, `--no-prefs` treats preferences as read-only.
- Others: `list`, `sync`, `update`, `install`, `remove`, `repo-list`, `repo-add`, `repo-remove`, `server-generate`.

What gets zipped (`blender_ext.py` lines 4620 to 4740):

- The manifest always, plus listed wheels.
- With `paths`: exactly those paths.
- Otherwise: a recursive scan of the source dir minus `paths_exclude_pattern` (or minus dot-files if the pattern list is empty).
- For `type = "add-on"`, the build fails unless some built path starts with `__init__.`: `Not a Python package: missing "__init__.*" file`.

Verified locally: building the toy with a stray `.DS_Store` and `__pycache__/x.pyc` in the package produced a zip with only `blender_manifest.toml`, `__init__.py`, `formats/...`, `blender/...`, all at the zip root.

Repo names on this machine (`$B --command extension repo-list`): `user_default` ("User Default", `~/Library/Application Support/Blender/5.2/extensions/user_default`, source USER), `blender_org`, `lab_blender_org`, `system` (inside the app bundle, source SYSTEM). `install-file -r user_default -e file.zip` installed and enabled the toy (verified locally in an isolated profile: `STATUS Installed "rs_toy"`).

## Q3. Mapping a `src/<pkg>/` layout onto an extension

Official guidance:

- The zip must have `__init__.py` and `blender_manifest.toml` at its root (or inside one top-level folder) (Manual, getting_started.html, "Add-on extension" and its note).
- "Blender expects extensions to have `blender_manifest.toml` and `__init__.py` files in the root directory. If the root of your project doesn't have those files, you need to symlink the subdirectory that does." (<https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/>, "Setting Up Project").
- `[build] paths` are "relative to the manifest" (Manual).

Consequence (verified locally): put the manifest in `src/<pkg>/` and build with `--source-dir src/<pkg>`. Two alternatives fail:

- `extension build` at the repo root with the manifest in `src/<pkg>/`: `FATAL_ERROR: File "./blender_manifest.toml" not found!`
- Manifest at the repo root with `paths = ["src/rs_toy/__init__.py", ...]`: `FATAL_ERROR: Not a Python package: missing "__init__.*" file`, because paths keep their `src/rs_toy/` prefix inside the zip.

With the manifest inside the package dir, pyproject, tests and fixtures are outside the source dir and never zipped; no exclude patterns are needed for them.

Development loop (verified locally): `repo-add dev --directory <dir>` plus a symlink `<dir>/rs_toy -> src/rs_toy` makes the package load as `bl_ext.dev.rs_toy` from the working tree. The handbook warns that uninstalling from Blender's UI can delete the symlink target, especially on Windows (same page).

The pyproject side (this is a project choice, not Blender guidance): `[tool.uv] package = false` keeps uv from building or installing the package, and pytest's `pythonpath = ["src"]` (<https://docs.pytest.org/en/stable/reference/reference.html#confval-pythonpath>) makes `import rsps_toolkit.formats` work. Verified locally in the toy. pytest's own good-practices page discusses the `src` layout: <https://docs.pytest.org/en/stable/explanation/goodpractices.html>.

Real-world examples (examples, not official guidance):

- extbpy (<https://github.com/bradyajohnston/extbpy>): generates `blender_manifest.toml` from `pyproject.toml` (`[tool.extbpy]`), supports `src/my_extension/`, downloads wheels from `uv.lock`, and runs `blender --command extension validate` if Blender is on PATH (README).
- peeler (<https://pypi.org/project/peeler/>, <https://github.com/Maxioum/Peeler>): "A tool to use a pyproject.toml instead of a blender_manifest.toml to build Blender add-ons" (PyPI summary, 0.11.5).

Neither is needed here: there are no wheels, and a hand-written manifest is 20 lines.

## Q4. Rules extensions impose

From <https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html> ("Converting a Legacy Add-on into an Extension" and following sections):

- Remove `bl_info`. If one is present, Blender deletes it on load and uses the manifest; with `--debug-python` it prints `has a "bl_info" which will be ignored` (`$S/modules/addon_utils.py` lines 513 to 530).
- Replace references to the module name with `__package__`; make all imports inside the add-on relative.
- The module name is `bl_ext.<repo_module>.<id>`, e.g. `bl_ext.user_default.rsps_toolkit`. Verified locally: `__package__` was `bl_ext.dev_repo.rs_toy`. `bpy.utils.extension_path_user` raises `ValueError` unless the package has exactly these 3 components (`addon_utils.py` `_extension_module_name_decompose`, line 1448).
- Add-on preferences: `bl_idname = __package__`; access with `bpy.context.preferences.addons[__package__]`. In a subpackage use `from .. import __package__ as base_package`. Never hard-code the string; never modify `__package__`.

From the Add-on Guidelines, which are requirements for extensions.blender.org and recommended elsewhere (<https://developer.blender.org/docs/handbook/extensions/addon_guidelines/>):

- No installing Python modules or pip packages at runtime.
- "Manipulating Blender's module loading such as changing the module search path or inserting modules directly into the global module dictionary is forbidden." So no `sys.path` edits in the extension. Test harness commands that run outside the extension are not covered by this.
- "Add-ons must not write files in their own directories since 'System' repositories may be used on read-only file-systems." The Manual's "Local Storage" section adds that upgrading the extension removes all files in its directory. Reading files shipped inside the package is not forbidden by either source.
- Network access must respect `bpy.app.online_access` (not relevant here).

## Q5. User data: `extension_path_user`

Signature (from `help(bpy.utils.extension_path_user)` in 5.2.3):

```text
extension_path_user(package, *, path='', create=False)
```

`path` and `create` are keyword-only. The docstring says the extension's own location "is not a suitable place to store files because it is cleared each upgrade and the users may not have write permissions".

Behaviour (`$S/modules/bpy/utils/__init__.py` lines 973 to 996):

- Result: `<USER>/extensions/.user/<repo_module>/<id>[/<path>]`.
- With `create=True` it runs `os.makedirs`. On failure it prints a traceback and returns `""`. If the path exists but is not a directory, it also returns `""`.
- Manual: "This directory will be kept between upgrades but will be removed if the extension is uninstalled." (addons.html, "Local Storage").

On macOS `<USER>` is `~/Library/Application Support/Blender/5.2` (`bpy.utils.resource_path('USER')`, verified locally), so for a `user_default` install the path is `~/Library/Application Support/Blender/5.2/extensions/.user/user_default/rsps_toolkit/`. Verified with `BLENDER_USER_RESOURCES` pointed at a temp dir: `.../blender_user/extensions/.user/toy_repo/rs_toy/texture_dump`.

Recommendation for `texture_dump/`:

- Add an `AddonPreferences.texture_dir` (`DIR_PATH`). When it is empty, fall back to `extension_path_user(base_package, path="texture_dump", create=True)`.
- Tell users to unzip `texture_dump.zip` into either location.

Shipping the PNGs inside the package and only reading them would not break the written rules, but it adds about 15 MB to every build. Uninstalling also deletes the user dir, which is another reason to prefer a preference path for data the user cares about.

## Q6. fake-bpy-module

From PyPI JSON (`https://pypi.org/pypi/<name>/json`, fetched 2026-11-04) and the README (<https://github.com/nutti/fake-bpy-module/blob/main/README.md>):

| Package | Targets | Latest | requires_python |
| --- | --- | --- | --- |
| `fake-bpy-module` | Blender main-branch daily build | 20261031 | `>=3.8` |
| `fake-bpy-module-latest` | same as above ("or, specify version latest") | 20261031 | `>=3.8` |
| `fake-bpy-module-5.2` | Blender 5.2 | 20260730 | `>=3.8` |
| `fake-bpy-module-5.1`, `-5.0`, `-4.5` | those versions | 20260730 | `>=3.8` |

- Use `fake-bpy-module-5.2`, pinned to the installed Blender. The unversioned and `-latest` packages track Blender main, which is ahead of 5.2 LTS.
- The README requires Python 3.8 or later because of `typing` use, so it works with 3.13.
- Packaging (verified locally): the 5.2 wheel installs PEP 561 stub-only packages (`bpy-stubs`, `bmesh-stubs`, `mathutils-stubs`, `bpy_extras-stubs`, `_bpy_types-stubs` and others), so `import bpy` still fails at runtime outside Blender. It helps type checkers only and cannot stand in for bpy in tests.
- Checkers (verified locally with `uv run pyright src` and `uv run mypy src`): both resolve the stubs.
  - Both report the property idiom `x: bpy.props.StringProperty(...)` as an invalid annotation (pyright `reportInvalidTypeForm`, mypy `valid-type`).
  - Both report `bpy.context.preferences` as Optional.
  - pyright reports `__package__` as `str | None`, which matters when it is passed to `bl_idname` or `extension_path_user`.
- ruff does no type resolution; `ruff check` passed on the toy. The handbook also recommends fake-bpy-module (<https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/>, "Code Completion").

## Q7. Testing

### (a) pytest inside headless Blender

Relevant flags, from `$B --help`:

- `-b`: run in the background, with no UI.
- `--python-expr <expr>`: run the expression as a script.
- `--python-exit-code <code>`: "exit-code in [0..255] to exit if a Python exception is raised (only for scripts executed from the command line), zero disables".
- `--python-use-system-env`: "Allow Python to use system environment variables such as 'PYTHONPATH'".
- `--factory-startup`: "Skip reading the 'startup.blend'".
- `BLENDER_USER_RESOURCES`: "Replace default directory of all user files".

Blender's Python runs isolated by default: `sys.flags.no_user_site == 1` and `PYTHONPATH` is ignored without the flag above (verified locally).

Exit codes, verified locally:

- `sys.exit(pytest.main([...]))` propagates: 0 when all tests pass, 1 when one fails. pytest documents `pytest.main` returning the exit code: <https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-from-python-code>.
- An uncaught exception without `--python-exit-code` exits 0. With `--python-exit-code 3` it exits 3. Always pass `--python-exit-code 1` as a backstop.

Getting pytest into Blender's Python:

- Verified locally: `PYTHONPATH=.venv/lib/python3.13/site-packages $B -b --python-use-system-env ...` imported pytest 9.2.0 from the uv venv. The venv's Python minor version must match Blender's 3.13; the uv venv here is CPython 3.13.15 and Blender's is 3.13.13.
- Also verified: `sys.path.append('<venv site-packages>')` inside `--python-expr` works. That is test-harness code, not extension code.
- Pip into the bundle (`/Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 -m pip install pytest`): not tested. That interpreter has pip 26.0.1 and its site-packages is writable by this user (verified). It modifies the signed app bundle (`codesign -dv` shows sealed resources), and the change is lost when Blender is updated. Unconfirmed whether macOS then refuses to launch the modified app.

Loading the extension under test, verified locally:

- With `--factory-startup` only the bundled add-ons are enabled. Neither the installed extension nor `--addons bl_ext.toy_repo.rs_toy` got it loaded.
- Without `--factory-startup` and with `BLENDER_USER_RESOURCES` pointing at a throwaway profile, the installed extension was enabled and importable as `bl_ext.toy_repo.rs_toy`.
- `extension_path_user` resolved into the throwaway profile.
- The real `~/Library/Application Support/Blender/5.2` repos were unchanged afterwards (`repo-list` without the variable).

Side effect seen once (unexplained): the fresh throwaway profile also listed the real profile's `lab_blender_org` repo and its `mcp` add-on. A guess, with no evidence checked: Blender copied settings from the existing user config on first start.

### (b) Pure-Python modules with plain `uv run pytest`

Yes, provided nothing on the import path imports `bpy`. Importing `rsps_toolkit.formats.model_317` executes `rsps_toolkit/__init__.py` first (standard Python package semantics), so that file must not import `bpy` at module level. Verified locally in both directions (see "Top-level `__init__.py`" above).

Options:

1. **Lazy import in the package `__init__.py`** (recommended, verified). Pure code lives in `formats/`, which only imports the standard library and its own siblings. The `blender/` layer imports `..formats`. Cost: Reload Scripts handling, as noted above.
2. **Separate non-extension core package** (e.g. `src/rs_formats/`) built as a wheel and listed in the manifest's `wheels`. This is the documented mechanism for third-party modules. The wheels page states "Wheels must be bundled unmodified from Python's package index" as a requirement (<https://docs.blender.org/manual/en/latest/advanced/extensions/python_wheels.html#requirements>), so a locally built wheel conflicts with that wording if the extension is ever submitted to extensions.blender.org. Unconfirmed whether that wording is enforced. It adds a build step and is not needed here.
3. **Adding a sibling package to `sys.path` at runtime**: forbidden by the Add-on Guidelines (Q4).

Mark the in-Blender suite so plain runs skip it: `testpaths = ["tests/unit"]` in pytest config (<https://docs.pytest.org/en/stable/reference/reference.html#confval-testpaths>), and pass `tests/blender` explicitly in the Blender command. Verified locally in the toy.
