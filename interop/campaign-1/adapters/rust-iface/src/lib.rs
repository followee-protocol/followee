//! Neutral interop-interface adapter for the frozen `followee-rs`
//! participant (interop/v0.9.1 `authoring/interface/INTERFACE.md`,
//! interface protocol "1").
//!
//! This crate is a thin translation layer. It contains no Followee
//! parsing, encoding, cryptography, verification, ordering, or selection
//! logic; every protocol decision is delegated to the frozen
//! implementation's public API through the mappings in [`ops`]. It holds
//! no expected protocol answer for any case.
//!
//! Known production-surface limitation (documented, not repaired here):
//! the frozen `followee-rs` public API does not expose the raw multihash
//! bytes of a derived DID, so `deriveIdentity` results omit the
//! `multihashHex` member instead of reconstructing it in the adapter.

#![forbid(unsafe_code)]

pub mod ops;

use std::fmt;

use serde::de::{self, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::Deserialize;
use serde_json::{json, Map, Value};

/// Interface protocol version implemented by this adapter.
pub const INTERFACE_PROTOCOL: &str = "1";

/// Maximum line length in each direction (INTERFACE.md transport framing).
pub const MAX_LINE_BYTES: usize = 1024 * 1024;

/// Handshake identity, fixed at build time from the verified checkout.
pub struct Identity {
    pub implementation: &'static str,
    pub implementation_repository: &'static str,
    pub implementation_commit: &'static str,
    pub specification_commit: &'static str,
}

impl Identity {
    /// The identity embedded by `build.rs` from the verified checkout.
    pub fn from_build() -> Self {
        Identity {
            implementation: "followee-rs",
            implementation_repository: "https://github.com/followee-protocol/followee-rs",
            implementation_commit: env!("FOLLOWEE_IMPL_COMMIT"),
            specification_commit: env!("FOLLOWEE_SPEC_SHA256"),
        }
    }
}

/// JSON value restricted to the interface profile (INTERFACE.md transport
/// framing): no bare numbers and no duplicate object member names.
#[derive(Debug, Clone, PartialEq)]
pub enum StrictValue {
    Null,
    Bool(bool),
    Text(String),
    Array(Vec<StrictValue>),
    Object(Vec<(String, StrictValue)>),
}

struct StrictValueVisitor;

impl<'de> Visitor<'de> for StrictValueVisitor {
    type Value = StrictValue;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("an interface-profile JSON value (no bare numbers)")
    }

    fn visit_unit<E: de::Error>(self) -> Result<StrictValue, E> {
        Ok(StrictValue::Null)
    }

    fn visit_bool<E: de::Error>(self, v: bool) -> Result<StrictValue, E> {
        Ok(StrictValue::Bool(v))
    }

    fn visit_str<E: de::Error>(self, v: &str) -> Result<StrictValue, E> {
        Ok(StrictValue::Text(v.to_owned()))
    }

    fn visit_string<E: de::Error>(self, v: String) -> Result<StrictValue, E> {
        Ok(StrictValue::Text(v))
    }

    fn visit_i64<E: de::Error>(self, _: i64) -> Result<StrictValue, E> {
        Err(E::custom(
            "bare JSON numbers are forbidden; use decimal strings",
        ))
    }

    fn visit_u64<E: de::Error>(self, _: u64) -> Result<StrictValue, E> {
        Err(E::custom(
            "bare JSON numbers are forbidden; use decimal strings",
        ))
    }

    fn visit_f64<E: de::Error>(self, _: f64) -> Result<StrictValue, E> {
        Err(E::custom("floating-point numbers are forbidden"))
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<StrictValue, A::Error> {
        let mut items = Vec::new();
        while let Some(item) = seq.next_element::<StrictValue>()? {
            items.push(item);
        }
        Ok(StrictValue::Array(items))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<StrictValue, A::Error> {
        let mut entries: Vec<(String, StrictValue)> = Vec::new();
        while let Some(key) = map.next_key::<String>()? {
            if entries.iter().any(|(k, _)| *k == key) {
                return Err(de::Error::custom(format!(
                    "duplicate object member {key:?}"
                )));
            }
            let value = map.next_value::<StrictValue>()?;
            entries.push((key, value));
        }
        Ok(StrictValue::Object(entries))
    }
}

impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        d.deserialize_any(StrictValueVisitor)
    }
}

