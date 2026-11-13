"""`score()` — sopimus S6 (B → A).

B-1: stub, joka palauttaa aina `uncertain`. Oikeat säännöt B-4:ssä, malli B-6:ssa.
"""

from __future__ import annotations

from bouncer.session._provisional_types import Campaign, IpIntel, Session, Verdict

MODEL_VERSION = "stub-v0"
MAX_REASONS = 3


def score(session: Session, intel: IpIntel | None, campaign: Campaign | None) -> Verdict:
    """Pisteyttää yhden session. Puhdas funktio: ei I/O:ta, ei tietokantaa.

    `intel` ja `campaign` voivat olla None, jos C:n tietoa ei ole saatavilla.
    """
    del session, intel, campaign  # stub ei vielä käytä syötteitä
    return Verdict(
        label="uncertain",
        score=0.5,
        reasons=("stub: tunnistusta ei ole vielä toteutettu",),
        model_version=MODEL_VERSION,
    )
