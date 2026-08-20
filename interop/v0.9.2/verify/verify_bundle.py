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
  the AUTHORING subset;
- the v0.9.2-r2 present-empty direct-wire fixtures: valid signatures,
  the claimed present-empty wire encodings, unreachability through the
  authoring canonicalization, and projection of the []/{}/absence
  distinction;
- the sealed twelve-file authoring aggregate (v0.9.2-r2), with the
  historical v0.9.2-r1 seal preserved in the coordinator record.
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

APPENDIX_B_HEADING = "## Appendix B. Normative test vectors"
APPENDIX_B_SHA256 = (
    "02bbaea79b26e2648d1f669f7175fbc074f90404916ab351175ce0dc8b658758"
)

# The v0.9.1 blind challenge inputs, preserved byte-for-byte: Campaign 2
# is a maintenance campaign, and the wrapper clarification requires no
# new challenge input.
CHALLENGE_INPUT_SHA256 = {
    "challenge-identities.json":
        "269c9d4a429e6fd37ad2b66d39cf9041c64ccdbc5b2372a4ad1bb0bf9969dd9e",
    "challenge-records.json":
        "fb6aaa31bf83eee9d702ff33a6fa81e4400ce3a343da9cae8c7d16052df1ffd1",
    "challenge-selection.json":
        "9aabfc8acfd1013bc8d75260b5b64b6f33fac4684d2371f59c30f864b61efde8",
}

