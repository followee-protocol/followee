//! Adapter transport and input-contract tests. Protocol behaviour is the
//! frozen implementation's; these tests only pin the translation layer:
//! the adapter answers infrastructure errors for contract violations and
//! never invents a protocol result.

use followee_interop_adapter_rust::{handle_line, Identity};
use serde_json::Value;

fn identity() -> Identity {
    Identity::from_build()
}

fn respond(raw: &str) -> Value {
    serde_json::from_str(&handle_line(&identity(), raw.as_bytes(), false))
        .expect("adapter output is JSON")
}

#[test]
fn hello_reports_the_frozen_pins() {
    let r =
        respond(r#"{"interfaceProtocol":"1","caseId":"handshake","operation":"hello","input":{}}"#);
    assert_eq!(r["status"], "accepted");
    assert_eq!(r["result"]["implementation"], "followee-rs");
    assert_eq!(
        r["result"]["implementationCommit"],
        "8606a102bfb4f2bbfbc81e364bdf548c437bf123"
    );
    assert_eq!(
        r["result"]["specificationCommit"],
        "1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71"
    );
}

#[test]
fn malformed_json_and_bare_numbers_are_infrastructure_errors() {
    for raw in [
        "{not json",
        r#"{"interfaceProtocol":1,"caseId":"x","operation":"hello","input":{}}"#,
        r#"{"interfaceProtocol":"1","caseId":"x","operation":"hello","input":{"n":0}}"#,
        r#"{"interfaceProtocol":"1","caseId":"x","caseId":"y","operation":"hello","input":{}}"#,
    ] {
        let r = respond(raw);
        assert_eq!(r["status"], "error", "raw: {raw:?}");
    }
}

#[test]
fn incoherent_signing_seed_is_refused_never_rekeyed() {
    let r = respond(
        r#"{"interfaceProtocol":"1","caseId":"x","operation":"authorRecord","input":{
            "rootSeedHex":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
            "revocationSeedHex":"202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f",
            "authority":"root","timestampMs":"1785589200123","validUntilMs":null,
            "contact":{"displayName":null,"summary":null,"avatar":null,"alsoKnownAs":[],
                       "services":[],"migration":null,"extensions":{}},
            "extensions":{},"signingSeed":"revocation"}}"#
            .replace('\n', " ")
            .as_str(),
    );
    assert_eq!(r["status"], "error");
    assert_eq!(r["errorSymbol"], "adapter.signingKeyMismatch");
}

#[test]
fn derive_identity_is_input_sensitive_not_echoed() {
    // The adapter holds no expected answers: flipping one seed bit must
    // change every derived member that depends on it.
    let line_a = r#"{"interfaceProtocol":"1","caseId":"a","operation":"deriveIdentity","input":{"rootSeedHex":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f","revocationSeedHex":"202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f"}}"#;
    let line_b = r#"{"interfaceProtocol":"1","caseId":"b","operation":"deriveIdentity","input":{"rootSeedHex":"010102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f","revocationSeedHex":"202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f"}}"#;
    let a = respond(line_a);
    let b = respond(line_b);
    assert_eq!(a["status"], "accepted");
    assert_eq!(b["status"], "accepted");
    assert_ne!(
        a["result"]["rootPublicKeyHex"],
        b["result"]["rootPublicKeyHex"]
    );
    assert_ne!(a["result"]["did"], b["result"]["did"]);
    assert_eq!(
        a["result"]["revocationPublicKeyHex"],
        b["result"]["revocationPublicKeyHex"]
    );
}

#[test]
fn select_current_rejects_malformed_target_with_implementation_error() {
    let r = respond(
        r#"{"interfaceProtocol":"1","caseId":"x","operation":"selectCurrent","input":{"targetDid":"did:flw:","candidateEnvelopesHex":[],"nowMs":"0","stickyAuthority":"unknown"}}"#,
    );
    assert_eq!(r["status"], "rejected");
    assert_eq!(r["error"], "invalidDid");
}
