# Evidence acquisition development interface

Version 0.1, 2026-11-01. Proposed runtime contract; no A–E retrieval or generation
campaign has executed. This document freezes the interface for the next offline
implementation, not model choices, token limits, or a new evaluation cohort.

## Source and development boundaries

The source is the existing PENELOPE workbook extraction. Its 243 annotation rows
are consumed development data. Five workbooks each contain a defect dictionary
and a nominal welding-setting dictionary. Dictionary content repeats across
workbooks; same-valued answers can cite the wrong scope. Score source binding
separately from answer value. Nominal settings are not measured process values.

The source-only builder reads no question, reference answer or expected evidence.
It emits annotation/dictionary nodes, source-bound edges and one textual chunk
per node/edge. A/B index those same relation facts that C/E traverse. A relation
is a researcher-defined same-workbook code lookup with recorded cells, not an
independently supplied universal identifier or automatically discovered relation.

No design-PDF edges enter this corpus. Existing manual design correspondence,
the incomplete PP4 PDF acquisition, raw HDF5 alignment, approval/version/change
history and physical defect identity are outside this bounded corpus.

## Runtime and scorer separation

| File or object | Consumer | Content |
|---|---|---|
| `source-corpus-v1.json` | all retrieval arms | source-only nodes, edges, text chunks, provenance and source hash |
| `development-questions.json` | runtime | opaque question ID and natural-language question only |
| `development-references.json` | offline scorer only | target row, task, answerability, values and admissible supporting nodes |
| query configuration | runtime | pinned model/index versions and shared budgets; not yet selected |
| retrieval envelope | generator and checker | selected chunks and their content hash, statuses and costs |
| answer envelope | scorer | answer disposition, claims and citations; no reference answer |

Scorer-only content is an access boundary enforced in implementation and review,
not an OS isolation claim. No expected evidence, task label or required-node list
may guide retrieval, reranking, expansion, checker selection or answer repair.
Dataset construction can use the source to author references before generation.
The 24 authored questions are six selected consumed rows × four tasks, not
independent trials or a fresh held-out cohort. Three tasks permit source-bound
answers; one asks for a process-review version absent from this bundle. Absence
here does not establish that the information does not exist in the full archive
or in the factory. Questions explicitly restrict their scope to supplied material.

## Retrieval envelope and equality controls

Every attempt must record `run_id`, `question_id`, `arm`, `attempt_id`,
`source_sha256`, `configuration_sha256`, `status`, `seed_chunk_ids`,
`candidate_chunk_ids`, `selected_chunk_ids`, `selected_chunks`, `evidence_sha256`,
`evidence_tokens`, `trace`, `costs` and `error`. Preserve failed envelopes.
Hash selected chunks in their serialized order, including their provenance.

Status is one of `ok`, `unavailable`, `retrieval_error`, `budget_error` or
`parity_error`. An unmeasured vector retriever is `unavailable`; lexical TF-IDF
does not substitute for a dense embedding baseline. A is embedding similarity;
B adds keyword search and reranking; C expands B's saved seeds; E uses the same
seeds, edge direction, depth, visit/deduplication policy and truncation in
SQL/Python. Freeze those choices before executing the retrieval comparison.

Node and edge chunks are distinct. Expansion records traversed edge IDs and
retrieved target nodes, not just a target label. A source-bound lookup requires
matching workbook namespace and code, not label similarity. The runtime must
retain the proof of a chosen link as accessible edge evidence, within the same
token budget. Freeze whether and how relation chunks count toward selection
before the first comparison; never make graph evidence free of cost.

C/E parity is exact ordered selected-chunk content, not only final answer value.
When parity fails, preserve both outputs and the mismatch; mark the paired
implementation contrast invalid. Other valid comparisons for that question may
remain reportable but failures stay in the full attempted denominator. Do not
use reference answers to repair either result.

## D checker input boundary

D reuses C's exact saved selected chunks and `evidence_sha256`. It may read only
that envelope and shared static schema/check definitions. It cannot fetch the
full source corpus, a hidden case-metadata table, a reference answer or another
retrieval result. Source-specific values required by a check must already occur
in the selected evidence. No filtering, replacement, additional retrieval or
automatic veto occurs in D0. D0 denotes the initial D implementation here, not
an extra arm. The LLM receives a report and decides using the common prompt.

Each result has `check_id`, `status` (`pass`, `violation`, `unknown`, `error`),
`evidence_chunk_ids` and `reason`. Missing version, missing endpoint or missing
required metadata means `unknown`, not pass or a claim of global source absence.
An explicitly present inconsistent value can yield a violation. SHACL results
are recorded separately from this three-valued applicability wrapper; SHACL
conformance alone does not establish complete evidence, external truth or correct
question interpretation. No rule or inferred metadata is inserted into evidence.

The report carries input evidence hash, rule version, completeness/truncation
flag and execution status. Reserve identical report-slot capacity across arms;
non-D arms receive a not-executed marker and cannot spend that capacity on more
evidence. Preflight both common evidence and report budgets. Overflow is a
`budget_error`, not silently truncated validation success. A checker error leaves
D a recorded failure, without a silent no-check retry.

## Answer envelope and denominator

An answer envelope records `run_id`, `question_id`, `arm`, `attempt_id`,
`status`, `disposition`, `claims`, `citations`, `missing_evidence`, `usage` and
`error`. On a valid response, disposition is `answer`, `partial` or `abstain`;
each claim identifies its value/unit and supporting chunk IDs. The initial
schema validator only checks structure. A well-formed wrong answer or invalid
source attribution remains a measured outcome rather than being repaired.

Runtime status distinguishes generation failure, invalid response schema and
successful generation. Unavailable model, failed retrieval, parity failure,
overflow and malformed response all remain in the attempted-question table.
There are no automatic retries. An explicitly inspected retry is a new attempt
linked to the original; it never replaces the original failure or refunds cost.

Report the complete attempted grid and status counts first. Then report evidence
coverage and supported-answer performance on their declared eligible subsets,
with every numerator/denominator visible. On answerable questions report wrong
answers, partial answers and unnecessary abstentions together. On bundle-absent
questions report unsupported specificity and appropriate uncertainty separately.
Partial answers do not count as complete answers. Valid alternate evidence sets
are allowed only if their source binding supports the same question scope.

The primary evidence criterion is a complete admissible source-bound support
set. Node IDs in the reference describe the facts needed; a path is accepted
only when every required link is present in selected relation evidence (or an
equivalent explicit source statement), not reconstructed from hidden scorer
knowledge. Repeated/identical text does not justify crossing namespaces.

## Remaining launch gates

Freeze tokenizer, embedding/reranker/generator IDs and licenses, index parameters,
seed/depth/candidate limits, deterministic tie-break, traversal and chunk packing,
token budgets, report schema, software hashes, scorer and failed-pair handling
before an empirical comparison. Independently verify runtime/scorer separation
and offline C/E parity on development fixtures. A CPU feasibility probe may
precede a campaign; no GPU serving or paid model calls are authorized here.

This cycle creates source and question artifacts only. No result demonstrates
GraphRAG efficacy, ontology superiority, external truth, or maintenance savings.
