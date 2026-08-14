// Coordinator relay driver for the frozen Motoko participant
// (interop/v0.9.1 campaign 1, phase 3).
//
// This driver contains no protocol logic and no expected protocol
// answer: every wire decode/encode, verification, ingress, resolve,
// client-acceptance, and synchronization-receiver decision is made by
// the frozen production modules imported below. The driver only parses
// space-separated command lines (embedded by the participant's own
// neutral embed plumbing), routes them to production entry points,
// maintains named relay states across commands, and prints one JSON
// result line per command.
//
// Scenario-setup commands (`seed`, `setCounter`, `setPeerCursor`) load
// published Appendix B.11 scenario state through the production `seed`
// entry point and public state fields; they inject inputs, never
// outcomes.
//
// The template placeholder @@SRC@@ is substituted at generation time
// with the relative path to the frozen Motoko checkout's `src`
// directory; the campaign verifies that checkout is the exact frozen
// revision before every run.

import Prim "mo:⛔";
import Iter "mo:core/Iter";
import Map "mo:core/Map";
import Nat "mo:core/Nat";
import Text "mo:core/Text";
import Errors "@@SRC@@/followee/Errors";
import RelayState "@@SRC@@/followee/RelayState";
import RelayWire "@@SRC@@/followee/RelayWire";
import Verify "@@SRC@@/followee/Verify";
import Hex "@@SRC@@/lib/Hex";
import Input "generated/DriverInput";

var states : [(Text, RelayState.Relay)] = [];

func state(name : Text) : RelayState.Relay {
  for ((n, s) in states.values()) {
    if (n == name) { return s };
  };
  let fresh = RelayState.empty();
  states := Iter.toArray(Iter.concat(states.values(), [(name, fresh)].values()));
  fresh;
};

