"""Unit tests for the bundle-verification toolkit (stdlib only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interopkit import base58, cbor, ed25519  # noqa: E402


class CborEncodeTests(unittest.TestCase):
    def test_shortest_forms(self):
        self.assertEqual(cbor.encode(0), bytes.fromhex("00"))
        self.assertEqual(cbor.encode(23), bytes.fromhex("17"))
        self.assertEqual(cbor.encode(24), bytes.fromhex("1818"))
        self.assertEqual(cbor.encode(255), bytes.fromhex("18ff"))
        self.assertEqual(cbor.encode(256), bytes.fromhex("190100"))
        self.assertEqual(cbor.encode(2**64 - 1),
                         bytes.fromhex("1bffffffffffffffff"))
        self.assertEqual(cbor.encode(-19), bytes.fromhex("32"))
        self.assertEqual(cbor.encode(-(2**64)),
                         bytes.fromhex("3bffffffffffffffff"))

    def test_map_key_order(self):
        encoded = cbor.encode({1: 1, 0: 0, "a": 2})
        # keys sort bytewise: 00, 01, 6161
        self.assertEqual(encoded, bytes.fromhex("a3000001016161" + "02"))

    def test_simple_values(self):
        self.assertEqual(cbor.encode(False), b"\xf4")
        self.assertEqual(cbor.encode(True), b"\xf5")
        self.assertEqual(cbor.encode(None), b"\xf6")


class CborDecodeTests(unittest.TestCase):
    def test_round_trip(self):
        value = {0: 1, 1: b"\x01\x02", 2: ["x", -5, None, True]}
        self.assertEqual(cbor.decode_strict(cbor.encode(value)), value)

    def assert_rejected(self, hex_str, allow_outer_tag=None):
        with self.assertRaises(cbor.CborError):
            cbor.decode_strict(bytes.fromhex(hex_str), allow_outer_tag)

    def test_non_minimal_integer(self):
        self.assert_rejected("1800")          # 0 as two bytes
        self.assert_rejected("190001")        # 1 as three bytes
        self.assert_rejected("a3001801015000")  # inside a map

    def test_duplicate_and_unordered_keys(self):
        self.assert_rejected("a200010001")         # duplicate key 0
        self.assert_rejected("a201010000")          # keys 1,0 out of order

    def test_truncation_and_trailing(self):
        self.assert_rejected("a2")
        self.assert_rejected("0000")               # trailing byte

    def test_indefinite_and_reserved(self):
        self.assert_rejected("9fff")               # indefinite array
        self.assert_rejected("5f4100ff")           # indefinite bytes
        self.assert_rejected("1c")                 # reserved info

    def test_utf8_validation(self):
        self.assert_rejected("62c0ae")             # overlong
        self.assert_rejected("63eda080")           # surrogate
        self.assert_rejected("62e282")             # incomplete code point

    def test_tags(self):
        self.assert_rejected("c100")               # inner tag forbidden
        tagged = cbor.decode_strict(bytes.fromhex("d28441a0a041005840" + "00" * 64),
                                    allow_outer_tag=18)
        self.assertEqual(tagged[0], "tag")
        self.assert_rejected("c100", allow_outer_tag=18)  # wrong tag number

    def test_floats_and_unknown_simple(self):
        self.assert_rejected("f97e00")             # float16
        self.assert_rejected("f0")                 # simple 16
        self.assert_rejected("f820")               # simple 32
        self.assert_rejected("f7")                 # undefined


class Base58Tests(unittest.TestCase):
    def test_round_trip(self):
        for data in (b"", b"\x00", b"\x00\x00hello", bytes(range(34))):
            self.assertEqual(base58.decode(base58.encode(data)), data)

    def test_known_alice_multihash(self):
        multihash = bytes.fromhex(
            "122012dc4b843d10c5ca7313aa2452db61d661afbe3943b3fdbea43405c7028d1eb2")
        self.assertEqual(base58.encode(multihash),
                         "QmPcGstBa7wW9hoYQbS6JZ4UxwZmoKr7YVf9y7qxiyD3Cm")

    def test_invalid_character(self):
        with self.assertRaises(ValueError):
            base58.decode("0OIl")


class Ed25519Tests(unittest.TestCase):
    # RFC 8032 Section 7.1 TEST 1
    SEED = bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    PUB = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    SIG = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

    def test_rfc8032_test1(self):
        self.assertEqual(ed25519.public_key(self.SEED), self.PUB)
        self.assertEqual(ed25519.sign(self.SEED, b""), self.SIG)
        self.assertTrue(ed25519.verify(self.PUB, b"", self.SIG))

    def test_tamper_rejected(self):
        bad = bytearray(self.SIG)
        bad[0] ^= 1
        self.assertFalse(ed25519.verify(self.PUB, b"", bytes(bad)))
        self.assertFalse(ed25519.verify(self.PUB, b"x", self.SIG))

    def test_s_out_of_range_rejected(self):
        s = int.from_bytes(self.SIG[32:], "little") + ed25519.L
        forged = self.SIG[:32] + s.to_bytes(32, "little")
        self.assertFalse(ed25519.verify(self.PUB, b"", forged))

    def test_bad_lengths_rejected(self):
        self.assertFalse(ed25519.verify(self.PUB[:31], b"", self.SIG))
        self.assertFalse(ed25519.verify(self.PUB, b"", self.SIG[:63]))


if __name__ == "__main__":
    unittest.main()
