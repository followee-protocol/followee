"""Anchored extraction of Appendix B values from the pinned specification.

Every value is located by its Appendix B subsection heading and the exact
label line that precedes it, so a transcription error in this tooling
fails loudly instead of silently extracting the wrong block.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SPEC_RELPATH = "authoring/specification/Followee-Specification.md"
SPEC_SHA256 = "1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71"

AAD = b"Followee/IdentityRecord/v1"
DESCRIPTOR_PREFIX = b"Followee/AuthorityDescriptor/v1\x00"
REVOCATION_PREFIX = b"Followee/RevocationKey/v1\x00"
PROTECTED_HEADER = bytes.fromhex("a10132")


class SpecText:
    def __init__(self, bundle_root: Path) -> None:
        path = bundle_root / SPEC_RELPATH
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != SPEC_SHA256:
            raise ValueError(
                f"pinned specification hash mismatch: {digest} != {SPEC_SHA256}"
            )
        self.text = data.decode("utf-8")

    def section(self, heading: str) -> str:
        """Return the body of one heading up to the next heading of <= depth."""
        pattern = re.compile(
            r"^(#{2,4}) " + re.escape(heading) + r"$", re.MULTILINE
        )
        match = pattern.search(self.text)
        if match is None:
            raise ValueError(f"heading not found: {heading}")
        depth = len(match.group(1))
        tail = self.text[match.end() :]
        next_heading = re.compile(r"^#{2," + str(depth) + r"} ", re.MULTILINE)
        nxt = next_heading.search(tail)
        return tail[: nxt.start()] if nxt else tail

    def labeled(self, heading: str, label: str) -> str:
        """Return the whitespace-joined block that follows `label:` in a section."""
        body = self.section(heading)
        anchor = label + ":\n"
        index = body.find(anchor)
        if index < 0:
            raise ValueError(f"label not found in {heading}: {label}")
        rest = body[index + len(anchor) :]
        lines = []
        for line in rest.split("\n"):
            if line.strip() == "" or line.strip() == "```":
                break
            lines.append(line.strip())
        if not lines:
            raise ValueError(f"empty labeled block in {heading}: {label}")
        return "".join(lines)

    def labeled_hex(self, heading: str, label: str) -> str:
        value = self.labeled(heading, label)
        if not re.fullmatch(r"[0-9a-f]+", value) or len(value) % 2:
            raise ValueError(f"non-hex block in {heading}: {label}")
        return value

    def labeled_int(self, heading: str, label: str) -> int:
        return int(self.labeled(heading, label), 10)
