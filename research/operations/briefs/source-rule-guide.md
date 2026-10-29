# Source preparation, rule contracts, bottleneck diagnosis and graph choice
User asked to add four questions to the fresh research design: raw natural-language/table-to-relations/SHACL with preprocessing and prompt/skill guidance; implementation-specific data and I/O contracts; rule-authoring versus rule-application bottlenecks and conditional recommendations; graph advantages/disadvantages. Documentation-only addition, no paid calls or new benchmark.

Read-only authorized files:
- docs/experiments/source-to-rule-guide.md (new companion guide)
- docs/experiments/evidence-report-study.md (added companion section only)
- mkdocs.yml (added guide navigation)
- research/evidence-report-1/protocol.json
- scripts/build_evidence_report_demo.py and docs/experiments/evidence-report-demo/shapes.ttl (existing implementation, unchanged)
- docs/journal/2026-10-16-review-nl2shacl-bench.md (historical literature context only)
Reviewers read their own request and these files only, write only their designated JSON result. No other reviewer outputs, secrets, held-out gold, historical raw model answers or source edits.

Methods review: distinguish authored examples from automated extraction; facts vs normative requirements; LLM/Python/ontology are different abstraction levels so use matched processing paths; finite semantic checks not equivalence proof; development-only crossed Dhat/Rhat replacement must not become runtime gold repair. Single main A/B/C primary CminusB remains unchanged; extraction/graph maintenance claims are proposals, not new measured effects. Diagnose target coverage and source/retrieval absence carefully. Sources are official W3C/pySHACL and NL2SHACL paper plus pinned code links; no broad literature completeness claim.
Implementation review: prose vs actual demo behavior; links, code example self-containment/scope, Mermaid, navigation; all new examples clearly authored/unexecuted. Existing demo/protocol hashes preserved. No new tests needed for prose-only edits; coordinator performs strict MkDocs, Chirpy and local light/dark/mobile diagram rendering. Registered checks empty, manual checks logged separately.

Final revision: first local build/browser checks passed structurally, but visual inspection found low-contrast dark-mode edges and small mobile labels. Only the Mermaid diagram was simplified to two source branches joining a shared review/execution path, and explicit #888 edges added. Prior ready reviews are retained but superseded for current source. Review this final diagram and unchanged prose; rerun manual builds/render checks.
