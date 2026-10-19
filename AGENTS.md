# Agent instructions (Codex, Orca-hosted agents, Cursor, etc.)

This repo now includes small GLEIF and native-SHACL YAGO → RDF → SHACL → OpenRouter QA pilots, alongside host bootstrap scripts. It is not yet a production GraphRAG system.

For session continuity, read local `MEMORY.md` if present. It is ignored by Git and must not be included in the public documentation site.

## Dataset and experiment scope

- GLEIF Golden Copy is the first dataset, replacing the earlier YAGO-first plan. Preserve same-release LEI/RR/REPEX files, source hashes and reporting exceptions. YAGO 4.6 is the second bounded pilot; keep its original SHACL bytes unchanged and retain CC BY 4.0 attribution.
- YAGO selective follow-up (protocol 0.4) keeps the same source/shapes and distinguishes question-relevant violations from missing evidence. Keep source absence separate from retrieval omission. S1/S2/C2 use a predeclared birthPlace contract, not a learned general-purpose policy. Report wrong answers and unnecessary abstentions together; this reuses the pilot cohort and is exploratory.
- User authorized a complete bounded pilot without routine clarification. Use conservative recorded budgets. Keep source corruption separate from retrieval omissions; never repair from evaluation gold. Preserve unsuccessful runs.
- Distinguish the 24-case pilot from representative benchmarks, free-form Text2SPARQL, full vector RAG and graph-engine comparisons.
- Semantic follow-up separates question/evidence applicability, conflicting evidence, and externally scored factual truth. Do not infer general LLM semantic weakness from prompts that prohibit real-world truth assessment. SHACL can encode declared semantic constraints; conformance is not external truth.
- Preserve semantically wrong model decisions as measured outcomes; do not correct or reject them with runtime oracle checks. Separate response-schema errors, citation applicability, final decisions and retrieval policy. Synthetic semantic development with supplied question contracts is not natural-language contract extraction or a fresh GLEIF benchmark.
- Protocol 0.5-study1 now has completed 12-entity development (72 cases) and 30-entity reserved evaluation (180 cases), six conditions and three repeats. This cohort is consumed, not fresh held-out data for future tuning. Keep frozen inputs, source-only retries, all failed attempts and entity-level analysis. Jev was measured separately on development only; actual Neo4j/Cypher parity covered 72 development cases, not engine performance.
- Expanded-study API reservations share `_workspace/expanded-study/campaign-budget.json` (3,200 attempts / $5 hard cap, never refund failures). Existing results must not be rerun merely to fill the budget. Scope new work explicitly; do not reset the ledger. Check intended subject limits and planned row counts before small paid smoke runs.

## Hybrid intervention research scope

- Current user objective: identify the data/question complexity and pipeline locations where a small explicit ontology/constraint layer helps controlled workflows and audit tasks. Do not assume RDF/SHACL superiority or require converting all source data to ontology.
- `hybrid-complexity-1` separates depth, constraint load, unrelated records and evidence state. It uses synthetic manufacturing approval contracts and a separate actual GLEIF bounded-reachability transfer check. Synthetic SHACL and GLEIF SPARQL are different comparators; no OWL reasoning or full graph-engine benchmark claim.
- Same-policy Python is essential. Pre-report benefits are computed-feature treatment, not proof of RDF superiority. Post-checks veto positive decisions only. Derived selective/post arms reuse model traces and are not independent paid measurements.
- Preserve the distinction between contract agreement, external synthetic truth, unnecessary rejection/abstention, source absence and projection/retrieval omission. A shape-conforming false fact with no contrary evidence cannot be identified by validation alone.
- Natural-language to typed-template selection is a separate bounded diagnostic, not free Text2SPARQL. Valid but wrong contracts must remain outcomes; a successful checker execution does not verify that the user's question was interpreted correctly.
- Keep interrupted runs and unresolved cost reservations. A manually inspected continuation must record its selected unfinished cases, separate original failure from recovery, and never silently rewrite the original denominator.

- Graph lifecycle protocol `graph-lifecycle-1` is a bounded synthetic JSON scan/indexed vs actual localhost Neo4j study. Preserve 2,880 rows and distinguish HTTP versus resident Python timing, full-file JSON update policy, predefined role changes and human maintenance effort (unmeasured). RDFLib SPARQL is an independent snapshot cross-check, not an RDF DB arm. Temporary owned Neo4j containers must be removed after execution; paid API stop remains.

