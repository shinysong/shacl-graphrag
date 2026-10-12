# Agent instructions (Codex, Orca-hosted agents, Cursor, etc.)

This repo is **bootstrap-first**: host setup scripts and docs exist; pipeline application code is still thin.

For session continuity, read local `MEMORY.md` if present. It is ignored by Git and must not be included in the public documentation site.

## Stack decisions (do not casually reverse)

- **Host OS:** Ubuntu 22.04 / 24.04 on AWS EC2
- **Python:** manage with **uv** only (`uv sync`, `uv run`). Do not introduce plain `pip`/`venv` workflows.
- **LLM gateway:** **OpenRouter** via `.env` (`OPENROUTER_*`). No local GPU serving.
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

## Safety / scope

- Do not push to remote unless explicitly asked.
- Do not expand into full GraphRAG pipeline, GraphDB install, or Terraform apply unless the user asks for that phase.
- No fabricated benchmark numbers; if a baseline was not measured, say so.
