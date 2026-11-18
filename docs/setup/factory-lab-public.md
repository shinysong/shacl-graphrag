# Factory Lab local demo

Factory Lab turns a compound factory question into a plan of reusable fixed queries, executes that plan against a small local RDF graph, and displays the answer with evidence and unresolved requirements. It is an exploratory software demo over fictional factory data, not an industrial approval system.

For CSV/policy onboarding, persistent review and the separate two-call workspace question path, see the [operations workspace guide](workspace.md). The three-call sequence below describes the original `/` research screen.

## Requirements and keyless startup

Use Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). The release verification target is Linux; macOS uses the same commands but is not yet verified. Windows is not supported by the process file lock; use a Linux environment such as WSL. No AWS account, Neptune, Neo4j, Docker, Ruby or API key is needed for this path.

From the repository root:

```bash
uv sync --locked
uv run --locked python -m apps.factory_lab.public_server
```

Open `http://localhost:9261`. Select a saved example on the left. These are real historical model answers with their saved query plans and evidence, labeled **saved record / no API call**. Opening them does not rerun a model or graph query. The graph panel starts collapsed and shows only relations in that question's retrieved evidence.

Use `--port 9262` if the port is occupied. Local state goes to `_workspace/factory-lab-public/`; `--data-dir` chooses a different private directory. Keep it out of version control. This entry point does not restart or replace the older research service on port 9260.

## Live execution with your own key

The default server cannot make paid calls. To enable them, stop it, copy the configuration template, and select an available model and provider with text chat support:

```bash
mkdir -p _workspace/factory-lab-public
cp examples/factory_lab/live-config.example.json _workspace/factory-lab-public/live-config.json
```

Edit the model/provider placeholders and the two per-million-token prices using your provider's current pricing. The example price values are illustrative, not a recommendation or verified quote. Choose your own small `max_usd`, `max_calls` and `hours` limits. Current demo ceilings are USD 5, 100 calls, eight hours and 4096 output tokens. One successful question uses three calls: requirement decomposition, query planning, final answer. Failures consume attempts too.

Set `OPENROUTER_API_KEY` in the server environment using your local secret manager, or an ignored `.env` file. Do not put a real key in a command copied into documentation, a config committed to Git, the browser, or a screenshot.

```bash
uv run --locked --env-file .env python -m apps.factory_lab.public_server \
  --live-config _workspace/factory-lab-public/live-config.json
```

The server uses OpenRouter's [Chat Completions endpoint](https://openrouter.ai/docs/api-reference/overview), pins the selected provider, disables fallback, and requests temperature 0. Model support varies and temperature 0 does not guarantee identical answers. A fresh real provider request was **not** made during release preparation. The BYOK path is verified with mocked HTTP and actual local graph/review execution; provider availability and model-specific output behavior remain unverified.

The app records conservative cost reservations before requests, keeps them after failures, retains provider-reported cost, and stops on missing billing or a cost anomaly. These local reservations are not an invoice guarantee. Provider pricing/configuration must be correct; a provider-side key spending limit is an additional account control. Stop requests prevent later calls; an in-flight request may still complete and be charged. There are no automatic retries.

## Persistent session and privacy

A session starts when the live server is first initialized. Its deadline and configuration are saved in the data directory. Restarting the server keeps that deadline, ledger and consumed reservations. Changing the configuration is rejected for an existing session. To intentionally start another session, stop the old server and choose a new data directory; keep the old one for audit. Never delete a ledger to make an interrupted experiment appear clean.

The server listens only on `127.0.0.1`. For remote development, use an SSH tunnel to port 9261. This is a single-user local app, without public hosting authentication. Host/origin/CSRF checks protect local requests; they do not turn it into a multiuser service.

New questions and retrieved evidence are sent to the configured model provider. The API key stays in server memory. Local SQLite records include questions, outputs, events and cost metadata; protect that directory. Private request/response files preserve model and HTTP failures before parsing. Authorization headers are never saved; the configured key is defensively redacted if echoed. These raw artifacts are not exposed by the HTTP API. Bundled examples contain authored synthetic entities and saved generated text.

## What the workflow does

```text
Original question
  -> LLM requirement decomposition
  -> BM25 top-3 contracts per requirement, combined catalog
  -> LLM fixed-query plan and prior-output bindings
  -> input/connection checks
  -> bounded local RDFLib queries with evidence lineage
  -> procedural scope report + optional Python/SHACL report
  -> LLM final answer and requirement coverage
  -> local history, evidence details and optional graph view
```

The request sequence is implemented in `apps/factory_lab/public_runtime.py`; HTTP endpoints and local access checks are in `public_server.py`.

```text
Browser        Local server        Model provider        RDFLib / reviewer
   | POST question  |                     |                      |
   |--------------->| reserve + decompose |                      |
   |                |-------------------->|                      |
   |                |<-- requirements ----|                      |
   |                | search catalog; reserve + plan             |
   |                |-------------------->|                      |
   |                |<-- raw plan --------|                      |
   |                | check bindings; fixed queries ------------>|
   |                |<---------------- rows + evidence + report --|
   |                | reserve + final answer                     |
   |                |-------------------->|                      |
   |                |<-- answer/coverage -|                      |
   | poll saved events/results            |                      |
   |<---------------|                     |                      |
```

LLM-generated free SPARQL/Cypher is not executed. Queries are fixed in code and entity arguments are checked. The plan can fan out over earlier results, retaining order/candidate context. At most eight plan steps and twelve actual queries are permitted. The bundled graph snapshot is `factory-v3`; no live industrial state or schedule data exists.

The optional SHACL/Python report checks only retrieved replacement candidates and selected qualification records. It does not fetch missing facts, guarantee that all original requirements were identified, or force the final model to withhold its answer. A supported qualification must match product, capability and date within one record. Scheduling, load, authenticity and physical approval remain outside scope. No candidates means not assessed, not validation success.

The portable live workflow combines retrieval, connection checking and optional qualification review. It is a new demo configuration; do not treat it as an unchanged arm of the frozen research comparison. Saved examples retain their original condition and were not generated with the current optional SHACL setting.

## Extension and troubleshooting

See [adding a fixed query](factory-lab-extension.md) for a runnable query/contract example. See [release readiness](../releases/factory-lab-readiness.md) for verified and unverified release scope, and [research freeze](../releases/research-freeze-001.md) for historical claims.

- **Example hash mismatch:** restore bundled fixture files from the release; do not silently rewrite hashes around an unintended edit.
- **Live calls disabled:** use saved examples or explicitly start with `--live-config` and your key.
- **Session configuration differs:** preserve the old ledger and choose a new directory for a deliberate new session.
- **Unknown billing / failed run:** inspect local events and provider billing. The app does not automatically retry or repair.
- **No answer or partial coverage:** inspect the raw plan, query results and unresolved needs. A successful query does not prove that the question was answered.
- **Connection refused:** keep the terminal server running, use the printed port, and check any SSH tunnel separately.
