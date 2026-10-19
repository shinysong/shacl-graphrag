# Local rule workbench

The workbench connects tabular data with document-derived rule candidates, lets a person select executable conditions, and reports actual SHACL checks against the loaded snapshot. The Korean interface runs locally. An optional, explicit OpenRouter action proposes document-grounded rules and column mappings. Proposals remain drafts until a person reviews them; the LLM does not approve business decisions.

## Start the interface

From the repository root:

```bash
uv sync --locked --group workbench
uv run --locked --group workbench streamlit run apps/rule_workbench.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8501`. When running on EC2, forward the port from your laptop with `ssh -L 8501:127.0.0.1:8501 your-ec2-host`, then open the same local address. The app binds to localhost and provides no multi-user authentication or public hosting.

## First complete cycle

1. Select **예제 프로젝트 불러오기** to load two example tables, a policy document and three confirmed rules. This replaces the current in-memory workspace.
2. In **데이터 연결**, inspect the supplier table. You can also upload CSV, XLSX or a SQLite snapshot, or read a PostgreSQL table.
3. In **규칙 문서**, upload PDF or Markdown, or paste text. In basic mode, nonblank lines become **draft** candidates with their original page or line. Choose **LLM 규칙·연결 제안** to request interpreted candidates and mappings. Headings may appear as candidates too. Review or delete them; no semantic extraction accuracy is assumed.
4. In **규칙 검토**, choose a table, column, condition and parameters. Confirm the interpretation and save it. Five conditions are supported: required value, numeric bounds, allowed values, date ordering, and existence in another table.
5. In **검사 결과**, execute the saved rules. Select a result to inspect its source row. Missing or malformed values are distinguished from violations; a successful check is not a business approval.
6. Change a condition and save. The old results become stale and are hidden. Run again to compare statuses with the immediately previous run. This comparison matches rule ID, table ID and row position, not independently verified business-entity identity.
7. In **내보내기**, download JSON, Excel or ZIP. Include source rows and document text explicitly if you want a self-contained workspace. Import the JSON to continue reviewing or run it through the CLI.

```text
CSV / XLSX / SQLite / PostgreSQL     PDF / Markdown / pasted text
                |                              |
          Loaded tables            Basic lines / LLM proposals
                +---------------+--------------+
                                |
                      Human mapping and review
                                |
                    RDF snapshot + SHACL shapes
                                |
             Pass / violation / unknown / not applicable
                                |
                    JSON / Excel / ZIP / Turtle
```

## Data connectors

CSV supports UTF-8 with optional BOM and a CP949 fallback. Text IDs retain leading zeros. XLSX imports all sheets with headers; formulas remain literal text and are not calculated. SQLite uploads are copied temporarily, opened read-only and removed after import. Views and virtual tables are excluded or rejected.

PostgreSQL uses a read-only transaction and validated, quoted table names in the default schema. It exposes no arbitrary SQL field. Connection strings stay in session memory and are excluded from exported project metadata. The connector has mocked verification; a live PostgreSQL instance is not part of this prototype's test environment.

Uploads are limited to 20 MB, 50 tables, 200 columns and 5,000 loaded rows per table. Truncation is recorded. A workspace is limited to 1,000,000 cells and each validation run to 20,000 rule-by-row checks. These are guardrails, not measured capacity guarantees. PostgreSQL snapshots have no stable row ordering guarantee across reads.

## Rule documents and adapters

PDF support extracts embedded text from at most 100 pages. It does not perform OCR or recover complex tables reliably. Markdown supports up to 2,000 lines. More than 100 candidate lines produces an explicit error rather than silently dropping candidates.

`rule_workbench.extractors.candidate_rules(document, extractor=callable)` accepts an alternative extractor. It must return rule dictionaries in the workspace format; its candidates are forced to draft status. External services can instead provide a project JSON. The interface requires a person to map and confirm executable conditions. A document with a rule sentence is not automatically a correct executable constraint.

## Results and export boundaries

| Status | Interpretation |
|---|---|
| Pass | The declared condition held for this eligible snapshot row |
| Violation | The executed SHACL condition failed |
| Unknown | Unreviewed rule, missing mapping/data, malformed value or execution failure |
| Not applicable | A mapped, genuinely empty table provided no rows to inspect |

Counts combine row-level checks and rule-level notices where execution cannot start; they are not entity counts or accuracy rates. A redacted JSON import has missing source rows and yields unknown rather than passing or claiming an empty source table.

The JSON format is versioned with `schema_version: 1`. Default exports omit source rows and full document text, while retaining rule quotations and mapping metadata. Those quotations may themselves be sensitive. The optional data-inclusive ZIP includes `data.ttl`. Reference-table values are stored in RDF data, not embedded as SHACL enumerations. Rule-authored allowed-value lists remain part of the rule.

Exported shapes target eligible snapshot rows. Unknown rows are recorded separately in results and coverage metadata. These shapes are a snapshot execution artifact, not a general ontology that can be applied unchanged to arbitrary new data. SHACL and RDF together reproduce eligible checks; use the JSON project to preserve unknown statuses and full workflow meaning. Metadata-only projects require data reconnection and remapping before rechecking.

