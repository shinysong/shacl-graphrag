# Local software integration scope

The current task verifies the researcher-side operations software, not a new
scientific study. Its deliverables are registered local check results, role outputs,
blocker gating, restart records and logical role-request accounting.

The two registered checks are unit-tests and e0-local. The first invokes unittest
discovery. The second invokes the existing synthetic validator with --local-only.
Their results establish local software behavior. They do not measure QA accuracy,
held-out generalization, source truth or peak memory use.

At plan, review and synthesis stages the checks have not yet executed in this job.
Judge whether these bounded checks may proceed, using ready or revise. Historical
scientific limitations are not prerequisites for executing local software tests.

At analysis stage the supplied check results contain actual exit codes. Use observe
and describe those results with their check IDs. No new experiment is authorized.
Native Codex role requests and local check commands are recorded separately.
The recorder never calls a model API; experimental OpenRouter usage is separate.

This prose packet deliberately contains only the current task scope. Broader
research background is provided separately when the task designs a new study.
