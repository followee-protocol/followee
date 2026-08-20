#!/usr/bin/env node
// Coordinator bridge over the frozen Motoko participant's own loopback
// shim (`shim/loopback.js` + `shim/RelayNode.mo`). It executes JSON
// commands from stdin (one per line) and answers one JSON line per
// command on stdout. It owns no protocol semantics: every protocol
// decision is made inside the participant process; this bridge only
// routes commands, ports, and raw bytes for the orchestrator, exactly
// like the participant's own scenario driver does.
//
// Commands:
//   {"op":"serve","port":N}          start the participant HTTP server
//   {"op":"client","port":N,"statement":"RelayNode.buildInfo(node, __ID__);"}
//       run one production client operation against 127.0.0.1:N and
//       return {raw:{status,contentType,bodyHex},outcome}
//   {"op":"statement","statement":"..."}   send a raw driver statement
//       (used for the tamper-free probe/setTamper hooks only)
//   {"op":"probe"}                   return the participant state probe
//   {"op":"stop"}                    shut everything down
"use strict";

const path = require("path");
const readline = require("readline");

const motokoRepo = process.env.FOLLOWEE_MOTOKO;
if (!motokoRepo) {
  console.error("FOLLOWEE_MOTOKO not set");
  process.exit(2);
}
process.chdir(motokoRepo);
const { Participant, startHttpServer, clientOperation } = require(
  path.join(motokoRepo, "shim", "loopback.js")
);
const http = require("http");

// Transport-only helpers mirroring the participant shim's hex framing
// (name:value CRLF-joined header lines as hex).
function headersToHexPairs(rawHeaders) {
  const lines = [];
  for (let i = 0; i + 1 < rawHeaders.length; i += 2) {
    lines.push(rawHeaders[i] + ":" + rawHeaders[i + 1]);
  }
  return Buffer.from(lines.join("\r\n"), "utf8").toString("hex");
}

function hexToHeaderPairsLocal(hexText) {
  if (!hexText) return [];
  const text = Buffer.from(hexText, "hex").toString("utf8");
  return text
    .split("\r\n")
    .filter((l) => l.length > 0)
    .map((line) => {
      const i = line.indexOf(":");
      return [line.slice(0, i), line.slice(i + 1)];
    });
}

// One production client operation, carried like the participant shim's
// clientOperation but able to represent a client-side build refusal
// (the participant emits FLW-CLIENT-OUTCOME with no request frame when
// its production client refuses to construct the request, e.g. for an
// over-limit record). Transport only; every decision is Motoko's.
function bridgeClientOperation(participant, port, statementTemplate) {
  const id = participant.freshId();
  participant.send(statementTemplate.replaceAll("__ID__", String(id)));
  return new Promise((resolve, reject) => {
    let settled = false;
    let rawResult = null; // set by the request path before receive()
    const done = (v) => {
      if (!settled) {
        settled = true;
        resolve(v);
      }
    };
    const fail = (e) => {
      if (!settled) {
        settled = true;
        reject(e);
      }
    };
    // Exactly one FLW-CLIENT-OUTCOME arrives per operation: either a
    // build refusal (no request frame, rawResult stays null) or the
    // production classification after the raw peer response was fed
    // back through receive() (rawResult already recorded).
    participant
      .waitFrame("FLW-CLIENT-OUTCOME", id, 115000)
      .then((frame) => done({ raw: rawResult, outcome: frame.slice(2).join("##") }))
      .catch((err) => fail(err));
    participant
      .waitFrame("FLW-CLIENT-REQUEST", id, 110000)
      .then((frame) => {
        const method = frame[2];
        const reqPath = frame[3];
        const headerPairs = hexToHeaderPairsLocal(frame[4] || "");
        const body = Buffer.from(frame[5] || "", "hex");
        const headers = {};
        for (const [n, v] of headerPairs) headers[n] = v;
        headers["content-length"] = String(body.length);
        const req = http.request(
          { host: "127.0.0.1", port, method, path: reqPath, headers },
          (res) => {
            const chunks = [];
            res.on("data", (c) => chunks.push(c));
            res.on("end", () => {
              rawResult = {
                status: res.statusCode,
                contentType: res.headers["content-type"] || null,
                bodyHex: Buffer.concat(chunks).toString("hex"),
              };
              participant.send(
                "RelayNode.receive(node, " + id + ", " + rawResult.status +
                ', "' + headersToHexPairs(res.rawHeaders) + '", "' +
                rawResult.bodyHex + '");'
              );
            });
          }
        );
        req.on("error", fail);
        req.end(body);
      })
      .catch(() => {
        // No request frame: a build refusal already resolved the
        // operation through the outcome waiter (or it will time out).
      });
  });
}

