"""Kaikkien kaistojen yhteinen: testit eivät saa riippua kehittäjän ympäristöstä.

`SIM_RUN_SECRET` (päätös 046) voi olla asetettu kehittäjän shellissä tai `.env`-
tiedostossa; silloin parseri vaatisi allekirjoitukset myös testien fixtureilta.
Testi, joka tarvitsee avaimen, asettaa sen itse (monkeypatch.setenv).
"""

import pytest


@pytest.fixture(autouse=True)
def _no_sim_run_secret_from_environment(monkeypatch):
    monkeypatch.delenv("SIM_RUN_SECRET", raising=False)
