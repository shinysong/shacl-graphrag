# Selected-evidence relation packing

This exploratory development policy is fixed after observing A/B support scores,
not a prospective held-out comparison. It does not use references at runtime.
It adapts the existing one-hop interface diagnostic to actual selected B evidence.
This cycle implements and tests the interface only; actual C/E execution follows
under a separately reviewed hash-bound runner.

```text
Identical selected B chunks (source-exact, IDs/hash/bytes checked)
 -> existing outgoing one-hop adjacency or SQLite expansion
 -> reject >32 candidates or >64000 intermediate bytes
 -> first8 candidates in existing traversal insertion order
 -> whole-chunk packing, skip oversized and continue within first8
 -> <=4096 pinned E5 accounting tokens and64000 UTF8 bytes
```

The original expansion policy is unchanged. Iterate B seeds in selected order.
A node seed adds that node; an edge seed adds that edge then its subject and target
nodes. Remove duplicates on first occurrence. After processing seeds, follow
outgoing edges from sorted endpoint/node starts, sorted by edge ID; add edge then
target node. No inverse, inferred or question-specific edges. Depth1, candidates32,
intermediate bytes64000 retain the earlier diagnostic limits and explicit failure.

Final first8 eligibility matches the A/B maximum number of parent candidates but
uses traversal order rather than relevance scores. This is a policy difference,
not identical ranking. Endpoint insertion can displace later B seeds; C evidence
is therefore not guaranteed to contain all B evidence or improve support. No
refill beyond the first8 after budget skips. Report displacement, dropped eligible
chunks and intermediate errors rather than concealing them. Final bytes use
canonical ordered JSON; count with the original pinned E5 tokenizer, no truncation.
Generator evidence_tokens remains null. Resource cost is not equalized by caps.

C and E use identical seeds, ordering, caps and packing; only adjacency versus
SQLite traversal differs. The existing implementation has independent traversal
logic but shared indexing and final packing. Agreement checks implementation
parity, not independent business truth or graph superiority. C minus B jointly
changes expansion and candidate ordering; it cannot isolate relational reasoning
from selection policy. No RDF, OWL or SHACL engine executes here.

The pure wrapper accepts source, a B envelope, tokenizer-count callable and backend.
It accepts no questions, scorer, reference targets, file paths or model clients.
Require successful nonempty B evidence, <=8 selected chunks, exact selected/seed
ID order, canonical hash/bytes, source-exact payloads and original final caps.
Failures return empty selected evidence with status and reason. Inputs are not
mutated. Caller must bind tokenizer/version/source/code/B hashes and count every
planned question, including failures. D later receives exact C evidence and a
separate checker report; it may not fetch missing records.

Tests use only synthetic software fixtures for parity, source-exact binding,
nonmutation, first8/no-refill, skip-and-continue and invalid token counts. Existing
expansion tests cover outgoing-only behavior, cycles and intermediate overflow.
Tests are not retrieval efficacy results. No actual C/E support score is reported
by this interface stage.
