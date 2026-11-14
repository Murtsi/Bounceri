"""MVP:n simulaattorit (tools/sim): suunnitelma ja allekirjoitetut pyynnöt, ilman verkkoa."""

from bouncer.ingest import simrun
from tools.sim import run as sim

SECRET = "test-secret"  # testiarvo


def test_plan_covers_every_mvp_scenario():
    actors = sim.plan("r1", seed=1, humans=3)
    classes = [a.sim_class for a in actors]
    assert classes.count("human") == 3
    assert {"scraper", "scanner", "credential_stuffing"} <= set(classes)
    assert any(a.ua == sim.GOOGLEBOT_UA and a.ip == sim.FAKE_GOOGLEBOT_IP for a in actors)
    assert len({a.ip for a in actors}) == len(actors)  # jokaisella oma IP


def test_stuffing_is_one_campaign_same_username_many_ips():
    actors = [a for a in sim.plan("r1") if a.sim_class == "credential_stuffing"]
    assert len(actors) >= 4 and len({a.campaign for a in actors}) == 1
    assert all(a.steps[0].method == "POST" and "username=admin" in a.steps[0].data for a in actors)


def test_humans_fetch_assets_and_send_browser_headers():
    h = sim.human(0, __import__("random").Random(1), "http://x")
    pages = [s for s in h.steps if not s.path.startswith("/static/")]
    assert len(h.steps) == len(pages) * 4  # jokaiselle sivulle CSS + JS + kuva
    assert all("Accept-Language" in s.headers and "Sec-Fetch-Mode" in s.headers for s in pages)
    assert all("Referer" in s.headers for s in pages[1:])


def test_request_is_signed_and_carries_client_ip():
    actor = sim.scanner()
    req = sim.build_request("http://127.0.0.1:8080", actor, actor.steps[0], "r1", SECRET)
    marker = req.get_header("X-sim-run")
    assert marker == "r1-scanner:scanner:-"
    assert simrun.verify(marker, req.get_header("X-sim-sig"), SECRET)
    assert req.get_header("X-forwarded-for") == actor.ip
    assert req.full_url == "http://127.0.0.1:8080/.env"


def test_cli_needs_secret(monkeypatch, capsys):
    monkeypatch.delenv(simrun.SECRET_ENV, raising=False)
    assert sim.main(["--dry-run"]) == 1
    monkeypatch.setenv(simrun.SECRET_ENV, SECRET)
    assert sim.main(["--dry-run", "--run-id", "r1"]) == 0
    assert "r1-stuff0:credential_stuffing:camp-stuff-r1" in capsys.readouterr().out