- `shared-semantics-1` compares three copied JSON configurations, shared live JSON, matched JSON materialization and RDFLib SPARQL hybrid across three typed workflows. Preserve 12,288 controlled rows and distinguish fault injection topology, repeated pinned foreground, output errors, full candidate evidence mismatch, and freshness provenance. No measured maintenance labor, natural failure rates, LLM/OWL/SHACL/DB-server claims. Independent scorer verifies saved source contracts; it must never repair runtime answers.

- `semantic-guards-1` replays the same 12,288 development outputs under six veto policies and three synthetic field catalogs (221,184 decisions, not independent trials). Separate published operational metadata from evaluation references; wrong mapping is published as wrong too. Preserve missing/mislabeled catalog controls, conservative group-wide vetoes and dependency scope. Report wrong allowed and correct-known unnecessary withholding together; no repaired-answer, external-truth, latency or RDF-specific benefit claims.

- `bounded-refresh-1` reuses original outputs under veto/selective/eager policies, three catalogs and current/unavailable/initial-source services. One JSON snapshot read per three-task bundle; original arm names are lineage, not refreshed engines. Preserve advertised current fingerprints and count attempts/bytes once per group. Semantic conflict blocks automatic refresh/remapping; missing source stays unknown. GLEIF official-definition address examples and typed contracts are manual illustrations, not automatic document interpretation or independent benchmark evidence.

- `refresh-fallback-1` derives 110,592 decisions from saved selective-refresh responses. Restore only prevalidated outputs and rerun mixed-workflow checks. Report zero new source calls, inherited costs, newly allowed wrong outputs and restored correct outputs separately. Preserve original group-failure behavior and results.

## Six business-question pilot

- `business-questions-1` fixes three manufacturing and three finance tasks: impact products, replacement conditions, rechecks; direct accounting parent, same reported ultimate parent, internal review readiness. Preserve 36 authored synthetic fixtures /108 rows separately from four unscored actual GLEIF illustrations. JSON/RDF share decision logic; do not claim RDF superiority or independent business accuracy.
- Real GLEIF ACTIVE relationships may have LAPSED registration. This pilot conservatively accepts PUBLISHED RR only; withholding does not prove recorded relations false. Next planned comparison separates reported facts with source status from decision eligibility. Manufacturing remains synthetic; completeness/dependency declarations are supplied.

## LLM-led ontology tool study

- `llm-ontology-tools-1` gives the LLM natural-language questions, schema and shared policies; it constructs SPARQL, chooses optional validation and finalizes. A adds source tools, B adds ontology information, C adds callable query-contract/SHACL checks. Same RDFLib backend; no RDF engine advantage claim. The earlier deterministic business study remains a tool baseline.
- Latest human authorized this bounded paid campaign: 18 consumed synthetic development cases ×3 arms, one repeat, max324 calls/$1.50 nonrefunded reservation ledger `_workspace/ontology-tools-study/campaign-budget.json`. Do not reset old ledgers. Inspect unresolved costs before each manual launch; no automatic retry. Existing paid stop remains outside this authorization.
- Runtime receives no scorer task/scenario/answer. Query checking uses model-declared interpretation and can pass a wrong interpretation; unsupported constructs return unknown. SHACL selected-record conformance does not certify complete evidence or truth. Preserve failed queries, source absence, retrieval omissions, unfinished episodes and wrong final outcomes separately. No gold repair.

## YAGO native-tool integration follow-up

- `yago-native-tools-1` uses the existing four consumed YAGO people and original 38-triple subset/schema/taxonomy. Twelve A query-only/B optional-check/C required-check episodes share schema information. Keep original byte hashes and CC BY 4.0 attribution; no ontology-information ablation, engine or JSON comparison.
- Preserve the separate posthoc one-episode binding-scaffold diagnostic. Generic query examples and linked-context guidance form a combined interface intervention, not an independent efficacy result. Never overwrite the first twelve outcomes.
- The human-authorized bounded campaign used 136 calls, $0.02452470 reported and $0.32394015 nonrefunded reservations under144/$1.50. It is complete; unused budget does not authorize reruns. Preserve `_workspace/yago-tools/campaign-budget.json` and the earlier ledger. Automatic continuation now performs offline improvements only until a new paid scope is authorized.
- Model validation requests that returned unknown are not actual SHACL pass/fail executions. Coordinator posthoc validation on original/saved evidence is separate. Missing linked-place type context can cause class violations despite source-supported answers; conformance does not certify truth/completeness.
- Future work must separate binding feedback, model-selected description retrieval and explicit evidence-insufficient termination. Preserve the original mandatory-check dead-end outcomes, never repair from gold.

