# Factory Lab first-release readiness

## Candidate scope

`0.1.0-rc1` is a local single-user demo over fictional factory data. Research conclusions are frozen separately in [research-freeze-001](research-freeze-001.md). This candidate is prepared locally, not published. No new paid calls, AWS starts, legacy service restarts, commits or pushes were performed.

## Required work and evidence

| Item | Result |
| --- | --- |
| Research preservation | baseline-001 records 506 pre-release files; existing outcome manifests remain authoritative for historical executions |
| Portable startup | Separate public server, bundled snapshots, in-process RDFLib; no AWS, Neo4j or API key required |
| Keyless examples | Four saved historical answers with original plans, evidence and provenance; explicitly labeled replay |
| Live workflow | Explicit BYOK, fixed-query composition, selected-evidence Python/SHACL review, persistent budget and failure accounting |
| Extension | Standalone unavailable-candidate query executes against bundled RDF; default catalog remains unchanged; registration documented |
| Independent review | Distinct methods and implementation reviewers approved revised source before registered tests; earlier blockers/failures retained |
| Registered checks | factory-public-tests, research-ops-tests and query-contract-tests all exit 0 |
| Fresh installation | Separate directory, fresh Python 3.12 environment, `uv sync --locked`, 10 public tests and runnable extension passed |
| Browser | Chromium at 1440px/light and 390px/dark: four examples, evidence links, initially collapsed graph, no horizontal overflow, JS errors or external requests |
| Credentials | Public checkout contains no private workspace/env/key files; pattern scan across 6,233 files found no matching private-key/OpenRouter/AWS access-key literals; not an exhaustive secret audit |
| Documentation | Strict MkDocs build, Chirpy build and site checks passed; `git diff --check` passed |
| License | Owner approved Apache-2.0 for original code and authored fixtures; third-party notices retained |
| Dependency inventory | Fresh default install contains 37 distributions, each with license metadata or license files; versions and available license hashes recorded |

The license inventories are under `research/factory-lab-release-1/`. Private operational logs, screenshots, clean-checkout hashes and review job records remain under ignored `_workspace/`; they must not be published as a directory. A public verification receipt records their hashes and outcomes.

## Preserved verification failures

The first independent review found filtered qualification evidence missing from the optional report and failed raw responses not retained. Both were corrected and reviewed again. An offline extension test then found that its expected known-Order input restriction was not enforced; the fixed template already encoded literals safely. A typed selected-view ID guard corrected the contract mismatch.

The first clean checkout omitted bundled snapshots because an inherited ignore pattern matched their directory. Narrow public-fixture exceptions corrected packaging. A browser harness initially used string evaluation blocked by the app CSP; the harness was corrected without weakening CSP. Original failures were retained.

## Unverified and deferred scope

- Real provider requests were prohibited during release work. Mocked HTTP and scripted model messages exercised actual RDFLib and SHACL execution; current provider availability, model-specific outputs and answer efficacy remain unverified.
- Linux/Python 3.12 was tested. macOS and other Python versions were not tested. Windows needs a Linux environment such as WSL because of the process lock.
- Budgets depend on supplied current prices and provider billing. Reservations are not an invoice guarantee. No peak-resource or throughput benchmark was performed.
- Review covers selected evidence only. It does not establish source completeness, external truth, physical safety or all original-question requirements.
- Public multiuser hosting, authentication, arbitrary datasets, Neptune operations and additional query languages are deferred.
- Existing website/paper/data materials retain separate terms. The root license does not relicense them; publishing a larger asset collection needs its own attribution review.

## Publication boundary

The deliverable is a local release candidate, not a published package. A future authorized release should commit the intended changes, verify the exact committed tree, and choose release/tag/publication scope. This work does not grant permission to publish private histories or claim SHACL accuracy improvements.
