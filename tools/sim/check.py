"""MVP:n hyväksymistarkistus (docs/MVP.md, kriteerit 1–6) API:n kautta.

    uv run python tools/sim/check.py --api http://127.0.0.1:8001 --expect 15

Odottaa, että worker on käsitellyt simulaattoriajon, ja tarkistaa jokaisen
kriteerin. Paluukoodi 0 = kaikki kunnossa. Ei katso mitään käsin.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from tools.sim.run import FAKE_GOOGLEBOT_IP

Check = tuple[str, str, Callable[[], tuple[bool, str]]]


def _get(api: str, path: str) -> Any:
    with urllib.request.urlopen(api + path, timeout=5) as r:
        body = r.read().decode()
    return json.loads(body) if path.startswith("/api/") else body


def wait_for(api: str, expect: int, timeout_s: float) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_s
    rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        try:
            rows = _get(api, "/api/sessions")
        except OSError:
            rows = []
        if sum(r["sim_class"] is not None for r in rows) >= expect:
            return rows
        time.sleep(1)
    return rows


def checks(api: str, rows: list[dict[str, Any]]) -> list[Check]:
    def of(cls: str) -> list[dict[str, Any]]:
        return [r for r in rows if r["sim_class"] == cls]

    def c1() -> tuple[bool, str]:
        s = of("scanner")
        ok = bool(s) and all(
            r["label"] == "bad_bot" and "haavoittuvuuspolku" in r["reason"] for r in s
        )
        return ok, f"{len(s)} skanneria: {[r['label'] for r in s]}"

    def c2() -> tuple[bool, str]:
        s = of("credential_stuffing")
        ok = len(s) >= 3 and all(r["label"] == "bad_bot" and r["campaign_id"] for r in s)
        return ok, f"{len(s)} sessiota, bad_bot {sum(r['label'] == 'bad_bot' for r in s)}"

    def c3() -> tuple[bool, str]:
        s = of("human")
        bad = [r["ip"] for r in s if r["label"] == "bad_bot"]
        return bool(s) and not bad, f"{len(s)} ihmistä, väärät hälytykset: {bad or 0}"

    def c4() -> tuple[bool, str]:
        s = [r for r in rows if r["ip"] == FAKE_GOOGLEBOT_IP]
        ok = bool(s) and all(r["label"] == "bad_bot" and "googlebot" in r["reason"] for r in s)
        return ok, f"{[r['label'] for r in s]} (vaatii DNS:n)"

    def c5() -> tuple[bool, str]:
        bad = next((r for r in rows if r["label"] == "bad_bot"), None)
        if bad is None:
            return False, "ei bad_bot-sessiota"
        d = _get(api, f"/api/sessions/{bad['id']}")
        v = d["verdict"]
        ok = 1 <= len(v["reasons"]) <= 3 and bool(v.get("explanation")) and bool(d["requests"])
        has = "on" if v.get("explanation") else "puuttuu"
        return ok, f"syitä {len(v['reasons'])}, selitys {has}"

    def c6() -> tuple[bool, str]:
        m = _get(api, "/api/metrics")
        page = _get(api, "/")
        honest = m["stub"] or m["synthetic_data"]
        ok = honest and len(m["known_weaknesses"]) >= 5 and '<div id="root">' in page
        n_weak = len(m["known_weaknesses"])
        return ok, f"stub={m['stub']} synteettinen={m['synthetic_data']} heikkouksia {n_weak}"

    return [
        ("1", "Skanneri → bad_bot", c1),
        ("2", "Tunnusten kokeilu → kampanja + bad_bot", c2),
        ("3", "Ihmiset eivät koskaan bad_bot", c3),
        ("4", "Väärennetty Googlebot → bad_bot", c4),
        ("5", "Session kortti: syyt + selitys", c5),
        ("6", "Mittarit rehellisesti + dashboard", c6),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MVP:n hyväksymistarkistus")
    ap.add_argument("--api", default="http://127.0.0.1:8001")
    ap.add_argument("--expect", type=int, default=15, help="labeloituja sessioita vähintään")
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args(argv)
    rows = wait_for(a.api, a.expect, a.timeout)
    if not rows:
        print(f"API {a.api} ei vastaa tai sessioita ei ole")
        return 1
    failed = 0
    for num, name, fn in checks(a.api, rows):
        try:
            ok, detail = fn()
        except Exception as e:  # tarkistus ei saa kaatua hiljaa
            ok, detail = False, f"virhe: {e}"
        failed += not ok
        print(f"{'✅' if ok else '❌'} {num} {name:42} {detail}")
    print(f"\n{6 - failed}/6 kriteeriä täyttyy" + ("" if failed else " — MVP toimii."))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
