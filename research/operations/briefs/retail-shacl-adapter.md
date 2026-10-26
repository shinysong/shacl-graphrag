# Bounded generated-shape adapter

Review retail_shacl_worker.py and check_retail_shacl_worker.py. Worker source is
trusted coordinator code; artifact Turtle parsing, SPARQL parse and validation all
occur inside reviewed bounded container with installed deps. Host creates data
graph/normalized metadata from runtime rows only; no modelartifact parsing onhost.

Supported subset is exact predicate allowlist in worker: direct IRI property paths,
enumerated Core constraints, RDFlists, sh:sparql/sh:select with SELECT query only,
no SERVICE or FROM dataset clauses. RDFtype limited NodeShape/PropertyShape.
Three named root IRIs urn:retail:shape:customer_analysis/quantity_sign/nonnegative_price
must be NodeShape. Targets/imports/JS/extensions outside allowlist rejected, not
silently stripped. This is an experimental subset, not full SHACL conformance.
Syntax supported but wrong constraints run without reference checks/repair.
Graph clone per root adds targets only for shared eligible rows; unknown precheck
is explicitly supplied adapter policy, not learned semantics or SHACL's third state.
Raw artifact preserved by caller in future paid pipeline; this check uses fixed
authored strings. actual validation reports retained; validationfailure yields errors.

After reviews run uv offline workbench -m scripts.check_retail_shacl_worker.
Five authored checks: existing shapes, syntactically supported wrong bound,
unsupported target, invalidTurtle, SERVICEquery. Check errors/unknowns and preserve
wrong valid decision. Each in isolated container; stop if cleanup unresolved.
No generation/API/heldout/newinfra/push. Later paid launch requires frozen subset
instructions and fresh review. Static reviewers no tests/API/secrets/otherreviews
or source edits; own result only.
