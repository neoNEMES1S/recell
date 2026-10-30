# Related work and the registered research question

Reviewed on 27 October 2026; no experiment settings or fitted results changed.

The published [Prior-Informed Hierarchical Fusion Network study](https://www.mdpi.com/2227-9717/14/5/768)
combines first-life summary metrics with current EIS and DCIR measurements to
estimate second-life SOH. Its Stanford case uses cell-wise cross-validation and
normalizes SOH by nominal capacity. This establishes relevant prior work; the
general idea that first-life history can help second-life assessment is not a
novelty claim for ReCell. This paper does not establish a repair for our failed
cycling-time/exposure records in the material reviewed.

ReCell's [sealed v2 protocol](../configs/transfer_protocol_v2.yaml) instead tests
encoder pretraining for future-checkpoint forecasting at limited retained history.
It uses past SOH, stage age and causal stage-relative Ah, resets the prediction
head, and excludes every test battery's first-life data from source fitting,
validation and scaling. Stages normalize to their first accepted capacities.

These are different prediction tasks, inputs, normalization conventions and split
designs. Published error numbers cannot be treated as directly comparable benchmark
results. No inference about the other study's leakage or scientific validity is
made from those differences. Its use of historical summaries also does not fill
our missing interval measurements.

The [2025 PHM degradation-model paper](https://www.papers.phmsociety.org/index.php/phmconf/article/download/4373/phmc_25_4373)
also uses the Stanford first-life release, fitting W9 and evaluating W10. The
reviewed paper does not provide a public corrected-file link or a clock-recovery
procedure for the specific failures found here. That bounded search result is not
proof that no correction exists elsewhere or in the authors' archives.

The primary R2-minus-R1 endpoint, six physical folds, seeds and context fractions
remain fixed. Research fitting still requires the original complete causal-feature
gate. Changes to source inputs or recovery rules require documented evidence and,
where they change the scientific contract, a versioned amendment before fitting.
