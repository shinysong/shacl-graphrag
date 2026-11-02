# Offline relation interface diagnostic

Version 1, fixed 2026-11-01 before implementation. This is a software diagnostic
of relation expansion and an evidence-only checker. It is NOT an A–E retrieval
or generation experiment. No embedding model, reranker, LLM or SHACL engine is
invoked. It does not establish runtime isolation for a future full pipeline.

## Traversal and packing

Use the existing source-corpus-v1.json without mutation. Two implementations
read exactly its declared edges: adjacency-list traversal and SQLite queries.
This is an implementation parity check, not an RDF/OWL or database performance
comparison. Supplied seeds are chunk IDs, not outputs of an executed B retriever.
Unknown seeds are errors. Duplicate seeds are removed preserving first order.

Node seeds start at that node. Edge seeds retain the edge chunk and start at
both endpoints. Expand OUTGOING edges only. For each breadth-first depth, sort
frontier node IDs; for each subject sort edge IDs; add each edge chunk then target
node chunk. Keep first occurrence of each chunk; visit each node once. Do not
infer inverse edges, label matches, missing links or source facts.

The diagnostic uses max_depth=1, max_candidates=32, max_evidence_bytes=64000.
It checks all 243 annotation nodes as individual supplied seeds, once each.
Additional adversarial fixtures are separate software tests, not extra source
cases. For generalized calls, depth is limited to 0..3 and candidates to 1..128.
Reject over-cap candidate lists explicitly rather than silently returning a
prefix. Byte budget is exact UTF-8 length of canonical JSON selected chunks.
Overflow returns budget_error with no selected evidence, preserving candidates.
These bounds do not replace the yet-unselected tokenizer and token budgets for
the later RAG experiment. Record evidence_tokens=null and budget_unit=utf8_bytes.

Envelope carries schema_version, backend, seed_chunk_ids, candidate_chunk_ids,
selected_chunk_ids, selected_chunks, evidence_sha256, evidence_bytes,
evidence_tokens, budget_unit, configuration, status, error and trace.
Hash exact ordered selected chunk objects in canonical JSON. Never repair outputs
using questions or reference answers. Preserve failing envelopes and count them
alongside successful pairs. Parity requires identical ordered selected chunks
and hash, not only values or IDs. Backend labels and backend trace may differ.

## Equivalent evidence and checker boundary

Freeze the support policy now: annotation node + matching dictionary node + the
annotation's explicit dictionary_refs is enough to express their link. An
explicit edge chunk is not additionally required. A selected explicit edge is
an alternative link statement only when both endpoint nodes are present and
workbook namespace, file hash, code and reference binding agree. Duplicate link
representations never add independent support. Apply this policy to all arms.
The later offline scorer may use a reference to select the needed question scope;
the checker cannot. The runtime checker reports generic selected-record checks,
not question relevance or externally scored answer correctness.

The checker accepts only one saved envelope. Its module has no filesystem or
network reader, full-corpus parameter, question contract or scorer parameter.
Validate hash, duplicate IDs and chunk-text structure. Non-ok retrieval envelopes
produce checker error, not pass. For each selected annotation and each declared
reference, report pass if the target is selected with matching namespace/hash/code;
unknown if the target or required metadata is absent; violation if present values
conflict. Record invalid selected edge bindings separately. A different workbook's
same-valued target does not satisfy the missing expected target.

For every selected annotation, report process_review_version=unknown when the
selected record has no such field. Do not read attribution release version as a
process review version. Unsupported nonmissing version claims remain unknown:
this diagnostic has no version-applicability rule. No annotation yields a named
no_selected_annotation unknown result, never a vacuous success.

Report input evidence hash, rule version, results (check_id/status/evidence IDs/
reason), execution status, complete and truncated=false. This is a deterministic
Python reference checker, not SHACL conformance. No global pass, automatic veto,
filter, repair, evidence addition or source completeness claim. Same envelope
before and after checking must be byte-identical. Caller enforces a 32000-byte
report cap; overflow is an error with no successful report.

## Verification boundaries

Tests must exercise independently implemented traversal, missing target,
wrong-namespace same-valued target, code conflict, hash tampering, empty evidence,
malformed/duplicate chunks, explicit-edge conflicts, candidate/byte overflow,
input nonmutation and absence of file/network reads during checker invocation.
The last check is a software guard, not an OS sandbox or a guarantee about all
future runtime code. Freeze source/code/config hashes in saved diagnostic results.
The full attempted source grid is 243 parity pairs. Do not report pair count as
independent evidence of retrieval effectiveness. Preserve old24questions unchanged.
