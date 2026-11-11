# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Regenerate revision149-palette.json with uv run extract_palette.py [--jar PATH]."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def extract(javap: str) -> dict[str, dict[str, Any]]:
    """Interpret only the array-building instructions in hv.<clinit>."""
    body = javap.split("  static {};", 1)[1].split("\n\n", 1)[0]
    instructions = {}
    for line in body.splitlines():
        match = re.fullmatch(r"\s*(\d+):\s+(\w+)(.*)", line)
        if match:
            instructions[int(match[1])] = (match[2], match[3].strip())
    offsets = list(instructions)
    following = dict(zip(offsets, offsets[1:], strict=False))
    stack: list[Any] = []
    fields = {}
    start = pc = offsets[0]
    visited = set()
    while True:
        assert pc not in visited, f"Initializer loop at {pc}"
        visited.add(pc)
        op, arg = instructions[pc]
        if op.startswith("iconst_"):
            stack.append(-1 if op == "iconst_m1" else int(op.removeprefix("iconst_")))
        elif op in ("bipush", "sipush"):
            stack.append(int(arg))
        elif op == "dup":
            stack.append(stack[-1])
        elif op in ("newarray", "anewarray"):
            assert arg == "short" if op == "newarray" else '// class "[S"' in arg
            stack.append([0 if op == "newarray" else None for _ in range(stack.pop())])
        elif op in ("sastore", "aastore"):
            value, index, array = stack.pop(), stack.pop(), stack.pop()
            assert 0 <= index < len(array)
            if op == "sastore":
                assert -32768 <= value <= 32767
            array[index] = value
        elif op == "putstatic":
            match = re.search(r"// Field ([ajnr]):(\[\[?S)$", arg)
            assert match, f"Unexpected field at {pc}: {arg}"
            fields[match[1]] = {"offsets": [start, pc], "values": stack.pop()}
            assert not stack
            start = None
        elif op == "goto":
            pc = int(arg)
            if start is None:
                start = pc
            continue
        elif op == "return":
            assert not stack and set(fields) == {"a", "j", "n", "r"}
            return fields
        else:
            raise AssertionError(f"Unsupported instruction at {pc}: {op} {arg}")
        pc = following[pc]


def reference_tables(source: str) -> dict[str, Any]:
    tables = {}
    for field in ("field2602", "field2599", "field2600", "field2601"):
        match = re.search(rf"{field} = new short\[\](?:\[\])?(\{{.*\}});", source)
        assert match, f"Missing revision-170 literal: {field}"
        literal = re.sub(r"\(short\)", "", match[1]).replace("new short[0]", "[]")
        tables[field] = json.loads(literal.replace("{", "[").replace("}", "]"))
    return tables


def unsigned(values: list[Any]) -> list[Any]:
    return [unsigned(value) if isinstance(value, list) else value & 0xFFFF for value in values]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    jar_bytes = args.jar.read_bytes()
    command = ["javap", "-c", "-p", "-classpath", str(args.jar), "hv"]
    javap = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    assert args.jar.read_bytes() == jar_bytes, "Jar changed during extraction"
    fields = extract(javap)
    primary, secondary = fields["j"]["values"], fields["r"]["values"]
    later = reference_tables(args.reference.read_text())
    assert len(primary) == len(secondary) == 5
    assert len(fields["a"]["values"]) == len(fields["n"]["values"]) == 5
    assert len(primary[4]) == 11 and primary[4][-2:] == [0, 127]
    assert primary[:4] == later["field2599"][:4]
    assert secondary == later["field2601"]
    assert fields["a"]["values"] == later["field2602"]
    assert fields["n"]["values"] == later["field2600"]
    assert later["field2599"][4] == [*primary[4], -31821]
    tables = {}
    for name, field in (
        ("primary_sources", "a"),
        ("primary_choices", "j"),
        ("secondary_sources", "n"),
        ("secondary_choices", "r"),
    ):
        values = fields[field]["values"]
        tables[name] = {
            "field": f"hv.{field}",
            "descriptor": "[[S" if name.endswith("choices") else "[S",
            "initializer_offsets_inclusive": fields[field]["offsets"],
            "signed_short": values,
            "unsigned_short": unsigned(values),
        }
    output = {
        "schema_version": 1,
        "client_revision": 149,
        "client_class": "hv",
        "jar": {"path": str(args.jar), "sha256": hashlib.sha256(jar_bytes).hexdigest()},
        "extraction": {
            "command": command,
            "method": "Static interpretation of javap output for hv.<clinit>; no client execution.",
            "offset_units": "Bytecode offsets in hv.<clinit>, inclusive through putstatic.",
            "unsigned_conversion": "signed_short & 65535; preserves the Java short bit pattern.",
        },
        "revision170_comparison": {
            "path": str(args.reference),
            "sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            "literal_lines": [15, 18],
            "matching": "Both source arrays, primary rows 0-3 and all secondary rows match.",
            "difference": "Primary row 4 differs: revision 149 has 11 entries ending 0,127; revision 170 appends -31821 (unsigned 33715), giving 12 entries.",
            "extra_signed_short": -31821,
            "extra_unsigned_short": 33715,
        },
        "tables": tables,
    }
    destination = Path(__file__).with_name("revision149-palette.json")
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=True) + "\n")
    print("PASS: 5 primary and 5 secondary rows; primary row 4 has 11 entries ending 0,127.")
    print("PASS: revision-170 comparisons, including the extra -31821 in row 4.")
    print(f"Jar SHA-256: {output['jar']['sha256']}")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
