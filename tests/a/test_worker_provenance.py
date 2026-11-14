from bouncer.contracts import IpIntel
from bouncer.ingest.worker import Worker
from tests.a.test_worker import SECRET, _rec, _write


class Resolver:
    def __init__(self):
        self.cycles = 0
        self.calls = 0

    def begin_cycle(self):
        self.cycles += 1

    def __call__(self, ip):
        self.calls += 1
        return IpIntel(verified_bot=True if self.cycles == 1 else None)

    def observation(self, ip):
        return {"checked_at": "2026-11-14T12:00:00+00:00",
                "resolver_outcome": "verified" if self.cycles == 1 else "timeout",
                "verified_bot": True if self.cycles == 1 else None,
                "asn": None, "asn_type": "unknown", "country": None,
                "asn_origin": "unknown", "crawler": "googlebot" if self.cycles == 1 else None}


def test_worker_retains_actual_network_and_rule_observations(tmp_path, monkeypatch):
    log = tmp_path / "access.log"
    _write(log, [_rec(1000, "192.0.2.1", uri="/trap", ua="Googlebot"),
                 _rec(1001, "192.0.2.1", uri="/trap", ua="other-client")], "w")
    monkeypatch.setattr("bouncer.ingest.worker.rules.load_traps", lambda: frozenset({"/trap"}))
    resolver = Resolver()
    w = Worker(log, tmp_path / "store.json", secret=SECRET, intel_fn=resolver,
               campaigns_fn=None, synthetic=True)
    first = w.cycle()
    assert resolver.cycles == 1 and resolver.calls == 1
    assert first["ip_evidence"]["192.0.2.1"]["verified_bot"] is True
    for session in first["sessions"]:
        observation = first["rule_observations"][session["id"]]
        assert observation["trap_hits"] == 1
        assert len(observation["trap_config_version"]) == 64
        assert "trap" in observation["rule_ids"]
        assert observation["features"]["vuln_path_hits"] == 0
    second = w.cycle()
    assert resolver.cycles == 2 and resolver.calls == 2
    assert second["ip_evidence"]["192.0.2.1"]["verified_bot"] is None
    assert all(v["verified_bot"] is None for v in second["verdicts"].values())


def test_worker_copies_evidence_before_resolver_observation_eviction(tmp_path):
    import json

    from bouncer.network.live import LiveIntel
    def lookup(ip, timeout):
        return json.dumps({"checked_at": "2026-11-14T12:00:00+00:00",
                           "resolver_outcome": "verified", "verified_bot": True,
                           "asn": None, "asn_type": "unknown", "country": None,
                           "asn_origin": "unknown", "crawler": "googlebot"}).encode()
    resolver = LiveIntel(runner=lookup, cache_size=1)
    _write(tmp_path / "access.log", [_rec(1000, "192.0.2.1", ua="Googlebot"),
                                    _rec(1001, "192.0.2.2", ua="Googlebot")], "w")
    w = Worker(tmp_path / "access.log", tmp_path / "store.json", secret=SECRET,
               intel_fn=resolver, campaigns_fn=None, synthetic=True)
    snapshot = w.cycle()
    assert all(row["verified_bot"] is True for row in snapshot["ip_evidence"].values())