# The sealed AUTHORING subset: SHA-256 over the path-sorted
# `sha256sum`-style lines of the twelve authoring files, paths relative
# to authoring/ with a ./ prefix. Revision 1 (v0.9.2-r1) is the
# historical seal of the subset the already-frozen participant input
# received; revision 2 (v0.9.2-r2) is the current corrected neutral
# interface seal. Both must stay recorded in
# coordinator/PRECLASSIFICATION.md; only r2 may match the tree.
AUTHORING_FILE_COUNT = 12
AUTHORING_AGGREGATE_SHA256_R1 = (
    "cec54f10520535b405c2eb11952cbe2e14976be3962cb26cacff29031c89ae6b"
)
AUTHORING_AGGREGATE_SHA256_R2 = (
    "1b6514da0c1a0c5289e0909b648b5de73a302e91b346440624badacf5747855e"
)

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
            "coordinator/transcripts/changes-premature-retained.json",
            "coordinator/transcripts/changes-reset-required.json",
            "coordinator/transcripts/info-missing-version.json",
            "coordinator/transcripts/info-missing-suite.json",
            "coordinator/transcripts/directory-duplicate-index.json",
        }
        variation = {
            "coordinator/transcripts/publish-no-change.json",
            "coordinator/transcripts/publish-no-change-diagnostic.json",
            "coordinator/transcripts/publish-losing-record.json",
        }
        if relpath == "coordinator/transcripts/TRANSCRIPTS.md":
            return "bundle-infrastructure", audience
        if relpath in illustrative:
            return "illustrative-nonnormative", audience
        if relpath in variation:
            return "permitted-diagnostic-variation", audience
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
            "version": "v0.9.2",
        },
        "pins": {
            "specificationTag": "v0.9.2-reviewed",
            "specificationTagCommit":
                "ac5a794f2fdadc13cddf5367fa3e047617e3e950",
            "specificationSha256": SPEC_SHA256,
            "appendixBSha256": APPENDIX_B_SHA256,
            "appendixBNote": "byte-identical to specification v0.9.1; "
                             "every published Appendix B vector is "
                             "unchanged",
            "previousBundle": {
                "path": "interop/v0.9.1",
                "tag": "v0.9.1-interop-bundle-reviewed",
                "commit": "c90742eb763cda5bd3c6e7d20ab1799590da489b",
            },
            "campaign1": {
                "path": "interop/campaign-1",
                "tag": "v0.9.1-interop-campaign-1",
                "commit": "515f37d86a35937b3539bfafdd671291d6abb443",
                "resultsAggregateSha256":
                    "13efa5fd8a1f4b3c34786eba0e6be7c16b1dc2f85d6585a"
                    "675183c4cda062a36",
            },
            "generatorNote": "The generator and verifier are the files "
                             "under verify/ in this inventory; their "
                             "per-file sha256 entries pin the exact "
                             "revision needed for deterministic "
                             "reproduction.",
        },
        "provenanceCategories": [
            "normative-specification", "mechanically-derived",
            "specification-determined", "challenge-input",
            "illustrative-nonnormative", "permitted-diagnostic-variation",
            "confirmed-evidence-pointer", "bundle-infrastructure",
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


@check("pinned Appendix B region is byte-identical to v0.9.1")
def check_appendix_b(root: Path) -> None:
    text = (root / SPEC_RELPATH).read_text(encoding="utf-8")
    index = text.find(APPENDIX_B_HEADING)
    if index < 0 or (index > 0 and text[index - 1] != "\n"):
        raise Failure("Appendix B heading not found at line start")
    digest = hashlib.sha256(text[index:].encode("utf-8")).hexdigest()
    if digest != APPENDIX_B_SHA256:
        raise Failure(f"Appendix B region digest {digest} != pinned "
                      f"{APPENDIX_B_SHA256}")


@check("blind challenge inputs are the v0.9.1 files, byte-for-byte")
def check_challenge_preservation(root: Path) -> None:
    directory = root / "authoring" / "vectors" / "challenge"
    for name, expected in CHALLENGE_INPUT_SHA256.items():
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if digest != expected:
            raise Failure(f"{name}: digest {digest} != preserved v0.9.1 "
                          f"input {expected}")


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
        "wire-empty-alsoKnownAs": pv.identities["alice"]["rootPublicKeyHex"],
        "wire-empty-contact-extensions":
            pv.identities["alice"]["rootPublicKeyHex"],
        "wire-empty-record-extensions":
            pv.identities["alice"]["rootPublicKeyHex"],
        "wire-empty-collections-combined":
            pv.identities["alice"]["rootPublicKeyHex"],
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
        env = case["input"].get("envelope")
        if env is None:
            # Direct-wire case: the envelope bytes are carried inline;
            # the expected digest must be the digest of the carried
            # payload.
            env_bytes = bytes.fromhex(case["input"]["envelopeHex"])
            tagged = cbor.decode_strict(env_bytes, allow_outer_tag=18)
            payload = tagged[2][2]
            digest = case["expected"]["recordBodyDigestHex"]
            if hashlib.sha256(payload).hexdigest() != digest:
                raise Failure(f"{case['id']}: inline envelope payload "
                              "digest mismatch")
            continue
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


@check("publish-response matrix is complete, self-consistent, and "
       "keeps the permitted status-1 forms byte-distinct")
def check_publish_responses(root: Path) -> None:
    from interopkit.published import wire_error_registry
    from interopkit.spec import SpecText

    registry = wire_error_registry(SpecText(root))
    doc = load_json(root, "coordinator", "expected", "publish-responses.json")
    cases = {c["id"]: c for c in doc["cases"]}
    if len(cases) != len(doc["cases"]):
        raise Failure("duplicate publish-response case ids")

    accepted: dict[tuple, str] = {}
    rejected_codes: dict[str, int | None] = {}
    for case in doc["cases"]:
        body = bytes.fromhex(case["input"]["responseHex"])
        if not cbor.is_deterministic(body):
            raise Failure(f"{case['id']}: response bytes are not "
                          "deterministic CBOR")
        decoded = cbor.decode_strict(body)
        status = decoded.get(1)
        error_code = decoded.get(2)
        expected = case["expected"]
        if expected["outcome"] == "accepted":
            if expected["status"] != str(status):
                raise Failure(f"{case['id']}: status member disagrees with "
                              "the encoded response")
            want_code = None if error_code is None else str(error_code)
            if expected["errorCode"] != want_code:
                raise Failure(f"{case['id']}: errorCode member disagrees "
                              "with the encoded response")
            accepted[(status, error_code)] = case["id"]
            # Section 15.3 is the complete v1 wire vocabulary: every
            # accepted errorCode value must be a registered member.
            if error_code is not None and error_code not in registry:
                raise Failure(f"{case['id']}: accepted errorCode "
                              f"{error_code} is not in the Section 15.3 "
                              "registry")
            # Status 1 accepts only the two no-change reasons.
            if status == 1 and error_code not in (None, 12, 13):
                raise Failure(f"{case['id']}: status 1 accepted with a "
                              "code other than losingRecord/duplicate")
            # Status 2 accepts only registered non-no-change codes.
            if status == 2 and (error_code is None or error_code in (12, 13)
                                or error_code not in registry):
                raise Failure(f"{case['id']}: status-2 acceptance outside "
                              "the registered non-no-change codes")
            if status == 0 and error_code is not None:
                raise Failure(f"{case['id']}: status 0 accepted with an "
                              "errorCode")
        else:
            rejected_codes[case["id"]] = error_code
            if expected["error"] != "schemaViolation":
                raise Failure(f"{case['id']}: rejection classification must "
                              "be schemaViolation")
            if case.get("requiredBehaviour") != (
                    "reject-complete-response-no-status-no-state-change"):
                raise Failure(f"{case['id']}: rejected case must state the "
                              "no-status/no-state-change behaviour")

    # Exactly the normative accept set (Section 12.5): status 0 bare,
    # status 1 bare or with a no-change reason, status 2 with every
    # registered non-no-change code.
    want_accept = {(0, None), (1, None), (1, 12), (1, 13)}
    want_accept |= {(2, code) for code in registry if code not in (12, 13)}
    if set(accepted) != want_accept:
        raise Failure("accepted publish-response combinations differ from "
                      f"the Section 12.5 rule: {sorted(set(accepted) ^ want_accept)}")

    # Every registered non-no-change code is individually rejected on
    # status 1; both no-change codes are rejected on status 2; status 0
    # rejects both a no-change and a rejection code; missing status-2
    # code rejected.
    for code, name in sorted(registry.items()):
        if code in (12, 13):
            if f"publish-reject-status-2-{name}" not in cases:
                raise Failure(f"missing status-2 rejection case for {name}")
        else:
            if f"publish-reject-status-1-{name}" not in cases:
                raise Failure(f"missing status-1 rejection case for {name}")
    for required in ("publish-reject-status-0-duplicate",
                     "publish-reject-status-0-identityBindingMismatch",
                     "publish-reject-status-2-missing-errorCode"):
        if required not in cases:
            raise Failure(f"missing case {required}")

    # Unregistered-value probes: the first value beyond the registered
    # range on every status, and the canonical uint64 maximum on
    # status 2 (so rejection is not a one-byte range check). Each must
    # be present, rejected, and encode a value outside the registry.
    first_unregistered = max(registry) + 1
    probes = {
        f"publish-reject-status-0-unregistered-{first_unregistered}":
            first_unregistered,
        f"publish-reject-status-1-unregistered-{first_unregistered}":
            first_unregistered,
        f"publish-reject-status-2-unregistered-{first_unregistered}":
            first_unregistered,
        "publish-reject-status-2-unregistered-uint64-max": 2**64 - 1,
    }
    for probe_id, want_code in probes.items():
        if probe_id not in cases:
            raise Failure(f"missing unregistered-code probe {probe_id}")
        if rejected_codes.get(probe_id) != want_code:
            raise Failure(f"{probe_id}: probe does not encode the "
                          f"unregistered value {want_code}, or is not "
                          "rejected")
        if want_code in registry:
            raise Failure(f"{probe_id}: probe value is registered")

    # The three accepted status-1 encodings stay byte-distinct permitted
    # forms, marked as diagnostic variation of the bare form.
    status1 = [cases[f"publish-accept-status-1-{suffix}"]
               for suffix in ("bare", "losingRecord", "duplicate")]
    bodies = [c["input"]["responseHex"] for c in status1]
    if len(set(bodies)) != 3:
        raise Failure("permitted status-1 encodings are not byte-distinct")
    for case in status1:
        if case.get("variationGroup") != "publish-status-1":
            raise Failure(f"{case['id']}: missing variationGroup")
    for case in status1[1:]:
        if case.get("comparisonRule") != "permitted-diagnostic-variation":
            raise Failure(f"{case['id']}: coded form must be classified "
                          "permitted-diagnostic-variation")
        if case.get("diagnosticVariationOf") != "publish-accept-status-1-bare":
            raise Failure(f"{case['id']}: coded form must reference the "
                          "bare form it varies from")


@check("present-empty direct-wire fixtures are valid, signed, and "
       "preserve the []/{}/absence distinction")
def check_present_empty_wire_fixtures(root: Path) -> None:
    """The v0.9.2-r2 direct-wire coverage: because the authorRecord
    input canonicalization cannot construct a present-empty optional
    array or map, those valid protocol encodings are exercised through
    verifyRecord against direct wire fixtures. Each fixture must be a
    validly signed record actually carrying the claimed present-empty
    labels, unreachable through the authoring canonicalization, and its
    expected projection must preserve the three-way distinction between
    [], {}, and absence."""
    pv = PublishedVectors(root)
    alice_pub = bytes.fromhex(pv.identities["alice"]["rootPublicKeyHex"])
    doc = load_json(root, "coordinator", "expected", "verification.json")
    cases = {c["id"]: c for c in doc["cases"]}
    # None means the label must be absent from the wire record (and
    # project to null); [] / {} mean present and empty.
    want = {
        "verify-wire-empty-alsoKnownAs":
            {"contact3": [], "contact6": None, "body8": None},
        "verify-wire-empty-contact-extensions":
            {"contact3": None, "contact6": {}, "body8": None},
        "verify-wire-empty-record-extensions":
            {"contact3": None, "contact6": None, "body8": {}},
        "verify-wire-empty-collections-combined":
            {"contact3": [], "contact6": {}, "body8": {}},
    }
    for case_id, shape in want.items():
        if case_id not in cases:
            raise Failure(f"missing present-empty wire fixture {case_id}")
        case = cases[case_id]
        if case["expected"]["outcome"] != "accepted":
            raise Failure(f"{case_id}: fixture must be accepted")
        env = bytes.fromhex(case["input"]["envelopeHex"])
        tagged = cbor.decode_strict(env, allow_outer_tag=18)
        _tag, _n, cose = tagged
        protected, unprotected, payload, signature = cose
        if protected != bytes.fromhex("a10132") or unprotected != {}:
            raise Failure(f"{case_id}: COSE profile members unexpected")
        if not ed25519.verify(alice_pub, sig_structure(payload), signature):
            raise Failure(f"{case_id}: signature does not verify")
        body = cbor.decode_strict(payload)
        contact = body[7]
        positions = (("contact label 3", contact, 3, shape["contact3"]),
                     ("contact label 6", contact, 6, shape["contact6"]),
                     ("record label 8", body, 8, shape["body8"]))
        for where, container, label, expected in positions:
            if expected is None:
                if label in container:
                    raise Failure(f"{case_id}: {where} must be absent")
            elif label not in container \
                    or container[label] != expected \
                    or type(container[label]) is not type(expected):
                raise Failure(f"{case_id}: {where} must be present and "
                              "empty on the wire")
        # The authoring canonicalization omits present-empty optional
        # collections; the canonicalized counterpart must differ.
        stripped_contact = {k: v for k, v in contact.items()
                            if v != [] and v != {}}
        stripped_body = {
            k: (stripped_contact if k == 7 else v)
            for k, v in body.items() if not (k == 8 and v == {})
        }
        if cbor.encode(stripped_body) == payload:
            raise Failure(f"{case_id}: fixture is reachable through the "
                          "authoring canonicalization")
        # The expected projection preserves the distinction.
        record = case["expected"]["record"]
        projected = {"contact3": record["contact"]["alsoKnownAs"],
                     "contact6": record["contact"]["extensions"],
                     "body8": record["extensions"]}
        for key, expected in shape.items():
            value = projected[key]
            if expected is None:
                if value is not None:
                    raise Failure(f"{case_id}: {key} must project to null")
            elif value != expected or type(value) is not type(expected):
                raise Failure(f"{case_id}: {key} projection must preserve "
                              "the present-empty value")


@check("authoring subset matches the sealed v0.9.2-r2 aggregate and "
       "the r1 seal stays recorded")
def check_authoring_seal(root: Path) -> None:
    """Recomputes the twelve-file authoring aggregate (SHA-256 over the
    path-sorted sha256sum-style lines, paths relative to authoring/
    with a ./ prefix) and pins it to the v0.9.2-r2 seal. The historical
    v0.9.2-r1 seal — the subset the already-frozen participant input
    received — must remain recorded in PRECLASSIFICATION.md alongside
    the r2 seal; overwriting its history is a failure."""
    base = root / "authoring"
    rels = sorted(
        "./" + path.relative_to(base).as_posix()
        for path in base.rglob("*") if path.is_file()
    )
    if len(rels) != AUTHORING_FILE_COUNT:
        raise Failure(f"authoring subset holds {len(rels)} files, "
                      f"expected {AUTHORING_FILE_COUNT}")
    stream = "".join(
        hashlib.sha256((base / rel[2:]).read_bytes()).hexdigest()
        + f"  {rel}\n"
        for rel in rels
    )
    aggregate = hashlib.sha256(stream.encode("ascii")).hexdigest()
    if aggregate != AUTHORING_AGGREGATE_SHA256_R2:
        raise Failure(f"authoring aggregate {aggregate} != sealed "
                      f"v0.9.2-r2 {AUTHORING_AGGREGATE_SHA256_R2}")
    preclassification = (
        root / "coordinator" / "PRECLASSIFICATION.md"
    ).read_text(encoding="utf-8")
    if AUTHORING_AGGREGATE_SHA256_R1 not in preclassification:
        raise Failure("PRECLASSIFICATION.md no longer records the "
                      "historical v0.9.2-r1 authoring seal")
    if AUTHORING_AGGREGATE_SHA256_R2 not in preclassification:
        raise Failure("PRECLASSIFICATION.md does not record the "
                      "v0.9.2-r2 authoring seal")
    revision = (
        root / "coordinator" / "AUTHORING-REVISION-2.md"
    ).read_text(encoding="utf-8")
    if "v0.9.2-r2" not in revision or "Predeclared expected impact" \
            not in revision:
        raise Failure("AUTHORING-REVISION-2.md must identify v0.9.2-r2 "
                      "and carry the predeclared impact record")


@check("coordinator-only case identifiers are absent from the "
       "AUTHORING subset")
def check_coordinator_case_id_leak(root: Path) -> None:
    """Constructed-case identifiers exist only in coordinator files.

    This complements the long-token leak check for coordinator values
    whose byte encodings are too short for the 40-hex-character rule
    (for example the publish-response wrappers)."""
    coordinator_only = ("verification.json", "selection.json",
                        "timestamps.json", "publish-responses.json")
    tokens: dict[str, str] = {}
    for name in coordinator_only:
        target = root / "authoring" / "vectors" / "published" / name
        if target.exists():
            raise Failure(f"{name} must have no authoring counterpart")
        for case in load_json(root, "coordinator", "expected", name)["cases"]:
            tokens.setdefault(case["id"], name)
    if not tokens:
        raise Failure("no coordinator-only case identifiers collected; "
                      "the check is not exercising anything")
    for path in sorted((root / "authoring").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == SPEC_RELPATH:
            continue
        text = path.read_text(encoding="utf-8")
        for token, origin in tokens.items():
            if token in text:
                raise Failure(f"{rel}: contains coordinator-only case id "
                              f"{token!r} (from {origin})")


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
                    field = ref["field"]
                    container = case.get("expected", case)
                    if field in container:
                        value = container[field]
                    elif field in case.get("input", {}):
                        value = case["input"][field]
                    else:
                        raise Failure(f"{path.name}: sameAs field "
                                      f"{field!r} not found")
                if value != side["bodyHex"]:
                    raise Failure(f"{path.name}: {side_name} sameAs mismatch")


@check("pre-Phase-3 gate and mandatory hostile-peer material is consistent")
def check_campaign_gates(root: Path) -> None:
    """The executable campaign obligations added by the coordinator
    preclassification: the premature emission/filtering gate pair, the
    minimally oversized publish case, and the mandatory info/directory
    rejection cases, each anchored in ACCEPTANCE.md."""
    pv = PublishedVectors(root)
    alice_did = pv.identities["alice"]["did"]
    b4 = pv.envelope_bytes("b4-root")
    directory = root / "coordinator" / "transcripts"

    def load(name: str) -> dict:
        return json.loads((directory / name).read_text(encoding="utf-8"))

    def body(doc: dict, side: str = "response") -> bytes:
        return bytes.fromhex(doc[side]["bodyHex"])

    # Gate G1 pair: premature retained tuple emitted by changes,
    # filtered from resolve.
    doc = load("changes-premature-retained.json")
    decoded = cbor.decode_strict(body(doc))
    entries = decoded.get(2)
    if decoded.get(1) != 0 or not isinstance(entries, list) \
            or len(entries) != 1:
        raise Failure("changes-premature-retained: response must be a "
                      "success carrying exactly one entry")
    entry = entries[0]
    if entry[0] != alice_did or entry[1] != {0: 0, 1: b4} or entry[2] != 41:
        raise Failure("changes-premature-retained: the entry must be the "
                      "retained B.4 Full tuple at lastUpdated 41")
    doc = load("resolve-premature-retained.json")
    decoded = cbor.decode_strict(body(doc))
    if decoded.get(2) != [{0: 3, 2: 10}]:
        raise Failure("resolve-premature-retained: response must carry "
                      "exactly the aligned per-DID Error(premature) result")

    # Gate G2 anchor: the minimally oversized publish case.
    doc = load("publish-record-too-large.json")
    request = body(doc, "request")
    if len(request) != 16385:
        raise Failure("publish-record-too-large: request must be exactly "
                      "16385 bytes (16 KiB + 1)")
    if cbor.decode_strict(body(doc)) != {0: 1, 1: 2, 2: 3}:
        raise Failure("publish-record-too-large: response must be status 2 "
                      "with errorCode 3 (recordTooLarge)")

    # Mandatory hostile info/directory rejection cases, fault-isolated.
    doc = load("info-missing-version.json")
    decoded = cbor.decode_strict(body(doc))
    if 1 in decoded.get(3, []) or -19 not in decoded.get(4, []):
        raise Failure("info-missing-version: label 3 must omit version 1 "
                      "while label 4 keeps suite -19")
    hostile_docs = [doc]
    doc = load("info-missing-suite.json")
    decoded = cbor.decode_strict(body(doc))
    if -19 in decoded.get(4, []) or 1 not in decoded.get(3, []):
        raise Failure("info-missing-suite: label 4 must omit suite -19 "
                      "while label 3 keeps version 1")
    hostile_docs.append(doc)
    doc = load("directory-duplicate-index.json")
    decoded = cbor.decode_strict(body(doc))
    endpoints: dict[int, str] = {}
    duplicate = False
    for item in decoded.get(2, []):
        if item[0] in endpoints and endpoints[item[0]] != item[2]:
            duplicate = True
        endpoints.setdefault(item[0], item[2])
    if not duplicate:
        raise Failure("directory-duplicate-index: one index must be "
                      "reused for a different endpoint within the same "
                      "generation")
    hostile_docs.append(doc)
    for hostile in hostile_docs:
        behaviour = hostile.get("requiredClientBehaviour", {})
        if behaviour.get("rejectCompleteResponse") is not True \
                or behaviour.get("classification") != "schemaViolation" \
                or behaviour.get("noUsableProtocolState") is not True:
            raise Failure(f"{hostile['file']}: must require complete "
                          "rejection with schemaViolation and no usable "
                          "protocol state")

    # No Campaign 2 transcript input may carry a never-issued cursor:
    # every changes-request cursor is null or one of the enumerated
    # documented values (the B.11 peer cursor and the reset-required
    # old-generation example).
    allowed_cursors = {None, b"v08-0000", b"old-gen-cursor"}
    checked_requests = 0
    for path in sorted(directory.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("operation") != "v1/changes":
            continue
        request = doc["request"]
        if "bodyHex" not in request:
            continue
        decoded_request = cbor.decode_strict(bytes.fromhex(request["bodyHex"]))
        if decoded_request.get(1) not in allowed_cursors:
            raise Failure(f"{path.name}: changes-request cursor is outside "
                          "the enumerated campaign input set; never-issued "
                          "cursors must not appear as campaign inputs")
        checked_requests += 1
    if checked_requests == 0:
        raise Failure("no changes-request transcripts found; the cursor "
                      "input check is not exercising anything")

    # Every obligation must be anchored in the acceptance protocol.
    acceptance = " ".join(
        (root / "ACCEPTANCE.md").read_text(encoding="utf-8").split())
    for needle in ("Pre-Phase-3 gates", "changes-premature-retained",
                   "resolve-premature-retained", "publish-record-too-large",
                   "info-missing-version", "info-missing-suite",
                   "directory-duplicate-index",
                   "permitted transport variation", "aborts",
                   # Gate G3 determined-cases-only restructuring:
                   "second relay instance of the same participant",
                   "No cursor forging, cursor injection, state seeding, "
                   "or test-only cursor-construction capability",
                   "excluded from every Campaign 2 input",
                   # Gate G2 evidence rule matches what Section 12.2
                   # actually exposes:
                   "contains no HTTP request-entity cap",
                   "declared pre-parse publish transport cap"):
        if needle not in acceptance:
            raise Failure(f"ACCEPTANCE.md: missing required gate text "
                          f"{needle!r}")
    # The withdrawn never-issued MUST interpretation must not reappear.
    if "watermark" in acceptance:
        raise Failure("ACCEPTANCE.md: contains withdrawn never-issued "
                      "cursor watermark language; never-issued positions "
                      "are permitted variation, not a mandatory comparison")


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
