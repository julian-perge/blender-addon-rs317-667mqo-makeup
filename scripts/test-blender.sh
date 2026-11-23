#!/usr/bin/env bash
# Runs the tests in tests/blender inside headless Blender, importing the package from src/ and pytest
# from the uv environment.
#
# With no arguments, BLENDER_TEST_JOBS copies of Blender (default: one per CPU core) run at the same time, and each
# runs its own share of the tests. pytest-xdist cannot do this, because it starts its workers with Blender's Python
# binary, which has no bpy. With arguments, one Blender runs pytest with them, on tests/blender unless an argument
# names a path in tests/.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
blender="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
site_packages="$(cd "$root" && uv run python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
source_folder="$root/src"
separator=":"
# Git Bash on Windows gives POSIX paths, and Blender for Windows reads Windows paths that are joined with ";".
if command -v cygpath >/dev/null 2>&1; then
  source_folder="$(cygpath -w "$source_folder")"
  site_packages="$(cygpath -w "$site_packages")"
  separator=";"
fi
cd "$root"

# Runs pytest in one Blender. The argument is the pytest arguments as the items of a Python list.
run_pytest() {
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$source_folder$separator$site_packages" "$blender" -b --factory-startup --python-use-system-env --python-exit-code 1 \
    --python-expr "import sys, pytest; sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', $1]))"
}

if [ $# -gt 0 ]; then
  # pytest runs every path it gets, so tests/blender is added only when no argument names a path in tests/.
  args="'tests/blender', "
  for arg in "$@"; do
    [[ "$arg" == tests/* ]] && args=""
  done
  for arg in "$@"; do
    args+="'${arg//\'/\\\'}', "
  done
  run_pytest "$args"
  exit
fi

# Runs one share of the tests and prints its pytest result line. The full output goes to a log, which stays only on a
# failure. tests/blender/conftest.py reads BLENDER_TEST_SHARD and keeps that share of the collected tests.
run_shard() {
  local log="$logs/share-$(($1 + 1)).log"
  if BLENDER_TEST_SHARD="$1/$jobs" run_pytest "'tests/blender'" >"$log" 2>&1; then
    echo "share $(($1 + 1)) of $jobs: $(grep -E ' (passed|skipped|deselected)' "$log" | tail -n 1)"
    rm "$log"
  else
    echo "share $(($1 + 1)) of $jobs: FAILED"
    return 1
  fi
}

jobs="${BLENDER_TEST_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc)}"
logs="$(mktemp -d)"
trap 'rm -rf "$logs"' EXIT
export root blender source_folder separator site_packages logs jobs
export -f run_pytest run_shard

status=0
seq 0 $((jobs - 1)) | xargs -P "$jobs" -I{} bash -c 'run_shard "$1"' _ {} || status=1

for log in "$logs"/*.log; do
  [ -e "$log" ] || continue
  echo
  echo "==== $(basename "$log" .log) failed ===="
  cat "$log"
done
exit "$status"
