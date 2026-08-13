"""Minimal deterministic CBOR encoder and profile checker.

Implements exactly what bundle verification needs from the pinned
Followee specification, Section 6.1: definite lengths, shortest-form
integer and length encodings, bytewise-lexicographic map-key order, and
rejection of floats, tags (other than an explicitly requested outer
tag), and non-shortest encodings. It is a checker for already-published
or specification-determined bytes, not a general CBOR library and not a
protocol implementation.
"""

from __future__ import annotations


class CborError(ValueError):
    """Raised when bytes violate well-formedness or the deterministic profile."""


def _head(major: int, value: int) -> bytes:
    if value < 0:
        raise CborError("negative length or argument")
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 0x100:
        return bytes([(major << 5) | 24, value])
    if value < 0x10000:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value < 0x100000000:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    if value < 0x10000000000000000:
        return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")
    raise CborError("argument exceeds 64 bits")


def encode(value: object) -> bytes:
    """Deterministically encode ints, bools, None, bytes, str, list, dict."""
    if value is True:
        return b"\xf5"
    if value is False:
        return b"\xf4"
    if value is None:
        return b"\xf6"
    if isinstance(value, int):
        if value >= 0:
            return _head(0, value)
        return _head(1, -1 - value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(value, list):
        return _head(4, len(value)) + b"".join(encode(item) for item in value)
    if isinstance(value, dict):
        entries = sorted(
            (encode(key), encode(val)) for key, val in value.items()
        )
        if len({key for key, _ in entries}) != len(entries):
            raise CborError("duplicate map key")
        return _head(5, len(entries)) + b"".join(key + val for key, val in entries)
    raise CborError(f"unsupported value type: {type(value).__name__}")


def encode_tagged(tag: int, value_bytes: bytes) -> bytes:
    """Encode a tag head followed by already-encoded content bytes."""
    return _head(6, tag) + value_bytes


class _Decoder:
    def __init__(self, data: bytes, allow_outer_tag: int | None) -> None:
        self.data = data
        self.pos = 0
        self.allow_outer_tag = allow_outer_tag

    def _byte(self) -> int:
        if self.pos >= len(self.data):
            raise CborError("truncated item")
        byte = self.data[self.pos]
        self.pos += 1
        return byte

    def _take(self, count: int) -> bytes:
        if self.pos + count > len(self.data):
            raise CborError("truncated item")
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def _argument(self, info: int) -> int:
        if info < 24:
            return info
        if info == 24:
            value = self._byte()
            if value < 24:
                raise CborError("non-shortest encoding")
            return value
        if info in (25, 26, 27):
            width = 1 << (info - 24)
            value = int.from_bytes(self._take(width), "big")
            if value < (1 << (8 * (width // 2))):
                raise CborError("non-shortest encoding")
            return value
        raise CborError("indefinite length or reserved additional info")

    def item(self, outer: bool = False) -> object:
        initial = self._byte()
        major, info = initial >> 5, initial & 0x1F
        if major == 0:
            return self._argument(info)
        if major == 1:
            return -1 - self._argument(info)
        if major == 2:
            return self._take(self._argument(info))
        if major == 3:
            raw = self._take(self._argument(info))
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise CborError("invalid UTF-8 text string") from exc
            if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
                raise CborError("surrogate code point")
            return text
        if major == 4:
            return [self.item() for _ in range(self._argument(info))]
        if major == 5:
            count = self._argument(info)
            entries: list[tuple[bytes, object, object]] = []
            for _ in range(count):
                key_start = self.pos
                key = self.item()
                key_bytes = self.data[key_start : self.pos]
                entries.append((key_bytes, key, self.item()))
            encoded_keys = [key_bytes for key_bytes, _, _ in entries]
            if encoded_keys != sorted(encoded_keys):
                raise CborError("map keys not in bytewise order")
            if len(set(encoded_keys)) != len(encoded_keys):
                raise CborError("duplicate map key")
            return {key: val for _, key, val in entries}
        if major == 6:
            if outer and self.allow_outer_tag is not None:
                tag = self._argument(info)
                if tag != self.allow_outer_tag:
                    raise CborError(f"unexpected tag {tag}")
                return ("tag", tag, self.item())
            raise CborError("tag forbidden by deterministic profile")
        # major 7
        if info == 20:
            return False
        if info == 21:
            return True
        if info == 22:
            return None
        raise CborError("simple/float value outside checker subset")


def decode_strict(data: bytes, allow_outer_tag: int | None = None) -> object:
    """Decode exactly one deterministic item; reject trailing bytes.

    Restricted to the value subset the bundle uses; anything else raises
    CborError. Tag `allow_outer_tag` (e.g. 18) is permitted only as the
    outermost item and is returned as ("tag", n, content).
    """
    decoder = _Decoder(data, allow_outer_tag)
    value = decoder.item(outer=True)
    if decoder.pos != len(data):
        raise CborError("trailing bytes")
    return value


def is_deterministic(data: bytes, allow_outer_tag: int | None = None) -> bool:
    try:
        decode_strict(data, allow_outer_tag)
    except CborError:
        return False
    return True
