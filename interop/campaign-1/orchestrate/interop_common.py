"""Shared coordinator orchestration for the first neutral Followee
v0.9.1 Rust<->Motoko interoperability campaign.

This module contains no expected protocol answer and no protocol
semantics: it verifies repository pins, invokes the two frozen
participants through their production-backed neutral interfaces, resolves
bundle-internal case references (envelope refs, identityRef
substitution as prescribed by CHALLENGES.md), and compares participant
results exactly. All expectations come from the bundle's coordinator
files; all participant values come from the participants.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CAMPAIGN_DIR = Path(__file__).resolve().parent.parent
BUNDLE_DIR = CAMPAIGN_DIR.parent / "v0.9.1"
PROTOCOL_REPO = CAMPAIGN_DIR.parent.parent
WORK_DIR = CAMPAIGN_DIR / "work"
RESULTS_DIR = CAMPAIGN_DIR / "results"

# Participant checkouts: overridable for machine layout, never for pins —
# the pin verification below refuses any checkout that is not the exact
# frozen revision.
RUST_REPO = Path(os.environ.get("FOLLOWEE_RS", PROTOCOL_REPO.parent / "followee-rs"))
MOTOKO_REPO = Path(
    os.environ.get(
        "FOLLOWEE_MOTOKO", PROTOCOL_REPO.parent.parent / "cleanrooms" / "followee-motoko"
    )
)

PINS = {
    "protocolRepoCommit": "c90742eb763cda5bd3c6e7d20ab1799590da489b",
    "protocolRepoTag": "v0.9.1-interop-bundle-reviewed",
    "specificationSha256": "1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71",
    "rustCommit": "8606a102bfb4f2bbfbc81e364bdf548c437bf123",
    "rustTag": "milestone-5-v0.9.1-reviewed",
    "motokoCommit": "3840d9adf07755d326d920f4711dafc4e08bcb40",
    "motokoTag": "motoko-v0.9.1-independent-freeze",
    "motokoParent": "7f2243ef729aa21e95e047becef12319ee50d765",
    "motokoGrandparent": "4bd922c301ed8f1583bcca37ac988b6493badfae",
    "motokoChallengeSha256": "e73c5697de68df7ec0f693834165bff7a1753a077959c9d9be50553b5722478e",
}

ADAPTER_DIR = CAMPAIGN_DIR / "adapters" / "rust-iface"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def verify_pins() -> dict:
    """Refuses to run against anything but the exact frozen revisions."""
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
    assert git(RUST_REPO, "rev-parse", "HEAD") == PINS["rustCommit"]
    assert (
        git(RUST_REPO, "rev-parse", PINS["rustTag"] + "^{commit}") == PINS["rustCommit"]
    )
    assert git(RUST_REPO, "status", "--porcelain") == ""
    assert git(MOTOKO_REPO, "rev-parse", "HEAD") == PINS["motokoCommit"]
    assert (
        git(MOTOKO_REPO, "rev-parse", PINS["motokoTag"] + "^{commit}")
        == PINS["motokoCommit"]
    )
    assert git(MOTOKO_REPO, "rev-parse", "HEAD^") == PINS["motokoParent"]
    assert git(MOTOKO_REPO, "rev-parse", "HEAD^^") == PINS["motokoGrandparent"]
    assert git(MOTOKO_REPO, "status", "--porcelain") == ""
    assert (
        sha256_file(MOTOKO_REPO / "outputs" / "challenge" / "challenge-results.jsonl")
        == PINS["motokoChallengeSha256"]
    )
    state.update(PINS)
    return state


# ---------------------------------------------------------------------------
# Bundle vector loading and reference materialization
# ---------------------------------------------------------------------------


def load_expected(name: str) -> dict:
    return json.loads((BUNDLE_DIR / "coordinator" / "expected" / (name + ".json")).read_text())


def load_challenge(name: str) -> dict:
    return json.loads(
        (BUNDLE_DIR / "authoring" / "vectors" / "challenge" / (name + ".json")).read_text()
    )


class ExpectedVectors:
    """Coordinator expected files with envelope-reference resolution."""

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


# ---------------------------------------------------------------------------
# Participant invocation (production-backed neutral interfaces)
# ---------------------------------------------------------------------------


def build_rust_adapter() -> Path:
    subprocess.run(
        ["cargo", "build", "--quiet", "--release"],
        cwd=ADAPTER_DIR,
        check=True,
    )
    return ADAPTER_DIR / "target" / "release" / "followee-interop-adapter-rust"


def run_rust(lines: list[str]) -> list[dict]:
    binary = build_rust_adapter()
    proc = subprocess.run(
        [str(binary)],
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


def run_motoko_driver(commands: list[str]) -> list[dict]:
    """Runs the coordinator relay driver against the frozen Motoko
    production modules (read-only imports). State is deterministic within
    one invocation; callers needing continuity across live HTTP steps
    replay the full command log, which the driver executes identically."""
    driver_dir = WORK_DIR / "motoko-driver"
    generated = driver_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    template = (
        CAMPAIGN_DIR / "adapters" / "motoko-driver" / "RelayDriver.tmpl.mo"
    ).read_text()
    src_rel = os.path.relpath(MOTOKO_REPO / "src", driver_dir)
    driver_path = driver_dir / "RelayDriver.mo"
    driver_path.write_text(template.replace("@@SRC@@", src_rel))
    embed = subprocess.run(
        [
            "node",
            str(MOTOKO_REPO / "runner" / "embed.js"),
            "lines",
            str(generated / "DriverInput.mo"),
        ],
        input="\n".join(commands) + "\n",
        text=True,
        check=True,
    )
    assert embed.returncode == 0
    moc = subprocess.run(
        ["bash", "-c", 'MOC="$(mops toolchain bin moc | tail -1)"; '
         f'exec "$MOC" -r $(mops sources) "{driver_path}"'],
        cwd=MOTOKO_REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [
        line
        for line in (moc.stdout + moc.stderr).splitlines()
        if line.startswith("{")
    ]
    if len(lines) != len(commands):
        raise RuntimeError(
            f"motoko driver: {len(lines)} outputs for {len(commands)} commands; "
            f"stderr: {moc.stderr[-2000:]}"
        )
    return [json.loads(line) for line in lines]


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
CAT_SHAPE = "interface-shape-gap"


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


def compare_members(expected: dict, actual: dict, published_members: list[str]) -> list[dict]:
    """Member-by-member exact comparison of `actual` against `expected`.

    Returns one verdict record per expected member. A member absent from
    `actual` is `notExposed` (a coverage failure to be classified by the
    caller), never silently skipped.
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