// HTTP server over a coordinator gate node: identical byte transport to
// the participant shim's startHttpServer, but routed to the named gate
// node with an explicit, settable scenario clock (Gates G1/G3 and the
// Phase 3 step 6a contrast).
function startGateServer(participant, port, name, clockBox) {
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", async () => {
      const body = Buffer.concat(chunks);
      const id = participant.freshId();
      participant.send(
        "GateNode.serve(" + name + ", " + id + ', "' + req.method + '", "' +
        req.url + '", "' + headersToHexPairs(req.rawHeaders) + '", "' +
        body.toString("hex") + '", ' + String(clockBox.nowMs) + ");"
      );
      try {
        const frame = await participant.waitFrame("FLW-HTTP-RESPONSE", id);
        const status = parseInt(frame[2], 10);
        const headerPairs = hexToHeaderPairsLocal(frame[3] || "");
        const responseBody = Buffer.from(frame[4] || "", "hex");
        const flat = [];
        for (const [n, v] of headerPairs) flat.push(n, v);
        flat.push("content-length", String(responseBody.length));
        res.writeHead(status, flat);
        res.end(responseBody);
      } catch (err) {
        res.destroy(err);
      }
    });
  });
  return new Promise((resolve) =>
    server.listen(port, "127.0.0.1", () => resolve(server))
  );
}

async function main() {
  const participant = new Participant();
  await participant.ready();
  let server = null;
  const gateServers = [];
  const gateClocks = {};
  let gateImported = false;

  const rl = readline.createInterface({ input: process.stdin });
  const reply = (value) => process.stdout.write(JSON.stringify(value) + "\n");

  for await (const line of rl) {
    if (!line.trim()) continue;
    let cmd;
    try {
      cmd = JSON.parse(line);
    } catch (err) {
      reply({ ok: false, error: "bad command json" });
      continue;
    }
    try {
      if (cmd.op === "serve") {
        server = await startHttpServer(participant, cmd.port);
        reply({ ok: true });
      } else if (cmd.op === "client") {
        const result = await bridgeClientOperation(participant, cmd.port, cmd.statement);
        reply({ ok: true, ...result });
      } else if (cmd.op === "gateInit") {
        // Materializes one coordinator gate node inside the participant
        // process. GateNode.mo is placed under the checkout's gitignored
        // runner/generated/ directory by the orchestrator beforehand.
        if (!gateImported) {
          participant.send('import GateNode "runner/generated/GateNode";');
          gateImported = true;
        }
        participant.send(
          "let " + cmd.name + " = GateNode.make(" + String(cmd.genStart) + ");"
        );
        const id = participant.freshId();
        participant.send("GateNode.ping(" + id + ");");
        await participant.waitFrame("FLW-PONG", id);
        reply({ ok: true });
      } else if (cmd.op === "gateServe") {
        gateClocks[cmd.name] = { nowMs: cmd.nowMs };
        gateServers.push(
          await startGateServer(participant, cmd.port, cmd.name, gateClocks[cmd.name])
        );
        reply({ ok: true });
      } else if (cmd.op === "gateClock") {
        gateClocks[cmd.name].nowMs = cmd.nowMs;
        reply({ ok: true });
      } else if (cmd.op === "probe") {
        const id = participant.freshId();
        participant.send("RelayNode.probe(node, " + id + ");");
        const frame = await participant.waitFrame("FLW-PROBE", id);
        reply({ ok: true, probe: frame.slice(2).join("##") });
      } else if (cmd.op === "statement") {
        participant.send(cmd.statement);
        reply({ ok: true });
      } else if (cmd.op === "stop") {
        if (server) server.close();
        for (const gs of gateServers) gs.close();
        participant.stop();
        reply({ ok: true });
        process.exit(0);
      } else {
        reply({ ok: false, error: "unknown op" });
      }
    } catch (err) {
      reply({ ok: false, error: String(err && err.message ? err.message : err) });
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
