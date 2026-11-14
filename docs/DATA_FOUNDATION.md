# Dataset foundation

This is an offline provenance and reproducibility layer for the **current repository**, not a trained replacement detector. It makes zero network or model calls. It does not overwrite `models/metrics.json`, load candidate weights, train on detector predictions, or automatically promote a model.

## Native synthetic fixtures

Choose a new output directory outside this Git checkout:

```powershell
uv run python -m tools.datasets generate --output C:/data/bounceri-native-v1 --seed 7 --runs-per-partition 2
uv run python -m tools.datasets verify --manifest C:/data/bounceri-native-v1/manifest.json
uv run python -m tools.datasets evaluate --manifest C:/data/bounceri-native-v1/manifest.json --output C:/data/bounceri-native-v1/baseline-candidate-validation.json
```

`generate` refuses to overwrite an existing nonempty directory. It produces:

- `access.jsonl`: native numeric-timestamp Caddy records, signed with the current `bouncer.ingest.simrun` implementation. Documentation IPv6 addresses and fake account names represent all actors; no HTTP requests are made.
- `truth.jsonl`: separate scenario reference intent, source identity, actor/run/campaign groups, origin and partition. These are generated labels, not verified real humans or inferred identities.
- `features.jsonl`: feature values computed by the imported current `bouncer.session.features.compute_features`. Truth, profile, run, IP and account fields are not predictor columns. Session references are metadata, outside the feature object.
- `manifest.json`: generator version/seed, source URL, MIT use/redistribution terms, label source, source unit, file SHA-256/byte counts, relevant current-code checksums and split memberships.

The reproducible signing key is a **public fixture key**, derived from the seed. It checks compatibility with the current HMAC/parser contract, not production authenticity. Never use it for hosted traffic or as `SIM_RUN_SECRET`. The current parser strips both simulator headers before native feature extraction. This adapter replaces the earlier packs' stale assumptions about numeric timestamps and username parsing; it imports current code rather than copying their vendored backend.

## Partition and leakage rules

The four partitions are `fit`, `calibration`, `candidate_validation` and `reserved`. Each contains separately generated whole runs with distinct actor/source identities. Every authentication campaign stays within its run. Shared-NAT actors share an IP only within one partition. Checks reject any run, campaign, actor, source-identity or client-group crossing partitions, missing reference truth, checksum modification and feature-contract drift.

The reserved partition contains **known public generator templates** with separate identities/random draws. It is **not a genuinely hidden attack** and must never be advertised as independently authored or withheld from the detector's authors. Evaluation defaults to `candidate_validation`. Reading reserved results requires explicit `--partition reserved --allow-reserved`; doing so consumes that local holdout for the chosen configuration. No partition is used to fit or calibrate anything by these commands.

This native seed is reproducible. Changing seed creates another synthetic scenario pack, not a new independent human dataset. Repeating the same templates does not establish generalization.

## Profiles and reference truth

| Profile | Reference traffic class | Interpretation |
|---|---|---|
| Cached rapid browser / assetless rapid browser | Synthetic `human` | Deliberate hard negatives: rapid, cached browsing can overlap scraping observations. |
| Privacy headers missing | Synthetic `human` | Missing browser headers alone do not establish maliciousness. |
| Ordinary login retries | Synthetic `human` | Two failed attempts followed by a successful mock response; not known credential theft. |
| Shared NAT | Synthetic `human` | Separate browser clients behind one documentation IP. |
| Legitimate automation | Unknown traffic class | Known automation with benign reference intent; not a DNS-verified `good_bot`. |
| Scanner | Synthetic `bad_bot` | Familiar hostile probe fixture, not a novel attack. |
| Distributed authentication | Synthetic `bad_bot` | Generator-defined hostile attempts from several clients; observed failures do not establish credential-stuffing versus password-spraying universally. |
| Scraper with unknown authorization | Unknown traffic class | Known automation, unknown maliciousness. It must not become malicious merely to improve a score. |

No profile injects `verified_bot=True`; DNS is never queried. Production labels remain separate from these generator reference intentions. Missing external observations are not manufactured.

## Offline baseline report

The report evaluates current `score(..., model=None, traps=frozenset())` plus current pure cross-session campaign detection, scoped separately to each generated run. It does not load `models/model.json`. Scoring receives current parsed sessions, unknown IP intelligence and observed campaigns; it does not receive truth/profile labels.

It reports per-run/per-profile and overall session counts, known/unknown reference-truth denominators, bad-bot precision, human false-positive rate, uncertainty share, and two-sided 95% Wilson intervals. Precision is conditional on the known synthetic `human`/`bad_bot` subset; unknown-intent sessions are excluded from that denominator and their bad-bot flags are reported separately. Uncertainty uses all sessions. Human FPR counts a simulated human labelled either bot class. Wilson intervals are descriptive and do not correct correlations within a generated run. Zero observed errors do not demonstrate real-human FPR below 1%.

`independent_real_humans` and `genuinely_hidden_attack` remain `unavailable`. The S8 metrics stub remains unchanged. Neither local success nor synthetic precision is an externally validated product metric.

## Historical robot corpus

`tools/datasets/registry.example.json` registers the earlier local learning pack's `simple_features.csv` by its actual archived SHA-256, source DOI, version, annotation column and archived CC-BY-4.0 metadata. The source is **Web robot detection — Server logs**, Lagopoulos and Tsoumakas, DOI [10.5281/zenodo.3477932](https://doi.org/10.5281/zenodo.3477932). Upstream terms were not refreshed over the network in this CPU-only task.

The published `ROBOT` label is a historical, source-specific robot label. It is **not maliciousness**, good-bot verification or independent human identity. No corpus rows, old prepared feature mappings, vendored project code, model weights or generated corpora are committed here. Features absent from the historical corpus are not invented or filled with values claiming new native observations.

To verify an existing local copy without downloading, copying, converting or training it:

```powershell
uv run python -m tools.datasets check-source --dataset-id zenodo-3477932-simple --file C:/path/to/bouncer-learning-pack/raw/simple_features.csv
```

Redistribution requires attribution, the license and a description of changes. Review the source's current terms before publishing derivatives. The registry deliberately marks native feature mapping unavailable. Collect consented real-human cases and an independently authored genuinely withheld attack separately; no such evidence is supplied by this foundation.
