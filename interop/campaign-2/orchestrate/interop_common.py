"""Shared coordinator orchestration for Campaign 2 — the Followee
v0.9.2 (authoring revision 2) maintenance interoperability campaign
between the frozen Rust and Motoko participants.

This module contains no expected protocol answer and no protocol
semantics: it verifies repository and freeze pins, invokes the two
frozen participants through their own production neutral-interface
engines, resolves bundle-internal case references, and compares
participant results exactly. All expectations come from the bundle's
coordinator files; all participant values come from the participants.

Campaign 2 framing (ACCEPTANCE.md): this is a maintenance campaign
between reviewed implementations. Agreement is maintained-implementation
agreement under the shared neutral authoring contract, never a second
independent-convergence result.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CAMPAIGN_DIR = Path(__file__).resolve().parent.parent
BUNDLE_DIR = CAMPAIGN_DIR.parent / "v0.9.2"
PROTOCOL_REPO = CAMPAIGN_DIR.parent.parent
WORK_DIR = CAMPAIGN_DIR / "work"
RESULTS_DIR = CAMPAIGN_DIR / "results"

# Participant checkouts: overridable for machine layout (the campaign
# ran against clean temporary clones), never for pins — the pin
# verification below refuses any checkout that is not the exact frozen
# revision with a clean tree.
RUST_REPO = Path(os.environ.get("FOLLOWEE_RS", PROTOCOL_REPO.parent / "followee-rs"))
MOTOKO_REPO = Path(
    os.environ.get("FOLLOWEE_MOTOKO", PROTOCOL_REPO.parent / "followee-motoko")
)

PINS = {
    "protocolRepoCommit": "ac5a794f2fdadc13cddf5367fa3e047617e3e950",
    "protocolRepoTag": "v0.9.2-reviewed",
    "specificationSha256": (
        "47af5fbf0c4505386b4e04d948ef89d013f878ea820fb02522817661d633633a"
    ),
    # The v0.9.2 bundle is an uncommitted coordinator tree; it is pinned
    # by its sealed 12-file authoring aggregate (revision 2) and by its
    # own verifier, both re-checked before every phase.
    "authoringAggregateR2Sha256": (
        "1b6514da0c1a0c5289e0909b648b5de73a302e91b346440624badacf5747855e"
    ),
    "authoringAggregateR1Sha256": (
        "cec54f10520535b405c2eb11952cbe2e14976be3962cb26cacff29031c89ae6b"
    ),
    "rustRepository": "https://github.com/followee-protocol/followee-rs.git",
    "rustTag": "rust-v0.9.2-maintained-freeze",
    "rustTagObject": "165533f54839aba9c25e6a37e58c85a406f9a8cb",
    "rustCommit": "d865dc3fae52b3e2a54d573c298de7b01a1539c9",
    "motokoRepository": "https://github.com/followee-protocol/followee-motoko.git",
    "motokoTag": "motoko-v0.9.2-r2-maintained-freeze",
    "motokoTagObject": "527b3f0c0618d96b484f21ee641a59fec1e3ebc6",
    "motokoCommit": "bb0b0782e96bea9169ddb723815d191b58de65d7",
    # Participant-owned preserved outputs (recorded at freeze, verified
    # before any comparison).
    "motokoBlindChallengeSha256": (
        "e73c5697de68df7ec0f693834165bff7a1753a077959c9d9be50553b5722478e"
    ),
    "motokoV092ChallengeSha256": (
        "d6c4e55650c03e5382abfe2caa77c8bc56ab2514d2f366d71526ee40e96311d3"
    ),
    "motokoV092R2ChallengeSha256": (
        "5c53c78735a05d81bc6a51bb813a003a6f181e604d334f1a6972203a6913315d"
    ),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def authoring_aggregate() -> str:
    """The sealed 12-file aggregate over the bundle's authoring tree
    (same recipe as the bundle verifier and both participant records)."""
    root = BUNDLE_DIR / "authoring"
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = "./" + path.relative_to(root).as_posix()
            lines.append(f"{sha256_file(path)}  {rel}\n")
    return sha256_bytes("".join(lines).encode())


def verify_pins() -> dict:
    """Refuses to run against anything but the exact frozen revisions
    and the sealed revision-2 bundle."""
    state = {}
    assert git(PROTOCOL_REPO, "rev-parse", "HEAD") == PINS["protocolRepoCommit"]
    assert (
        git(PROTOCOL_REPO, "rev-parse", PINS["protocolRepoTag"] + "^{commit}")
        == PINS["protocolRepoCommit"]
    )
    assert (
        sha256_file(PROTOCOL_REPO / "Followee-Specification.md")
        == PINS["specificationSha256"]
    )
    assert (
        sha256_file(
            BUNDLE_DIR / "authoring" / "specification" / "Followee-Specification.md"
        )
        == PINS["specificationSha256"]
    )
    assert authoring_aggregate() == PINS["authoringAggregateR2Sha256"]

    # Rust freeze: annotated tag object, peeled commit, clean tree.
    assert git(RUST_REPO, "rev-parse", PINS["rustTag"]) == PINS["rustTagObject"]
    assert git(RUST_REPO, "cat-file", "-t", PINS["rustTag"]) == "tag"
    assert (
        git(RUST_REPO, "rev-parse", PINS["rustTag"] + "^{}") == PINS["rustCommit"]
    )
    assert git(RUST_REPO, "rev-parse", "HEAD") == PINS["rustCommit"]
    assert git(RUST_REPO, "status", "--porcelain") == ""

    # Motoko freeze: annotated tag object, peeled commit, clean tree.
    assert git(MOTOKO_REPO, "rev-parse", PINS["motokoTag"]) == PINS["motokoTagObject"]
    assert git(MOTOKO_REPO, "cat-file", "-t", PINS["motokoTag"]) == "tag"
    assert (
        git(MOTOKO_REPO, "rev-parse", PINS["motokoTag"] + "^{}")
        == PINS["motokoCommit"]
    )
    assert git(MOTOKO_REPO, "rev-parse", "HEAD") == PINS["motokoCommit"]
    assert git(MOTOKO_REPO, "status", "--porcelain") == ""

    # Participant-received authoring input equals the sealed r2 subset.
    motoko_input = MOTOKO_REPO / "inputs" / "v0.9.2-r2"
    lines = []
    for path in sorted(motoko_input.rglob("*")):
        if path.is_file():
            rel = "./" + path.relative_to(motoko_input).as_posix()
            lines.append(f"{sha256_file(path)}  {rel}\n")
    assert (
        sha256_bytes("".join(lines).encode()) == PINS["authoringAggregateR2Sha256"]
    )

    # Preserved participant outputs (never regenerated by this campaign).
    assert (
        sha256_file(MOTOKO_REPO / "outputs" / "challenge" / "challenge-results.jsonl")
        == PINS["motokoBlindChallengeSha256"]
    )
    assert (
        sha256_file(MOTOKO_REPO / "outputs" / "v0.9.2" / "challenge-results.jsonl")
        == PINS["motokoV092ChallengeSha256"]
    )
    assert (
        sha256_file(
            MOTOKO_REPO / "outputs" / "v0.9.2-r2" / "challenge-results.jsonl"
        )
        == PINS["motokoV092R2ChallengeSha256"]
    )

    # Rust participant-owned outputs match their own frozen manifest.
    manifest = json.loads(
        (RUST_REPO / "interop" / "v0.9.2" / "outputs" / "MANIFEST.json").read_text()
    )
    assert (
        manifest["authoringSubset"]["aggregateSha256"]
        == PINS["authoringAggregateR2Sha256"]
    )
    for name, digest in manifest["outputs"].items():
        actual = sha256_file(RUST_REPO / "interop" / "v0.9.2" / "outputs" / name)
        assert actual == digest, f"rust output {name} hash mismatch"

    state.update(PINS)
    return state


# ---------------------------------------------------------------------------
# Bundle vector loading and reference materialization
# ---------------------------------------------------------------------------


def load_expected(name: str) -> dict:
    return json.loads(
        (BUNDLE_DIR / "coordinator" / "expected" / (name + ".json")).read_text()
    )


def load_challenge(name: str) -> dict:
    return json.loads(
        (
            BUNDLE_DIR / "authoring" / "vectors" / "challenge" / (name + ".json")
        ).read_text()
    )


class ExpectedVectors:
    """Coordinator expected files with envelope-reference resolution.
    v0.9.2-r2 verification cases may carry the envelope inline
    (`envelopeHex`) instead of a reference (the direct-wire cases)."""

    def __init__(self) -> None:
        self.files = {
            name: load_expected(name)
            for name in (
                "identities",
                "records",
                "envelopes-negative",
                "verification",
                "selection",
                "timestamps",
                "wire-b11",
                "publish-responses",
            )
        }
        self.by_case = {
            name: {c["id"]: c for c in data["cases"]}
            for name, data in self.files.items()
        }

    def envelope_hex(self, ref: dict) -> str:
        case = self.by_case[ref["vector"]][ref["case"]]
        field = ref.get("field", "envelopeHex")
        if field in case:
            return case[field]
        return case["expected"][field]

    def verification_envelope_hex(self, case: dict) -> str:
        if "envelopeHex" in case["input"]:
            return case["input"]["envelopeHex"]
        return self.envelope_hex(case["input"]["envelope"])


# ---------------------------------------------------------------------------
# Participant invocation (production neutral-interface engines)
# ---------------------------------------------------------------------------

RUST_BIN = RUST_REPO / "target" / "release" / "followee"


def build_rust() -> Path:
    subprocess.run(
        ["cargo", "build", "--quiet", "--release", "--locked", "--bin", "followee"],
        cwd=RUST_REPO,
        check=True,
    )
    return RUST_BIN


def run_rust(lines: list[str]) -> list[dict]:
    build_rust()
    proc = subprocess.run(
        [
            str(RUST_BIN),
            "interop",
            "--implementation-commit",
            PINS["rustCommit"],
        ],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_responses(proc.stdout, len(lines), "rust")


def run_motoko(lines: list[str]) -> list[dict]:
    proc = subprocess.run(
        [str(MOTOKO_REPO / "runner" / "run.sh")],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
        cwd=MOTOKO_REPO,
    )
    return _parse_responses(proc.stdout, len(lines), "motoko")


def _parse_responses(stdout: str, expected_count: int, who: str) -> list[dict]:
    responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if len(responses) != expected_count:
        raise RuntimeError(
            f"{who}: {len(responses)} responses for {expected_count} requests"
        )
    return responses


def request_line(case_id: str, operation: str, input_obj: dict) -> str:
    return json.dumps(
        {
            "interfaceProtocol": "1",
            "caseId": case_id,
            "operation": operation,
            "input": input_obj,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# Comparison: exact equality, visible classifications, no normalization
# ---------------------------------------------------------------------------

# Section 20.4 reporting categories for disagreements.
CAT_ACCEPTANCE = "acceptance-rejection-disagreement"
CAT_SYMBOLIC = "permitted-symbolic-difference"
CAT_AMBIGUITY = "unresolved-specification-ambiguity"
# Non-disagreement annotations.
CAT_COVERAGE = "coverage-limitation"
CAT_DIAGNOSTIC = "permitted-diagnostic-variation"
CAT_TRANSPORT = "permitted-transport-variation"


def strip_diagnostic(value):
    """Removes namespaced `diagnostic` members (excluded from equality by
    the interface contract). Nothing else is altered."""
    if isinstance(value, dict):
        return {
            k: strip_diagnostic(v) for k, v in value.items() if k != "diagnostic"
        }
    if isinstance(value, list):
        return [strip_diagnostic(v) for v in value]
    return value


def compare_members(
    expected: dict, actual: dict, published_members: list[str]
) -> list[dict]:
    """Member-by-member exact comparison of `actual` against `expected`.

    Returns one verdict record per expected member. A member absent from
    `actual` is `notExposed` (a coverage failure to be classified by the
    caller), never silently skipped. The v0.9.2-r2 `record` member is a
    deep structure compared exactly like every other member: the
    interface contract now pins its complete shape, so no name mapping
    exists in this campaign.
    """
    verdicts = []
    for member, want in expected.items():
        provenance = (
            "normative-specification"
            if member in (published_members or [])
            else "specification-determined"
        )
        if member not in actual:
            verdicts.append(
                {"member": member, "verdict": "notExposed", "provenance": provenance}
            )
            continue
        got = strip_diagnostic(actual[member])
        verdicts.append(
            {
                "member": member,
                "verdict": "match" if got == want else "mismatch",
                "provenance": provenance,
                **({} if got == want else {"expected": want, "actual": got}),
            }
        )
    return verdicts


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def canonical_json_line(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_result(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value))


def bundle_verify_dir() -> Path:
    return BUNDLE_DIR / "verify"


def run_bundle_verifier() -> None:
    """The coordinator bundle's own complete verification, re-run before
    any phase consumes an expectation."""
    subprocess.run(
        [sys.executable, str(bundle_verify_dir() / "verify_bundle.py")],
        check=True,
        capture_output=True,
        cwd=BUNDLE_DIR,
    )