def map_motoko_record_to_rust_shape(record: dict) -> dict:
    """Documented member-name mapping between the two participants'
    `verifyRecord` `record` shapes (INTERFACE.md leaves the descriptor
    sub-shape unspecified; each participant chose a shape).

    This maps NAMES only so that VALUES can be compared exactly; it is
    reported visibly as an interface-shape gap, never as agreement
    evidence, and no value is rewritten.
    """
    descriptor = record["authorityDescriptor"]
    return {
        "authorityDescriptor": {
            "descriptorVersion": descriptor["descriptorVersion"],
            "rootPublicKeyHex": descriptor["rootPublicKeyHex"],
            "revocationCommitmentHex": descriptor["revocationCommitmentHex"],
        },
        "revocationPublicKeyHex": record["revocationPublicKeyHex"],
        "contact": record["contact"],
        "extensions": record["extensions"],
    }


def map_rust_record_to_common_shape(record: dict) -> dict:
    """Projects the Rust adapter's conformance-schema `record` shape onto
    the same comparison shape as `map_motoko_record_to_rust_shape`."""
    descriptor = record["authorityDescriptor"]
    revocation = record["revocationKey"]
    return {
        "authorityDescriptor": {
            "descriptorVersion": descriptor["descriptorVersion"],
            "rootPublicKeyHex": descriptor["rootKey"]["publicKeyHex"],
            "revocationCommitmentHex": descriptor["revocationCommitmentHex"],
        },
        "revocationPublicKeyHex": (
            None if revocation is None else revocation["publicKeyHex"]
        ),
        "contact": record["contact"],
        "extensions": record["extensions"],
    }


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def canonical_json_line(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_result(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value))


def bundle_verify_dir() -> Path:
    return BUNDLE_DIR / "verify"


def base58btc_encode(data: bytes) -> str:
    """Coordinator-side base58btc via the bundle's own interopkit (used
    only for coordinator analysis annotations, never as participant
    output)."""
    sys.path.insert(0, str(bundle_verify_dir()))
    try:
        from interopkit import base58  # type: ignore

        return base58.encode(data)
    finally:
        sys.path.pop(0)
