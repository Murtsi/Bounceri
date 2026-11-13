"""Arviointi (B-7): kynnykset opetusjoukolla, luvut testijoukolla → S8-muoto.

Rehellisyyssäännöt (AGENTS.md §7, ARCHITECTURE.md §5), jotka tämä koodi pakottaa:

- Kynnykset valitaan **vain opetusjoukolla**; testijoukkoa ei katsota ennen kuin
  kynnykset ovat lukossa.
- Simuloitu ja oikea liikenne raportoidaan erikseen (`split`).
- Ansat ovat labeleita, joten pisteyttäjä ajetaan arvioinnissa **ilman ansoja**.
  DNS-varmistetut botit ovat labeleita ja samalla varma sääntö → kehämäinen, joten
  `source == "dns"` -rivit jätetään luvuista pois ja niiden määrä raportoidaan.
- Ihmisten FPR raportoidaan otoskoon ja 95 %:n Wilson-ylärajan kanssa: 0/40 ei
  todista, että FPR < 1 %.
- Synteettisellä datalla laskettuja lukuja ei voi kirjoittaa `models/metrics.json`:iin.

Päätökset 028–031.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bouncer.contracts import Campaign, IpIntel, Label, Session, Verdict
from bouncer.eval.dataset import Dataset, DatasetRow
from bouncer.eval.metrics import METRICS_PATH, validate
from bouncer.eval.split import Split, temporal_split
from bouncer.eval.weaknesses import KNOWN_WEAKNESSES

Scorer = Callable[..., Verdict]

#: Ihmisten FPR:n yläraja botti-kynnykselle (IDEA.md: < 1 %).
MAX_HUMAN_FPR = 0.01
#: Kuinka suuri osa boteista saa jäädä ihminen-kynnyksen alle (päätös 029).
MAX_BOT_AS_HUMAN = 0.05
#: Wilsonin välin z (95 %).
Z95 = 1.959964

TRUTH_ORDER: tuple[Label, ...] = ("human", "good_bot", "bad_bot")
PRED_ORDER: tuple[Label, ...] = ("human", "good_bot", "bad_bot", "uncertain")


# --- kynnykset -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Thresholds:
    bot: float | None  # score ≥ bot → bad_bot. None = ei koskaan (ei kalibroitu)
    human: float | None  # score ≤ human → human. None = ei koskaan
    calibrated: bool
    note: str = ""


def choose_thresholds(
    humans: Sequence[float],
    bots: Sequence[float],
    max_human_fpr: float = MAX_HUMAN_FPR,
    max_bot_as_human: float = MAX_BOT_AS_HUMAN,
) -> Thresholds:
    """Valitsee kynnykset opetusjoukon pisteistä.

    - `bot`: pienin kynnys, jolla ihmisistä ≤ `max_human_fpr` saa score ≥ kynnys.
    - `human`: suurin kynnys < `bot`, jolla boteista ≤ `max_bot_as_human` saa
      score ≤ kynnys. Välissä = `uncertain`.
    Ilman ihmisiä tai botteja ei voi kalibroida → kynnys None (ei päätöstä).
    """
    if not humans:
        return Thresholds(None, None, False, "opetusjoukossa ei ihmisiä: FPR:ää ei voi kalibroida")
    candidates = sorted(set(humans) | set(bots))

    bot_t = next(
        (t for t in candidates if sum(h >= t for h in humans) / len(humans) <= max_human_fpr),
        None,
    )
    if not bots:
        return Thresholds(bot_t, None, False, "opetusjoukossa ei botteja")

    human_t = None
    for t in candidates:
        if bot_t is not None and t >= bot_t:
            break
        if sum(b <= t for b in bots) / len(bots) <= max_bot_as_human:
            human_t = t
    return Thresholds(bot_t, human_t, True)


def apply_thresholds(verdict: Verdict, th: Thresholds) -> Label:
    """Lopullinen luokka. `good_bot` tulee vain varmasta säännöstä, joten se säilyy."""
    if verdict.label == "good_bot":
        return "good_bot"
    if th.bot is not None and verdict.score >= th.bot:
        return "bad_bot"
    if th.human is not None and verdict.score <= th.human:
        return "human"
    return "uncertain"


# --- luvut ---------------------------------------------------------------------


def wilson_upper(k: int, n: int, z: float = Z95) -> float | None:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (centre + margin) / denom)


def _ratio(k: int, n: int) -> float | None:
    return k / n if n else None


def metrics_for(rows: Sequence[DatasetRow], preds: Mapping[str, Label]) -> dict[str, Any]:
    """Luvut yhdelle osajoukolle. `preds`: session_id → lopullinen luokka."""
    rows = [r for r in rows if r.session_id in preds]
    confusion = [[0] * len(PRED_ORDER) for _ in TRUTH_ORDER]
    for r in rows:
        confusion[TRUTH_ORDER.index(r.truth)][PRED_ORDER.index(preds[r.session_id])] += 1

    humans = [r for r in rows if r.truth == "human"]
    human_fp = sum(preds[r.session_id] in ("good_bot", "bad_bot") for r in humans)
    bots = [r for r in rows if r.truth != "human"]

    per_class: dict[str, dict[str, Any]] = {}
    for label in TRUTH_ORDER:
        tp = sum(r.truth == label and preds[r.session_id] == label for r in rows)
        predicted = sum(preds[r.session_id] == label for r in rows)
        actual = sum(r.truth == label for r in rows)
        per_class[label] = {
            "n": actual,
            "precision": _ratio(tp, predicted),
            "recall": _ratio(tp, actual),
        }
    # Alaluokat (scraper, scanner, …): kuinka moni tunnistettiin botiksi oikein.
    for sub in sorted({r.subclass for r in bots}):
        sub_rows = [r for r in bots if r.subclass == sub]
        hit = sum(preds[r.session_id] == r.truth for r in sub_rows)
        per_class[f"sub:{sub}"] = {"n": len(sub_rows), "recall": _ratio(hit, len(sub_rows))}

    uncertain = sum(preds[r.session_id] == "uncertain" for r in rows)
    bot_hit = sum(preds[r.session_id] == r.truth for r in bots)
    return {
        "n": len(rows),
        "n_humans": len(humans),
        "human_fpr": _ratio(human_fp, len(humans)),
        "human_fpr_ci95_upper": wilson_upper(human_fp, len(humans)),
        "bot_recall": _ratio(bot_hit, len(bots)),
        "uncertain_share": _ratio(uncertain, len(rows)),
        "per_class": per_class,
        "confusion": confusion,
    }


# --- koko ajo ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvalResult:
    metrics: dict[str, Any]
    split: Split
    thresholds: Thresholds
    synthetic: bool


def _predict(
    rows: Sequence[DatasetRow],
    sessions: Mapping[str, Session],
    scorer: Scorer,
    intel_by_ip: Mapping[str, IpIntel],
    campaign_by_session: Mapping[str, Campaign],
    network: bool,
) -> dict[str, Verdict]:
    out = {}
    for r in rows:
        s = sessions[r.session_id]
        intel = intel_by_ip.get(s.ip) if network else None
        camp = campaign_by_session.get(s.id) if network else None
        out[r.session_id] = scorer(s, intel, camp, traps=frozenset())  # ansat = labeleita
    return out


def run_evaluation(
    dataset: Dataset,
    sessions: Mapping[str, Session],
    scorer: Scorer,
    model_version: str,
    *,
    synthetic: bool,
    intel_by_ip: Mapping[str, IpIntel] | None = None,
    campaign_by_session: Mapping[str, Campaign] | None = None,
    hidden: Dataset | None = None,
    known_weaknesses: Sequence[str] | None = None,
    test_fraction: float = 0.3,
) -> EvalResult:
    """Koko B-7-arviointi. `scorer(session, intel, campaign, *, traps)` → Verdict.

    `synthetic=True` merkitsee, ettei luvuilla ole todistusarvoa (testidata).
    `hidden`: piilotetun hyökkäyksen datasetti (B-11) — ei käytetä kynnyksiin.
    `known_weaknesses=None` → `weaknesses.KNOWN_WEAKNESSES`.
    """
    intel_by_ip = intel_by_ip or {}
    campaign_by_session = campaign_by_session or {}
    usable = [r for r in dataset.rows if r.source != "dns"]
    excluded_dns = len(dataset.rows) - len(usable)
    split = temporal_split(usable, test_fraction=test_fraction)

    def scored(rows: Sequence[DatasetRow], network: bool = True) -> dict[str, Verdict]:
        return _predict(rows, sessions, scorer, intel_by_ip, campaign_by_session, network)

    train_v = scored(split.train)
    th = choose_thresholds(
        [train_v[r.session_id].score for r in split.train if r.truth == "human"],
        [train_v[r.session_id].score for r in split.train if r.truth != "human"],
    )

    test_v = scored(split.test)
    preds = {sid: apply_thresholds(v, th) for sid, v in test_v.items()}
    overall = metrics_for(split.test, preds)

    test_nonet = scored(split.test, network=False)
    ablation = metrics_for(split.test, {k: apply_thresholds(v, th) for k, v in test_nonet.items()})

    hidden_metrics: dict[str, Any] = {}
    if hidden is not None and hidden.rows:
        hidden_rows = [r for r in hidden.rows if r.source != "dns"]
        hv = scored(hidden_rows)
        hidden_metrics = metrics_for(
            hidden_rows, {k: apply_thresholds(v, th) for k, v in hv.items()}
        )

    times = [r.started_at for r in split.test]
    metrics = {
        "model_version": model_version,
        "test_window": {"from": min(times).isoformat(), "to": max(times).isoformat()},
        "threshold": {"bot": th.bot, "human": th.human},
        "human_fpr": overall["human_fpr"],
        "human_fpr_ci95_upper": overall["human_fpr_ci95_upper"],
        "per_class": overall["per_class"],
        "uncertain_share": overall["uncertain_share"],
        "confusion": overall["confusion"],
        "confusion_axes": {"truth": list(TRUTH_ORDER), "pred": list(PRED_ORDER)},
        "split": {
            "simulated": metrics_for([r for r in split.test if r.origin == "simulated"], preds),
            "real": metrics_for([r for r in split.test if r.origin == "real"], preds),
            "hidden_attack": hidden_metrics,
        },
        "ablation": {
            "without_network_signals": {
                "human_fpr": ablation["human_fpr"],
                "recall": ablation["bot_recall"],
            }
        },
        "known_weaknesses": list(
            KNOWN_WEAKNESSES if known_weaknesses is None else known_weaknesses
        ),
        "data": {
            "synthetic": synthetic,
            "n_train": len(split.train),
            "n_test": len(split.test),
            "cutoff": split.cutoff.isoformat(),
            "straddling_runs": list(split.straddling_runs),
            "excluded_dns_labelled": excluded_dns,
            "thresholds_calibrated": th.calibrated,
            "thresholds_note": th.note,
        },
        "stub": False,
    }
    return EvalResult(metrics, split, th, synthetic)


def write_metrics(result: EvalResult, path: Path = METRICS_PATH) -> None:
    """Kirjoittaa S8-tiedoston.

    Kieltäytyy synteettisestä datasta ja kalibroimattomista kynnyksistä.
    """
    if result.synthetic:
        raise ValueError("synteettisen datan lukuja ei kirjoiteta metrics.json:iin")
    if not result.thresholds.calibrated:
        raise ValueError(f"kynnyksiä ei kalibroitu: {result.thresholds.note}")
    errors = validate(result.metrics)
    if errors:
        raise ValueError(f"skeemavirheet: {errors}")
    text = json.dumps(result.metrics, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", "utf-8")
