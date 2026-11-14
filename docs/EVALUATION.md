# Offline synthetic evaluation

This is a measured synthetic pipeline check, not an independent real-human or genuinely hidden-attack study. Public aggregate: [evaluation.synthetic.json](../models/evaluation.synthetic.json). The production S8 metrics file remains a stub with null results; only its scorer version changed to `rules-v2`.

## What was frozen and evaluated

Dataset `native-7`, generator `native-synthetic-v1`, used whole-run fit/calibration/candidate-validation/reserved partitions with separate actors and campaign groups. The two reserved runs were evaluated once after commit `b92b333b41857695bcace285fe6ae1b9bcf95488` froze the narrow session-rule fix. Their templates were public and known to the developers. They are not an independently authored hidden attack.

The current repository rules and pure network detector ran without coefficient fitting, a loaded model file, trap labels, DNS verification or model calls. The four unknown-intent examples (legitimate automation and scraping without known authorization) were not relabelled to improve scores. Historical robot labels were not used as maliciousness labels or mapped into missing native features.

## Before, development and reserved results

The viewed candidate-validation runs became **development data** when their false positives informed the fix. Before/after development figures therefore do not measure independent generalization.

| Evaluation role | Bad-bot precision, known-reference subset | Simulated-human false positives | Uncertainty, all sessions |
|---|---|---|---|
| Before, viewed development, rules-v1 | 10/12 (83.33%) | 2/14 (14.29%) | 16/28 (57.14%) |
| After, same development, rules-v2 | 10/10 (100.00%) | 0/14 (0.00%) | 18/28 (64.29%) |
| Once-only reserved known templates, rules-v2 | 10/10 (100.00%) | 0/14 (0.00%) | 18/28 (64.29%) |

Each row covers 28 sessions from two runs: 24 known-reference cases (14 simulated human, 10 hostile-fixture sessions) and four unknown-intent cases. Precision excludes unknown intent; uncertainty includes all sessions. No unknown-intent session was flagged `bad_bot` in the reserved result.

Reserved two-sided 95% Wilson intervals:

- Bad-bot precision: 72.25–100.00%.
- Simulated-human false-positive rate: 0.00–21.53%.
- Uncertainty share: 45.83–79.29%.

The JSON preserves the exact recorded floating-point intervals. Display rounding above is for readability. These intervals are descriptive and do not correct within-run correlation. In particular, 0/14 false positives has a 95% upper bound of 21.53%; it does not demonstrate real-human FPR below 1%.

## Counterexample and rule change

In each development run, ordinary login retries (two failures followed by a successful mock response) overlapped four attack clients in a generic distributed-login-spray window. Campaign membership promoted the unrelated retry session to `bad_bot` despite no shared-target relationship.

`rules-v2` keeps generic spray visible as an advisory network finding but no longer treats membership alone as a definitive session label. The stronger same-target credential-stuffing rule and existing controlled six-client demonstration remain. The ordinary retry cases now abstain; the improvement increases uncertainty rather than establishing human identity. Neither generator nor thresholds were retuned after this inspection.

## Remaining limits

Independent consented real-human labels and a genuinely independently withheld attack remain **unavailable**. Same-target fixture success is not proof that every same-target retry in the wild is malicious. Familiar probes do not establish novel-attack recall. Repeating these templates or citing the development improvement cannot fill those evidence gaps. Dataset provenance and reproduction commands are in [DATA_FOUNDATION.md](DATA_FOUNDATION.md).
