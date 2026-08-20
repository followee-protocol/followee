/// Coordinator gate driver for the Motoko-serving direction of the
/// pre-Phase-3 gates (ACCEPTANCE.md G1/G3) and the Phase 3 step 6a
/// premature-retention contrast.
///
/// This file is coordinator campaign glue in the exact sense of the
/// participant's own `shim/RelayNode.mo`: every protocol decision —
/// method and path classification, media types, bounds, CBOR,
/// admission, status selection, cursors, error and HTTP-status
/// decisions, exact response bytes — is made by the frozen production
/// modules (`RelayHttp`, `RelayServe`). The differences from
/// `RelayNode.mo` are scenario configuration only, all in territory
/// the specification leaves to the relay or the test environment:
///
/// - the relay clock is an explicit per-call `nowMs` argument (the
///   gate scenarios pin serving clocks; `RelayHttp.handle` takes the
///   clock as an explicit production parameter);
/// - the opaque relay/cursor-generation identifiers are configurable
///   test constants, so a second instance of the same participant has
///   its own independently configured generation (the Gate G3
///   foreign-generation probe is a cursor genuinely returned by that
///   second instance, never forged);
/// - no client, tamper, or pending-state machinery is included.
///
/// It is materialized under the participant checkout's gitignored
/// `runner/generated/` directory (the same place the participant's own
/// runner writes its embeddings), so the frozen tree stays clean.
import Prim "mo:⛔";
import Text "mo:core/Text";
import Char "mo:core/Char";
import Array "mo:core/Array";
import Blob "mo:core/Blob";
import Nat "mo:core/Nat";
import Nat8 "mo:core/Nat8";
import List "mo:core/List";
import Runtime "mo:core/Runtime";
import Hex "../../src/lib/Hex";
import RelayServe "../../src/followee/RelayServe";
import RelayHttp "../../src/followee/RelayHttp";

module {
  public type Node = { server : RelayServe.Server };

  /// Same shape as the participant's own loopback configuration, with
  /// the opaque identifiers derived from the caller-chosen start byte.
  public func make(genStart : Nat8) : Node {
    let server = switch (
      RelayServe.make({
        relayId = fixedBytes(genStart + 1);
        cursorGeneration = fixedBytes(genStart);
        directoryGeneration = fixedBytes(0x00);
        directory = [
          {
            index = 0;
            relayId = fixedBytes(genStart + 1);
            baseUri = "https://relay.example/followee/";
            capabilityBits = 7;
          },
        ];
        baseUri = "https://relay.example/followee/";
        capabilityBits = 7;
        limits = RelayServe.defaultLimits();
        includePublishDiagnostic = true;
      })
    ) {
      case (?s) { s };
      case null { Runtime.trap("gate server configuration invalid") };
    };
    { server };
  };

  func fixedBytes(start : Nat8) : [Nat8] {
    let out = List.empty<Nat8>();
    var i : Nat8 = 0;
    while (i < 16) {
      out.add(start + i);
      i += 1;
    };
    out.toArray();
  };

  func emit(frame : Text) {
    Prim.debugPrint(frame);
  };

  func hexToBytes(t : Text) : [Nat8] {
    switch (Hex.decode(t)) {
      case (?b) { b };
      case null { Runtime.trap("frame hex invalid") };
    };
  };

  func hexToText(t : Text) : Text {
    switch (Text.decodeUtf8(hexToBytes(t).toBlob())) {
      case (?s) { s };
      case null { Runtime.trap("frame text invalid") };
    };
  };

  func textToHex(t : Text) : Text {
    Hex.encode(Blob.toArray(t.encodeUtf8()));
  };

  func decodeHeaders(headersHex : Text) : [(Text, Text)] {
    let out = List.empty<(Text, Text)>();
    if (headersHex == "") { return out.toArray() };
    for (line in hexToText(headersHex).split(#text "\r\n")) {
      if (line != "") {
        var name = "";
        var value = "";
        var separatorSeen = false;
        for (c in line.chars()) {
          if (separatorSeen) { value #= Char.toText(c) } else if (c == ':') {
            separatorSeen := true;
          } else { name #= Char.toText(c) };
        };
        if (not separatorSeen) { Runtime.trap("frame header invalid") };
        out.add((name, value));
      };
    };
    out.toArray();
  };

  func encodeHeaders(headers : [(Text, Text)]) : Text {
    var joined = "";
    var first = true;
    for ((name, value) in headers.values()) {
      if (not first) { joined #= "\r\n" };
      joined #= name # ":" # value;
      first := false;
    };
    textToHex(joined);
  };

  /// Serves one HTTP request through the production handler at the
  /// explicit scenario clock and prints the response frame (the same
  /// frame vocabulary as the participant's own shim).
  public func serve(node : Node, id : Nat, method : Text, path : Text, headersHex : Text, bodyHex : Text, nowMs : Nat) {
    let response = RelayHttp.handle(
      node.server,
      {
        method;
        path;
        headers = decodeHeaders(headersHex);
        body = hexToBytes(bodyHex);
      },
      nowMs,
    );
    emit(
      "##FLW-HTTP-RESPONSE##" # Nat.toText(id) # "##" # Nat.toText(response.status) # "##" #
      encodeHeaders(response.headers) # "##" # Hex.encode(response.body)
    );
  };

  public func ping(id : Nat) {
    emit("##FLW-PONG##" # Nat.toText(id));
  };
};
