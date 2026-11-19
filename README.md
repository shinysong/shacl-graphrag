# Factory Lab · SHACL GraphRAG

A local GraphRAG demo for compound questions: an LLM selects and connects reusable fixed queries, a small RDF graph supplies evidence, and the answer shows what was answered and what remains unresolved. Optional SHACL or Python checks review selected qualification evidence.

The repository also preserves exploratory research. Current evidence does **not** establish that SHACL or contract checks generally improve answer accuracy. See the [research freeze](docs/releases/research-freeze-001.md).

## Run without an API key

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync --locked
uv run --locked python -m apps.factory_lab.public_server
```

Open **http://localhost:9261** and select a saved example. The bundled fictional factory data and historical answers let you inspect requirements, query plans, evidence, unresolved needs and a compact graph view. Replay makes no model or graph request. AWS, Neptune, Neo4j and Docker are not required.

This is a local single-user release candidate, `0.1.0-rc1`. Linux is the verification target; macOS is unverified and Windows needs a Linux environment such as WSL. Keep the server running while using the page.

## Use your own CSV and policy documents

Open **http://localhost:9261/workspace** for the evolving single-user operations workspace. Upload sources, review field suggestions, save review drafts, run approved-source lookups and compare revisions. Start with the [workspace guide](docs/setup/workspace.md), including supported inputs and current limitations, or the [three-file commerce example](examples/factory_lab/workspace/commerce-lines/README.md).

Workspace free questions require the separate `--workspace-questions` opt-in and use at most two model calls. `--workspace-model-proposals` separately enables a one-call meaning-draft proposal. Both share the configured budget; neither is enabled by a plain startup. Scripted local integration and bounded live-model onboarding checks are recorded separately; neither establishes general model quality. Existing factory research paths remain available.

## Ask new questions with your own key

Live execution is disabled by default. Follow the [setup guide](docs/setup/factory-lab-public.md) to configure an OpenRouter model/provider, current prices, a small session budget and your server-side API key. One completed question in the original `/` research screen uses three LLM calls. No automatic retry or provider fallback is enabled. Session limits and failure reservations persist across restarts.

No new paid provider call was made for release preparation. Mocked HTTP plus actual local RDFLib/SHACL execution verifies software behavior; it does not verify current provider availability or answer quality.

## Workflow

```text
Compound question -> LLM requirements -> retrieved query contracts
                  -> LLM dependency plan -> checked fixed-query execution
                  -> evidence + optional SHACL/Python report
                  -> final answer + unresolved requirements
```

The model selects query IDs and arguments; it does not write executable SPARQL or Cypher. Query success, shape conformance and answer correctness are different. The demo has no schedule, load, authenticity or physical approval service.

## Learn and extend

- [Installation, BYOK, privacy and troubleshooting](docs/setup/factory-lab-public.md)
- [Inspect SHACL constraints, OWL derivations and historical answer changes](docs/setup/factory-lab-explanation.md)
- [제조·이커머스 사례와 내 데이터 입력](docs/setup/commerce-data.md)
- [Add a fixed query and contract](docs/setup/factory-lab-extension.md)
- [Release checklist and limitations](docs/releases/factory-lab-readiness.md)
- [Frozen research results](docs/releases/research-freeze-001.md)
- [Latest compound-query experiment](docs/experiments/compound-query-composition.md)
- [Research documentation](https://shinysong.github.io/shacl-graphrag/)

Runnable extension, with no model call:

```bash
uv run --locked python -m examples.factory_lab.extensions.unavailable_candidates
```

## Development

```bash
uv run --locked python -m unittest discover -s tests -p 'test_factory_public.py'
```

`apps/factory_lab/public_*` contains the portable entry point and UI. Historical research services and campaigns retain their original paths. `examples/factory_lab/` contains the small hashed demo bundle. Local state under `_workspace/` is private and ignored by Git. Do not commit keys, runtime histories or `.env` files.

## License

Original project code and authored synthetic Factory Lab fixtures: **Apache-2.0**, selected by the owner. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md). Third-party datasets, paper figures, browser dependencies and website assets retain their own terms. The root license does not relicense them.

CSV·정책 문서에서 시작하려면 [데이터 준비 안내](docs/setup/data-preparation.md)를 확인하세요.
