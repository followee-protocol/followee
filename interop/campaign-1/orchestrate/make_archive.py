"""Builds the deterministic campaign result archive under `results/`.

The archive is a pure function of the recorded campaign state under
`work/` plus the verified repository pins: rebuilding it twice from the
same recorded state produces byte-identical output (verified by the
campaign gate). Phase 1 and phase 2 executions are themselves
byte-deterministic and are re-runnable to identical bytes; phase 3 live
exchanges necessarily contain relay-chosen opaque values (generations,
cursors, relay identifiers) that differ between live executions, exactly
as `authoring/NONDETERMINISM.md` prescribes — the archive records the
raw bytes of this campaign's execution.

Machine-local absolute path prefixes are redacted to `~`-relative form
so the archive carries no local layout or username.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import interop_common as ic

HOME = str(Path.home())


def redact(text: str) -> str:
    return text.replace(HOME, "~")


def copy_json(src: Path, dst: Path) -> None:
    value = json.loads(redact(src.read_text()))
    dst.write_text(ic.canonical_json(value))


def copy_jsonl(src: Path, dst: Path) -> None:
    lines = [
        ic.canonical_json_line(json.loads(redact(line)))
        for line in src.read_text().splitlines()
        if line.strip()
    ]
    dst.write_text("\n".join(lines) + "\n")


def toolchains() -> dict:
    def line(*args: str) -> str:
        return subprocess.run(args, capture_output=True, text=True).stdout.strip()

    return {
        "rustc": line("rustc", "--version"),
        "cargo": line("cargo", "--version"),
        "moc": "1.14.0 (pinned via mops toolchain)",
        "mops": line("mops", "--version").splitlines()[0] if line("mops", "--version") else "",
        "core (mops package)": "2.6.1 (exact-pinned in mops.toml / mops.lock)",
        "node": line("node", "--version"),
        "python3": sys.version.split()[0],
    }


REPRODUCTION = [
    "# From the protocol repository root, with the three frozen checkouts",
    "# at their pinned revisions (paths overridable via FOLLOWEE_RS and",
    "# FOLLOWEE_MOTOKO; every script refuses non-pinned checkouts):",
    "cd interop/v0.9.1 && python3 verify/verify_bundle.py",
    "cd interop/v0.9.1 && python3 -m unittest discover -s verify/tests",
    "cd interop/campaign-1/adapters/rust-iface && cargo test",
    "cd interop/campaign-1/orchestrate && python3 phase1.py",
    "cd interop/campaign-1/orchestrate && python3 phase2.py",
    "cd interop/campaign-1/orchestrate && python3 phase3.py",
    "cd interop/campaign-1 && python3 -m unittest discover -s orchestrate/tests -t orchestrate",
    "cd interop/campaign-1/orchestrate && python3 make_archive.py",
    "# Phase 1 and phase 2 outputs are byte-deterministic across runs;",
    "# phase 3 raw exchanges contain relay-chosen opaque values that vary",
    "# between live executions per authoring/NONDETERMINISM.md.",
]


def main() -> None:
    pins = ic.verify_pins()
    results = ic.RESULTS_DIR
    results.mkdir(parents=True, exist_ok=True)
    for stale in results.iterdir():
        stale.unlink()

    work = ic.WORK_DIR
    copy_json(work / "phase1" / "phase1-report.json", results / "phase1-report.json")
    copy_jsonl(work / "phase1" / "requests.jsonl", results / "phase1-requests.jsonl")
    copy_jsonl(
        work / "phase1" / "rust-responses.jsonl",
        results / "phase1-rust-responses.jsonl",
    )
    copy_jsonl(
        work / "phase1" / "motoko-responses.jsonl",
        results / "phase1-motoko-responses.jsonl",
    )
    copy_json(work / "phase2" / "phase2-report.json", results / "phase2-report.json")
    # The frozen Motoko challenge output is preserved byte-for-byte —
    # exactly the pre-comparison bytes, never regenerated or reformatted.
    (results / "phase2-motoko-challenge-frozen.jsonl").write_bytes(
        (work / "phase2" / "motoko-challenge-frozen.jsonl").read_bytes()
    )
    copy_jsonl(
        work / "phase2" / "rust-challenge-results.jsonl",
        results / "phase2-rust-challenge-results.jsonl",
    )
    copy_json(work / "phase3" / "phase3-report.json", results / "phase3-report.json")

    meta = {
        "campaign": "followee-interop/v0.9.1 campaign 1 (first neutral Rust<->Motoko run)",
        "pins": pins,
        "toolchains": toolchains(),
        "reproduction": REPRODUCTION,
        "scope": {
            "exercised": [
                "phase 1: all 76 interface-contract expected-vector cases "
                "on both participants (deriveIdentity, authorRecord, "
                "verifyRecord incl. all B.8/B.10/B.12 negatives and "
                "target-DID variants, nextTimestamp, selectCurrent incl. "
                "all enumerated permutations)",
                "phase 2: all 36 blind challenge cases three ways "
                "(frozen Motoko vs Rust vs coordinator derivation), "
                "cross-verification of each side's envelopes by the other, "
                "identityRef resolution, permutation invariance",
                "phase 3 rust-serves: live v1/info, v1/directory, "
                "v1/publish (statuses 0/1/2), v1/resolve (duplicates, "
                "malformed DID, invalid outer 400), v1/changes (initial "
                "enumeration, incremental update visibility, itemLimit-1 "
                "pagination, ResetRequired) with the Motoko production "
                "client/receiver on the other end",
                "phase 3 motoko-serves: live v1/publish (statuses 0/1/2) "
                "and v1/resolve (duplicates, malformed DID, invalid outer "
                "400, B.11.3 candidate scenario) with the Rust production "
                "CLI client on the other end",
                "hostile-peer client behaviour: published B.11.2, B.11.5, "
                "and B.11.7 responses against both production clients",
            ],
            "notExercised": [
                "motoko-as-relay: v1/info, v1/directory, and v1/changes "
                "serving (deferred by the frozen Motoko participant to its "
                "wire-transport milestone)",
                "motoko publish-response client decoding (coordinator "
                "byte-compared those responses instead)",
                "motoko validation of served relay-info/directory shapes "
                "(coordinator-checked)",
                "HTTP media-type/status handling as evidence for Motoko "
                "(transport shim territory)",
                "multi-relay resolver traversal, WebFinger handles, and "
                "every role beyond the operations listed above",
            ],
        },
    }
    (results / "campaign-meta.json").write_text(ic.canonical_json(meta))

    manifest = {}
    for path in sorted(results.iterdir()):
        if path.name == "MANIFEST.json":
            continue
        manifest[path.name] = {
            "sha256": ic.sha256_file(path),
            "bytes": path.stat().st_size,
        }
    (results / "MANIFEST.json").write_text(ic.canonical_json(manifest))
    print("archive files:", len(manifest) + 1)
    print("archive sha256:", ic.sha256_bytes((results / "MANIFEST.json").read_bytes()))


if __name__ == "__main__":
    main()