func hex(t : Text) : [Nat8] {
  switch (Hex.decode(t)) {
    case (?b) { b };
    case null { Prim.trap("driver: bad hex token: " # t) };
  };
};

func nat(t : Text) : Nat {
  switch (Nat.fromText(t)) {
    case (?n) { n };
    case null { Prim.trap("driver: bad nat token: " # t) };
  };
};

func authorityState(t : Text) : RelayState.AuthorityState {
  if (t == "unknown") { #unknown } else if (t == "root") { #root } else if (t == "rootRevoked") {
    #rootRevoked;
  } else { Prim.trap("driver: bad authority state: " # t) };
};

func authorityText(a : RelayState.AuthorityState) : Text {
  switch (a) {
    case (#unknown) { "unknown" };
    case (#root) { "root" };
    case (#rootRevoked) { "rootRevoked" };
  };
};

func optCursor(t : Text) : ?[Nat8] {
  if (t == "-") { null } else { ?hex(t) };
};

func ingressText(outcome : RelayState.IngressOutcome) : Text {
  switch (outcome) {
    case (#admitted(n)) { "{\"admitted\":" # Nat.toText(n) # "}" };
    case (#noChange(e)) { "{\"noChange\":\"" # Errors.name(e) # "\"}" };
    case (#rejected(e)) { "{\"rejected\":\"" # Errors.name(e) # "\"}" };
  };
};

func handle(line : Text) : Text {
  let tokens = Iter.toArray(Text.split(line, #char ' '));
  if (tokens.size() == 0) { Prim.trap("driver: empty command") };
  let command = tokens[0];

  if (command == "seed") {
    // seed <state> <did> <envelopeHex> <authorityState> <lastUpdated>
    //      <timestampMs> <bodyDigestHex>
    RelayState.seed(
      state(tokens[1]),
      tokens[2],
      hex(tokens[3]),
      authorityState(tokens[4]),
      nat(tokens[5]),
      nat(tokens[6]),
      hex(tokens[7]),
    );
    return "{\"ok\":\"seed\"}";
  };
  if (command == "setCounter") {
    state(tokens[1]).updateCounter := nat(tokens[2]);
    return "{\"ok\":\"setCounter\"}";
  };
  if (command == "setPeerCursor") {
    state(tokens[1]).peerCursor := optCursor(tokens[2]);
    return "{\"ok\":\"setPeerCursor\"}";
  };
  if (command == "publish") {
    // publish <state> <did> <envelopeHex> <nowMs>
    let outcome = RelayState.ingress(state(tokens[1]), tokens[2], hex(tokens[3]), nat(tokens[4]));
    let (status, errorCode) = RelayState.publishStatus(outcome);
    let body = switch (RelayWire.encodePublishResponse(status, errorCode)) {
      case (?b) { b };
      case null { Prim.trap("driver: publish response encoding failed") };
    };
    let errorText = switch (errorCode) {
      case (?c) { Nat.toText(c) };
      case null { "null" };
    };
    return "{\"op\":\"publish\",\"httpStatus\":200,\"status\":" # Nat.toText(status)
    # ",\"errorCode\":" # errorText
    # ",\"bodyHex\":\"" # Hex.encode(body) # "\""
    # ",\"ingress\":" # ingressText(outcome) # "}";
  };
  if (command == "resolve") {
    // resolve <state> <requestHex> <generationHex> <nowMs>
    switch (RelayState.handleResolve(state(tokens[1]), hex(tokens[2]), hex(tokens[3]), nat(tokens[4]))) {
      case (#ok(body)) {
        return "{\"op\":\"resolve\",\"httpStatus\":200,\"bodyHex\":\"" # Hex.encode(body) # "\"}";
      };
      case (#badRequest(e)) {
        return "{\"op\":\"resolve\",\"httpStatus\":400,\"error\":\"" # Errors.name(e) # "\"}";
      };
    };
  };
  if (command == "clientResolveRequest") {
    // clientResolveRequest <did1,did2,...>
    let dids = Iter.toArray(Text.split(tokens[1], #char ','));
    switch (RelayWire.encodeResolveRequest({ dids })) {
      case (?bytes) {
        return "{\"op\":\"clientResolveRequest\",\"bodyHex\":\"" # Hex.encode(bytes) # "\"}";
      };
      case null {
        return "{\"op\":\"clientResolveRequest\",\"error\":\"unencodable\"}";
      };
    };
  };
  if (command == "clientProcessResolve") {
    // clientProcessResolve <did1,did2,...> <responseHex> <nowMs>
    let dids = Iter.toArray(Text.split(tokens[1], #char ','));
    let nowMs = nat(tokens[3]);
    switch (RelayState.clientProcessResolve(dids, hex(tokens[2]))) {
      case (#reject(e)) {
        return "{\"op\":\"clientProcessResolve\",\"outcome\":\"reject\",\"error\":\""
        # Errors.name(e) # "\"}";
      };
      case (#ok(results)) {
        var parts = "";
        var index = 0;
        for (result in results.values()) {
          let item = switch (result) {
            case (#absent) { "{\"kind\":\"absent\"}" };
            case (#ref(n)) { "{\"kind\":\"ref\",\"index\":" # Nat.toText(n) # "}" };
            case (#error(code)) { "{\"kind\":\"error\",\"code\":" # Nat.toText(code) # "}" };
            case (#full(bytes)) {
              // Full-candidate verification stays with the client
              // (Section 12.3): the production verifier judges the
              // candidate for the DID at this request index.
              switch (Verify.verifyRecord(dids[index], bytes, nowMs)) {
                case (#ok(v)) {
                  "{\"kind\":\"full\",\"verified\":true,\"bodyDigestHex\":\""
                  # Hex.encode(v.bodyDigest) # "\",\"authority\":"
                  # (switch (v.body.authority) { case (#root) { "\"root\"" }; case (#rootRevoked) { "\"rootRevoked\"" } })
                  # ",\"premature\":" # (if (v.premature) { "true" } else { "false" })
                  # ",\"stale\":" # (if (v.stale) { "true" } else { "false" }) # "}";
                };
                case (#err(e)) {
                  "{\"kind\":\"full\",\"verified\":false,\"error\":\"" # Errors.name(e) # "\"}";
                };
              };
            };
          };
          parts := parts # (if (index == 0) { "" } else { "," }) # item;
          index += 1;
        };
        return "{\"op\":\"clientProcessResolve\",\"outcome\":\"ok\",\"results\":[" # parts # "]}";
      };
    };
  };
  if (command == "clientChangesRequest") {
    // clientChangesRequest <cursorHexOrDash> <itemLimit> <byteLimit>
    let request : RelayWire.ChangesRequest = {
      cursor = optCursor(tokens[1]);
      itemLimit = nat(tokens[2]);
      byteLimit = nat(tokens[3]);
    };
    switch (RelayWire.encodeChangesRequest(request)) {
      case (?bytes) {
        return "{\"op\":\"clientChangesRequest\",\"bodyHex\":\"" # Hex.encode(bytes) # "\"}";
      };
      case null {
        return "{\"op\":\"clientChangesRequest\",\"error\":\"unencodable\"}";
      };
    };
  };
  if (command == "receiveChanges") {
    // receiveChanges <state> <cursorHexOrDash> <itemLimit> <byteLimit>
    //                <responseHex> <nowMs>
    let relay = state(tokens[1]);
    let request : RelayWire.ChangesRequest = {
      cursor = optCursor(tokens[2]);
      itemLimit = nat(tokens[3]);
      byteLimit = nat(tokens[4]);
    };
    let outcome = RelayState.receiveChanges(relay, request, hex(tokens[5]), nat(tokens[6]));
    let outcomeText = switch (outcome) {
      case (#rejectedResponse(e)) {
        "{\"outcome\":\"rejectedResponse\",\"error\":\"" # Errors.name(e) # "\"}";
      };
      case (#resetRequired) { "{\"outcome\":\"resetRequired\"}" };
      case (#relayError(code)) { "{\"outcome\":\"relayError\",\"code\":" # Nat.toText(code) # "}" };
      case (#processed(items)) {
        var parts = "";
        var first = true;
        for (item in items.values()) {
          let text = switch (item) {
            case (#ingress(i)) { "{\"ingress\":" # ingressText(i) # "}" };
            case (#refHint(n)) { "{\"refHint\":" # Nat.toText(n) # "}" };
          };
          parts := parts # (if (first) { "" } else { "," }) # text;
          first := false;
        };
        "{\"outcome\":\"processed\",\"items\":[" # parts # "]}";
      };
    };
    let cursorText = switch (relay.peerCursor) {
      case (?c) { "\"" # Hex.encode(c) # "\"" };
      case null { "null" };
    };
    return "{\"op\":\"receiveChanges\",\"result\":" # outcomeText
    # ",\"peerCursorHex\":" # cursorText
    # ",\"updateCounter\":" # Nat.toText(relay.updateCounter) # "}";
  };
  if (command == "dumpState") {
    // dumpState <state> <did1,did2,...>
    let relay = state(tokens[1]);
    let dids = Iter.toArray(Text.split(tokens[2], #char ','));
    var parts = "";
    var first = true;
    for (did in dids.values()) {
      let entryText = switch (relay.entries.get(did)) {
        case null { "null" };
        case (?entry) {
          let envelopeText = switch (entry.envelope) {
            case (?e) { "\"" # Hex.encode(e) # "\"" };
            case null { "null" };
          };
          "{\"authorityState\":\"" # authorityText(entry.authorityState)
          # "\",\"lastUpdated\":" # Nat.toText(entry.lastUpdated)
          # ",\"timestampMs\":" # Nat.toText(entry.timestampMs)
          # ",\"bodyDigestHex\":\"" # Hex.encode(entry.bodyDigest)
          # "\",\"envelopeHex\":" # envelopeText # "}";
        };
      };
      parts := parts # (if (first) { "" } else { "," }) # "\"" # did # "\":" # entryText;
      first := false;
    };
    let cursorText = switch (relay.peerCursor) {
      case (?c) { "\"" # Hex.encode(c) # "\"" };
      case null { "null" };
    };
    return "{\"op\":\"dumpState\",\"entries\":{" # parts # "}"
    # ",\"peerCursorHex\":" # cursorText
    # ",\"updateCounter\":" # Nat.toText(relay.updateCounter) # "}";
  };
  Prim.trap("driver: unknown command: " # command);
};

var i = 0;
while (i < Input.lines.size()) {
  Prim.debugPrint(handle(Input.lines[i]));
  i += 1;
};
