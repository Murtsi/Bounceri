"""Temporaalinen train/test-jako (B-7, ARCHITECTURE.md §5).

Opetus ja kynnysten valinta tehdään *ennen* ajanhetkeä `cutoff` alkaneilla
sessioilla, testi sen jälkeen alkaneilla. Satunnainen jako vuotaisi saman
hyökkäysajon sessioita molemmille puolille ja antaisi liian hyvät luvut.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from bouncer.eval.dataset import DatasetRow

DEFAULT_TEST_FRACTION = 0.3


@dataclass(frozen=True, slots=True)
class Split:
    train: list[DatasetRow]
    test: list[DatasetRow]
    cutoff: datetime
    #: Ajot/kampanjat, joilla on sessioita molemmin puolin rajaa. Ei virhe
    #: (pitkä hyökkäys jatkuu yli rajan), mutta raportoidaan, koska ne tekevät
    #: testistä helpomman kuin täysin uusi hyökkäys (vrt. piilotettu hyökkäys).
    straddling_runs: tuple[str, ...]


def temporal_split(
    rows: Sequence[DatasetRow],
    cutoff: datetime | None = None,
    test_fraction: float = DEFAULT_TEST_FRACTION,
) -> Split:
    """Jakaa rivit `started_at`-ajan mukaan.

    `cutoff=None` → raja valitaan niin, että myöhäisin ~`test_fraction` osa
    sessioista menee testiin. Rajalla alkava sessio menee testiin.
    """
    if not rows:
        raise ValueError("tyhjä datasetti")
    if cutoff is None:
        if not 0.0 < test_fraction < 1.0:
            raise ValueError("test_fraction pitää olla välillä (0, 1)")
        times = sorted(r.started_at for r in rows)
        idx = min(len(times) - 1, max(1, round(len(times) * (1.0 - test_fraction))))
        cutoff = times[idx]

    train = [r for r in rows if r.started_at < cutoff]
    test = [r for r in rows if r.started_at >= cutoff]
    train_runs = {r.run_id for r in train if r.run_id}
    test_runs = {r.run_id for r in test if r.run_id}
    return Split(train, test, cutoff, tuple(sorted(train_runs & test_runs)))
