# Divergence Analysis — May 2026 eval run

## Headline finding

Composite returned 89 (recovered) on all 15 labeled days. Felt scores ranged 6–8. Pearson and Spearman are undefined because predicted variance is zero. MAE 16.3 reflects systematic over-prediction, not noise.

## Root cause

NLR×HRV scorer returned `unknown` for every labeled day. This cascades into composite using its default fallback, which lands in `recovered` when no flagship lens reports a degraded state.

The unknown-NLR×HRV cause is data-coverage, not formula:

1. The 7-day HRV baseline window had insufficient prior observations
2. The CBC panel (only one in the dataset, dated 2025-06-15) is now ~330d stale, well past the 60d staleness ceiling — scorer correctly refuses

## What this means for the model

The model isn't wrong on the labeled days. It's silent. Silence + "recovered" default = false confidence. The fix is not retuning thresholds.

## Proposed changes (justified, not retuned)

1. **Composite default state when all lenses unknown.** Currently falls to `recovered`. Should fall to `insufficient_data` with a confidence floor (e.g. 0.3) and explicit reasoning string. New state, not a reweight. This is the only spec change.

2. **Snapshot builder must surface data-coverage state.** When composite is `insufficient_data`, the headline state name and bridge subline must say so plainly. Don't show a confident 89 when the inputs aren't there. New input the snapshot builder needs from composite, not a formula change.

3. **No threshold retunes.** The divergences here are not from formula error. Tuning thresholds against n=15 felt scores while the underlying inputs are silent would overfit to bias.

## Out of scope for this analysis

- Heat acclimatization, alcohol, life-stressor inputs — these would only be justified after the data-coverage issue is fixed and a re-run shows systematic divergences with reasoning. Don't add inputs to mask data gaps.
