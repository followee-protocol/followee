#!/usr/bin/env python3
"""Check that numeric internal section references have matching headings.

This deliberately checks structural integrity only. It cannot decide whether a
reference points to the semantically correct section when that section exists.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\.?(?:\s|$)")
SINGULAR_RE = re.compile(r"\bSection\s+(\d+(?:\.\d+)*)\b")
PLURAL_RE = re.compile(
    r"\bSections\s+"
    r"(\d+(?:\.\d+)*(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)"
    r"\d+(?:\.\d+)*)*)"
)
NUMBER_RE = re.compile(r"\d+(?:\.\d+)*")
EXTERNAL_TAIL_RE = re.compile(r"^\s+of\s+(?:that\s+)?RFC\b", re.IGNORECASE)


@dataclass(frozen=True)
class Reference:
    section: str
    line: int
    column: int
    source: str


def numbered_headings(lines: list[str]) -> set[str]:
    headings: set[str] = set()
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            headings.add(match.group(1))
    return headings


def is_external_reference(line: str, match_end: int) -> bool:
    """Ignore constructions such as 'Section 4.2.1 of that RFC'."""
    return EXTERNAL_TAIL_RE.match(line[match_end:]) is not None


def section_references(lines: list[str]) -> list[Reference]:
    references: list[Reference] = []

    for line_number, line in enumerate(lines, start=1):
        for match in PLURAL_RE.finditer(line):
            if is_external_reference(line, match.end()):
                continue
            for number in NUMBER_RE.finditer(match.group(1)):
                references.append(
                    Reference(
                        section=number.group(0),
                        line=line_number,
                        column=match.start(1) + number.start() + 1,
                        source=line.rstrip(),
                    )
                )

        for match in SINGULAR_RE.finditer(line):
            if is_external_reference(line, match.end()):
                continue
            references.append(
                Reference(
                    section=match.group(1),
                    line=line_number,
                    column=match.start(1) + 1,
                    source=line.rstrip(),
                )
            )

    return references


def check_document(path: Path) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        print(f"{path}: unable to read document: {error}", file=sys.stderr)
        return 2

    headings = numbered_headings(lines)
    references = section_references(lines)
    missing = [reference for reference in references if reference.section not in headings]

    for reference in missing:
        print(
            f"{path}:{reference.line}:{reference.column}: "
            f"Section {reference.section} has no numbered heading",
            file=sys.stderr,
        )
        print(f"    {reference.source.strip()}", file=sys.stderr)

    if missing:
        print(
            f"FAILED: {len(missing)} dangling reference(s) in {path}",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {path}: {len(references)} internal section reference(s), "
        f"{len(headings)} numbered heading(s)"
    )
    return 0


def self_test() -> int:
    valid = [
        "## 1. First",
        "### 1.1 Detail",
        "## 2. Second",
        "See Section 1, Sections 1.1 and 2, and Section 4.2.1 of that RFC.",
    ]
    assert numbered_headings(valid) == {"1", "1.1", "2"}
    assert [reference.section for reference in section_references(valid)] == [
        "1.1",
        "2",
        "1",
    ]

    dangling = ["## 1. First", "See Sections 1 and 9."]
    headings = numbered_headings(dangling)
    assert [
        reference.section
        for reference in section_references(dangling)
        if reference.section not in headings
    ] == ["9"]

    print("OK: cross-reference checker self-test")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", nargs="*", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if not args.self_test and not args.documents:
        parser.error("provide at least one Markdown document or --self-test")

    status = self_test() if args.self_test else 0
    for document in args.documents:
        status = max(status, check_document(document))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
