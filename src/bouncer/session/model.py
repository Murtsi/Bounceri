"""Malli (B-6): logistinen regressio session piirteiden päällä, puhdas Python.

Miksi näin (päätös 034):
- 20 piirrettä → yksinkertainen lineaarinen malli riittää, ja kertoimista saa
  jokaiselle päätökselle rehellisen selityksen: "tämä piirre nosti
  bottitodennäköisyyttä eniten" (S6: `reasons[3]`).
- Ei riippuvuuksia (ei yhteistä `pyproject.toml`:ia, CI asentaa vain pytestin).
- Opetus IRLS:llä (Newtonin menetelmä) + L2 → deterministinen, konvergoi
  ~10 kierroksessa myös erottuvalla datalla.

Malli antaa vain todennäköisyyden P(botti). Varmat säännöt (`rules.py`) ajetaan
ennen mallia, ja lopullinen luokka tulee kynnyksistä (`evaluate.choose_thresholds`).
Ansapiirrettä ei ole syötteissä, koska ansat ovat labeleita (ARCHITECTURE.md §5).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bouncer.contracts import Campaign, IpIntel
from bouncer.session.features import SessionFeatures

MODEL_VERSION = "lr-v1"
MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "model.json"

L2 = 1.0
MAX_ITER = 50
TOL = 1e-8


@dataclass(frozen=True, slots=True)
class Feature:
    name: str
    value: Callable[[SessionFeatures, IpIntel | None, Campaign | None], float]
    describe: Callable[[SessionFeatures, IpIntel | None, Campaign | None], str]
    network: bool = False  # C:n signaali → pois ablaatiossa


def _b(x: bool) -> float:
    return 1.0 if x else 0.0


FEATURES: tuple[Feature, ...] = (
    Feature("log_n_requests", lambda f, i, c: math.log1p(f.n_requests),
            lambda f, i, c: f"{f.n_requests} pyyntöä sessiossa"),
    Feature("log_duration", lambda f, i, c: math.log1p(f.duration_s),
            lambda f, i, c: f"Session kesto {f.duration_s:.0f} s"),
    Feature("log_rpm", lambda f, i, c: math.log1p(f.requests_per_min),
            lambda f, i, c: f"Keskitahti {f.requests_per_min:.0f} pyyntöä/min"),
    Feature("log_peak_rpm", lambda f, i, c: math.log1p(f.peak_requests_per_min),
            lambda f, i, c: f"Huipputahti {f.peak_requests_per_min} pyyntöä/min"),
    Feature("interarrival_cv", lambda f, i, c: f.interarrival_cv or 0.0,
            lambda f, i, c: "Pyyntöjen välien vaihtelu "
            + ("ei mitattavissa" if f.interarrival_cv is None else f"{f.interarrival_cv:.2f}")),
    Feature("cv_missing", lambda f, i, c: _b(f.interarrival_cv is None),
            lambda f, i, c: "Alle 3 pyyntöä: välien vaihtelua ei voi mitata"),
    Feature("static_share", lambda f, i, c: f.static_share,
            lambda f, i, c: f"CSS/JS/kuvien osuus {f.static_share:.0%}"),
    Feature("html_share", lambda f, i, c: f.html_share,
            lambda f, i, c: f"HTML-sivujen osuus {f.html_share:.0%}"),
    Feature("path_diversity", lambda f, i, c: f.path_diversity,
            lambda f, i, c: f"Eri polkujen osuus {f.path_diversity:.0%}"),
    Feature("robots_txt", lambda f, i, c: _b(f.robots_txt_fetched),
            lambda f, i, c: "Haki robots.txt:n" if f.robots_txt_fetched
            else "Ei hakenut robots.txt:ää"),
    Feature("error_4xx_share", lambda f, i, c: f.error_4xx_share,
            lambda f, i, c: f"4xx-virheiden osuus {f.error_4xx_share:.0%}"),
    Feature("not_found_share", lambda f, i, c: f.not_found_share,
            lambda f, i, c: f"404-vastausten osuus {f.not_found_share:.0%}"),
    Feature("log_vuln_hits", lambda f, i, c: math.log1p(f.vuln_path_hits),
            lambda f, i, c: f"{f.vuln_path_hits} haavoittuvuuspolkua"),
    Feature("header_inconsistency", lambda f, i, c: f.header_inconsistency_share,
            lambda f, i, c: "Selaimen otsakkeita puuttui "
            f"{f.header_inconsistency_share:.0%} sivuista"),
    Feature("missing_referer", lambda f, i, c: f.missing_referer_share,
            lambda f, i, c: f"Referer puuttui {f.missing_referer_share:.0%} sisäsivuista"),
    Feature("ua_is_tool", lambda f, i, c: _b(f.ua_is_tool),
            lambda f, i, c: "User-Agent on työkalu tai kirjasto" if f.ua_is_tool
            else "User-Agent on selain"),
    Feature("ua_claims_bot", lambda f, i, c: _b(f.ua_claims_bot),
            lambda f, i, c: "User-Agent ilmoittaa olevansa botti" if f.ua_claims_bot
            else "User-Agent ei ilmoita olevansa botti"),
    Feature("asn_datacenter", lambda f, i, c: _b(i is not None and i.asn_type == "datacenter"),
            lambda f, i, c: "IP on datakeskuksessa" if i is not None and i.asn_type == "datacenter"
            else "IP ei ole datakeskuksessa", network=True),
    Feature("asn_consumer",
            lambda f, i, c: _b(i is not None and i.asn_type in ("residential", "mobile")),
            lambda f, i, c: "IP on koti- tai mobiililiittymä"
            if i is not None and i.asn_type in ("residential", "mobile")
            else "IP ei ole koti- tai mobiililiittymä", network=True),
    Feature("in_campaign", lambda f, i, c: _b(c is not None),
            lambda f, i, c: f"Kuuluu kampanjaan {c.id} ({c.kind})" if c is not None
            else "Ei kuulu tunnettuun kampanjaan", network=True),
)  # fmt: skip


def feature_names(network: bool = True) -> tuple[str, ...]:
    return tuple(f.name for f in FEATURES if network or not f.network)


def vectorize(
    feats: SessionFeatures, intel: IpIntel | None, campaign: Campaign | None, network: bool = True
) -> list[float]:
    return [f.value(feats, intel, campaign) for f in FEATURES if network or not f.network]


# --- lineaarialgebra (pieni d, puhdas Python) ------------------------------------


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussin eliminointi osittaisella pivotoinnilla. a on d×d, b pituus d."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("singulaarinen matriisi")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            k = m[r][col] / m[col][col]
            if k:
                for cc in range(col, n + 1):
                    m[r][cc] -= k * m[col][cc]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][cc] * x[cc] for cc in range(r + 1, n))) / m[r][r]
    return x


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


# --- malli ---------------------------------------------------------------------


@dataclass(slots=True)
class LogisticModel:
    names: tuple[str, ...]
    means: list[float]
    stds: list[float]
    weights: list[float]
    bias: float
    network: bool = True
    thresholds: dict[str, float | None] = field(
        default_factory=lambda: {"bot": None, "human": None}
    )
    trained: dict[str, Any] = field(default_factory=dict)
    model_version: str = MODEL_VERSION

    def _z(self, x: Sequence[float]) -> list[float]:
        return [(v - m) / s for v, m, s in zip(x, self.means, self.stds, strict=True)]

    def predict_proba(self, x: Sequence[float]) -> float:
        z = self._z(x)
        return _sigmoid(self.bias + sum(w * v for w, v in zip(self.weights, z, strict=True)))

    def contributions(self, x: Sequence[float]) -> list[tuple[str, float]]:
        """Kunkin piirteen osuus logitissa (w·z). Positiivinen = kohti bottia."""
        z = self._z(x)
        return [(n, w * v) for n, w, v in zip(self.names, self.weights, z, strict=True)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "kind": "logistic_regression",
            "names": list(self.names),
            "means": self.means,
            "stds": self.stds,
            "weights": self.weights,
            "bias": self.bias,
            "network": self.network,
            "thresholds": self.thresholds,
            "trained": self.trained,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> LogisticModel:
        names = tuple(d["names"])
        if names != feature_names(d.get("network", True)):
            raise ValueError("mallin piirteet eivät vastaa koodia — opeta uudelleen")
        return cls(
            names, list(d["means"]), list(d["stds"]), list(d["weights"]), float(d["bias"]),
            d.get("network", True), dict(d.get("thresholds", {})), dict(d.get("trained", {})),
            d.get("model_version", MODEL_VERSION),
        )  # fmt: skip


def fit(
    xs: Sequence[Sequence[float]],
    ys: Sequence[int],
    network: bool = True,
    l2: float = L2,
) -> LogisticModel:
    """Opettaa mallin. ys: 1 = botti, 0 = ihminen. Luokat painotetaan tasan."""
    n = len(xs)
    if n == 0 or len(set(ys)) < 2:
        raise ValueError("opetukseen tarvitaan sekä ihmisiä että botteja")
    d = len(xs[0])
    means = [sum(x[j] for x in xs) / n for j in range(d)]
    stds = []
    for j in range(d):
        var = sum((x[j] - means[j]) ** 2 for x in xs) / n
        stds.append(math.sqrt(var) if var > 1e-12 else 1.0)
    zs = [[1.0] + [(x[j] - means[j]) / stds[j] for j in range(d)] for x in xs]  # 0 = bias

    n_pos = sum(ys)
    sw = [n / (2 * n_pos) if y else n / (2 * (n - n_pos)) for y in ys]
    w = [0.0] * (d + 1)
    for _ in range(MAX_ITER):
        grad = [0.0] * (d + 1)
        hess = [[0.0] * (d + 1) for _ in range(d + 1)]
        for z, y, s in zip(zs, ys, sw, strict=True):
            p = _sigmoid(sum(a * b for a, b in zip(w, z, strict=True)))
            r = s * (y - p)
            q = s * p * (1 - p)
            for i in range(d + 1):
                grad[i] += r * z[i]
                qi = q * z[i]
                row = hess[i]
                for k in range(i, d + 1):
                    row[k] += qi * z[k]
        for i in range(d + 1):
            for k in range(i):
                hess[i][k] = hess[k][i]
        for i in range(1, d + 1):  # bias ei regularisoida
            grad[i] -= l2 * w[i]
            hess[i][i] += l2
        step = _solve(hess, grad)
        w = [a + b for a, b in zip(w, step, strict=True)]
        if max(abs(s) for s in step) < TOL:
            break
    return LogisticModel(feature_names(network), means, stds, w[1:], w[0], network)


def reasons(
    model: LogisticModel,
    feats: SessionFeatures,
    intel: IpIntel | None,
    campaign: Campaign | None,
    towards_bot: bool,
    k: int = 3,
) -> list[str]:
    """k eniten päätöksen suuntaan painanutta piirrettä selkokielisenä."""
    x = vectorize(feats, intel, campaign, model.network)
    contrib = model.contributions(x)
    by_name = {f.name: f for f in FEATURES}
    sign = 1.0 if towards_bot else -1.0
    ranked = sorted(contrib, key=lambda nc: sign * nc[1], reverse=True)
    out = []
    for name, c in ranked:
        if sign * c <= 0 or len(out) == k:
            break
        verb = "nosti" if c > 0 else "laski"
        out.append(
            f"{by_name[name].describe(feats, intel, campaign)} ({verb} bottitodennäköisyyttä)"
        )
    return out


def save_model(model: LogisticModel, path: Path = MODEL_PATH, *, synthetic: bool) -> None:
    """Tallentaa tuotantomallin. Kieltäytyy synteettisestä datasta ja kalibroimattomasta."""
    if synthetic:
        raise ValueError("synteettisellä datalla opetettua mallia ei tallenneta models/:iin")
    if model.thresholds.get("bot") is None:
        raise ValueError("mallilla ei ole kalibroitua botti-kynnystä")
    path.write_text(json.dumps(model.to_dict(), indent=2, ensure_ascii=False) + "\n", "utf-8")


def load_model(path: Path = MODEL_PATH) -> LogisticModel | None:
    try:
        return LogisticModel.from_dict(json.loads(path.read_text("utf-8")))
    except FileNotFoundError:
        return None
