//! Embeds the frozen participant pins into the adapter binary.
//!
//! The adapter refuses to build unless the `followee-rs` checkout it links
//! is exactly the reviewed frozen revision, so a `hello` response can
//! never advertise an unverified implementation commit.

use std::process::Command;

/// The reviewed frozen Rust participant (tag `milestone-5-v0.9.1-reviewed`).
const EXPECTED_IMPL_COMMIT: &str = "8606a102bfb4f2bbfbc81e364bdf548c437bf123";

/// SHA-256 of the pinned Followee specification v0.9.1.
const SPEC_SHA256: &str = "1c1a20c639aaf90b1bfc54b5e9ea72c49f680566ba9b12ad10615412ece3cd71";

fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR");
    let impl_dir = std::path::Path::new(&manifest_dir).join("../../../../../followee-rs");
    let output = Command::new("git")
        .arg("-C")
        .arg(&impl_dir)
        .args(["rev-parse", "HEAD"])
        .output()
        .expect("git rev-parse for the frozen followee-rs checkout");
    assert!(output.status.success(), "git rev-parse failed");
    let commit = String::from_utf8(output.stdout)
        .expect("utf8")
        .trim()
        .to_owned();
    assert_eq!(
        commit, EXPECTED_IMPL_COMMIT,
        "the linked followee-rs checkout is not the reviewed frozen revision"
    );
    println!("cargo:rustc-env=FOLLOWEE_IMPL_COMMIT={commit}");
    println!("cargo:rustc-env=FOLLOWEE_SPEC_SHA256={SPEC_SHA256}");
    println!("cargo:rerun-if-changed=build.rs");
}
