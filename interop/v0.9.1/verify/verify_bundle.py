#!/usr/bin/env python3
"""Deterministic verification for the Followee v0.9.1 interoperability bundle.

Usage:
  python3 verify_bundle.py                  # run every check
  python3 verify_bundle.py --write-manifest # (re)write MANIFEST.json

Stdlib-only. Imports no Followee implementation. Verifies:

- MANIFEST.json: exact file set, SHA-256 digests, sizes, provenance and
  audience assignments;
- the pinned specification copy's hash;
- byte-identical regeneration of every generated vector and transcript
  file, for both audiences, from the pinned specification;
- every reconstruction assertion in the generators (published bytes,
  lengths, digests, signatures, wrapper constructions);
- independent Ed25519 re-verification of every published envelope
  signature under its correct key;
- internal reference resolution and winner-digest consistency across
  the coordinator expectation files;
- transcript framing against the Section 12.1 operation table, body
  digest/length consistency, deterministic encoding of CBOR bodies, and
  `sameAs` equality with coordinator expected vectors;
- the independence boundary: every result-like token in the coordinator
  tree that is not published verbatim in the pinned specification is
  proven absent from the entire AUTHORING subset, and every authoring
  vector case is a value-identical subset of its coordinator case;
- blindness of the challenge files (inputs only, no expected values,
  fresh seeds disjoint from published seeds);
- absence of implementation-specific or environment-specific text in
  the AUTHORING subset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract_published_vectors  # noqa: E402
import gen_transcripts  # noqa: E402
from interopkit import cbor, ed25519  # noqa: E402
from interopkit.published import BUNDLE, PublishedVectors, sig_structure  # noqa: E402
from interopkit.spec import SPEC_RELPATH, SPEC_SHA256  # noqa: E402

CHECKS: list = []


def check(name):
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn

    return wrap


class Failure(Exception):
    pass


def bundle_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Manifest


def classify(relpath: str) -> tuple[str, str]:
    """Return (provenance, audience) for one bundle-relative path.

    Audience is a pure directory rule: exactly the files under
    ``authoring/`` are the authoring audience; everything else is
    coordinator-only. No expected value that is absent from the pinned
    specification may be classified into the authoring audience; the
    leak-proof check enforces this mechanically.
    """
    audience = "authoring" if relpath.startswith("authoring/") else "coordinator"
    if relpath.startswith("authoring/specification/"):
        return "normative-specification", audience
    if relpath.startswith("authoring/vectors/published/"):
        return "normative-specification", audience
    if relpath == "authoring/interface/INTERFACE.md":
        return "mechanically-derived", audience
    if relpath.startswith("authoring/vectors/challenge/"):
        return "challenge-input", audience
    if relpath in ("authoring/AUTHORING.md", "authoring/NONDETERMINISM.md"):
        return "bundle-infrastructure", audience
    if relpath.startswith("coordinator/expected/"):
        return "specification-determined", audience
    if relpath.startswith("coordinator/transcripts/"):
        illustrative = {
            "coordinator/transcripts/info.json",
            "coordinator/transcripts/directory.json",
            "coordinator/transcripts/changes-initial-enumeration.json",
            "coordinator/transcripts/changes-reset-required.json",
        }
        if relpath == "coordinator/transcripts/TRANSCRIPTS.md":
            return "bundle-infrastructure", audience
        if relpath in illustrative:
            return "illustrative-nonnormative", audience
        return "specification-determined", audience
    if relpath.startswith("evidence/"):
        return "confirmed-evidence-pointer", audience
    return "bundle-infrastructure", audience


def bundle_files(root: Path) -> list[str]:
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "MANIFEST.json" or "__pycache__" in rel:
            continue
        out.append(rel)
    return out


def build_manifest(root: Path) -> dict:
    files = []
    for rel in bundle_files(root):
        data = (root / rel).read_bytes()
        provenance, audience = classify(rel)
        files.append({
            "path": rel,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": str(len(data)),
            "provenance": provenance,
            "audience": audience,
        })
    return {
        "bundle": BUNDLE,
        "specification": {
            "path": SPEC_RELPATH,
            "sha256": SPEC_SHA256,
            "version": "v0.9.1",
        },
        "provenanceCategories": [
            "normative-specification", "mechanically-derived",
            "specification-determined", "challenge-input",
            "illustrative-nonnormative", "confirmed-evidence-pointer",
            "bundle-infrastructure",
        ],
        "audiences": ["authoring", "coordinator"],
        "description": "Per-file inventory. The authoring audience marks "
                       "the exact file set a fresh independent "
                       "implementation session may receive.",
        "files": files,
    }


def render(content: dict) -> bytes:
    return (json.dumps(content, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


@check("manifest file set, digests, sizes, and classifications")
def check_manifest(root: Path) -> None:
    path = root / "MANIFEST.json"
    if not path.exists():
        raise Failure("MANIFEST.json missing; run --write-manifest")
    if path.read_bytes() != render(build_manifest(root)):
        raise Failure("MANIFEST.json is not the deterministic regeneration "
                      "of the current file set")


@check("pinned specification hash")
def check_spec(root: Path) -> None:
    data = (root / SPEC_RELPATH).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SPEC_SHA256:
        raise Failure(f"specification copy hash {digest} != pinned {SPEC_SHA256}")
    repo_spec = root.parent.parent / "Followee-Specification.md"
    if repo_spec.exists() and repo_spec.read_bytes() != data:
        raise Failure("bundle specification copy differs from the "
                      "repository document")


@check("vector files (both audiences) regenerate byte-identically")
def check_published_regeneration(root: Path) -> None:
    for (audience, name), content in extract_published_vectors.build_all(root).items():
        path = extract_published_vectors.target_path(root, audience, name)
        if path.read_bytes() != extract_published_vectors.render(content):
            raise Failure(f"{audience}/{name} is not the deterministic "
                          "regeneration from the pinned specification")


@check("transcripts regenerate byte-identically")
def check_transcript_regeneration(root: Path) -> None:
    for name, content in gen_transcripts.build_all(root).items():
        path = root / "coordinator" / "transcripts" / name
        if path.read_bytes() != gen_transcripts.render(content):
            raise Failure(f"{name} is not the deterministic regeneration "
                          "from the pinned specification")


# ---------------------------------------------------------------------------
# Vector semantics


def load_json(root: Path, *parts: str) -> dict:
    return json.loads((root / Path(*parts)).read_text(encoding="utf-8"))


def resolve_ref(root: Path, ref: dict) -> dict:
    data = load_json(root, "coordinator", "expected", f"{ref['vector']}.json")
    for case in data["cases"]:
        if case["id"] == ref["case"]:
            return case
    raise Failure(f"unresolved reference: {ref}")


def envelope_of(case: dict) -> str:
    if "expected" in case and "envelopeHex" in case.get("expected", {}):
        return case["expected"]["envelopeHex"]
    return case["envelopeHex"]


@check("published envelope signatures re-verify under the correct keys")
def check_signatures(root: Path) -> None:
    pv = PublishedVectors(root)
    keys = {
        "b4-root": pv.identities["alice"]["rootPublicKeyHex"],
        "b5-root-revoked": pv.identities["alice"]["revocationPublicKeyHex"],
        "b6-alice-a": pv.identities["alice"]["rootPublicKeyHex"],
        "b6-alice-b": pv.identities["alice"]["rootPublicKeyHex"],
        "b9-bob-root": pv.identities["bob"]["rootPublicKeyHex"],
        "b8-descriptor-substitution": pv.identities["attacker"]["rootPublicKeyHex"],
        "b10-duplicate-key": pv.identities["alice"]["rootPublicKeyHex"],
        "b10-utf8-overlong": pv.identities["alice"]["rootPublicKeyHex"],
        "b10-utf8-surrogate": pv.identities["alice"]["rootPublicKeyHex"],
        "b10-utf8-above-max": pv.identities["alice"]["rootPublicKeyHex"],
        "b10-utf8-incomplete": pv.identities["alice"]["rootPublicKeyHex"],
        "b12-simple-value-16": pv.identities["alice"]["rootPublicKeyHex"],
        "b12-simple-value-32": pv.identities["alice"]["rootPublicKeyHex"],
    }
    for case_id, key_hex in keys.items():
        env = pv.envelope_bytes(case_id)
        tagged = cbor.decode_strict(env, allow_outer_tag=18)
        _tag, _n, cose = tagged
        protected, unprotected, payload, signature = cose
        if protected != bytes.fromhex("a10132") or unprotected != {}:
            raise Failure(f"{case_id}: COSE profile members unexpected")
        if not ed25519.verify(bytes.fromhex(key_hex), sig_structure(payload),
                              signature):
            raise Failure(f"{case_id}: signature does not verify")


@check("vector cross-references and winner digests are consistent")
def check_vector_references(root: Path) -> None:
    records = {c["id"]: c for c in load_json(
        root, "coordinator", "expected", "records.json")["cases"]}
    verification = load_json(root, "coordinator", "expected",
                             "verification.json")
    for case in verification["cases"]:
        env = case["input"]["envelope"]
        resolved = resolve_ref(root, env)
        envelope_of(resolved)
        if case["expected"]["outcome"] == "accepted":
            digest = case["expected"]["recordBodyDigestHex"]
            if resolved["expected"]["recordBodyDigestHex"] != digest:
                raise Failure(f"{case['id']}: digest mismatch with referenced case")
    selection = load_json(root, "coordinator", "expected", "selection.json")
    for case in selection["cases"]:
        for ref in case["input"]["candidates"]:
            resolve_ref(root, ref)
        winner = case["expected"]["winnerRecordBodyDigestHex"]
        if winner is not None:
            digests = set()
            for ref in case["input"]["candidates"]:
                resolved = resolve_ref(root, ref)
                if "expected" in resolved:
                    digests.add(resolved["expected"]["recordBodyDigestHex"])
                else:
                    digests.add(resolved["recordBodyDigestHex"])
            if winner not in digests:
                raise Failure(f"{case['id']}: winner digest is not among "
                              "candidate digests")
    permutation_groups: dict[str, set] = {}
    for case in selection["cases"]:
        group = case.get("permutationOf")
        if group:
            expected = json.dumps(case["expected"], sort_keys=True)
            permutation_groups.setdefault(group, set()).add(expected)
    for group, outcomes in permutation_groups.items():
        if len(outcomes) != 1:
            raise Failure(f"permutation group {group} has divergent expected "
                          "outcomes")
    # every record case referenced by id resolves
    for case_id in ("b4-root", "b5-root-revoked", "b6-alice-a", "b6-alice-b",
                    "b9-bob-root"):
        if case_id not in records:
            raise Failure(f"records.json missing {case_id}")


# ---------------------------------------------------------------------------
# Transcripts

OPERATIONS = {
    "v1/info": ("GET", None, "application/cbor"),
    "v1/resolve": ("POST", "application/cbor", "application/cbor"),
    "v1/directory": ("GET", None, "application/cbor"),
    "v1/publish": ("POST", "application/cose", "application/cbor"),
    "v1/changes": ("POST", "application/cbor", "application/cbor"),
}


@check("transcript framing, body digests, determinism, and sameAs references")
def check_transcripts(root: Path) -> None:
    directory = root / "coordinator" / "transcripts"
    for path in sorted(directory.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        operation = doc["operation"]
        method, request_type, response_type = OPERATIONS[operation]
        request = doc["request"]
        if request["method"] != method or request["path"] != operation:
            raise Failure(f"{path.name}: framing does not match the "
                          "Section 12.1 operation table")
        if request_type is None:
            if request.get("body") is not None or "bodyHex" in request:
                raise Failure(f"{path.name}: GET request must carry no body")
        else:
            if request.get("contentType") != request_type:
                raise Failure(f"{path.name}: request content type")
        response = doc["response"]
        if response["httpStatus"] == 200:
            if response.get("contentType") != response_type:
                raise Failure(f"{path.name}: response content type")
        for side_name, side in (("request", request), ("response", response)):
            if "bodyHex" not in side:
                continue
            body = bytes.fromhex(side["bodyHex"])
            if side["bodyLength"] != str(len(body)):
                raise Failure(f"{path.name}: {side_name} length")
            if side["bodySha256"] != hashlib.sha256(body).hexdigest():
                raise Failure(f"{path.name}: {side_name} digest")
            content_type = side.get("contentType")
            deliberately_invalid = (
                side_name == "request" and response["httpStatus"] == 400
            )
            if deliberately_invalid:
                if cbor.is_deterministic(body):
                    raise Failure(f"{path.name}: request documented as a "
                                  "CBOR-layer fault decodes cleanly")
            elif content_type == "application/cbor":
                if not cbor.is_deterministic(body):
                    raise Failure(f"{path.name}: {side_name} body is not "
                                  "deterministic CBOR")
            elif content_type == "application/cose":
                if not cbor.is_deterministic(body, allow_outer_tag=18):
                    raise Failure(f"{path.name}: {side_name} body is not a "
                                  "deterministic tagged COSE item")
            if "sameAs" in side:
                ref = side["sameAs"]
                if ref["vector"] == "wire-b11":
                    data = load_json(root, "coordinator", "expected",
                                     "wire-b11.json")
                    case = next(c for c in data["cases"]
                                if c["id"] == ref["case"])
                    value = case[ref["field"]]
                else:
                    case = resolve_ref(root, ref)
                    container = case.get("expected", case)
                    value = container[ref["field"]]
                if value != side["bodyHex"]:
                    raise Failure(f"{path.name}: {side_name} sameAs mismatch")


# ---------------------------------------------------------------------------
# Challenge blindness


PUBLISHED_SEED_PREFIXES = ("000102", "202122", "404142", "606162", "808182",
                           "a0a1a2")
FORBIDDEN_CHALLENGE_KEYS = {"expected", "expectedResult", "result", "winner",
                            "winnerRecordBodyDigestHex", "did",
                            "envelopeHex", "recordBodyCborHex",
                            "recordBodyDigestHex", "signatureHex",
                            "sigStructureHex", "authorityState"}


def _walk_keys(value: object):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _walk_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk_keys(inner)


@check("challenge files are input-only, blind, and use fresh seeds")
def check_challenges(root: Path) -> None:
    directory = root / "authoring" / "vectors" / "challenge"
    seeds: list[str] = []
    ids: set[str] = set()
    identity_names: set[str] = set()
    record_ids: set[str] = set()
    for name in ("challenge-identities.json", "challenge-records.json",
                 "challenge-selection.json"):
        doc = json.loads((directory / name).read_text(encoding="utf-8"))
        if doc.get("provenance") != "challenge-input" or doc.get("blind") is not True:
            raise Failure(f"{name}: must declare provenance challenge-input "
                          "and blind true")
        for key in _walk_keys(doc["cases"]):
            if key in FORBIDDEN_CHALLENGE_KEYS:
                raise Failure(f"{name}: forbidden output-like key {key!r}")
        for case in doc["cases"]:
            if case["id"] in ids:
                raise Failure(f"duplicate challenge case id {case['id']}")
            ids.add(case["id"])
            if name == "challenge-identities.json":
                identity_names.add(case["id"].rsplit("-", 1)[-1])
                for member in ("rootSeedHex", "revocationSeedHex"):
                    seed = case["input"][member]
                    if len(seed) != 64 or set(seed) - set("0123456789abcdef"):
                        raise Failure(f"{case['id']}: malformed seed")
                    seeds.append(seed)
            if name == "challenge-records.json":
                record_ids.add(case["id"])
                if case["identityRef"] not in identity_names:
                    raise Failure(f"{case['id']}: unknown identityRef")
            if name == "challenge-selection.json":
                if case["input"]["targetIdentityRef"] not in identity_names:
                    raise Failure(f"{case['id']}: unknown targetIdentityRef")
                for ref in case["input"]["candidates"]:
                    if ref["challengeCase"] not in record_ids:
                        raise Failure(f"{case['id']}: unresolved challengeCase "
                                      f"{ref['challengeCase']}")
    if len(set(seeds)) != len(seeds):
        raise Failure("challenge seeds are not pairwise distinct")
    for seed in seeds:
        for prefix in PUBLISHED_SEED_PREFIXES:
            if seed.startswith(prefix):
                raise Failure(f"challenge seed collides with a published "
                              f"Appendix B seed pattern: {seed[:6]}...")


# ---------------------------------------------------------------------------
# Independence boundary: no coordinator-derived result reachable from
# the AUTHORING subset


@check("no coordinator-derived value is reachable from the AUTHORING subset")
def check_leakproof(root: Path) -> None:
    """Mechanical independence rule.

    Collect every result-like byte sequence in the coordinator tree —
    maximal hexadecimal runs of 40+ characters (digests, signatures,
    bodies, envelopes, wire messages) and every ``did:flw:`` string —
    and split them into *published* (the token appears verbatim in the
    pinned specification text) and *coordinator-derived* (it does not).
    No coordinator-derived token may appear anywhere in the AUTHORING
    subset, including inside longer strings. Together with the
    audience-is-a-directory rule in classify(), this proves that no
    expected value absent from the specification is reachable from the
    authoring audience.
    """
    import re

    spec_text = (root / SPEC_RELPATH).read_text(encoding="utf-8")
    hex_run = re.compile(r"[0-9a-f]{40,}")
    did_run = re.compile(r"did:flw:[0-9A-Za-z%]+")
    # The pinned document cannot contain its own hash; that digest is
    # bundle metadata, not a derived protocol result.
    metadata_tokens = {SPEC_SHA256}

    derived: dict[str, str] = {}
    for path in sorted((root / "coordinator").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for pattern in (hex_run, did_run):
            for match in pattern.finditer(text):
                token = match.group(0)
                if token not in spec_text and token not in metadata_tokens:
                    derived.setdefault(token, rel)
    if not derived:
        raise Failure("coordinator tree contains no coordinator-derived "
                      "tokens; the leak check is not exercising anything")

    for path in sorted((root / "authoring").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == SPEC_RELPATH:
            continue
        text = path.read_text(encoding="utf-8")
        for token, origin in derived.items():
            if token in text:
                raise Failure(
                    f"{rel}: contains coordinator-derived value "
                    f"{token[:24]}... (from {origin})"
                )


@check("authoring vector members are a subset of coordinator members")
def check_authoring_projection(root: Path) -> None:
    """Every authoring vector case must be a member-for-member subset of
    the corresponding coordinator case with identical values, so the
    authoring tree can never assert anything the coordinator tree does
    not."""
    for name in ("identities.json", "records.json",
                 "envelopes-negative.json", "wire-b11.json"):
        authoring = {c["id"]: c for c in load_json(
            root, "authoring", "vectors", "published", name)["cases"]}
        full = {c["id"]: c for c in load_json(
            root, "coordinator", "expected", name)["cases"]}
        if set(authoring) != set(full):
            raise Failure(f"{name}: case sets differ between audiences")

        def subset(a: object, b: object, where: str) -> None:
            if isinstance(a, dict) and isinstance(b, dict):
                for k, v in a.items():
                    if k not in b:
                        raise Failure(f"{name}:{where}.{k} absent from "
                                      "coordinator")
                    subset(v, b[k], f"{where}.{k}")
            elif a != b:
                raise Failure(f"{name}:{where} differs from coordinator")

        for case_id, case in authoring.items():
            subset(case, full[case_id], case_id)


# ---------------------------------------------------------------------------
# AUTHORING hygiene


FORBIDDEN_AUTHORING_PATTERNS = (
    "/ho" + "me/", r"followee-rs", r"followee-conformance",
    r"\bcleanroom\b", r"\bclean-room\b", r"\bmotoko\b", r"\brust\b",
    r"\bpython\b", r"\bcargo\b", r"\badapters?\b", r"\bdifferential\b",
    r"\bpromotion\b", r"\bwhitepaper\b", "sna" + "ssy", r"\brailway\b",
    r"c:\\", r"unwrap\(",
)


@check("AUTHORING subset contains no implementation or environment traces")
def check_authoring_hygiene(root: Path) -> None:
    import re

    for path in sorted((root / "authoring").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == SPEC_RELPATH:
            continue  # the pinned normative document is verified by hash
        text = path.read_text(encoding="utf-8").lower()
        for pattern in FORBIDDEN_AUTHORING_PATTERNS:
            if re.search(pattern, text):
                raise Failure(f"{rel}: forbidden text {pattern!r}")


@check("no generated timestamps, absolute paths, or usernames in the bundle")
def check_bundle_hygiene(root: Path) -> None:
    for rel in bundle_files(root):
        if rel == SPEC_RELPATH:
            continue
        text = (root / rel).read_text(encoding="utf-8")
        needles = ("/ho" + "me/", "sna" + "ssy", "Generated" + " on",
                   "generated" + " at")
        for needle in needles:
            if needle in text:
                raise Failure(f"{rel}: forbidden text {needle!r}")


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = bundle_root()

    if args.write_manifest:
        (root / "MANIFEST.json").write_bytes(render(build_manifest(root)))
        print("wrote MANIFEST.json")
        return 0

    failures = 0
    for name, fn in CHECKS:
        try:
            fn(root)
        except Failure as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
        else:
            print(f"ok   {name}")
    if failures:
        print(f"{failures} check(s) failed")
        return 1
    print("bundle verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
