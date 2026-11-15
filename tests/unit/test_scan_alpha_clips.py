import os
import subprocess
import sys
from pathlib import Path

import pytest

SNAPSHOT_430 = Path(os.environ.get("RSPS_SNAPSHOT_430_CACHE", "")).expanduser()
HAS_SNAPSHOT_430 = "RSPS_SNAPSHOT_430_CACHE" in os.environ and SNAPSHOT_430.is_dir()
SCRIPT = Path(__file__).parents[2] / "scripts/scan-alpha-clips.py"


@pytest.mark.skipif(not HAS_SNAPSHOT_430, reason="RSPS_SNAPSHOT_430_CACHE does not name a snapshot 430 cache folder")
def test_scan_of_snapshot_430_finds_only_sequence_3364() -> None:
    # The fixture README says 3364 is the only one of the 217 player clips with a face alpha transform that gives the
    # player's face labels more than one curve.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--cache", str(SNAPSHOT_430)], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == ["3364: 0 1 2 4 9 10 11 12 13 14 15 16 17 22 27 | 18 19 20 21 23 24 25 26"]
    assert result.stderr.strip() == "217 player clips have a face alpha transform"
