# Twenty-slide seminar delivery review

User requested an approximately twenty-slide clear Korean academic/seminar presentation with white background, Pretendard, animation, basic RDF/OWL/SHACL/Shape/pySHACL explanations, actual code, generated data, calls and input/output examples. This is educational repackaging with small offline example executions, not a new study, paid campaign, manuscript submission or publication.

Read only your request and the following authorized files; write only your own result. Do not read the other review, secrets, held-out gold or raw historical QA traces. Source inputs outside this list are unverified.

Deliverable source:
- docs/experiments/seminar/slides.md (twenty sections, speaker notes; placeholders resolved by builder)
- docs/experiments/seminar/theme.css and app.js
- scripts/build_seminar.py and scripts/seminar_examples.py
- docs/experiments/seminar/index.html (generated standalone; embedded font ~1MB, use parser rather than printing font bytes)
- docs/experiments/seminar/examples/examples.json, project-input.json, project-report.json, shape.ttl, over_limit-report.ttl, missing-report.ttl, M2_shacl_report_prompt.txt
- docs/experiments/seminar-guide.md (generated static guide)
- scripts/prepare_chirpy.py and mkdocs.yml (public static artifact integration)

Evidence sources:
- docs/experiments/records/20261022-unified-rule-lifecycle.md (corrected scope; authoritative over stale MEMORY/handoff)
- docs/experiments/records/20261013-hybrid-comparison.md (separate historical completed LLM bundles)
- scripts/unified_rule_lifecycle.py (public implementation)
- https://www.w3.org/TR/rdf11-primer/
- https://www.w3.org/TR/owl2-primer/
- https://www.w3.org/TR/shacl/
- https://github.com/RDFLib/pySHACL

Methods review: factual accuracy of basic concepts, absence vs violation, report vs policy decision, synthetic/provenance labels, 0 new LLM calls, repeated cases vs independent samples, historical LLM outcomes vs offline M0-M2, no RDF superiority or measured labor claims. Flag actual unsupported claims, not missing experiments outside scope.

Implementation review: source-to-output integrity, executable code snippets, sample output correspondence, offline assets, animation/navigation/notes/print behavior, file/source links and static publication boundaries. Exact software versions recorded in examples.json. Browser rendering observed by coordinator in Chromium at 1280x720, 1440x900 and 390x844; all twenty slides no horizontal overflow and desktop no vertical overflow. Controls, embedded font, downloads and no external network calls checked. PDF produced, pending final page/text inspection. These are software checks, not research results. Independent reviewers need not rerun examples.

Registered check IDs: none (the runner's two registered checks are unrelated whole-repository tests/experiments). Manual bounded validation after review: example runner to private comparison output; deterministic report equality; browser and PDF checks; strict MkDocs source build; Chirpy site build with available Ruby 3.4 Docker image if host Ruby unavailable. Preserve failures. No secrets, paid calls, publishing, push, database or cloud work.
