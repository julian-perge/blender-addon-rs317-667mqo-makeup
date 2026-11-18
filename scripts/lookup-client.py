#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Finds a name of the revision 149 client in the named source tree that `scripts/named-client/build.sh` writes.

    uv run scripts/lookup-client.py <name>

`<name>` is a real name (`vertexSkins`), an obfuscated name pair (`dv.ae`) or a class and member pair
(`ModelData.light`). A single word that is not a real name is also tried as an obfuscated class (`dv`). For each match
the script prints the kind, the real name, the obfuscated name, the descriptor, and the file and line range in the
source folder.

The names come from `docs/research/client-names.tsv`. The source folder is `$NAMED_CLIENT_DIR/src`, and
`NAMED_CLIENT_DIR` defaults to `~/git/osrs-149-named`. `--names` and `--src` replace both.
"""

import argparse
import csv
import difflib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).parent.parent
COLUMNS = ("kind", "obf_class", "obf_member", "descriptor", "name", "evidence")
BUILD_COMMAND = "scripts/named-client/build.sh --gamepack <path to gamepack-149.jar>"
CLOSE_NAMES = 3
CALLER_LIMIT = 20
PRIMITIVES = {
    "B": "byte",
    "C": "char",
    "D": "double",
    "F": "float",
    "I": "int",
    "J": "long",
    "S": "short",
    "Z": "boolean",
    "V": "void",
}
OBFUSCATED_NAME = re.compile(r'^\s*@ObfuscatedName\("([^"]+)"\)')
# Vineflower indents the members of a top-level class by 3 spaces, so a method body ends at the first line that is
# exactly 3 spaces and a brace.
METHOD_END = "   }"


@dataclass(frozen=True)
class Row:
    kind: str
    obf_class: str
    obf_member: str
    descriptor: str
    name: str
    evidence: str


@dataclass(frozen=True)
class ClassFile:
    path: Path
    name: str
    start: int
    lines: list[str]


@dataclass(frozen=True)
class Hit:
    path: Path
    number: int
    text: str


@dataclass(frozen=True)
class Span:
    path: Path
    start: int
    end: int
    body: int


def read_names(path: Path) -> list[Row]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, [])
        if tuple(header) != COLUMNS:
            raise ValueError(f"{path} has the header {header}, and the lookup expects {list(COLUMNS)}")
        return [Row(*record) for record in reader if record]


def load_sources(src: Path) -> dict[Path, list[str]]:
    return {
        path: path.read_text(encoding="utf-8", errors="replace").splitlines() for path in sorted(src.rglob("*.java"))
    }


def index_classes(sources: dict[Path, list[str]]) -> dict[str, ClassFile]:
    """Maps an obfuscated class name to its file. The first `@ObfuscatedName` of a file at column 0 names the class."""
    classes: dict[str, ClassFile] = {}
    for path, lines in sources.items():
        for number, line in enumerate(lines, start=1):
            match = OBFUSCATED_NAME.match(line)
            if match and not line.startswith(" "):
                classes[match.group(1)] = ClassFile(path, path.stem, number, lines)
                break
    return classes


def find_rows(rows: list[Row], query: str) -> list[Row]:
    if "." in query:
        owner, _, member = query.partition(".")
        owner_names = {row.obf_class for row in rows if row.kind == "class" and row.name == owner} | {owner}
        return [
            row
            for row in rows
            if row.kind != "class" and row.obf_class in owner_names and member in (row.name, row.obf_member)
        ]
    return [row for row in rows if row.name == query or (row.kind == "class" and row.obf_class == query)]


def java_type(descriptor: str) -> tuple[str, str]:
    """Reads one type from the front of a descriptor and returns it with the rest."""
    dimensions = len(descriptor) - len(descriptor.lstrip("["))
    descriptor = descriptor[dimensions:]
    if descriptor[0] == "L":
        end = descriptor.index(";")
        return descriptor[1:end].replace("/", ".") + "[]" * dimensions, descriptor[end + 1 :]
    return PRIMITIVES[descriptor[0]] + "[]" * dimensions, descriptor[1:]


def method_types(descriptor: str) -> tuple[list[str], str]:
    rest = descriptor[1:]
    parameters = []
    while not rest.startswith(")"):
        parameter, rest = java_type(rest)
        parameters.append(parameter)
    return parameters, java_type(rest[1:])[0]


def simple_name(java: str) -> str:
    return java.split(".")[-1]


def split_parameters(text: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for char in text:
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current)
    types = []
    for part in parts:
        words = [word for word in part.split() if word != "final"]
        types.append(" ".join(words[:-1]))
    return types


def declaration_of(lines: list[str], first: int) -> int:
    """Returns the index of the declaration line that follows the annotation lines that start at `first`."""
    index = first
    while lines[index].lstrip().startswith("@"):
        depth = lines[index].count("(") - lines[index].count(")")
        index += 1
        while depth > 0:
            depth += lines[index].count("(") - lines[index].count(")")
            index += 1
    return index


def member_end(lines: list[str], declaration: int) -> int:
    if lines[declaration].rstrip().endswith("{"):
        for index in range(declaration + 1, len(lines)):
            if lines[index].rstrip() == METHOD_END:
                return index
    for index in range(declaration, len(lines)):
        if lines[index].rstrip().endswith(";"):
            return index
    return declaration


def parse_declaration(text: str) -> tuple[bool, str, str]:
    """Returns whether the declaration is a method, its name, and its text between the parentheses."""
    paren, equals = text.find("("), text.find("=")
    if paren != -1 and (equals == -1 or paren < equals):
        name = re.findall(r"(\w+)\s*\(", text[: paren + 1])[-1]
        return True, name, text[paren + 1 : text.rfind(")")]
    match = re.search(r"(\w+)\s*(=|;)", text)
    return False, match.group(1) if match else "", ""


def locate(row: Row, classes: dict[str, ClassFile]) -> list[Span]:
    owner = classes.get(row.obf_class)
    if owner is None:
        return []
    lines = owner.lines
    if row.kind == "class":
        end = max(index for index, line in enumerate(lines, start=1) if line.strip())
        return [Span(owner.path, owner.start, end, end)]
    found: list[tuple[Span, list[str]]] = []
    for number, line in enumerate(lines, start=1):
        match = OBFUSCATED_NAME.match(line)
        if not match or match.group(1) != row.obf_member or not line.startswith("   @"):
            continue
        declaration = declaration_of(lines, number - 1)
        is_method, name, parameters = parse_declaration(lines[declaration])
        if is_method != (row.kind == "method") or name != row.name:
            continue
        end = member_end(lines, declaration)
        found.append(
            (Span(owner.path, number, end + 1, declaration + 2), split_parameters(parameters) if is_method else [])
        )
    if len(found) > 1 and row.kind == "method":
        expected = method_types(row.descriptor)[0]
        exact = [span for span, types in found if [simple_name(t) for t in types] == [simple_name(t) for t in expected]]
        if exact:
            return exact
    return [span for span, _ in found]


def word(name: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(name)}\b")


def callers(row: Row, span: Span | None, sources: dict[Path, list[str]]) -> list[Hit]:
    """Lines of other files that contain the real name. This is a text search, so another class that has a member
    with the same name is listed too."""
    pattern = word(row.name)
    hits = []
    for path, lines in sources.items():
        if span is not None and path == span.path:
            continue
        hits.extend(
            Hit(path, number, line.strip()) for number, line in enumerate(lines, start=1) if pattern.search(line)
        )
    return hits


def callees(row: Row, span: Span, sources: dict[Path, list[str]], rows: list[Row]) -> list[str]:
    """Names of fields and methods in names.tsv that the body of a method contains."""
    if row.kind != "method":
        return []
    known = {other.name for other in rows if other.kind != "class"}
    body = "\n".join(sources[span.path][span.body - 1 : span.end])
    return sorted(name for name in known if word(name).search(body))


def citation_patterns(row: Row) -> list[re.Pattern[str]]:
    """The real name, and the obfuscated name as notes write it: `dv.ae` for a member, `dv` in code font for a class."""
    if row.kind == "class":
        return [word(row.name), re.compile(rf"(?:`|\bclass\s){re.escape(row.obf_class)}\b")]
    return [word(row.name), word(f"{row.obf_class}.{row.obf_member}")]


def citing_notes(row: Row, repo: Path) -> dict[Path, list[int]]:
    patterns = citation_patterns(row)
    notes: dict[Path, list[int]] = {}
    for folder in ("docs", "spec"):
        for path in sorted((repo / folder).rglob("*.md")):
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            numbers = [n for n, line in enumerate(lines, start=1) if any(p.search(line) for p in patterns)]
            if numbers:
                notes[path.relative_to(repo)] = numbers
    return notes


def describe(row: Row) -> str:
    if row.kind == "class":
        return f"class {row.name} ({row.obf_class})"
    return f"{row.kind} {row.name} ({row.obf_class}.{row.obf_member}) {row.descriptor}"


def print_hits(label: str, hits: list[Hit]) -> None:
    print(f"  {label}: {len(hits)}" if hits else f"  {label}: none")
    for hit in hits[:CALLER_LIMIT]:
        print(f"    {hit.path.name}:{hit.number}: {hit.text}")
    if len(hits) > CALLER_LIMIT:
        print(f"    ... and {len(hits) - CALLER_LIMIT} more")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="a real name, an obfuscated name such as dv.ae, or a class.member pair")
    parser.add_argument("--names", type=Path, default=REPO / "docs/research/client-names.tsv")
    parser.add_argument("--src", type=Path, help="the decompiled source folder, default $NAMED_CLIENT_DIR/src")
    parser.add_argument("--repo", type=Path, default=REPO, help="the folder whose docs/ and spec/ hold the notes")
    args = parser.parse_args(argv)

    named_dir = Path(os.environ.get("NAMED_CLIENT_DIR", "~/git/osrs-149-named")).expanduser()
    src = args.src or named_dir / "src"
    if not src.is_dir():
        print(f"no source folder at {src}. Build it with: {BUILD_COMMAND}", file=sys.stderr)
        return 2

    rows = read_names(args.names)
    sources = load_sources(src)
    classes = index_classes(sources)
    matches = find_rows(rows, args.name)
    if not matches:
        print(f"no match for {args.name}")
        close = difflib.get_close_matches(args.name, sorted({row.name for row in rows}), n=CLOSE_NAMES, cutoff=0)
        print("closest names: " + ", ".join(close))
        return 0
    for row in matches:
        print(describe(row))
        spans = locate(row, classes)
        if not spans:
            print("  not found in the source folder")
        for span in spans:
            print(f"  {span.path}:{span.start}-{span.end}")
        print_hits("callers", callers(row, spans[0] if spans else None, sources))
        for span in spans:
            names = callees(row, span, sources, rows)
            if row.kind == "method":
                print("  callees: " + (", ".join(names) if names else "none"))
        notes = citing_notes(row, args.repo)
        print("  notes:" if notes else "  notes: none cite this name")
        for note, numbers in notes.items():
            print(f"    {note}:" + ",".join(str(n) for n in numbers))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
