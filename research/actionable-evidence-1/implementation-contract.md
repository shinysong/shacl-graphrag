# Actionable evidence implementation contract 0.2

Frozen before the first runtime execution, 2026-10-29. Development only. This refines protocol0.1 and does not claim independent evaluation. No paid API, source edits or physical prescriptions.

## Runtime JSON schema and boundaries

One JSON object has `target`, `nodes`, `edges`, `dependencies`.
- target: `{id, field, unit, version, value, minimum, maximum}`; field is `setting` or `end_mm`; value is null or an integer; other numeric bounds are integers. IDs are bounded ASCII identifiers, not state labels.
- nodes: reference `{id, type:"Reference", entity, field, unit, version, value, citation}` or bridge `{id,type:"Bridge"}`. Reference value is an integer. Citation is a supplied synthetic source locator, never a scorer file. `entity` may identify another subject deliberately.
- edges: `{from,to}`; source target or bridge, destination bridge or reference. Only target→reference and target→Bridge→reference paths count. Cycles or other depths are outside the fixed grammar and rejected.
- dependencies: `{id,target,minimum,maximum}`; these are supplied bounds on the patched target, modeling an authored downstream compatibility/interval constraint. They are not learned manufacturing rules.
- At most16 nodes,24 edges,8 dependencies and four references; uniqueIDs; no unknown keys, float/bool values, dangling links or missing required fields. Reject malformed input as schema_error, never repair. Only one target; all dependencies must reference it. Bounded schema supports this diagnostic, not arbitrary RDF inputs.

## Candidate policy

An applicable reference must be reachable in the arm's path scope and match target entity, field, unit and version exactly. Reference records remain distinct even if their values coincide; policy requires exactly one applicable reference. Zero references requests evidence, more than one requests reconciliation. Never use an evaluation value to construct a candidate.

`direct_local_candidate` traverses only target→reference. `matched_Python_relation_candidate` and `SHACL_AF_relation_candidate` traverse both allowed path lengths. All other matching, uniqueness and postcheck policies are identical. This ablates traversal depth, not a competitive search system. Direct cannot see through a bridge; apparent extra withholding at depth2 is designed, not an empirical claim about SQL/Python limitations.

SHACL-AF derives target `applicableReference` triples using an actual SPARQLRule. The wrapper reads these triples, counts references and constructs the candidate. Python implements the same reachability/matching independently. No OWL closure. Both return sorted reference IDs, citation strings, and a proposed `{target,field,old,new}` patch or null. Save pre-veto candidate separately from final disposition.

## Shadow validation and final disposition

Validation always records the pre-patch asserted snapshot. For a candidate, deep-copy the original input and replace only target.value. Build a fresh RDF graph from the copy, deriving references anew when the rule arm is used; never copy prior inferred triples. Check the target integer value, required value, declared target bounds and every supplied dependency (entire bounded bundle). No unrelated dependency is silently excluded.

Both postcheck conditions compute and save the same diagnostics. `no_postcheck` final disposition is propose_patch whenever a unique candidate exists; diagnostics do not veto. `shadow_revalidation` final disposition is propose_patch only if the entire shadow bundle conforms, otherwise request_reconciliation. Thus this factor isolates enforcement, NOT validation runtime/latency. Target repair with any dependency violation is ineligible. No candidate yields request_evidence or request_reconciliation as above. Original JSON and graph remain unchanged; complete diff must contain only target.value. Real source cases do not enter this patch experiment.

## Fixture and scorer separation

32 authored cases:2roles×2path depths×8states. Runtime files use opaque IDs c000–c031 externally, not state-bearing payloads. Missing-source and omitted-projection states share byte-identical runtime payloads within each role/depth family. Only scorer metadata distinguishes hidden causes; no source fetch is implemented.

Fields: setting/code bounds1..11, ordinary reference2, false reference3; end_mm/mm bounds0..1000, ordinary reference200, false reference210. Target initially null. Dependency default accepts values; dependency-violation state adds a maximum below ordinary reference. Wrong-entity-or-field state combines entity and field mismatch (not an isolated factor). Conflict has two otherwise applicable references. Stale has v0 against targetv1. Conforming-false reference retains the ordinary external synthetic truth but supplies the alternate in-range value. All source locators and values are authored.

Scorer JSON is separate, read only AFTER all runtime outputs are persisted. Per-case labels fixed before execution:
- reference_applicable: exactly one correct-scope/current reference under full path contract (clean, conforming_false, dependency_violation).
- contract_eligible: reference_applicable and patch satisfies all declared bounds (clean and conforming_false). This label does not imply factual truth.
- correct_known_eligible: contract_eligible and supported candidate value equals external synthetic author truth (clean only).
- expected_candidate_value: reference-supplied value for applicable states; null otherwise.
- external_truth: independently recorded author expectation; never runtime input or repair fallback. Synthetic reference and truth originate from authored fixtures, not independently observed real evidence.

Report per arm counts with denominators: proposals/all32; unsupported proposals (not contract_eligible or wrong supported value)/all32 and /proposals; unnecessary withholding on correct_known_eligible /4 and /all32; externally wrong proposed values /proposals and /all32. Undefined rates are null. Report contract-eligible proposals separately from correct-known eligible proposals. Do not call withholding a dependency-violating patch unnecessary. Report complete candidate evidence/action parity of Python/SHACL-AF by each postcheck (32 paired comparisons), with no multiplication into independent trials. Errors remain denominator rows, separately labeled, never silently retried.

## Execution and reproducibility

- Installed pinned uv.lock versions: pySHACL0.40.1, RDFLib7.6.0. Record versions and lock hash each run.
- Rule phase uses advanced=True,inference='none',iterate_rules=False,inplace=True on a newly built private graph. One nonrecursive SPARQLRule, no blank-node creation. One pass is sufficient for independent1/2edge matching. Validation occurs separately without inference; preserve Turtle rules and shapes.
- Single process/arm child execution; timeout30seconds per row, one attempt, no automatic retry; max192rows. Smoke uses2synthetic cases×6arms and consumes those development cases; full run is same32, not fresh held-out. Save stdout/stderr/exit/errors. Do not reuse successful counts as independent samples.
- Freeze inputs/scorer/code/rule/shape/contract hashes before smoke and full run. Reserve new run directory; never overwrite failed or successful attempts. Verify expected32/192 before full execution.
- Before/after reports, candidate IDs/citations, diff, final disposition, versions and exact input hash saved. A runner launches isolated runtime with only input and arm; evaluator separately loads scorer after outputs saved. Unknown exceptions are errors, not a fabricated abstention.
- Runtime unit checks cover malformed inputs, no original mutation, path/role/version/uniqueness conditions, dependency veto and false-fact limitation. Fresh independent methods/implementation review required before completed-study claims.
