import ast
import hashlib
import json
from pathlib import Path

FIXTURES = Path(__file__).parents[1] / "fixtures/models/osrs149"


def test_osrs149_reference_closure_is_complete():
    coverage = json.loads((FIXTURES / "coverage.json").read_text())
    inventory = json.loads((FIXTURES / "inventory.json").read_text())
    assert coverage["format"] == "osrs149-static-reference"
    assert coverage["version"] == 1
    assert coverage["profile"] == "osrs-149"
    assert coverage["source"]["snapshot_id"] == 430
    assert coverage["source"]["revision"] == 149
    assert coverage["source"]["dataset_sha256"] == inventory["dataset_sha256_name_nul_per_file_digest"]
    assert coverage["source"]["client_sha256"] == "19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd"
    assert (
        coverage["source"]["inventory_sha256"] == hashlib.sha256((FIXTURES / "inventory.json").read_bytes()).hexdigest()
    )
    harness = FIXTURES.parents[1] / "Osrs149Reference.java"
    assert coverage["source"]["recorder_sha256"] == hashlib.sha256(harness.read_bytes()).hexdigest()
    records = coverage["models"]
    selected = {int(value) for value in records}
    assert set(inventory["referenced_complex_models"]) <= selected
    assert set(inventory["above63"]) <= selected
    assert set(inventory["render2_models"]) <= selected
    flags = set()
    tails = set()
    for model_id, record in records.items():
        data = (FIXTURES / record["path"]).read_bytes()
        reference_bytes = (FIXTURES / record["reference"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"], model_id
        assert hashlib.sha256(reference_bytes).hexdigest() == record["reference_sha256"], model_id
        reference = json.loads(reference_bytes)
        assert reference["id"] == int(model_id)
        assert reference["source_sha256"] == record["sha256"]
        assert reference["client_sha256"] == coverage["source"]["client_sha256"]
        if reference["encoding"] == "osrs-ffff":
            flags.add(tuple(reference["raw"]["section_flags"]))
            tails.add(reference["raw"]["tail_hex"])
    assert flags == {ast.literal_eval(value) for value in inventory["footer_flags"]}
    assert tails == set(inventory["trailing"])


def test_osrs149_icon_reference_has_replayable_inputs():
    icons = FIXTURES / "icons"
    manifest = json.loads((icons / "coverage.json").read_text())
    assert manifest["policy"] == "transparent-zero-neighbor-outside-framebuffer"
    assert manifest["viewport"] == [36, 32]
    assert {8283, 4151, 995} == set(manifest["items"])
    assert "ArrayIndexOutOfBoundsException" in (icons / "8283-original-error.txt").read_text()
    for name, sha256 in manifest["files"].items():
        assert hashlib.sha256((icons / name).read_bytes()).hexdigest() == sha256, name


def load_comparator():
    import importlib.util

    path = Path(__file__).parents[2] / "scripts" / "compare-osrs149-references.py"
    spec = importlib.util.spec_from_file_location("compare_osrs149_references", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_references(destination: Path, ids: tuple[int, ...]) -> None:
    destination.mkdir()
    for model_id in ids:
        (destination / f"{model_id}.json").write_bytes((FIXTURES / f"{model_id}.json").read_bytes())


def test_reference_comparison_detects_encoded_field_loss(tmp_path: Path):
    comparator = load_comparator()
    # 28954 has texture records and independent colours; every fixture with a tail also has the tail field.
    ids = (28954, 28634)
    copy_references(tmp_path / "expected", ids)
    copy_references(tmp_path / "actual", ids)
    assert comparator.compare(tmp_path / "expected", tmp_path / "actual") == {}

    def change(edit) -> dict:
        target = tmp_path / "actual" / f"{ids[0]}.json"
        record = json.loads((FIXTURES / f"{ids[0]}.json").read_text())
        edit(record)
        target.write_text(json.dumps(record))
        return comparator.compare(tmp_path / "expected", tmp_path / "actual")

    removed = change(lambda r: r["raw"]["texture_records"].pop())
    assert f"{ids[0]}.json" in removed
    tail = change(lambda r: r["raw"].__setitem__("tail_hex", r["raw"]["tail_hex"] + "00"))
    assert any("tail_hex" in line for line in tail[f"{ids[0]}.json"])
    colours = change(
        lambda r: r["raw"]["face_colours"].__setitem__(
            next(i for i, t in enumerate(r["raw"]["face_textures"]) if t is not None and t >= 0),
            12345,
        ),
    )
    assert any("face_colours" in line for line in colours[f"{ids[0]}.json"])
    (tmp_path / "actual" / f"{ids[1]}.json").unlink()
    assert "missing" in comparator.compare(tmp_path / "expected", tmp_path / "actual")[f"{ids[1]}.json"][0]


def test_reference_comparison_ignores_only_the_source_hash(tmp_path: Path):
    comparator = load_comparator()
    copy_references(tmp_path / "expected", (28954,))
    copy_references(tmp_path / "actual", (28954,))
    target = tmp_path / "actual" / "28954.json"
    record = json.loads(target.read_text())
    record["source_sha256"] = "0" * 64
    target.write_text(json.dumps(record))
    assert comparator.compare(tmp_path / "expected", tmp_path / "actual") == {}


def test_reference_comparison_flags_extra_files_and_compares_nan_values(tmp_path: Path):
    comparator = load_comparator()
    copy_references(tmp_path / "expected", (28954,))
    copy_references(tmp_path / "actual", (28954, 28634))
    assert comparator.compare(tmp_path / "expected", tmp_path / "actual") == {
        "28634.json": ["present only in the actual folder"]
    }
    assert comparator.differences({"a": float("nan")}, {"a": float("nan")}) == []
    assert comparator.differences({"a": 1}, {"a": 1.0}) == ["a: 1 became 1.0"]
