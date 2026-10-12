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

## Coding agents on this host

- **Codex** reads this `AGENTS.md` (standard name). Optional overrides: `AGENTS.override.md`.
- **Orca** is an IDE/runtime that *hosts* agents; it does **not** replace Codex/Claude Code/etc. Install and authenticate the agent CLI on the machine where agents actually run (see `docs/setup/agents.md`).
- For SSH-only laptop→EC2: agents still need their CLIs/credentials available on the EC2 side when work runs remotely.
- For phone/mobile continuity: prefer Remote Orca Server (`orca serve`) on EC2, not SSH-only.

## Safety / scope

- Do not push to remote unless explicitly asked.
- Do not expand into full GraphRAG pipeline, GraphDB install, or Terraform apply unless the user asks for that phase.
- No fabricated benchmark numbers; if a baseline was not measured, say so.
