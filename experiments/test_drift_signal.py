import os, sys, subprocess, tempfile, time, unittest
from pathlib import Path
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from core.drift_signal import DriftConfig, DriftReport, DriftRow, scan_drift_signal, scan_drift_signal_from_paths, write_drift_report, DRIFT_STALE, DRIFT_EXPIRED, DRIFT_NOT_YET_VALID, DRIFT_UNKNOWN_KEY, DRIFT_INVALID_SIGNATURE, DRIFT_PAYLOAD_MISMATCH, DRIFT_MALFORMED, DRIFT_FIRST_ENCOUNTER, DRIFT_OLD_ALGORITHM
from core.signed_advisory_envelope import EnvelopeConfig, KeyRegistry, SignatureAlgorithm, sign_envelope, envelope_to_json, generate_ed25519_keypair

def _hmac(tmp, key_id, secret, age=0, exp_in=3600, nb_in=None):
    payload = {"advisory_id": "adv-" + key_id, "note": "test"}
    exp = time.time() + exp_in if exp_in else None
    nb = time.time() + nb_in if nb_in else None
    cfg = EnvelopeConfig(algorithm=SignatureAlgorithm.HMAC_SHA256.value, expires_at=exp, not_before=nb)
    now = time.time() - age if age else None
    env = sign_envelope(payload=payload, key_id=key_id, key=secret, config=cfg, now=now)
    import uuid
    p = tmp / (key_id + "-" + uuid.uuid4().hex + ".json")
    p.write_text(envelope_to_json(env))
    return p

class TestDriftConfig(unittest.TestCase):
    def test_defaults(self):
        c = DriftConfig()
        self.assertEqual(c.stale_threshold_seconds, 3600)
        self.assertIn("hmac-sha256", c.trusted_algorithms)
        self.assertFalse(c.follow_symlinks)
        self.assertIsNone(c.now)
    def test_custom(self):
        c = DriftConfig(stale_threshold_seconds=60, trusted_algorithms=frozenset({"ed25519"}), follow_symlinks=True, now=1234.5, include_files=("a.json",))
        self.assertEqual(c.stale_threshold_seconds, 60)
        self.assertEqual(c.trusted_algorithms, frozenset({"ed25519"}))
        self.assertTrue(c.follow_symlinks)
        self.assertEqual(c.now, 1234.5)

class TestDriftRow(unittest.TestCase):
    def test_to_csv_dict_keys(self):
        row = DriftRow(envelope_id="abc", key_id="k1", shape="envelope", algorithm="hmac-sha256", issued_at=1.0, age_seconds=10.0, not_before=None, expires_at=2.0, status="VALID", drift_flags=[], reasons=[], payload_digest="sha256:0")
        d = row.to_csv_dict()
        for k in ("envelope_id", "key_id", "algorithm", "shape", "issued_at", "age_seconds", "not_before", "expires_at", "status", "drift_flags", "reasons", "payload_digest"):
            self.assertIn(k, d)
        self.assertEqual(d["drift_flags"], "")
    def test_to_csv_round_trip(self):
        row = DriftRow(envelope_id="abc", key_id="k1", shape="envelope", algorithm="hmac-sha256", issued_at=1.0, age_seconds=10.0, not_before=None, expires_at=None, status="VALID", drift_flags=["STALE"], reasons=["r"], payload_digest="sha256:0")
        d = row.to_csv_dict()
        self.assertEqual(d["drift_flags"], "STALE")
        self.assertEqual(d["reasons"], "r")

