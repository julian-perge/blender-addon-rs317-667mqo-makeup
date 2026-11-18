import csv
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/lookup-client.py"
FIXTURE = ROOT / "tests/fixtures/named_client"
SRC = FIXTURE / "src"
NAMES = FIXTURE / "client-names.tsv"

# The fixture holds excerpts of the decompiled gamepack 149. Its names are rows of the mapper's names-osrs-149.tsv,
# and its sources are trimmed copies of the vineflower output for ModelData (dv), Model (ej) and Buffer (fe).
# The expected line ranges are the lines of the fixture files, and each test also reads the lines it points at.


def run_lookup(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--names", str(NAMES), "--src", str(SRC), "--repo", str(FIXTURE), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def spans(output: str) -> list[tuple[str, int, int]]:
    result = []
    for line in output.splitlines():
        if line.startswith("  ") and not line.startswith("    ") and ".java:" in line:
            path, _, lines = line.strip().rpartition(":")
            start, _, end = lines.partition("-")
            result.append((Path(path).name, int(start), int(end)))
    return result


def test_real_name_prints_the_member_and_its_lines() -> None:
    result = run_lookup("vertexSkins")

    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == "field vertexSkins (dv.ae) [I"
    assert spans(result.stdout) == [("ModelData.java", 9, 11)]


def test_obfuscated_name_prints_every_member_with_that_name() -> None:
    # In gamepack 149, dv.ae is both a field and a method, so the pair matches both.
    result = run_lookup("dv.ae")

    assert [line for line in result.stdout.splitlines() if not line.startswith(" ")] == [
        "field vertexSkins (dv.ae) [I",
        "method light (dv.ae) (IIIII)LModel;",
    ]
    assert spans(result.stdout) == [("ModelData.java", 9, 11), ("ModelData.java", 15, 23)]


def test_class_and_member_pair_prints_the_method() -> None:
    result = run_lookup("ModelData.light")

    assert result.stdout.splitlines()[0] == "method light (dv.ae) (IIIII)LModel;"
    assert spans(result.stdout) == [("ModelData.java", 15, 23)]


def test_obfuscated_class_with_real_member_prints_the_member() -> None:
    result = run_lookup("dv.vertexSkins")

    assert spans(result.stdout) == [("ModelData.java", 9, 11)]


def test_a_class_name_prints_the_whole_class() -> None:
    result = run_lookup("Model")

    assert result.stdout.splitlines()[0] == "class Model (ej)"
    assert spans(result.stdout) == [("Model.java", 6, 15)]


def test_the_lines_of_a_span_open_the_member() -> None:
    result = run_lookup("light")

    [(name, start, end)] = spans(result.stdout)
    lines = (SRC / name).read_text().splitlines()[start - 1 : end]
    assert lines[0] == '   @ObfuscatedName("ae")'
    assert "Model light(" in lines[3]
    assert lines[-1] == "   }"
    assert len(lines) == 9


def test_a_name_with_two_matches_prints_both_with_their_own_lines() -> None:
    # Buffer has two decryptXtea overloads. They have the same real name and different obfuscated names.
    result = run_lookup("decryptXtea")

    assert [line for line in result.stdout.splitlines() if not line.startswith(" ")] == [
        "method decryptXtea (fe.as) ([I)V",
        "method decryptXtea (fe.ab) ([III)V",
    ]
    assert spans(result.stdout) == [("Buffer.java", 9, 15), ("Buffer.java", 17, 23)]


def test_a_name_with_no_match_prints_that_and_three_close_names() -> None:
    result = run_lookup("vertxSkins")

    assert result.returncode == 0
    first, second = result.stdout.splitlines()
    assert first == "no match for vertxSkins"
    close = second.removeprefix("closest names: ").split(", ")
    assert close[0] == "vertexSkins"
    assert len(close) == 3


def test_a_missing_source_folder_exits_non_zero_and_names_the_build_command(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--names", str(NAMES), "--src", str(tmp_path / "missing"), "light"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "scripts/named-client/build.sh --gamepack <path to gamepack-149.jar>" in result.stderr


def test_the_source_folder_defaults_to_the_named_client_dir_variable() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--names", str(NAMES), "light"],
        capture_output=True,
        text=True,
        env={**os.environ, "NAMED_CLIENT_DIR": str(FIXTURE)},
    )

    assert result.returncode == 0
    assert spans(result.stdout) == [("ModelData.java", 15, 23)]


def section(output: str, label: str) -> list[str]:
    """Returns the lines under `  <label>:` of the first match, up to the next line with two spaces of indent."""
    lines = output.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"  {label}:"))
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].startswith("    ")), len(lines))
    return [lines[start], *(line.strip() for line in lines[start + 1 : end])]


