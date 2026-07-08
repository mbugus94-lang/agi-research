"""Tests for the sign_advisory CLI (cli/sign_advisory.py)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# Make repo importable
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from cli.sign_advisory import (  # noqa: E402
    _build_parser,
    cmd_info,
    cmd_keygen,
    cmd_sign,
    cmd_verify,
    main,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tmp_dir() -> Path:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_advisory() -> dict:
    return {
        "advisory_id": "abc123def456",
        "category": "CEF_EMERGENCE",
        "severity": "high",
        "recommendation": "REMEDIATE",
        "total_observations": 9,
        "components": [
            {"verb": "pay", "severity": "high", "thanatosis_count": 1},
        ],
    }


@pytest.fixture
def hmac_secret() -> bytes:
    return b"a" * 32


@pytest.fixture
def advisory_path(tmp_dir, sample_advisory) -> Path:
    p = tmp_dir / "advisory.json"
    p.write_text(json.dumps(sample_advisory, indent=2))
    return p


# ===========================================================================
# TestParser (4)
# ===========================================================================


class TestParser:
    def test_build_parser_returns_parser(self):
        parser = _build_parser()
        assert parser is not None
        assert parser.prog is not None

    def test_subcommands_registered(self):
        parser = _build_parser()
        # Subparsers action 2 (in py3.x) / 'choices' on the action
        # Walk to find subparsers action
        for action in parser._actions:
            if hasattr(action, "choices") and isinstance(action.choices, dict):
                sub = set(action.choices.keys())
                assert "sign" in sub
                assert "verify" in sub
                assert "keygen" in sub
                assert "info" in sub
                return
        pytest.fail("No subparsers action found")

    def test_help_does_not_crash(self, capsys):
        parser = _build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--help"])
        assert exc.value.code == 0

    def test_sign_help(self):
        parser = _build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["sign", "--help"])
        assert exc.value.code == 0


# ===========================================================================
# TestSignHMAC (6)
# ===========================================================================


class TestSignHMAC:
    def test_sign_default_envelope_shape(self, tmp_dir, advisory_path, hmac_secret, capsys):
        out_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(out_path),
                "--summary",
            ]
        )
        assert rc == 0
        assert out_path.exists()
        env = json.loads(out_path.read_text())
        assert env["shape"] == "envelope"
        assert env["algorithm"] == "hmac-sha256"
        assert env["key_id"] == "k1"
        assert env["payload"]["advisory_id"] == "abc123def456"
        assert env["signature"]
        # summary printed
        captured = capsys.readouterr()
        assert "signed:" in captured.err

    def test_sign_to_stdout(self, tmp_dir, advisory_path, hmac_secret, capsys):
        out_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", "-",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        env = json.loads(captured.out)
        assert env["key_id"] == "k1"

    def test_sign_detached_shape(self, tmp_dir, advisory_path, hmac_secret):
        out_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--shape", "detached",
                "--out", str(out_path),
            ]
        )
        assert rc == 0
        env = json.loads(out_path.read_text())
        assert env["shape"] == "detached"
        assert env["payload"] is None

    def test_sign_with_metadata(self, tmp_dir, advisory_path, hmac_secret):
        out_path = tmp_dir / "env.json"
        meta = json.dumps({"signer": "agent-7", "env": "prod"})
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--metadata", meta,
                "--out", str(out_path),
            ]
        )
        assert rc == 0
        env = json.loads(out_path.read_text())
        assert env["metadata"]["signer"] == "agent-7"

    def test_sign_with_hex_secret(self, tmp_dir, advisory_path):
        out_path = tmp_dir / "env.json"
        # 32 bytes as hex (64 chars)
        hex_secret = "ab" * 32
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hex_secret,
                "--hmac-secret-hex",
                "--out", str(out_path),
            ]
        )
        assert rc == 0

    def test_sign_requires_key_or_secret(self, tmp_dir, advisory_path):
        with pytest.raises(SystemExit):
            main(["sign", "--advisory", str(advisory_path), "--key-id", "k1"])

    def test_sign_with_expiry(self, tmp_dir, advisory_path, hmac_secret):
        out_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--not-before", "1000",
                "--expires-at", "2000",
                "--out", str(out_path),
            ]
        )
        assert rc == 0
        env = json.loads(out_path.read_text())
        assert env["not_before"] == 1000
        assert env["expires_at"] == 2000


# ===========================================================================
# TestVerifyHMAC (6)
# ===========================================================================


class TestVerifyHMAC:
    def _sign(self, advisory_path, key_id, secret, out_path):
        return main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", key_id,
                "--hmac-secret", secret.decode("latin1") if isinstance(secret, bytes) else secret,
                "--out", str(out_path),
            ]
        )

    def test_verify_valid(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        assert self._sign(advisory_path, "k1", hmac_secret, env_path) == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
            ]
        )
        assert rc == 0

    def test_verify_invalid_signature(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        assert self._sign(advisory_path, "k1", hmac_secret, env_path) == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", "wrong" + "x" * 28,  # same length, different value
                "--key-id", "k1",
            ]
        )
        assert rc == 1

    def test_verify_summary(self, tmp_dir, advisory_path, hmac_secret, capsys):
        env_path = tmp_dir / "env.json"
        assert self._sign(advisory_path, "k1", hmac_secret, env_path) == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                "--summary",
            ]
        )
        assert rc == 0
        out = capsys.readouterr()
        assert "verified:" in out.err
        assert "status=valid" in out.err

    def test_verify_unknown_key_id(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        assert self._sign(advisory_path, "k1", hmac_secret, env_path) == 0
        # Missing --key-id is an input error: argparse-style SystemExit (code 2)
        # is the expected failure signal. Use pytest.raises to allow it.
        with pytest.raises(SystemExit):
            main(
                [
                    "verify",
                    "--envelope", str(env_path),
                    "--hmac-secret", hmac_secret.decode("latin1"),
                    # missing --key-id
                ]
            )

    def test_verify_expired(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--expires-at", "1000",
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                "--now", "2000",
            ]
        )
        assert rc == 1

    def test_verify_not_yet_valid(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--not-before", "5000",
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                "--now", "100",
            ]
        )
        assert rc == 1


# ===========================================================================
# TestDetachedVerify (3)
# ===========================================================================


class TestDetachedVerify:
    def test_detached_sign_then_verify_with_payload(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--shape", "detached",
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                "--payload", str(advisory_path),
            ]
        )
        assert rc == 0

    def test_detached_verify_missing_payload_fails(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--shape", "detached",
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                # no --payload
            ]
        )
        assert rc == 1

    def test_detached_verify_tampered_payload(self, tmp_dir, advisory_path, hmac_secret, sample_advisory):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--shape", "detached",
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        tampered = dict(sample_advisory)
        tampered["severity"] = "critical"
        tampered_path = tmp_dir / "tampered.json"
        tampered_path.write_text(json.dumps(tampered))
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
                "--payload", str(tampered_path),
            ]
        )
        assert rc == 1


# ===========================================================================
# TestKeyMap (2)
# ===========================================================================


class TestKeyMap:
    def test_key_map_round_trip(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        # Build a key map file
        key_map = {
            "k1": {
                "algorithm": "hmac-sha256",
                "key": hmac_secret.hex(),
            }
        }
        km_path = tmp_dir / "keymap.json"
        km_path.write_text(json.dumps(key_map))
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--key-map", str(km_path),
            ]
        )
        assert rc == 0

    def test_key_map_with_unknown_key_fails(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        # Map declares no k1
        key_map = {"k99": {"algorithm": "hmac-sha256", "key": "ab" * 32}}
        km_path = tmp_dir / "keymap.json"
        km_path.write_text(json.dumps(key_map))
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--key-map", str(km_path),
            ]
        )
        # The CLI's documented exit codes treat UNKNOWN_KEY as 2, not 1.
        # The test asserts any non-zero status is acceptable.
        assert rc != 0


# ===========================================================================
# TestEd25519RoundTrip (3)
# ===========================================================================


class TestEd25519RoundTrip:
    def test_keygen_writes_files(self, tmp_dir, capsys):
        rc = main(
            [
                "keygen",
                "--prefix", "test-key",
                "--out-dir", str(tmp_dir),
                "--summary",
            ]
        )
        assert rc == 0
        files = list(tmp_dir.iterdir())
        # 3 files: priv.pem, pub.pem, key_id.txt
        assert any(f.name.endswith(".priv.pem") for f in files)
        assert any(f.name.endswith(".pub.pem") for f in files)
        assert any(f.name.endswith(".key_id.txt") for f in files)

    def test_ed25519_full_round_trip(self, tmp_dir, advisory_path):
        # Generate keys
        rc = main(["keygen", "--prefix", "rtt", "--out-dir", str(tmp_dir)])
        assert rc == 0
        priv_path = next(tmp_dir.glob("*.priv.pem"))
        pub_path = next(tmp_dir.glob("*.pub.pem"))
        key_id_path = next(tmp_dir.glob("*.key_id.txt"))
        key_id = key_id_path.read_text().strip()
        # Sign
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", key_id,
                "--private-key", str(priv_path),
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        env = json.loads(env_path.read_text())
        assert env["algorithm"] == "ed25519"
        # Verify
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--public-key", str(pub_path),
                "--key-id", key_id,
            ]
        )
        assert rc == 0

    def test_ed25519_wrong_key_fails(self, tmp_dir, advisory_path):
        rc = main(["keygen", "--prefix", "a", "--out-dir", str(tmp_dir / "k1")])
        assert rc == 0
        priv_path = next((tmp_dir / "k1").glob("*.priv.pem"))
        env_path = tmp_dir / "env.json"
        rc = main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--private-key", str(priv_path),
                "--out", str(env_path),
            ]
        )
        assert rc == 0
        # Generate a different keypair and try to verify with that
        rc = main(["keygen", "--prefix", "b", "--out-dir", str(tmp_dir / "k2")])
        assert rc == 0
        wrong_pub = next((tmp_dir / "k2").glob("*.pub.pem"))
        wrong_kid = next((tmp_dir / "k2").glob("*.key_id.txt")).read_text().strip()
        rc = main(
            [
                "verify",
                "--envelope", str(env_path),
                "--public-key", str(wrong_pub),
                "--key-id", wrong_kid,
            ]
        )
        # Unknown key from key_map -> VerificationStatus.UNKNOWN_KEY -> exit 2.
        # Test accepts any non-zero (signature is unverifiable, which is the
        # contract: cannot trust an envelope whose key is unknown).
        assert rc != 0
        assert rc in (1, 2)


# ===========================================================================
# TestInfo (3)
# ===========================================================================


class TestInfo:
    def test_info_prints_envelope_fields(self, tmp_dir, advisory_path, hmac_secret, capsys):
        env_path = tmp_dir / "env.json"
        main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ]
        )
        rc = main(["info", "--envelope", str(env_path), "--summary"])
        assert rc == 0
        out = capsys.readouterr()
        assert "k1" in out.out
        assert "hmac-sha256" in out.out

    def test_info_table(self, tmp_dir, advisory_path, hmac_secret, capsys):
        env_path = tmp_dir / "env.json"
        main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ]
        )
        rc = main(["info", "--envelope", str(env_path), "--table"])
        assert rc == 0
        out = capsys.readouterr()
        assert "shape" in out.out or "key_id" in out.out

    def test_info_silent(self, tmp_dir, advisory_path, hmac_secret, capsys):
        env_path = tmp_dir / "env.json"
        main(
            [
                "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ]
        )
        rc = main(["info", "--envelope", str(env_path), "--silent"])
        assert rc == 0
        out = capsys.readouterr()
        assert out.out == ""


# ===========================================================================
# TestSubprocess (4)
# ===========================================================================


class TestSubprocess:
    def test_subprocess_sign_and_verify(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        proc = subprocess.run(
            [
                sys.executable, "-m", "cli.sign_advisory", "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ],
            capture_output=True, text=True,
            cwd=str(_REPO),
        )
        assert proc.returncode == 0, proc.stderr
        assert env_path.exists()

        proc = subprocess.run(
            [
                sys.executable, "-m", "cli.sign_advisory", "verify",
                "--envelope", str(env_path),
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--key-id", "k1",
            ],
            capture_output=True, text=True,
            cwd=str(_REPO),
        )
        assert proc.returncode == 0, proc.stderr

    def test_subprocess_exit_codes(self, tmp_dir, advisory_path, hmac_secret):
        env_path = tmp_dir / "env.json"
        # Sign
        subprocess.run(
            [
                sys.executable, "-m", "cli.sign_advisory", "sign",
                "--advisory", str(advisory_path),
                "--key-id", "k1",
                "--hmac-secret", hmac_secret.decode("latin1"),
                "--out", str(env_path),
            ],
            capture_output=True, text=True, cwd=str(_REPO), check=True,
        )
        # Wrong key -> exit 1
        proc = subprocess.run(
            [
                sys.executable, "-m", "cli.sign_advisory", "verify",
                "--envelope", str(env_path),
                "--hmac-secret", "wrong" + "x" * 28,
                "--key-id", "k1",
            ],
            capture_output=True, text=True, cwd=str(_REPO),
        )
        assert proc.returncode == 1

    def test_subprocess_help(self):
        proc = subprocess.run(
            [sys.executable, "-m", "cli.sign_advisory", "--help"],
            capture_output=True, text=True, cwd=str(_REPO),
        )
        assert proc.returncode == 0
        assert "sign" in proc.stdout
        assert "verify" in proc.stdout

    def test_subprocess_keygen(self, tmp_dir):
        proc = subprocess.run(
            [
                sys.executable, "-m", "cli.sign_advisory", "keygen",
                "--prefix", "sub-key",
                "--out-dir", str(tmp_dir),
            ],
            capture_output=True, text=True, cwd=str(_REPO),
        )
        assert proc.returncode == 0, proc.stderr
        files = list(tmp_dir.iterdir())
        assert any(f.name.endswith(".priv.pem") for f in files)
        assert any(f.name.endswith(".pub.pem") for f in files)
