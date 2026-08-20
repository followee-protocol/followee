"""Builds the deterministic Campaign 2 results archive.

Copies the phase, gate, and raw comparison outputs from `work/` into
`results/`, redacting machine-local absolute paths (the participant
checkout and work locations) to stable `~`-relative placeholders, and
writes `campaign-meta.json` plus a `MANIFEST.json` with per-file
SHA-256 digests and the aggregate. The archive contains no wall-clock
value: the deterministic phase-1/2 material is byte-stable across
reruns, and the phase-3/gate raw exchanges record this campaign's
execution (relay-chosen opaque values differ between live executions,
exactly as NONDETERMINISM.md prescribes).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic

REDACTIONS = [
    (re.escape(str(ic.RUST_REPO)), "~/followee-rs"),
    (re.escape(str(ic.MOTOKO_REPO)), "~/followee-motoko"),
    (re.escape(str(ic.WORK_DIR)), "~/campaign-2-work"),
    (re.escape(str(ic.PROTOCOL_REPO)), "~/followee"),
    (r"/tmp/[A-Za-z0-9_./-]*?/campaign2", "~"),
    (r"/home/[A-Za-z0-9_-]+", "~"),
]


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = re.sub(pattern, replacement, text)
    return text


ARCHIVE_FILES = {
    "phase1-report.json": ic.WORK_DIR / "phase1" / "phase1-report.json",
    "phase1-requests.jsonl": ic.WORK_DIR / "phase1" / "requests.jsonl",
    "phase1-rust-responses.jsonl": ic.WORK_DIR / "phase1" / "rust-responses.jsonl",
    "phase1-motoko-responses.jsonl": ic.WORK_DIR / "phase1" / "motoko-responses.jsonl",
    "phase2-report.json": ic.WORK_DIR / "phase2" / "phase2-report.json",
    "phase2-motoko-challenge-frozen-r2.jsonl": ic.WORK_DIR / "phase2" / "motoko-challenge-frozen-r2.jsonl",
    "phase2-cross-verification-raw.json": ic.WORK_DIR / "phase2" / "cross-verification-raw.json",
    "gates-report.json": ic.WORK_DIR / "gates" / "gates-report.json",
    "phase3-report.json": ic.WORK_DIR / "phase3" / "phase3-report.json",
}
# The frozen Rust challenge responses preserved pre-comparison.
for group in ("challenge-identities", "challenge-records", "challenge-verify", "challenge-selection"):
    ARCHIVE_FILES[f"phase2-rust-frozen-{group}.responses.ndjson"] = (
        ic.WORK_DIR / "phase2" / f"rust-frozen-{group}.responses.ndjson"
    )


def campaign_meta() -> dict:
    return {
        "campaign": 2,
        "bundle": "followee-interop/v0.9.2 (authoring revision 2)",
        "framing": (
            "Maintenance interoperability campaign between reviewed "
            "implementations. Both participants received the identical "
            "sealed v0.9.2-r2 authoring subset; agreement is "
            "maintained-implementation agreement under the shared neutral "
            "authoring contract, never a second independent-convergence "
            "result. The independence evidence remains Campaign 1 and the "
            "motoko-v0.9.1-independent-freeze ancestry."
        ),
        "pins": ic.PINS,
        "toolchains": {
            "rust": "rustc/cargo 1.97.1 (rust-toolchain.toml pin), locked dependencies",
            "motoko": "moc 1.14.0 via mops toolchain, mops CLI 2.14.1 (API 1.3), core 2.6.1 exact-pinned",
            "node": "v24.17.0 (byte-transport shim/bridge only)",
            "python": "3.10 stdlib only (coordinator orchestration)",
        },
        "participantLocalGates": {
            "rust": "cargo fmt --check clean; cargo clippy --release --all-targets -D warnings clean; cargo test --release: 25 suites, 331 tests, 0 failures",
            "motoko": "mops check clean; mops format --check clean; mops test: 17 files, 213 tests, all passing",
        },
        "coordinatorGates": {
            "bundleVerifier": "19 checks passed (re-run before phases 1 and 3 and at archive time)",
            "bundleTests": "52 tests passed",
            "campaignTamperSuite": "13 tests passed",
            "phase12Determinism": "phases 1 and 2 re-executed end to end; all reports and raw responses byte-identical",
        },
        "reproduction": {
            "phase1": "FOLLOWEE_RS=<checkout> FOLLOWEE_MOTOKO=<checkout> python3 orchestrate/phase1.py",
            "phase2": "FOLLOWEE_RS=<checkout> FOLLOWEE_MOTOKO=<checkout> python3 orchestrate/phase2.py",
            "gates": "FOLLOWEE_RS=<checkout> FOLLOWEE_MOTOKO=<checkout> python3 orchestrate/gates.py",
            "phase3": "FOLLOWEE_RS=<checkout> FOLLOWEE_MOTOKO=<checkout> python3 orchestrate/phase3.py",
            "tamperSuite": "FOLLOWEE_RS=<checkout> FOLLOWEE_MOTOKO=<checkout> python3 -m unittest discover -s orchestrate/tests",
            "archive": "python3 orchestrate/make_archive.py",
            "note": (
                "Checkouts are clean temporary clones at the exact frozen "
                "tags (verified by every script). Phase-3 and gate raw "
                "exchanges contain relay-chosen opaque values that differ "
                "between live executions (NONDETERMINISM.md); the archive "
                "records this campaign's execution."
            ),
        },
        "scope": (
            "Exercised: the nine interface operations on both participants "
            "against every coordinator expectation including the v0.9.2 "
            "publish-response matrix and the v0.9.2-r2 direct-wire "
            "present-empty cases; frozen challenge maintenance comparison "
            "with live cross-verification; gates G1-G3 live in both "
            "directions; live HTTP/CBOR exchange in both directions over "
            "all five relay operations (info, directory, publish with "
            "statuses 0/1-bare/1-coded/2 and the losing and oversized "
            "cases, resolve with duplicates and a malformed DID, changes "
            "with initial/incremental/pagination/exactly-once), hostile-peer "
            "material to both serving sides and both production client "
            "paths, the premature-retention contrast in both directions, "
            "and challenge-authored state crossing the wire in both "
            "directions. Not exercised: multi-relay resolver traversal "
            "beyond the single-relay Ref/directory rejection path, "
            "WebFinger handles, concurrency behaviour, and public "
            "(non-loopback) deployment."
        ),
    }


def build() -> dict:
    ic.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for name, source in sorted(ARCHIVE_FILES.items()):
        text = redact(source.read_text())
        (ic.RESULTS_DIR / name).write_text(text)
    meta = campaign_meta()
    (ic.RESULTS_DIR / "campaign-meta.json").write_text(ic.canonical_json(meta))
    for path in sorted(ic.RESULTS_DIR.iterdir()):
        if path.name == "MANIFEST.json" or not path.is_file():
            continue
        manifest[path.name] = {
            "sha256": ic.sha256_file(path),
            "bytes": path.stat().st_size,
        }
    aggregate_lines = "".join(
        f"{entry['sha256']}  ./{name}\n" for name, entry in sorted(manifest.items())
    )
    manifest_doc = {
        "campaign": 2,
        "files": manifest,
        "aggregateSha256": ic.sha256_bytes(aggregate_lines.encode()),
    }
    (ic.RESULTS_DIR / "MANIFEST.json").write_text(ic.canonical_json(manifest_doc))
    return manifest_doc


if __name__ == "__main__":
    manifest = build()
    print("archive files:", len(manifest["files"]))
    print("aggregate sha256:", manifest["aggregateSha256"])
