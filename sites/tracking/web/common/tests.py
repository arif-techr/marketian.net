import base64
import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from . import crypto

VECTOR = json.loads((Path(__file__).resolve().parent.parent / "docs" / "crypto-test-vector.json").read_text("utf-8"))
REAL_SECRET = "x" * 50


class CryptoTests(SimpleTestCase):
    def setUp(self):
        self.keys = crypto.generate_key("k1")

    def test_round_trip(self):
        token = crypto.encrypt("EAAB secret ভ", self.keys)
        self.assertTrue(token.startswith("v1:k1:"))
        self.assertNotIn("secret", token)
        self.assertEqual(crypto.decrypt(token, self.keys), "EAAB secret ভ")

    def test_every_value_gets_a_fresh_nonce(self):
        self.assertNotEqual(crypto.encrypt("same", self.keys), crypto.encrypt("same", self.keys))

    def test_published_vector(self):
        nonce = base64.b64decode(VECTOR["nonce_base64"])
        self.assertEqual(crypto.encrypt(VECTOR["plaintext"], VECTOR["keys"], _nonce=nonce), VECTOR["token"])
        self.assertEqual(crypto.decrypt(VECTOR["token"], VECTOR["keys"]), VECTOR["plaintext"])

    def test_old_keys_still_decrypt_after_rotation(self):
        token = crypto.encrypt("old", self.keys)
        rotated = f"{crypto.generate_key('k2')},{self.keys}"
        self.assertEqual(crypto.decrypt(token, rotated), "old")
        self.assertTrue(crypto.encrypt("new", rotated).startswith("v1:k2:"))

    def test_changed_data_or_wrong_key_is_refused(self):
        token = crypto.encrypt("value", self.keys)
        version, key_id, encoded = token.split(":")
        blob = bytearray(base64.b64decode(encoded))
        blob[-1] ^= 1
        tampered = f"{version}:{key_id}:{base64.b64encode(bytes(blob)).decode()}"
        cases = [
            (tampered, self.keys),
            (token, crypto.generate_key("k1")),  # same id, different key
            (token, crypto.generate_key("k9")),  # key not listed
            ("plain", self.keys),
            ("v2:k1:AAAA", self.keys),
        ]
        for bad, keys in cases:
            with self.assertRaises(crypto.CryptoError):
                crypto.decrypt(bad, keys)

    def test_bad_key_lists(self):
        for value in ["", "k1", "k1:notbase64!", f"k1:{base64.b64encode(b'short').decode()}", f"{self.keys},{self.keys}"]:
            with self.assertRaises(crypto.CryptoError):
                crypto.parse_keys(value)


class ProductionGuardTests(SimpleTestCase):
    def test_real_values_pass(self):
        crypto.check_production_secrets(REAL_SECRET, crypto.generate_key("k1"))

    def test_placeholder_secret_key_stops_the_site(self):
        for secret in ["", "change-me", "dev-insecure-change-me", "short"]:
            with self.assertRaises(ImproperlyConfigured):
                crypto.check_production_secrets(secret, crypto.generate_key("k1"))

    def test_missing_or_dev_encryption_keys_stop_the_site(self):
        dev = "dev:" + base64.b64encode(b"dev-insecure-key-32-bytes-long!!").decode()
        for keys in ["", "k1:<base64 32 bytes>", dev]:
            with self.assertRaises(ImproperlyConfigured):
                crypto.check_production_secrets(REAL_SECRET, keys)
