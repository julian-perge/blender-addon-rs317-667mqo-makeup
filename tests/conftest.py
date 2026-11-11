"""Shared temporary animation bundles use the independently recorded cache payloads."""

import json
import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/animations/2013"


@pytest.fixture
def bundle_root(tmp_path):
    manifest = json.loads((FIXTURE / "bundle-manifest.json").read_text())
    (tmp_path / "animations").mkdir()
    (tmp_path / "animations/manifest.json").write_text(json.dumps(manifest))
    for model_id, resource in manifest["models"].items():
        path = tmp_path / resource["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURE / f"raw/7/{model_id}/0.dat", path)
    for texture_id, resource in manifest["textures"].items():
        path = tmp_path / resource["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURE / f"textures/{texture_id}.png", path)
    return tmp_path
