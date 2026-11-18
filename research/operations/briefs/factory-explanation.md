# Engine explanation demo review

Goal: make actual SHACL constraints/reports and OWL-RL derived facts inspectable in public Factory Lab. No efficacy claim, paid call, cloud or publication. Frozen review.py and historical studies unchanged.

Read only apps/factory_lab/{explanation,diagnostics,public_runtime,public_server,review}.py, public_static/*, tests/test_factory_explanation.py,test_factory_public.py and operations check registration. Do not read secrets/private results or other reviewers. Write only own result.

New explanation adapter returns original selected RDF/shapes/raw pySHACL report, candidate/shape checks, native path/value nullable. No targets means not assessed. Same-policy Python preserved. Live explanation excluded from LLM input (original small report retained), no draft comparison falsely claimed. Three authored diagnostics execute actual fixed RDF queries and local engines via CSRF-protected POST; manually select one returned candidate and optionally omit qual query, selection recorded. No LLM/generated answers in diagnostic. OWL-RL closure uses authored CAP-CUT classification overlay; direct asserted-type/subclass supports reconstructed, not internal proof. No OWL output fed into qualification evidence. UI displays bounded result, actual engine vs historical replay vs live labels; graph still collapsed.

Review method/implementation correctness and required gaps against user aim. Full integration, docs, diagnostics rationale and browser checks are still in progress; this is a source gate for offline checks, not completion. In particular distinguish pass/no-effect-on-answer (not measured), missing source/retrieval and unsupported truth. No source lookup in trace.


## Integration revision
Added exact historical actual model cases01/07/10 from llm-001 as allowlisted bundle with SHA256 integrity check; original strings, reports, evidence, hashes and exact curated quotes preserved. New trace is explicitly current posthoc engine on saved evidence, not original model input. Text diff is not semantic score. Same-policy Python/self selectable; uncorrected unsupported certainty case07 retained. Added altered selected qualification valid_until diagnostic contradicting source but conforming; intervention metadata excluded from checker. UI uses projected validation RDF wording. Endpoint locks same single-user execution lock with finally release. Tests cover HTTP/CSRF/lock/error, original archive bytes/quotes/reports and no fulltrace in final modelmessages.

Read also examples/factory_lab/explanations/*, historical public research/factory-complexity-1/llm-001/case-{01,07,10}.json only for provenance, and docs/setup/factory-lab-explanation.md. Do not inspect other reviewer output/privategold/secrets. Prior registered tests passed before this revision. Review this revision before rerun.


## Opt-in end-to-end revision
Previous revision all three checks and seven-case desktop/mobile browser passed; full archive evidence/report equality receipt retained. Added optional boolean owl in public live start, defaultfalse. Actual selected_owl requires retrieved CAP-CUT required_capability, computes authored classification closure, persists full trace but sends only assessment/evidenceIDs/provenance/scope/witnesses to finalmodel. No extra calls or qual-evidence changes; no-target not-assessed. UI checkbox and JSON download; SHACL unselected distinct not_executed. Scripted regression captures final modelcontext; actualprovider remains prohibited. This completes prospective answer-input connection, not observed answer effect.


## Export provenance correction
V3 methods blocker preserved: downloaded trace omitted modified-data provenance. All live/history/diagnostic renderers now pass complete displayed response to download, retaining intervention/mode/projection/source hashes and historical original reports outside checkerinput. Browser regression will compare exported JSON to exact HTTP response for all7cases. Detailed constraint cards collapsed with counts and readable labels; OWL no-target status explicit. No runtime engine delta from v3.

## Frozen source hashes
- apps/factory_lab/explanation.py: e5833854059a7c2069e637d0af168136c0318d48903729ff30fc11917f915caf
- apps/factory_lab/diagnostics.py: f0c79046995cf7f52fb05f6b004c62025256e72bffa9daf3eeba3d71836f7f6e
- apps/factory_lab/public_runtime.py: f27d04d4bb8f173f5e5dea6c9db6aad60473c4adc4c697e1907715e3e3205f91
- apps/factory_lab/public_server.py: 8f7b67cb4d1081fea1b8cfb790a9fef1be4d11b4cfbc3ae579569044022f4395
- apps/factory_lab/public_static/app.js: cf72c35611abf42f86c5be81d289597d6e3f39cdae11c13f2641fa4c7d4d18dc
- apps/factory_lab/public_static/index.html: 4b8a8875d9870006dc9476fcd1a9c04aea3e6863107b606b59ba5157c4b94c7f
- tests/test_factory_explanation.py: 32325f202ae4c3199208324ce8ecf29814ca913d57d7533334b01a168e7b61dd
- tests/test_factory_public.py: cd63bb0f75c494fd6d18dc9ac39c812f49a5b8651b341693920e090cd0077fa4
