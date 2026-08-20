"""Pure-Python Ed25519 (RFC 8032, pure variant) for bundle verification.

Written directly from RFC 8032 Section 5.1 using only hashlib. Used to
reproduce specification-determined public keys and deterministic
signatures for the published Appendix B seeds and to verify published
envelope signatures. It is verification tooling for already-normative
values, not a protocol implementation, and it deliberately implements
only what checking the published material requires.
"""

from __future__ import annotations

import hashlib

P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P

_BASE_Y = (4 * pow(5, P - 2, P)) % P


def _recover_x(y: int, sign: int) -> int:
    if y >= P:
        raise ValueError("non-canonical y")
    x2 = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
    if x2 == 0:
        if sign:
            raise ValueError("invalid sign bit")
        return 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * pow(2, (P - 1) // 4, P) % P
    if (x * x - x2) % P != 0:
        raise ValueError("not a square")
    if x & 1 != sign:
        x = P - x
    return x


_BASE = (_recover_x(_BASE_Y, 0), _BASE_Y, 1, _recover_x(_BASE_Y, 0) * _BASE_Y % P)


def _add(p: tuple, q: tuple) -> tuple:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % P
    b = (y1 + x1) * (y2 + x2) % P
    c = 2 * t1 * t2 * D % P
    d = 2 * z1 * z2 % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _scalar_mul(scalar: int, point: tuple) -> tuple:
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _compress(point: tuple) -> bytes:
    x, y, z, _ = point
    inv = pow(z, P - 2, P)
    x, y = x * inv % P, y * inv % P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decompress(data: bytes) -> tuple:
    if len(data) != 32:
        raise ValueError("point must be 32 bytes")
    value = int.from_bytes(data, "little")
    y = value & ((1 << 255) - 1)
    x = _recover_x(y, value >> 255)
    return (x, y, 1, x * y % P)


def _equal(p: tuple, q: tuple) -> bool:
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % P == 0 and (y1 * z2 - y2 * z1) % P == 0


def _clamp(seed: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], "little")
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def public_key(seed: bytes) -> bytes:
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    scalar, _ = _clamp(seed)
    return _compress(_scalar_mul(scalar, _BASE))


def sign(seed: bytes, message: bytes) -> bytes:
    scalar, prefix = _clamp(seed)
    pub = _compress(_scalar_mul(scalar, _BASE))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % L
    r_point = _compress(_scalar_mul(r, _BASE))
    k = int.from_bytes(hashlib.sha512(r_point + pub + message).digest(), "little") % L
    s = (r + k * scalar) % L
    return r_point + s.to_bytes(32, "little")


def verify(pub: bytes, message: bytes, signature: bytes) -> bool:
    if len(pub) != 32 or len(signature) != 64:
        return False
    try:
        a_point = _decompress(pub)
        r_point = _decompress(signature[:32])
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= L:
        return False
    k = int.from_bytes(hashlib.sha512(signature[:32] + pub + message).digest(), "little") % L
    left = _scalar_mul(s, _BASE)
    right = _add(r_point, _scalar_mul(k, a_point))
    return _equal(left, right)
