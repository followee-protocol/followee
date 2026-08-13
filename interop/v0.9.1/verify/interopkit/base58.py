"""Base58btc (Bitcoin alphabet) encoding for multihash DID checking."""

from __future__ import annotations

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


def encode(data: bytes) -> str:
    value = int.from_bytes(data, "big")
    digits = []
    while value > 0:
        value, rem = divmod(value, 58)
        digits.append(ALPHABET[rem])
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + "".join(reversed(digits))


def decode(text: str) -> bytes:
    value = 0
    for ch in text:
        if ch not in _INDEX:
            raise ValueError(f"invalid base58 character: {ch!r}")
        value = value * 58 + _INDEX[ch]
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    pad = 0
    for ch in text:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw
