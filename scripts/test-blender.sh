#!/usr/bin/env bash
# Runs the tests in tests/blender inside headless Blender, importing the package from src/ and pytest
# from the uv environment. Extra arguments go to pytest.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
blender="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
site_packages="$(cd "$root" && uv run python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"

args=""
for arg in "$@"; do
  args+="'${arg//\'/\\\'}', "
done

cd "$root"
PYTHONPATH="$root/src:$site_packages" "$blender" -b --factory-startup --python-use-system-env --python-exit-code 1 \
  --python-expr "import sys, pytest; sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', 'tests/blender', ${args}]))"
