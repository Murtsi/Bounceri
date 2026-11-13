"""PoC-skripti (`notebooks/b/poc.py`) pysyy toimivana: A → C → B → C-selitys."""

import importlib.util
from pathlib import Path

POC = Path(__file__).resolve().parents[2] / "notebooks" / "b" / "poc.py"


def _load():
    spec = importlib.util.spec_from_file_location("b_poc", POC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_poc_runs_offline_end_to_end():
    poc = _load()
    rows = poc.run(dns=False)
    assert len(rows) == 8  # A:n näyte (3) + C:n stuffing-fixture (5), yksi numerointi
    assert len({r["id"] for r in rows}) == len(rows)
    scanner = next(r for r in rows if r["truth"] == "scanner")
    assert scanner["rules"].startswith("bad_bot")
    stuffed = [r for r in rows if r["truth"] == "credential_stuffing"]
    assert stuffed and all(r["campaign"].startswith("credential_stuffing") for r in stuffed)
    assert all(r["explain"].startswith("Verdict:") for r in rows)
    md = poc.to_markdown(rows)
    assert "synteettinen" in md
