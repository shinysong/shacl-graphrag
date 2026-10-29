# Introductory semantics seminar expansion

User requested an accessible Korean seminar explaining RDF/RDFS/OWL, reasoning, SHACL, Shape authoring and pySHACL, with actual code/data/calls/input/output, business scenarios and research design. Expand previous20 slides to42 to include requested foundations and proposed research hypotheses. White Pretendard, editable animated SVG, standalone offline HTML and PDF. Uploaded reference is layout/tone inspiration, not evidence; video was summarized by user, not watched or timestamp verified.

Read only your own request and these authorized source files; write only own result. Do not read other reviews, secrets, held-out gold or raw historical QA answers.

- docs/experiments/seminar/slides.md, theme.css, app.js, diagrams/*.svg
- scripts/build_seminar.py, scripts/seminar_examples.py, scripts/seminar_semantics_examples.py
- docs/experiments/seminar/semantics/* (tiny actual executed sensor/closure/validation teaching examples; no LLM or benchmark)
- docs/experiments/seminar/examples/* (unchanged saved prior project examples)
- docs/experiments/seminar/index.html (parse without dumping embeddedfont), docs/experiments/seminar-guide.md
- docs/experiments/records/20261022-unified-rule-lifecycle.md
- docs/experiments/records/20261013-hybrid-comparison.md
- docs/experiments/records/20261013-ontology-reasoning.md
- docs/journal/2026-10-20-retail-comparison-closeout.md
- scripts/unified_rule_lifecycle.py
- scripts/prepare_chirpy.py, mkdocs.yml
- https://www.w3.org/TR/rdf11-primer/
- https://www.w3.org/TR/rdf-schema/
- https://www.w3.org/TR/owl2-primer/
- https://www.w3.org/TR/shacl/
- https://github.com/RDFLib/pySHACL
- https://owl-rl.readthedocs.io/en/latest/owlrl.html

Methods: check inference vs graph validation vs externaltruth. RDFS domain/range infer types, not reject input. OWA; universal restriction doesn't imply existence; distinctIRIs not necessarily distinctentities. Ontologyloading not automaticreasoning; engine support matters. SimpleASK false means no match in chosen graph. DatalogstylePython computes reachablepairs, not allpaths. Rawvsclosure SHACL example uses hasValueDevice because sh:class supports subclassmembership. UnverifiedIRI passes shape but no actualtruth established. Originalretail/lifecycle not OWLbenchmark; historical boundedOWL did exist (504/640 asserted,640/640 bothPythonandOWL), no RDF superiority. New certification-chain/fourhypotheses/sixevidencestates are proposeddesign, not freshmeasurements or finalizedprotocol. Subclassing alone doesn't inherit arbitrary regulation properties. FairPythonSQLsharedJSON alternatives and explicitpolicysemantics. Sourceabsence/retrievalomission/internalfalsefact separated. No maintenance labor benefit established.

Implementation: placeholderresolution and dynamic42navigation/print; savedresults vs liveexecution; code/sourcehash correspondence; semantic caseoutputs; offlinefont/assets; guide static tables and SVG; desktop/mobile layout. Newexample contains assertions and was executed. Slides show actual saved values through JS selectors. Browser does not execute Python. PDF/staticguide must show comparisontables independent of selected demo. Originalexampledata unchanged. Manual browser/PDF/build checks handled by main, not researchoutcomes.

Registered checks none (existing registry unrelated). Main manually checks browser controls/layout at1280x720,1440x900,390x844, PDF42pages, strictMkDocs and Chirpy builds. No paidcalls, sourceexperimentreruns, cloudactions, push or deployment. No reviewer sourceedits. Flag concrete defects, not experiments outside user scope.