```text
rules-workbench.zip
├── manifest.json
├── project.json
├── rules.json
├── mappings.json
├── review.xlsx
├── shapes.ttl       when current results exist
├── results.csv      when current results exist
├── coverage.json    when current results exist
└── data.ttl         only with explicit source-data inclusion
```

## Library and CLI

```python
from rule_workbench.core import demo_project, run_checks
from rule_workbench.exports import export_bundle, import_json

project = demo_project()
result = run_checks(project)
archive_bytes = export_bundle(project, result, include_data=True)
```

```bash
uv run --locked --group workbench python scripts/run_rule_workbench.py --demo --include-data --output /tmp/rules-demo.zip
uv run --locked --group workbench python scripts/run_rule_workbench.py --project project.json --include-data --output /tmp/rules-recheck.zip
uv run --locked --group workbench python -m unittest discover -s tests -p 'test_workbench_*.py'
```

Output ZIP paths must not already exist. Validation and CLI checks run offline; only the explicit LLM proposal action makes experimental model calls. Replacing the extractor, adding rule templates, live database integration and background refresh require their own checks; the current prototype does not implement automatic ontology discovery, arbitrary Text2SHACL or an agent orchestration service.

## Optional LLM proposals

`rule_workbench.llm` builds a whitelisted prompt and validates structured JSON. `rule_workbench.transport` reuses the repository accounting runner and OpenRouter structured outputs. It sends selected document text and table IDs/names/column names, never source rows, existing rules or database credentials. Document text and labels are untrusted input. No generated code or SQL is executed.

The five executable templates remain the same. Conditional approvals, strict inequalities and unsupported joins must be retained as unsupported candidates rather than weakened. Quotes must occur literally in the cited source segment. This verifies quotation provenance, not semantic correctness. Invalid mapping names are cleared and accompanied by questions. All returned rules are drafts.

The GUI shows the full prompt before the explicit execution button, model ID, reported cost, rationale and unresolved questions. JSON, Excel and ZIP retain model/request metadata. A person must review meanings and mappings before confirming. The original model response is retained separately from later manual edits.

Server-owned `_workspace/rule-workbench-llm/session.json` records allowed model prices, deadline, historical ledgers and a bounded ceiling (20 calls / USD 2 for the integration campaign). Credentials come from `.env` or the server environment. The GUI cannot raise the cap or renew the deadline. This private file is not part of public exports. A fresh authorized scope is needed after expiry; never reset consumed ledgers. Raw requests/responses under the same private directory contain selected document text.

Identical model/prompt/schema requests reuse saved responses without another paid call. Failed consumed requests are preserved and never automatically retried. Truncated or schema/provenance-invalid outputs add no rules. Unknown provider costs block further paid calls pending inspection. Per-workbench cumulative reservations and all discovered historical daily study calls are accounted for.

LLM inputs are limited to 8 documents, 100 segments, 24,000 text characters, 20 tables and 200 columns per table; the provider request also has a 60 KB bound. These bounds reject inputs rather than silently truncating them. This is a template-based proposal tool, not arbitrary Text2SHACL, automatic ontology discovery or autonomous workflow orchestration.

## Verified integration examples

On 2026-10-19, six paid requests covered three authored examples with each of two models (`anthropic/claude-haiku-5.5`, `openai/gpt-6-luna`). Reported cost was USD 0.002886625; reservations were USD 0.0177583. All six responses completed. This is a small software integration demonstration, not a representative extraction benchmark or model ranking.

| Example | Candidates per model | Demonstration review | Checks after review, per model |
|---|---:|---|---|
| Supplier policy | 3 | All three confirmed against the source and schema | 7 pass, 3 violations, 2 unknown |
| Payment policy | 4 | All four confirmed against the source and schema | 4 pass, 4 violations |
| Conditional approval plus injected instruction | Haiku 2; Luna 1 | All retained as drafts | Haiku 2 unknown; Luna 1 unknown |

Both models represented conditional approval as unsupported. Haiku also surfaced the injected instruction as an unsupported candidate; Luna omitted it. Neither caused automatic confirmation or database actions. This single example does not establish general prompt-injection resistance.

The coordinator reviewed fourteen supported candidates and changed only their status for the demonstration; model outputs remain preserved. Missing dates remain unknown, the date comparison includes equality, currency matching uses exact strings, and registry references check value existence. These are declared operating semantics, not proof of external business truth.

All six projects retained their statuses and LLM metadata through JSON export/import and reproduced check counts. Exported RDF/SHACL was executed separately. Unsupported-only projects have no executable shapes: an empty SHACL report can conform while the workbench correctly reports unknown. The browser test reused a saved LLM response, downloaded three draft candidates and checked desktop/mobile layouts. Forty-three scoped tests passed. The published Chirpy build remains unverified because Ruby's `bundle` command is unavailable; the strict MkDocs source check passed.

See the [machine-readable integration record](../experiments/records/20261019-rule-workbench-llm.json) for the full candidate counts, review scope and limitations.
