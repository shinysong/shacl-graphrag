# Actual-source annotation validation contract v1

## Frozen scope

Declared before bridge execution on 2026-10-29. This is a software demonstration
on already inspected, consumed PENELOPE PP3–PP7 annotations. The known PP5 descending
interval is not a blinded discovery or an estimated error rate. Preserve all source
and earlier synthetic runs. Input: source/workbook-extraction-v1.json, SHA-256
`d4a68588bd5841c46d3503f23454956c090626c8216d0b955bec21df67276740`.

## Interpretation and obligations

Retain raw XLSX and extracted JSON. Export a small RDF projection with stable
annotation and codebook URIs scoped by coupon and sheet. Retain source file hash,
archive member, sheet, row and field-cell provenance. Preserve formula/cache data
in the JSON source; RDF need not duplicate every spreadsheet cell. No inference,
OWL, SHACL Rules or design-PDF mapping in this step. It is SHACL Core validation.

Each annotation must have exactly one defect reference and setting reference to
an existing node of the declared corresponding class. Each reference must point
to the codebook node indicated by the extracted code in the same coupon; the
source-to-RDF adapter binds this interpretation, not the SHACL class check alone.
Bead number must be an integer. Start/end millimetres and start/end sample positions
must be numeric and recorded. Sample coordinates are integers, millimetres may be
integer or decimal. Null values are omitted from RDF and are reported as missing,
not zero. No interval ordering decision is supported when either endpoint is missing.

For two present, correctly typed endpoints, require start <= end independently
for millimetres and samples. Equal endpoints are permitted. This researcher-declared
ascending-interval contract is not a published weld acceptance or repair policy.
No cross-unit conversion, sample alignment or physical defect identity is tested.
No conformance claim for nominal electrical values, which are retained as source
context rather than tested as measured settings.

## Matched comparison and requests

Implement Python checks independently against the extracted JSON and SHACL Core
checks against the RDF projection. Normalize violations to annotation ID, field
and constraint kind (required/type/reference/order); compare sets and per-record
status. Extra SHACL rows caused by constraint implementation must not silently count
as independent cases. Save complete raw RDF report and readable report in addition
to normalized results. Both checks operate on the same supplied record projection;
parity is not proof that mapping or source facts are true.

A failed present-value order condition yields request_source_confirmation, with
original values and exact cell references. Missing required evidence yields
request_evidence. No automatic replacement, swapping, physical action or release
approval. A conforming record has no detected violation under this contract; it is
not certified physically correct. Requests are researcher-authored workflow output,
not source-issued official instructions. No new efficacy cohort or gold repair.

## Verification

Meaningful copy-only controls cover equal endpoints, one missing endpoint, wrong
numeric type, unknown dictionary reference and namespace/type mismatch. Controls
are unit tests, not additional source observations or research trials. Preserve
failed attempts. Report software checks and actual saved results separately.