def test_a_member_used_in_two_other_classes_lists_both_as_callers() -> None:
    result = run_lookup("ModelData.light")

    callers = section(result.stdout, "callers")
    assert callers[0] == "  callers: 2"
    assert callers[1].startswith("NPCComposition.java:18: return var11.light(")
    assert callers[2].startswith("PlayerComposition.java:14: var8 = var18.light(")
    assert [line.split(":")[0] for line in callers[1:]] == ["NPCComposition.java", "PlayerComposition.java"]


def test_a_use_inside_the_defining_class_is_not_a_caller() -> None:
    # ModelData.java uses vertexSkins in light(), and no other file does.
    result = run_lookup("vertexSkins")

    assert section(result.stdout, "callers") == ["  callers: none"]


def test_a_method_lists_the_names_of_the_table_that_its_body_uses() -> None:
    # The body of light() also uses field1793, and that name is not in the table.
    result = run_lookup("ModelData.light")

    assert section(result.stdout, "callees") == ["  callees: boundsType, vertexSkins"]


def test_a_method_that_calls_itself_and_others_lists_them() -> None:
    result = run_lookup("ip.v")

    assert section(result.stdout, "callees") == ["  callees: getModel, light, transform"]


def test_a_member_that_is_not_a_method_has_no_callees_line() -> None:
    result = run_lookup("vertexSkins")

    assert "callees" not in result.stdout


def test_a_real_name_cited_in_the_docs_lists_the_note_and_line() -> None:
    result = run_lookup("boundsType")

    assert section(result.stdout, "notes") == ["  notes:", "docs/research/skins.md:5"]


def test_an_obfuscated_pair_cited_in_a_spec_lists_that_spec() -> None:
    # lighting.md never writes the real name light. It writes dv.ae, which is the obfuscated pair of light.
    result = run_lookup("light")

    assert section(result.stdout, "notes") == ["  notes:", "spec/lighting.md:3"]


def test_a_note_that_cites_the_real_name_or_the_pair_is_listed_once_for_each() -> None:
    result = run_lookup("vertexSkins")

    assert section(result.stdout, "notes") == ["  notes:", "docs/research/skins.md:3", "spec/lighting.md:3"]


def test_a_name_that_no_note_cites_says_so() -> None:
    result = run_lookup("modelViewportYs")

    assert "  notes: none cite this name" in result.stdout


def test_callers_stop_at_twenty_lines_and_say_how_many_more(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "Model.java").write_text(SRC.joinpath("Model.java").read_text())
    (src / "Scene.java").write_text("".join(f"x = Model.modelViewportYs[{n}];\n" for n in range(25)))

    result = run_lookup("modelViewportYs", "--src", str(src))

    callers = section(result.stdout, "callers")
    assert callers[0] == "  callers: 25"
    assert callers[-1] == "... and 5 more"
    assert len(callers) == 22


def load_module():
    spec = importlib.util.spec_from_file_location("lookup_client", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", [NAMES, ROOT / "docs/research/client-names.tsv"])
def test_the_lookup_reads_every_column_of_the_names_header(path: Path) -> None:
    module = load_module()
    with path.open(newline="") as handle:
        header = next(csv.reader(handle, delimiter="\t"))

    assert tuple(header) == module.COLUMNS
    rows = module.read_names(path)
    assert rows
    assert all(len(vars(row)) == len(header) for row in rows)


def test_a_names_file_with_another_header_is_refused(tmp_path: Path) -> None:
    module = load_module()
    wrong = tmp_path / "names.tsv"
    wrong.write_text("kind\tname\n")

    with pytest.raises(ValueError, match="header"):
        module.read_names(wrong)