## Domain and introductory-guide research

- User expanded the objective to change-impact decision support across manufacturing, finance/GLEIF/FIBO, healthcare records, YAGO, Wikidata and documents. Separate domain, semantic layer and serialization; do not call renamed synthetic nodes domain transfer.
- `change-impact-1` is synthetic manufacturing potential-impact targeting, not physical simulation or change approval. Preserve 192 cases / 2,304 rows, aggregate one serialization only, and separate candidate errors from completeness claims. Typed JSON and RDF share eligibility semantics; supplied completeness/version metadata does not detect hidden source omissions. Direct and untyped arms always mark partial/unknown, so zero unsafe-complete claims do not establish superior safety.
- `domain-characteristics-1` is descriptive profiling of purposeful bounded real artifacts, not a cross-domain accuracy benchmark. Keep FIBO/YAGO schema inspection, official FHIR examples, one Wikidata entity and first-256 GLEIF source rows separate. Preserve identifier namespaces, reference roles, time/rank/provenance, imports, original hashes and failed source acquisitions. Do not infer global absence from a selected bundle or archive prefix.
- Build future 101 guidance from traceable input examples, preprocessing prerequisites, minimum semantics, measured outputs/failures and unverified scope. Include cases where JSON or LPG rules suffice; ontology is not presumed superior.
- User requested continued improvements if no reply within 30 minutes after results. Continue bounded authorized work in an active session, honoring existing budgets and paid-API stop. This instruction is not an installed scheduler; record continuation state and never claim an automatic wake-up without a supported tool and confirmed registration.

## Stack decisions (do not casually reverse)

- Ontology research now includes a bounded offline OWL-RL reasoning study, beyond SHACL validation. JSON rules and OWL-RL receive identical ontology semantics; asserted lookup is an ablation. Keep positive-rule closure membership, graph-wide disjoint-class witnesses, external truth and LLM hallucination separate. Vocabulary renaming is not real-domain transfer. Preserve the historical 2026-10-13 one-day 105-request authorization. On 2026-10-15 the user raised the ongoing daily role-request cap to 500; do not rewrite historical ledgers.

- **Host OS:** Ubuntu 22.04 / 24.04 on AWS EC2
- **Python:** manage with **uv** only (`uv sync`, `uv run`). Do not introduce plain `pip`/`venv` workflows.
- **Experimental LLM gateway:** **OpenRouter** via `.env` (`OPENROUTER_*`). Research operations and code work use the current Codex session and native subagents, not OpenRouter. No local GPU serving.
- **Secrets:** never commit `.env`, API keys, PEM, or AWS credentials. Use `.env.example` as the template.
- **IaC:** Terraform lives under `infra/terraform/` (placeholder until the account/region is fixed).
- **Graph stores (later):** GraphDB Free (primary SHACL), Neo4j Community (LPG baseline), Neptune (short window). Do not invent install scripts unless asked.

## How to work