class TestDriftReport(unittest.TestCase):
    def test_counts(self):
        r = DriftReport(directory="/tmp", generated_at=time.time(), n_envelopes=10, n_valid=7, n_drift=2, n_invalid=1, n_expired=1, n_not_yet_valid=0, n_malformed=0, drift_counts={DRIFT_STALE: 2}, first_encounter_keys=("k1",), frequent_keys=("k2", "k3"), rows=())
        d = r.to_dict()
        self.assertEqual(d["n_envelopes"], 10)
        self.assertEqual(d["n_valid"], 7)
        self.assertIn("envelopes", d)
    def test_csv_header(self):
        r = DriftReport(directory="/tmp", generated_at=0.0, n_envelopes=0, n_valid=0, n_drift=0, n_invalid=0, n_expired=0, n_not_yet_valid=0, n_malformed=0, drift_counts={}, first_encounter_keys=(), frequent_keys=(), rows=())
        csv = r.to_csv()
        self.assertIn("envelope_id", csv)
        self.assertIn("drift_flags", csv)

class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.secret = b"super-secret-key-1"
    def _reg(self, key_id="k1"):
        r = KeyRegistry()
        r.register(key_id=key_id, key=self.secret)
        return r
    def test_fresh_valid(self):
        _hmac(self.tmp, "k1", self.secret, age=0)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertEqual(rep.n_envelopes, 1)
        self.assertEqual(rep.n_valid, 1)
        self.assertEqual(rep.n_invalid, 0)
        self.assertEqual(rep.n_malformed, 0)
    def test_stale(self):
        _hmac(self.tmp, "k1", self.secret, age=7200)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time(), stale_threshold_seconds=3600))
        self.assertIn(DRIFT_STALE, rep.rows[0].drift_flags)
        self.assertGreater(rep.n_drift, 0)
    def test_expired(self):
        _hmac(self.tmp, "k1", self.secret, age=0, exp_in=-10)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_EXPIRED, rep.rows[0].drift_flags)
    def test_not_yet_valid(self):
        _hmac(self.tmp, "k1", self.secret, age=0, nb_in=600)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_NOT_YET_VALID, rep.rows[0].drift_flags)
    def test_unknown_key(self):
        _hmac(self.tmp, "ghost", self.secret, age=0)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg("k1"), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_UNKNOWN_KEY, rep.rows[0].drift_flags)
        self.assertEqual(rep.n_invalid, 1)
    def test_invalid_signature(self):
        p = _hmac(self.tmp, "k1", self.secret, age=0)
        import json
        d = json.loads(p.read_text())
        d["signature"] = d["signature"][:-4] + "AAAA"
        p.write_text(json.dumps(d))
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_INVALID_SIGNATURE, rep.rows[0].drift_flags)
    def test_payload_mismatch(self):
        p = _hmac(self.tmp, "k1", self.secret, age=0)
        import json
        d = json.loads(p.read_text())
        d["payload"]["advisory_id"] = "tampered"
        p.write_text(json.dumps(d))
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_PAYLOAD_MISMATCH, rep.rows[0].drift_flags)
    def test_malformed(self):
        p = self.tmp / "bad.json"
        p.write_text("not json {{{")
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertEqual(rep.n_malformed, 1)
    def test_first_encounter(self):
        _hmac(self.tmp, "newkey", self.secret, age=0)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg("newkey"), config=DriftConfig(now=time.time()))
        self.assertIn(DRIFT_FIRST_ENCOUNTER, rep.rows[0].drift_flags)
        self.assertIn("newkey", rep.first_encounter_keys)
    def test_frequent(self):
        for i in range(3):
            _hmac(self.tmp, "k1", self.secret, age=i)
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertIn("k1", rep.frequent_keys)
    def test_old_algorithm(self):
        priv, pub = generate_ed25519_keypair()
        payload = {"advisory_id": "adv-ed1", "note": "ed"}
        cfg = EnvelopeConfig(algorithm=SignatureAlgorithm.ED25519.value)
        env = sign_envelope(payload=payload, key_id="ed1", key=priv, config=cfg)
        (self.tmp / "ed1.json").write_text(envelope_to_json(env))
        reg = KeyRegistry()
        reg.register(key_id="ed1", key=pub)
        rep = scan_drift_signal(str(self.tmp), registry=reg, config=DriftConfig(now=time.time(), trusted_algorithms=frozenset({"hmac-sha256"})))
        self.assertIn(DRIFT_OLD_ALGORITHM, rep.rows[0].drift_flags)
    def test_empty_dir(self):
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertEqual(rep.n_envelopes, 0)
    def test_ignores_non_json(self):
        (self.tmp / "readme.txt").write_text("not an envelope")
        rep = scan_drift_signal(str(self.tmp), registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertEqual(rep.n_envelopes, 0)
    def test_deterministic(self):
        for i in range(3):
            _hmac(self.tmp, "k1", self.secret, age=i*10)
        cfg = DriftConfig(now=time.time())
        r1 = scan_drift_signal(str(self.tmp), registry=self._reg(), config=cfg)
        r2 = scan_drift_signal(str(self.tmp), registry=self._reg(), config=cfg)
        self.assertEqual([row.envelope_id for row in r1.rows], [row.envelope_id for row in r2.rows])
    def test_from_paths(self):
        p1 = _hmac(self.tmp, "k1", self.secret, age=0)
        p2 = _hmac(self.tmp, "k1", self.secret, age=0)
        rep = scan_drift_signal_from_paths([str(p1), str(p2)], registry=self._reg(), config=DriftConfig(now=time.time()))
        self.assertEqual(rep.n_envelopes, 2)

class TestWriteReport(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
    def test_csv_and_json(self):
        r = DriftReport(directory="/tmp", generated_at=0.0, n_envelopes=0, n_valid=0, n_drift=0, n_invalid=0, n_expired=0, n_not_yet_valid=0, n_malformed=0, drift_counts={}, first_encounter_keys=(), frequent_keys=(), rows=())
        write_drift_report(r, csv_path=str(self.tmp / "a.csv"), json_path=str(self.tmp / "a.json"))
        self.assertTrue((self.tmp / "a.csv").exists())
        self.assertTrue((self.tmp / "a.json").exists())
    def test_csv_only(self):
        r = DriftReport(directory="/tmp", generated_at=0.0, n_envelopes=0, n_valid=0, n_drift=0, n_invalid=0, n_expired=0, n_not_yet_valid=0, n_malformed=0, drift_counts={}, first_encounter_keys=(), frequent_keys=(), rows=())
        write_drift_report(r, csv_path=str(self.tmp / "b.csv"))
        self.assertTrue((self.tmp / "b.csv").exists())
    def test_json_only(self):
        r = DriftReport(directory="/tmp", generated_at=0.0, n_envelopes=0, n_valid=0, n_drift=0, n_invalid=0, n_expired=0, n_not_yet_valid=0, n_malformed=0, drift_counts={}, first_encounter_keys=(), frequent_keys=(), rows=())
        write_drift_report(r, json_path=str(self.tmp / "b.json"))
        self.assertTrue((self.tmp / "b.json").exists())
    def test_neither_raises(self):
        r = DriftReport(directory="/tmp", generated_at=0.0, n_envelopes=0, n_valid=0, n_drift=0, n_invalid=0, n_expired=0, n_not_yet_valid=0, n_malformed=0, drift_counts={}, first_encounter_keys=(), frequent_keys=(), rows=())
        write_drift_report(r)


class TestCLISubprocess(unittest.TestCase):
    def test_cli_runs(self):
        import os, tempfile
        d = tempfile.mkdtemp()
        s = tempfile.NamedTemporaryFile(delete=False); s.write(b"k1"); s.close()
        r = subprocess.run([sys.executable, "-m", "cli.drift_signal", "scan",
            "--envelopes-dir", d, "--hmac-secret-file", s.name, "--summary"],
            capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "/home/workspace/agi-research"})
        self.assertIn("n_envelopes", r.stderr)

if __name__ == "__main__":
    unittest.main()
