# 2026-11-06 — Backend and checker boundaries

## Context

A bounded Neo4j+n10s / Neptune RDF study reused frozen development source records,
then checked saved outputs with Python and SHACL advisory metadata policies.

## Incident

- A combined Cypher MATCH excluded reusing the same relationship across patterns.
  Separate MATCH clauses restored the declared basic-graph-pattern contract.
- n10s 5.26.0 KEEP export changed URN predicates, although triple counts matched.
  SHORTEN preserved the selected full 3,999-triple projection in a separate followup.
- A trailing LF after a 64-character hash passed the original SHACL pattern but
  failed Python fullmatch. Non-string inputs caused four Python checker failures.
  These original outcomes were retained; a separate v2 contract added a shared
  string-or-null input gate and exact SHACL length/datatype constraints.
- Root-owned files left by an earlier container build prevented regenerating the
  ignored Chirpy source and output. The first failed build logs were retained.

## Lesson

Check identities and typed values, not only counts or successful API status.
Separate input rejection, checker exceptions, conformance and factual correctness.
A new contract version must not replace earlier failed or discrepant outcomes.

Run container documentation builds with the host UID/GID. Correct ownership only
on known generated directories; do not rewrite tracked website sources to bypass
an ownership error.

## Follow-up

- [x] Preserve original runs and independent review blockers.
- [x] Record versioned boundary replay with separate rejection denominators.
- [x] Correct ownership of generated `_workspace/chirpy-source` and `site`.
- [ ] Measure new final-answer effects only under a separately frozen paid scope.
