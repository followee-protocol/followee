//! NDJSON transport loop for the interop-interface adapter: one request
//! per stdin line, one response per stdout line, diagnostics to stderr
//! only (INTERFACE.md transport framing).

#![forbid(unsafe_code)]

use std::io::{BufRead, Write};

use followee_interop_adapter_rust::{handle_line, Identity, MAX_LINE_BYTES};

fn main() {
    let identity = Identity::from_build();
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut reader = stdin.lock();
    let mut writer = stdout.lock();
    let mut buffer: Vec<u8> = Vec::new();

    loop {
        buffer.clear();
        let mut truncated = false;
        // Bounded read: stop at newline or EOF, discard past the limit.
        loop {
            let chunk = match reader.fill_buf() {
                Ok(chunk) => chunk,
                Err(e) => {
                    eprintln!("stdin read error: {e}");
                    return;
                }
            };
            if chunk.is_empty() {
                if buffer.is_empty() {
                    return; // clean EOF between lines
                }
                break; // final unterminated line
            }
            match chunk.iter().position(|&b| b == b'\n') {
                Some(pos) => {
                    if !truncated {
                        let take = pos.min(MAX_LINE_BYTES - buffer.len());
                        buffer.extend_from_slice(&chunk[..take]);
                        if take < pos {
                            truncated = true;
                        }
                    }
                    reader.consume(pos + 1);
                    break;
                }
                None => {
                    let len = chunk.len();
                    if !truncated {
                        let take = len.min(MAX_LINE_BYTES - buffer.len());
                        buffer.extend_from_slice(&chunk[..take]);
                        if take < len {
                            truncated = true;
                        }
                    }
                    reader.consume(len);
                }
            }
        }
        let response = handle_line(&identity, &buffer, truncated);
        if writeln!(writer, "{response}")
            .and_then(|()| writer.flush())
            .is_err()
        {
            return;
        }
    }
}