/// A parsed interface request envelope (INTERFACE.md).
#[derive(Debug)]
pub struct Request {
    pub interface_protocol: String,
    pub case_id: String,
    pub operation: String,
    pub input: StrictValue,
}

struct RequestVisitor;

impl<'de> Visitor<'de> for RequestVisitor {
    type Value = Request;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("an interface request object")
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Request, A::Error> {
        let mut interface_protocol: Option<String> = None;
        let mut case_id: Option<String> = None;
        let mut operation: Option<String> = None;
        let mut input: Option<StrictValue> = None;
        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "interfaceProtocol" => {
                    if interface_protocol.is_some() {
                        return Err(de::Error::duplicate_field("interfaceProtocol"));
                    }
                    interface_protocol = Some(map.next_value()?);
                }
                "caseId" => {
                    if case_id.is_some() {
                        return Err(de::Error::duplicate_field("caseId"));
                    }
                    case_id = Some(map.next_value()?);
                }
                "operation" => {
                    if operation.is_some() {
                        return Err(de::Error::duplicate_field("operation"));
                    }
                    operation = Some(map.next_value()?);
                }
                "input" => {
                    if input.is_some() {
                        return Err(de::Error::duplicate_field("input"));
                    }
                    input = Some(map.next_value()?);
                }
                other => {
                    return Err(de::Error::custom(format!(
                        "unknown object member {other:?}"
                    )));
                }
            }
        }
        Ok(Request {
            interface_protocol: interface_protocol
                .ok_or_else(|| de::Error::missing_field("interfaceProtocol"))?,
            case_id: case_id.ok_or_else(|| de::Error::missing_field("caseId"))?,
            operation: operation.ok_or_else(|| de::Error::missing_field("operation"))?,
            input: input.ok_or_else(|| de::Error::missing_field("input"))?,
        })
    }
}

impl<'de> Deserialize<'de> for Request {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        d.deserialize_map(RequestVisitor)
    }
}

fn infrastructure_error(protocol: &str, case_id: &str, symbol: &str, message: &str) -> String {
    json!({
        "interfaceProtocol": protocol,
        "caseId": case_id,
        "status": "error",
        "errorSymbol": symbol,
        "message": message,
    })
    .to_string()
}

fn hello_result(identity: &Identity) -> Value {
    let mut result = Map::new();
    result.insert("implementation".into(), identity.implementation.into());
    result.insert(
        "implementationRepository".into(),
        identity.implementation_repository.into(),
    );
    result.insert(
        "implementationCommit".into(),
        identity.implementation_commit.into(),
    );
    result.insert(
        "specificationCommit".into(),
        identity.specification_commit.into(),
    );
    result.insert("interfaceProtocols".into(), json!([INTERFACE_PROTOCOL]));
    result.insert(
        "operations".into(),
        json!([
            "hello",
            "deriveIdentity",
            "authorRecord",
            "verifyRecord",
            "strictEd25519",
            "nextTimestamp",
            "validateCbor",
            "selectCurrent"
        ]),
    );
    Value::Object(result)
}

fn operation_response(case_id: &str, outcome: Result<Value, ops::OpError>) -> String {
    match outcome {
        Ok(result) => json!({
            "interfaceProtocol": INTERFACE_PROTOCOL,
            "caseId": case_id,
            "status": "accepted",
            "result": result,
        })
        .to_string(),
        Err(ops::OpError::Rejected { error }) => json!({
            "interfaceProtocol": INTERFACE_PROTOCOL,
            "caseId": case_id,
            "status": "rejected",
            "error": error,
        })
        .to_string(),
        Err(ops::OpError::Infrastructure { symbol, message }) => {
            infrastructure_error(INTERFACE_PROTOCOL, case_id, symbol, &message)
        }
    }
}

