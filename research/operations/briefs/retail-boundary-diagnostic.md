# Retail boundary diagnostic

Review scripts/retail_boundary_diagnostic.py and its imported local helpers.
This tick runs one offline diagnostic only, no model API calls. Current human
scope permits useful extensions after the initial48 calls; this diagnostic freezes
28 candidate paired requests but does not execute them or change any budget.

Two previously observed actual development rows (2408,4349) are selected
purposively for rare quantity-sign violations. Twelve explicitly authored probes
cover cancellation sign, zero/fraction, leading-space invoice, missing invoice,
invalid quantity, negative/zero/nonfinite price, and blank customer.
Never pool authored probes with actual-source performance, estimate prevalence,
claim heldout/general accuracy or treat policy violations as verified business errors.

Freeze cases and raw/metadata packets before scorer references. Runtime packets
contain no provenance/selection rationale or reference answers. Separate-reference
implementation is not expert gold. Execute existing authored Python and actual
row-graph SHACL, save every decision and validation trace, report split metrics.
Disagreements are results and must not be repaired to match references.
Only metadata is removed in raw condition; schema/policy remain shared.

After independent methods and implementation readiness, main manually executes
`UV_OFFLINE=true uv run --locked --group workbench python -m scripts.retail_boundary_diagnostic`.
Inspect split support, error/unknown/missing and disagreement counts; record exact
exit status. No tests/API/heldout reads by reviewers. No source edits by reviewers.
Later paid launch requires fresh runner/budget/duplicate audit review, preserving
the existing48 reservations and campaign144/$5 total ceiling. No new infrastructure.
