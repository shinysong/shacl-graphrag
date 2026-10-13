# Research operations context

This is the researcher-side workflow, separate from the experimental QA architecture.
The main coding agent implements changes after reviewing handoff tasks. This bounded
runner plans, independently reviews, executes registered offline checks, and analyzes
the check results. It does not autonomously edit code or execute generated commands.

Existing GLEIF and YAGO pipelines use fixed RDFLib retrieval, pySHACL, code-defined
abstention/repair policies and an OpenRouter answer model. They are bounded pilots,
not full vector RAG, free-form Text2SPARQL, or graph-engine benchmarks.

YAGO protocol 0.4 compares G0/G1/G2/U2/S1/S2/C2. The same three pilot subjects and
one birthPlace contract were reused in the selective follow-up; this is exploratory.
Source absence and retrieval-only omission are distinct. S2 retrieves only the
available source; evaluation gold never enters repair. Original YAGO shapes are
unchanged and CC BY 4.0 attribution is retained.

A shape-conforming false place passed SHACL. An external evaluator labeled it
incorrect by comparing against the pre-injection snapshot. This did not demonstrate
SHACL detecting a factual error. New independent evidence would be required to
identify a source conflict; a conflict alone does not establish which source is true.

Next possible work: define a new evaluation cohort before changing policy, retain
development/evaluation separation, and separately specify source-conflict detection
and abstention. None of those future experiments is implemented by this task packet.

Host target: Ubuntu EC2 r7g.large, 16GiB nominal RAM; peak experiment memory has not
been measured. Use uv only. No GPU serving, database install or Terraform apply.
Research operations uses native Codex collaboration and counts logical role requests;
experimental QA keeps its separate OpenRouter dollar and call budgets.

Allowed local checks: unit-tests invokes unittest discovery; e0-local invokes the
existing synthetic validation runner with --local-only. Passing these establishes
software functionality, not research quality, independent facts, or QA accuracy.
