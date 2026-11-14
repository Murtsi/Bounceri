"""`score()` — sopimus S6 (B → A).

Kolme kerrosta (ARCHITECTURE.md §3):
1. Varmat säännöt (`rules.py`) — osuma ratkaisee.
2. Malli (`model.py`, B-6) — P(botti), jos `models/model.json` on olemassa.
3. Kynnykset mallin tiedostosta → `bad_bot` / `human` / `uncertain`.

Ilman mallitiedostoa käytös on sama kuin `rules-v1`: ei osumaa → `uncertain`.
"""

from __future__ import annotations

import functools

from bouncer.contracts import Campaign, IpIntel, Label, Session, Verdict
from bouncer.session import rules
from bouncer.session.features import compute_features
from bouncer.session.model import LogisticModel, load_model, reasons, vectorize

MODEL_VERSION = "rules-v2"
MAX_REASONS = 3
UNCERTAIN_SCORE = 0.5
NO_SIGNAL_REASON = "Ei varmaa sääntöosumaa; malli (B-6) ei ole vielä käytössä"

_DEFAULT = object()


@functools.cache
def _default_model() -> LogisticModel | None:
    return load_model()


def _label(p: float, model: LogisticModel) -> Label:
    bot, human = model.thresholds.get("bot"), model.thresholds.get("human")
    if bot is not None and p >= bot:
        return "bad_bot"
    if human is not None and p <= human:
        return "human"
    return "uncertain"


def score(
    session: Session,
    intel: IpIntel | None,
    campaign: Campaign | None,
    *,
    traps: frozenset[str] | None = None,
    model: LogisticModel | None | object = _DEFAULT,
) -> Verdict:
    """Pisteyttää yhden session. Puhdas funktio: ei tietokantaa.

    `intel` ja `campaign` voivat olla None, jos C:n tietoa ei ole saatavilla.
    `traps` oletuksena A:n `deploy/traps.txt`; `model` oletuksena `models/model.json`
    (None = vain säännöt). Mallin kynnykset puuttuvat → luokka `uncertain`, mutta
    `score` on mallin todennäköisyys (arviointi käyttää sitä).
    """
    if traps is None:
        traps = rules.load_traps()
    m = _default_model() if model is _DEFAULT else model
    feats = compute_features(session)

    hits = rules.evaluate(session, intel, traps, campaign)
    if hits:
        top = hits[0]
        why = [h.reason for h in hits]
        if len(why) < MAX_REASONS:
            why += rules.observations(feats)
        return Verdict(
            label=top.label,
            score=top.score,
            reasons=tuple(dict.fromkeys(why))[:MAX_REASONS],
            model_version=m.model_version if isinstance(m, LogisticModel) else MODEL_VERSION,
        )

    if isinstance(m, LogisticModel):
        p = m.predict_proba(vectorize(feats, intel, campaign, m.network))
        label = _label(p, m)
        why = reasons(m, feats, intel, campaign, towards_bot=label == "bad_bot" or p >= 0.5)
        return Verdict(
            label=label,
            score=p,
            reasons=tuple(why[:MAX_REASONS]) or ("Mikään piirre ei poikennut tavallisesta",),
            model_version=m.model_version,
        )

    obs = rules.observations(feats)
    return Verdict(
        label="uncertain",
        score=UNCERTAIN_SCORE,
        reasons=tuple(obs[:MAX_REASONS]) or (NO_SIGNAL_REASON,),
        model_version=MODEL_VERSION,
    )
