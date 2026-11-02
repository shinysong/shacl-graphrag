# Offline provenance demonstrator

Presentation only. Reuse run-001 saved outputs and two actual source audit rows.
No new inference, LLM/API calls, source edits, gold-driven repair or benchmark.
Files under docs/experiments/actionable-evidence-demo/; independent builder at
scripts/build_actionable_demo.py validates exact saved grid/hash bindings and emits
demo.json plus data.js (`window.ACTIONABLE_DEMO = ...;`) for offline file viewing.

## Data interface

Top object: `study`, `mode`, `source_attribution`, `arms` and `postchecks` arrays
of `{id,label}`, `cases` array, `provenance` (source file hashes).
Every case: `{id,kind,label,question,note,input,relations,provenance}`.
`kind` is `real_audit` or `synthetic_replay`.
`input` contains source/extracted raw JSON; UI should show readable key/value table
plus expandable exact JSON. `relations` is array of `{from,relation,to}`.
`provenance` array of `{label,locator,sha256,url?}`; no personal report imagery.

Real case additionally: `request:{title,reason,items:[string],forbidden:[string]}`.
No computed/SHACL result exists for these rows; explicitly researcher-authored
confirmation requests from descriptive audit. Disable arm/post controls for real
cases. Present PP5 interval review and PP7 nominal-versus-recorded setting review;
neither source is automatically declared wrong. Numerical source rows untouched.

Synthetic case additionally: `runtime` (exact authored JSON), `outputs` mapping
`arm + '|' + postcheck` to saved row.result, `evaluation` (separate scorer labels),
and `paired_missing_case` optional. Keys in saved result: candidate_reference_ids,
candidate_citations, candidate_patch {target,field,old,new} or null, before_report,
after_report (each {shacl:{conforms,results},python:{conforms,results},validators_agree}),
diff, disposition, provenance, diagnostics. Raw replay output is exact saved JSON.
Evaluation appears in a visually separated panel labeled posthoc synthetic
evaluation, never part of the displayed runtime input or decision rationale.

Selected synthetic c008 (supported two-hop), c015 (dependency veto), c014
(conforming false reference), c009 (missing evidence; c010 has identical payload).
All six arm/post combinations available, no filtering by successful final answer.

## UI and checks

White background, local Pretendard font with OFL, restrained lines/color, concise
Korean noun headings and polite prose. All meaningful panels visible initially.
Replay button highlights successive panels but never hides original content or
pretends live execution. Label prominently saved execution replay, no browser
reasoning. Respect reduced motion, cancel timers on selection changes, keyboard
focus and accessible form labels, mobile layout and print. No third-party network
requests; source link opens only when clicked. Use DOM textContent for data.

Show input → relationship evidence → candidate/request → before/after report →
final disposition. For real cases replace executable report with explanatory
request; do not fabricate conforms or execution times. For synthetic false reference
show that conformance passes while posthoc external expectation differs. No
correction/action execution button. Optional JSON download of displayed record only.

Builder verifies selected source values against full original extract, complete
32×3×2 grid, case/arm/post and exact fixture hash bindings, runtime output file hashes,
frozen fixture/code hashes and missing-pair identity. Preserve run001 unchanged.
Browser tests cover all real cases and4synthetic×6conditions, display-value equality,
no live API calls, no errors/overflow, replay cancellation and reduced motion.
Obtain fresh independent methods/implementation review before reporting completion.