1. Prefer changing `scripts/`, `docs/`, `AGENTS.md`, and config templates before writing app code.
2. After host bootstrap: `./scripts/bootstrap.sh` (or `--verify-only`).
3. Record non-obvious mistakes in `docs/lessons-learned/YYYY-MM-DD-slug.md` using the template.
4. Keep README / setup docs accurate when you change bootstrap behavior.
5. For experiments, keep the protocol in `docs/experiments/specification.md`, run summaries in `docs/experiments/records/`, and interpretation/decisions in `docs/journal/`. Preserve failed runs; never present synthetic E0 results as GraphRAG benchmarks.
6. Apply the user-requested [humanize-korean skill](https://github.com/epoko77-ai/im-not-ai/tree/main/codex/skills/humanize-korean) when writing Korean documentation. Read its `SKILL.md` and preserve facts, measurements, code, and technical terms. Keep intermediate writing artifacts under ignored `_workspace/`.
7. GitHub Pages uses Jekyll with Chirpy, configured in `website/`. Keep `docs/` as the canonical Markdown source. Check source docs with `uv run --locked --group docs mkdocs build --strict`, then build and check the published site with `./scripts/build_site.sh` (Ruby 3.4 and `BUNDLE_GEMFILE=website/Gemfile bundle install` required). The MkDocs build is a source check only; publish the final Chirpy output in `site/`. GitHub Pages is the chosen hosting destination; do not publish to another service. Pushing still requires an explicit request.

## Documentation headings and tone

- Use reader-facing stage names "사전 점검" and "1단계" through "4단계" instead of E0–E4. Preserve existing run IDs, fixture paths, archived results and machine-readable experiment identifiers. R0/G0/G1/G2 identify comparison conditions, not stages.

- User preference: use concise, specific noun phrases for section headings in research introductions, journals, protocols, and explanatory documentation. Avoid repetitive question-style headings such as "What do we compare?" or "Why did we do this?", which the user finds formulaic and AI-like.
- Name the actual subject, comparison, procedure, or rationale in each heading; do not merely remove the question ending or replace it with a vague academic label. Examples: "Validation, abstention, and retry conditions", "Evaluation metrics and interpretation criteria", and "Comparison-group selection rationale".
- Keep headings academically precise while making the body approachable with concrete examples and diagrams. Avoid unnecessary nominalization or inflated academic wording in the prose.
- A central research question may remain a question in the body when useful. This preference is not a blanket ban on questions, including genuine FAQ content.

## Documentation and explanation visuals

- User preference: proactively use diagrams wherever they make documentation or explanations easier to understand. Apply this when writing or revising research notes, experiment protocols, architecture descriptions, and code explanations.
- Prefer Mermaid for process, sequence, state, and relationship diagrams; SVG for precise reusable illustrations; function/call-flow diagrams for execution paths; and ASCII art for compact text-only explanations or terminal output. Choose the format that best communicates the content.
- Make inputs, outputs, branches, dependencies, and validation/repair loops explicit when relevant. Pair diagrams with concise explanatory text and preserve facts, measurements, and the distinction between implemented behavior and planned work.
- Keep diagram sources editable in the repository. For published diagrams, verify actual rendering in Chirpy, mobile readability, and light/dark contrast; provide a text fallback when needed.

## Coding agents on this host

- **Codex** reads this `AGENTS.md` (standard name). Optional overrides: `AGENTS.override.md`.
- **Orca** is an IDE/runtime that *hosts* agents; it does **not** replace Codex/Claude Code/etc. Install and authenticate the agent CLI on the machine where agents actually run (see `docs/setup/agents.md`).
- For SSH-only laptop→EC2: agents still need their CLIs/credentials available on the EC2 side when work runs remotely.
- For phone/mobile continuity: prefer Remote Orca Server (`orca serve`) on EC2, not SSH-only.

## Research operations workflow

- Research operations and code changes use the current Codex session and native Codex subagents. Only experimental QA calls OpenRouter. Never substitute an OpenRouter or OpenAI API worker for an unavailable native subagent.
- Main Codex owns planning, synthesis, implementation and interpretation. Delegate independent methods and implementation reviews with separate contexts (`fork_turns="none"` where supported); give each only its phase request and own result path. Reviewers must not read one another's outputs or write source code. Native subagents inherit workspace/tool access; these boundaries are instructions, not an OS sandbox.
- Follow `research/operations/RUNBOOK.md`. `scripts/research_ops.py` only freezes requests, records returned JSON, enforces reviewer gates and runs registered offline checks. It never starts an LLM client, nested Codex CLI or background service. Use Codex's available collaboration tools to dispatch requested reviews.
- Config, role instructions and task examples live in `research/operations/`. New requests, submissions, attempts and a logical request ledger live under ignored `_workspace/research-ops-codex/`. Preserve historical OpenRouter jobs and costs in `_workspace/research-ops/`; do not rerun them through the new runner.
- Keep the user-authorized maximum of 500 recorded role requests per UTC day, 7 per job and 2 concurrent reviewers. This is a repository workflow limit, not a Codex token/account or monetary cap. Do not claim Codex usage is free. Experimental API budgets remain in their existing runners; AWS billing is separate.
- Explicit prose packets exclude held-out gold and secrets. A reviewer receiving an abbreviated packet must mark omitted facts unverified, not invent defects. Never repair from evaluation gold. Preserve source absence, retrieval omission and externally scored factual error as separate concepts.
- Every submission records its request binding and operator-supplied agent ID. That ID is an audit annotation, not authenticated proof. Both reviewers must be distinct agents; a coordinator cannot override a reviewer blocker. If collaboration is unavailable, leave the work awaiting review and report the limitation.
- Preserve unsuccessful attempts and consumed request reservations. Inspect before explicit retry; changed verification code or plan requires a new job. Completed steps are reused. Source code changes after a review need fresh review/check records. Local software tests are not GraphRAG benchmarks.

## Safety / scope

- Do not push to remote unless explicitly asked.
- Do not expand into full GraphRAG pipeline, GraphDB install, or Terraform apply unless the user asks for that phase.
- No fabricated benchmark numbers; if a baseline was not measured, say so.
