"""`score()` — sopimus S6 (B → A).

B-4: varmat säännöt (`rules.py`). Jos mikään ei osu → `uncertain` + havainnot
syinä. Malli (B-6) korvaa `uncertain`-haaran.
"""

from __future__ import annotations

from bouncer.contracts import Campaign, IpIntel, Session, Verdict
from bouncer.session import rules
from bouncer.session.features import compute_features

MODEL_VERSION = "rules-v1"
MAX_REASONS = 3
UNCERTAIN_SCORE = 0.5
NO_SIGNAL_REASON = "Ei varmaa sääntöosumaa; malli (B-6) ei ole vielä käytössä"


def score(
    session: Session,
    intel: IpIntel | None,
    campaign: Campaign | None,
    *,
    traps: frozenset[str] | None = None,
) -> Verdict:
    """Pisteyttää yhden session. Puhdas funktio: ei tietokantaa.

    `intel` ja `campaign` voivat olla None, jos C:n tietoa ei ole saatavilla.
    `traps` oletuksena A:n `deploy/traps.txt` (luetaan kerran, välimuistissa).
    """
    del campaign  # käytetään vasta mallissa (B-6)
    if traps is None:
        traps = rules.load_traps()

    hits = rules.evaluate(session, intel, traps)
    if hits:
        top = hits[0]
        reasons = [h.reason for h in hits]
        if len(reasons) < MAX_REASONS:
            reasons += rules.observations(compute_features(session))
        return Verdict(
            label=top.label,
            score=top.score,
            reasons=tuple(dict.fromkeys(reasons))[:MAX_REASONS],
            model_version=MODEL_VERSION,
        )

    obs = rules.observations(compute_features(session))
    return Verdict(
        label="uncertain",
        score=UNCERTAIN_SCORE,
        reasons=tuple(obs[:MAX_REASONS]) or (NO_SIGNAL_REASON,),
        model_version=MODEL_VERSION,
    )
