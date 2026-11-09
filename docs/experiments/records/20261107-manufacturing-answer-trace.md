# Manufacturing evidence projection and identity review

Date: 2026-11-07. This is a bounded software/source diagnostic, not a new answer-quality benchmark.

## Inputs and execution

- Existing manufacturing source: seven nodes/four edges from the consumed development corpus, unchanged file provenance and CC BY 4.0 attribution.
- Historical replay: 36 slots; deterministic adapter emits 20 implemented-claim completions, 12 partial outputs and four unsupported outputs. Completion does not mean the entire question was answered.
- Corrected offline projection: 18 planned/emitted slots, 16 completed, two unsupported Q7.
- Corrected actual-backend run: 36 planned/emitted slots, 32 completed, four unsupported Q7. All eight supported questions have equal complete bindings across SQLite/Python, RDFLib, actual Neo4j/Cypher and actual Neptune/SPARQL.
- Posthoc source checks: 84 payload occurrences exactly match retained source objects; 28 legacy projections preserve values and cardinality. Q8 is intentionally excluded from legacy equality because its requested evidence changes.
- Both live namespaces cleaned: Neo4j remaining=0; Neptune remaining=false. Existing resources stopped, Neptune terminal state confirmed by AWS API error at 16:04:46 UTC, Neo4j stopped. The owned temporary stop timer was disabled only after this confirmation. No new AWS infrastructure.

## Artifacts

| Purpose | Repository path |
|---|---|
| Manually declared input obligations | `research/manufacturing-answer-trace-1/coverage-design-001/contracts.json` |
| Corrected runtime query contracts | `research/manufacturing-answer-trace-1/projection-v2/runtime-queries.json` |
| Offline evidence packages | `research/manufacturing-answer-trace-1/cards-001/` |
| Historical/offline input availability | `research/manufacturing-answer-trace-1/coverage-001/` |
| Actual corrected backend run and posthoc checks | `research/manufacturing-answer-trace-1/manufacturing-v2-20261107-001/` |
| Published-ticket identity diagnostic | `research/manufacturing-identity-1/run-001/` |

## Identity diagnostic

All three policies completed on the same 100 source records. Equipment-only: 20 groups, one multiple-location advisory finding. Location+Equipment: 21 groups, zero findings. Location+Equipment+Device: 32 groups, zero findings. Python/pySHACL finding tuples match in all three cases. These are not three independent datasets. The single name spans 35 records at two reported locations; physical identity and movement history remain unknown. Source inspection preceded policy construction.

## Checks and limits

Evidence-card tests: eight pass. Input-path tests: three pass. Identity prototype checks: four grouping/missing-value/duplicate-ID cases plus six acquisition/CSV failure-retention checks pass. Browser display checks cover all 36 question/backend selections and the three identity grouping controls; no script errors or horizontal overflow at 390px light and 1280px dark. These checks are software evidence only.

Independent native methods/implementation reviews are recorded in the ignored operations ledger. Earlier blocked versions remain preserved: evidence-card header/null handling, independent power-stop branches, and CSV failure retention. Review packets omitted some raw source and execution details; independent source verification is not claimed.

New paid model calls in this extension: zero. Existing paid budget and failures are preserved. No LLM accuracy, unnecessary withholding, human review-time reduction, SHACL-specific answer benefit, n10s inference performance, or backend throughput conclusion follows from these checks. Source absence and projection omission remain distinct.
