# NL2SHACL English/Korean diagnostic
User authorizes original benchmark reproduction and Korean paired requirements; paid calls allowed;8h continuation requested10min cadence. New campaign120calls/$5 ceiling, initially24calls only. Daily allstudy<=500 includes expanded-study,ontology-tools-study,yago-tools ledgers (all zero today). No gold repair or retries. Scheduler73143f1b active, must skip running/unansweredhuman.
Read-only evidence allowed for this review (do not read other reviewer outputs, .env, gold shapes or historical QA):
- research/operations/designs/nl2shacl-ko-diagnostic.json
- scripts/nl2shacl_pair_study.py
- tests/test_nl2shacl_pair_study.py
- _workspace/nl2shacl-ko/prepare.py
- _workspace/nl2shacl-ko/pairs.json
- _workspace/nl2shacl-ko/inputs.json
- _workspace/nl2shacl-ko/config.json
- _workspace/nl2shacl-ko/reference-preflight.json if exists (coordinator observations only)
- _workspace/nl2shacl-ko/framework/NL2SHACL-Translator/generate_prompts.py
- _workspace/nl2shacl-ko/framework/NL2SHACL-Translator/run_openrouter.py
- _workspace/nl2shacl-ko/framework/Shapes-Evaluation/evaluators.py
Scope: review runner before first paid24calls and paired requirement translations. Methods independently check all12 EN/KO pairs for quantifiers/negation/cardinality/type/target drift; no gold access. Ready only for bounded diagnostic, no representative benchmark claims. Implementation checks paid limits/reservations/restart/outputs and exact one-variable prompt construction. Native builder11mockedtests passed; main will run registered fullunit-tests after review. Source selection first2records/subset, example exclusion via description text check by coordinator. ModelQwen3.5 same as one paper model; temp0, reasoning disabled,4096output cap explicit deviations. Current API prices0.5/3.6 perM, configured provider ceilings0.6/4.0.8h stops newrequests, pendingrequest may extendtimeout.
Evaluation initially raw parse+original structural metrics; upstream module dependency missing pkg_resources fixed by uv --with setuptools<81 (originalfiles unchanged). No semantic correctness fromparse/structure. OriginalSERsamplegraph needs self/negativecontrols; LERnotimplemented. Pair sample12 too small to establish language disadvantage. Englishprompt andontology labels retained intentionally, translation-onlycondition. Subsequentexpansion requires review and successful evaluator/translationaudit. Reviewers write only assigned result and mark unverified outside evidence. No paid calls in review.

Revision2: require config inputs_sha256 frozen ordered24rows, reject edited/appended/reordered/removedinputs beforetransport; no silent expansion. Firstreview implementation blocker preserved in oldjob; inspect finalsource afresh. Translation pairs unchanged. New coordinator-observed evaluator control: upstreamSER reports equivalent for original bookexactly1author vs weaker0..2authors on generated30triples10nodes; explicitzeroauthorbook originalFalse weakerTrue. This is a sample-test blind spot, not dataset/model error or failure of theoreticalequivalence. No upstream semanticcorrectness claim. Furtherexpansion requires newreview and sessionaggregate budget mechanism.