/// Handle one raw request line (without its newline) and return the
/// response line (without a newline).
///
/// `truncated` marks a line that exceeded [`MAX_LINE_BYTES`]; the excess
/// bytes were discarded by the reader.
pub fn handle_line(identity: &Identity, raw: &[u8], truncated: bool) -> String {
    if truncated {
        return infrastructure_error(
            INTERFACE_PROTOCOL,
            "unknown",
            "adapter.lineTooLong",
            "request line exceeded the 1 MiB interface limit",
        );
    }
    if raw.starts_with(b"\xef\xbb\xbf") {
        return infrastructure_error(
            INTERFACE_PROTOCOL,
            "unknown",
            "adapter.malformedRequest",
            "request line begins with a UTF-8 byte-order mark",
        );
    }
    if raw.iter().all(|b| b.is_ascii_whitespace()) {
        return infrastructure_error(
            INTERFACE_PROTOCOL,
            "unknown",
            "adapter.malformedRequest",
            "blank protocol line",
        );
    }
    let text = match std::str::from_utf8(raw) {
        Ok(text) => text,
        Err(e) => {
            return infrastructure_error(
                INTERFACE_PROTOCOL,
                "unknown",
                "adapter.malformedRequest",
                &format!("request line is not UTF-8: {e}"),
            );
        }
    };
    let request: Request = match serde_json::from_str(text) {
        Ok(request) => request,
        Err(e) => {
            return infrastructure_error(
                INTERFACE_PROTOCOL,
                "unknown",
                "adapter.malformedRequest",
                &format!("request does not satisfy the interface JSON profile: {e}"),
            );
        }
    };
    // Responses repeat the request's interfaceProtocol and caseId exactly,
    // even on infrastructure errors.
    if request.interface_protocol != INTERFACE_PROTOCOL {
        return infrastructure_error(
            request.interface_protocol.as_str(),
            request.case_id.as_str(),
            "adapter.unsupportedProtocol",
            &format!(
                "interface protocol {:?} is not supported; this adapter speaks {:?}",
                request.interface_protocol, INTERFACE_PROTOCOL
            ),
        );
    }
    match request.operation.as_str() {
        "hello" => {
            if !matches!(&request.input, StrictValue::Object(entries) if entries.is_empty()) {
                return infrastructure_error(
                    INTERFACE_PROTOCOL,
                    request.case_id.as_str(),
                    "adapter.invalidInput",
                    "hello takes an empty input object",
                );
            }
            json!({
                "interfaceProtocol": INTERFACE_PROTOCOL,
                "caseId": request.case_id,
                "status": "accepted",
                "result": hello_result(identity),
            })
            .to_string()
        }
        "deriveIdentity" => {
            operation_response(&request.case_id, ops::derive_identity(request.input))
        }
        "authorRecord" => operation_response(&request.case_id, ops::author_record(request.input)),
        "verifyRecord" => {
            operation_response(&request.case_id, ops::verify_record_op(request.input))
        }
        "strictEd25519" => operation_response(&request.case_id, ops::strict_ed25519(request.input)),
        "nextTimestamp" => {
            operation_response(&request.case_id, ops::next_timestamp_op(request.input))
        }
        "validateCbor" => {
            operation_response(&request.case_id, ops::validate_cbor_op(request.input))
        }
        "selectCurrent" => {
            operation_response(&request.case_id, ops::select_current_op(request.input))
        }
        other => infrastructure_error(
            INTERFACE_PROTOCOL,
            request.case_id.as_str(),
            "adapter.unsupportedOperation",
            &format!("operation {other:?} is not supported"),
        ),
    }
}
