# Historical reply-targeting research preview

Live location: Metrics → Reply attack research preview.

Source: Manita Pote, [Coordinated Reply Attacks](https://zenodo.org/records/13896309), DOI 10.5281/zenodo.13896309, CC BY 4.0. The authors' [replication repository](https://github.com/osome-iu/io-coordinated-replies) and datasheet define the task.

- Input: `RQ2_tweet_classifier_features.csv`; SHA-256 `038783083dfad6f8b80949a352044b9eacb65ad1e1cdbbfaebb20e9fd501533f`.
- 7,816 rows; first-row deduplication leaves 7,732 posts: 3,866 targeted and 3,866 selected controls. Raw IDs and source rows are not published here.
- Labels describe historical targeted tweets versus selected controls. Both groups were selected for replies; these are not ordinary-post, bot, maliciousness or operator-identity labels.
- Fixed hash split before fitting: train 5,378, validation 1,139, test 1,215. All versions of a post stay together.
- One predeclared feature, `mean_cosine`; threshold/direction selected only on training balanced accuracy. This is a naive decision stump with no calibrated confidence or abstention.
- Test: TP 373, FP 264, TN 334, FN 244; precision 58.56%, recall 60.45%, selected-control FPR 44.15%, F1 59.49%. The UI includes counts and Wilson intervals.
- Actor/campaign grouping is unavailable, so related posts can cross partitions. This is exploratory post-level validation, not campaign-independent swarm validation.

Only the small derived aggregate report is committed. The source CSV stays outside Git; no pickle, raw text, account data or live social feed is executed or displayed. Underlying platform terms still apply. The full Spot the Swarm capability remains unavailable. Native production metrics remain unchanged.

Reproduce from a permitted local copy:

```text
uv run --no-sync python -m tools.datasets.reply_attacks SOURCE.csv --output models/evaluation.social_replies.json
```
