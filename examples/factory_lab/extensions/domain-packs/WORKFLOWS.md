# Three small-domain reviewed workflows

Use these recipes to register a public synthetic pack, review its fields and policy, execute its second fixed question, and classify the saved output with an explicit RDFS ontology. The inputs are [commerce-small](commerce-small/query-config.json), [manufacturing-small](manufacturing-small/query-config.json) and [organization-small](organization-small/query-config.json). Their adjacent `runtime-questions.json` files preserve the questions; `domain-config.json` identifies source columns and declared foreign keys.

The route is **registered source → reviewed fields and policy → approved relation → approved query → saved answer → approved RDF projection and ontology → actual local reasoning → separate advisory record**. Approval, execution and advisory use are separate actions. These recipes use authored interpretations. Actual auto-ontology semantic-result editing/adoption was demonstrated separately on the originating small commerce source; manufacturing and organization reasoning used authored mappings and ontologies. A catalog export alone is not generated business semantics.

This is a manually executable recipe checked against public configs and current UI source. It is not a claim that this new document was executed end to end. See the [recorded results](../../../../docs/experiments/records/factory-lab-extensions-20261119.md), [upstream setup](../../../../docs/setup/factory-lab-upstream-extensions.md) and [detailed commerce UI walkthrough](../../../../docs/setup/factory-lab-extension-walkthrough.md) for their measured scopes. All examples remain synthetic and consumed demonstrations, not new accuracy trials.

## Generate and register the selected pack

Follow the [operator recipe](../operator/README.md) for the pinned optional upstreams and local OO binary. The following steps do not need a model gateway or auto-ontology service. Run from the repository root, choose an absent output directory, and select one pack; repeat registration for the other packs when needed.

```bash
uv run --locked python examples/factory_lab/extensions/domain-packs/generate.py \
  --output _workspace/my-domain-workflows
FACTORY_PACK=manufacturing-small
uv run --locked python -m apps.factory_lab.database_sources_cli \
  --registry _workspace/my-workflow-databases register \
  "_workspace/my-domain-workflows/$FACTORY_PACK/source.sqlite" \
  --label "$FACTORY_PACK"
```

Set `FACTORY_PACK` to `commerce-small`, `manufacturing-small` or `organization-small`. Retain the actual registration output's `source_id` and `snapshot_sha256`. For manufacturing/organization, register `note-01.txt` from the generated pack's `documents/` directory against those exact values:

```bash
uv run --locked python -m apps.factory_lab.document_sources_cli \
  --database-registry _workspace/my-workflow-databases \
  --registry _workspace/my-workflow-documents register \
  "_workspace/my-domain-workflows/$FACTORY_PACK/documents/note-01.txt" \
  --source-id SOURCE_ID --snapshot-sha256 SNAPSHOT_SHA256 \
  --label "$FACTORY_PACK policy" --version v1
```

Replace the two uppercase placeholders with the returned values; they are not example IDs to submit. Commerce question 2 does not require a policy paragraph, so skip this document command for commerce. The [registration guide](../../../../docs/setup/factory-lab-registered-sources.md) covers additional text documents. Do not substitute its separately authored `registered-commerce` database for this pack.

Start the server with these registries and the actual local binary built by the operator recipe. Replace `/absolute/path/to/open-ontologies` with that binary; use an unused loopback port.

```bash
uv run --locked python -m apps.factory_lab.public_server \
  --port 9273 --data-dir _workspace/my-domain-workflow-server \
  --workspace-database-registry _workspace/my-workflow-databases \
  --workspace-document-registry _workspace/my-workflow-documents \
  --workspace-reasoner-binary /absolute/path/to/open-ontologies
```

Open `/workspace`, choose `등록된 원본 목록 보기`, select the registered pack and use `선택한 등록 원본으로 자료실 만들기`. Confirm the snapshot hash against registration. Start with a new workspace for each pack. No live model option is needed.

## Field and paragraph review

In `데이터 정리`, select `검토할 표`, search with `열 이름 검색`, and open the exact table/column card. Set `검토 상태` to `승인`, enter its meaning in `검토한 의미 · 승인 시 필수`, then use `이 필드의 검토 결정 저장`. Review all fields in the relevant row below. Keys identify records in this snapshot; identifiers do not establish real-world identity.

| Pack | Fields to review for question 2 | Meaning to preserve |
| --- | --- | --- |
| commerce-small | `order_items.line_id`, `order_items.order_id`, `order_items.quantity`, `orders.order_id`, `orders.status` | One item row is the aggregate grain; quantity is recorded integer units; `delivered` is recorded status, not independent delivery confirmation. |
| manufacturing-small | `bom.id`, `bom.product_id`, `bom.quantity`, `bom.valid_from`, `bom.valid_to`, `products.id`, `products.release_state` | One BOM row is the grain; quantity is the authored integer amount; dates bound inclusive applicability; released is recorded product state. |
| organization-small | `assignments.id`, `assignments.employee_id`, `assignments.project_id`, `assignments.valid_from`, `assignments.valid_to`, `employees.id`, `employees.active` | One assignment row is the grain; project/employee identifiers reference recorded entities; active status and assignment validity are separate conditions. |

For manufacturing and organization, open `원문 문단 검토`, select the registered `note-01.txt` and its paragraph beginning `Policy`. Read the actual paragraph and its displayed source hash. In `검토한 해석 · 적용 범위`, record inclusive `valid_from ≤ as_of ≤ valid_to`. For organization also state that employee active status is checked separately and the result counts distinct employees. Save with `이 원문과 해석의 검토 저장`. This supplies a durable paragraph review, not an automatic policy interpretation or expert approval.

## Relation approval and query entry

Under `선언된 외래키 검토`, open the relation for the selected recipe. Both endpoint fields must already be approved. Use the suggested relation name below in `관계 식별 이름 · 영문자로 시작`, explain the child→parent meaning in `관계의 의미와 적용 범위`, and select `관계 제안 저장`.

| Pack | Declared relation | Suggested relation name | Child alias → parent alias |
| --- | --- | --- | --- |
| commerce-small | `order_items.order_id → orders.order_id` | `item_order` | `order_items → orders` |
| manufacturing-small | `bom.product_id → products.id` | `bom_product` | `bom → products` |
| organization-small | `assignments.employee_id → employees.id` | `assignment_employee` | `assignments → employees` |

For example, describe the relationship as “Recorded declared foreign key; LEFT many-to-one join preserves child row grain; unmatched parent values are NULL.” Open the saved proposal, check both endpoints and source binding, write a review note, check `저장된 원본·조건·한계를 확인하고 이 정의를 승인합니다`, then select `이 저장된 정의 승인`. Use this saved approval, not the pending proposal, in the query.

Open `원본 조회` → `질의 정의 작성` and choose `행 조회 · 비교 · 집계`. Use a new query name such as `manufacturing_small_2` in `질의 식별 이름 · 영문자/숫자/밑줄`. Copy the selected question from its `runtime-questions.json` into `제목` and `질문의 범위`, then explain its bounded recorded-data meaning. Set `결과 의미` to `기록된 사실`; leave `중복 출력 제거 DISTINCT` unchecked. Use the exact table names below as aliases throughout this recipe. The detailed commerce walkthrough uses shorter aliases instead; do not mix the two alias conventions.

| Query setting | commerce-small-2 | manufacturing-small-2 | organization-small-2 |
| --- | --- | --- | --- |
| `기준 행의 승인 필드` | `order_items.line_id` | `bom.id` | `assignments.id` |
| `기준 표 별칭` | `order_items` | `bom` | `assignments` |
| `매개변수 추가`: name / type / later execution value | `status` / `text` / `delivered` | `state` / `text` / `released`; `as_of` / `date` / `2026-11-19` | `active` / `integer` / `1`; `as_of` / `date` / `2026-11-19` |
| `출력 열 추가`: field → output name | `orders.order_id → order_id` | `products.id → product_id` | `assignments.project_id → project_id` |
| `그룹 키 추가`: field | `orders.order_id` | `products.id` | `assignments.project_id` |
| `집계 추가`: method / field / output name | `sum` / `order_items.quantity` / `total_quantity` | `sum` / `bom.quantity` / `total_units` | `count_distinct` / `employees.id` / `active_employee_count` |

For each field reference set `표 별칭` to the table name shown before the dot. In `관계 연결 추가`, open `저장된 관계 승인 선택` → `저장 목록 불러오기`, find the approved relationship above and use `이 저장본 열기`. Set `이미 연결된 자식 별칭` and `새 부모 별칭` to the table aliases in the relation table.

Add each condition with `필터 추가`. Select its approved field and table alias, comparison, and parameter name; all conditions are ANDed.

| Pack | Field | `비교` | Parameter |
| --- | --- | --- | --- |
| commerce-small | `orders.status` | `같음` (`eq`) | `status` |
| manufacturing-small | `products.release_state` | `같음` (`eq`) | `state` |
| manufacturing-small | `bom.valid_from` | `이하` (`lte`) | `as_of` |
| manufacturing-small | `bom.valid_to` | `이상` (`gte`) | `as_of` |
| organization-small | `employees.active` | `같음` (`eq`) | `active` |
| organization-small | `assignments.valid_from` | `이하` (`lte`) | `as_of` |
| organization-small | `assignments.valid_to` | `이상` (`gte`) | `as_of` |

For manufacturing/organization, in `검토한 정책 문단` load the saved paragraph list and open the review created above. Confirm that its original text and interpretation appear as a selected reference. Do not type a guessed review ID.

In `한계 · 한 줄에 하나`, preserve the selected question's `limitations` from `query-config.json`. Add “Authored synthetic snapshot; recorded quantities/counts do not establish external truth.” Commerce quantity totals do not determine return eligibility. Manufacturing sums authored BOM quantities; it does not predict physical requirements. Organization counts distinct employees, not assignment rows. NULL aggregate inputs are excluded and empty groups are absent; zero-member projects are not synthesized as zero. Do not add scalar bindings or additional output columns for these recipes.

Choose `정의 검증 후 제안 저장`. Inspect the saved source, fields, relationship approval, paragraph reference and parameters. Add the review note and confirmation, then choose `이 저장된 정의 승인`. Under `승인된 정의 실행`, supply the values from the table and select `승인된 질의 실행`. Values belong to execution, not the parameter-definition form. Open `결과와 근거 열기` to inspect the saved result, returned/total output counts, completeness, source and approval lineage. Retain failures; do not turn a failed query into an empty result.

## Saved-output RDFS and advisory reuse

Only continue from a completed, complete, nontruncated saved relational result. In that answer, open `저장된 질의 결과에서 추론 · 별도 참고 근거` → `투영과 RDFS 온톨로지 작성`. Each RDF subject denotes one saved output observation, not the underlying order, product or project. Use `출력 열 매핑 추가` for the second output column.

Use the prefix `urn:factory-lab:semantics:` for every class and predicate name in this table:

| Pack | `관측 행 클래스 IRI` suffix | Output → predicate suffix / declared datatype | Before superclass → added after superclass |
| --- | --- | --- | --- |
| commerce-small | `RecordedDeliveredQuantity` | `order_id → recordedOrderId` / `문자열` (`text`); `total_quantity → recordedQuantity` / `정확한 signed64 정수` (`integer`) | `RecordedQuantity → ReviewEvidence` |
| manufacturing-small | `RecordedBomQuantity` | `product_id → recordedProductId` / `integer`; `total_units → recordedBomUnits` / `integer` | `SnapshotObservation → ReviewEvidence` |
| organization-small | `RecordedProjectStaffingCount` | `project_id → recordedProjectId` / `integer`; `active_employee_count → recordedActiveEmployeeCount` / `integer` | `SnapshotObservation → ReviewEvidence` |

In `이 투영의 해석`, write “Each subject denotes one saved grouped query output observation, not a real-world entity or certification.” In `해석의 한계 · 한 줄에 하나`, state that the source and semantics are authored, only this saved result is projected, and classification does not establish delivery, physical requirements, workforce adequacy or approval authority.

For commerce, the before ontology is:

```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:factory-lab:semantics:RecordedDeliveredQuantity> rdfs:subClassOf <urn:factory-lab:semantics:RecordedQuantity> .
```

For manufacturing replace the two class names with `RecordedBomQuantity` and `SnapshotObservation`; for organization use `RecordedProjectStaffingCount` and `SnapshotObservation`. Enter the complete ontology in `검토할 RDFS 온톨로지 · UTF-8 최대 16 KiB` and select `투영·온톨로지 계획 저장`. Review the saved inputs, fill `계획 승인 검토 메모`, check the explicit plan confirmation and select `이 추론 계획만 승인`, then `승인한 입력으로 OO 추론 실행`. See the [detailed reasoning walkthrough](../../../../docs/setup/factory-lab-extension-walkthrough.md). Inspect input/ontology/binary hashes, actual output and retained errors. Do not substitute expected triples for actual native results.

Create a new plan from the **same saved query answer**, retain its before ontology, and append the appropriate superclass statement for the after version. For commerce append:

```turtle
<urn:factory-lab:semantics:RecordedQuantity> rdfs:subClassOf <urn:factory-lab:semantics:ReviewEvidence> .
```

For manufacturing/organization append `SnapshotObservation rdfs:subClassOf ReviewEvidence` using the same complete IRIs. Review, approve and execute separately. This new simple superclass extension is a runnable authored recipe; it is not the exact manufacturing/organization ontology used in the earlier recorded 13→39 and 20→61 diagnostics, and those counts must not be reused as its expected outputs.

In each successful result, open `참고로 저장할 행 분류 선택 · N개`, select actual eligible saved statements, explain their interpretation, and use `선택한 도출문을 참고 기록으로 저장` after the confirmation. Use `저장한 참고 문장 원문 불러오기`, `원래 질의 답 열기` and `이 답의 추론·참고 기록 불러오기` to inspect the linked records. Derivations are separate advice; they do not update the query answer, recompute aggregates, certify truth or fill missing evidence. Preserve before/after plans and compare actual derived sets, including any ontology-level statements separately from row classifications.

## Configuration and optional binder use

`query-config.json` is an authored recipe, not a UI import format. `parameters` pairs contain a type and an execution value; `joins` contain field names; `projection` and `aggregates` specify output names. The tables above translate only question 2 into manual controls. Other questions retain their own policy and evidence requirements.

[`bind_config.py`](bind_config.py) offers the pure Python function `bind(config, runtime_questions, draft, policy_review_operation_id=...)` for operator integrations. It returns `spec`, `relation_specs`, `parameters` and `origin`; it does not save, approve or execute them. It processes **all** questions, so a full call needs every referenced field already reviewed and the required actual policy review—even when question 2 alone does not need policy. No invented field IDs, approval IDs or edited approval flags are valid inputs.

An integration must obtain the current saved draft from the normal workspace API, pass the real completed paragraph-review operation ID, and retain returned source/question provenance. `relation_specs` are proposals: submit each through `database_relation_propose`, review and approve it with `database_relation_approve`, then pass the actual returned approval operation IDs as `relation_operation_ids` to `database_query_propose`. Review/approve that proposal with `database_query_approve` before `database_query_execute`. The UI above performs these actions and attaches the actual IDs. A binder's relation identifier is a logical name, not an approval-operation ID. Do not paste a binder `spec` into an unrelated upload panel or bypass review with a database edit. See the [query service source](../../../../apps/factory_lab/workspace_query_service.py) for current structured action inputs.

## Optional generated proposal and preservation

The [operator recipe](../operator/README.md) explains actual native export and the UI import boundary. Importing `native-export.yaml` creates a pending proposal; catalog output supplies physical metadata, while semantic mode separately needs an authorized model gateway. These manual workflows do not authorize a paid launch. Do not attach a saved semantic export from another source merely because its column names look similar.

The commerce generated-result adoption evidence is separate from these authored recipes. To reuse a source-matched native file, open `외부 온톨로지 제안 가져오기 · 선택 기능`, import its original YAML, inspect semantic/physical/relation candidates and review actual source bindings. Field approval can change the workspace revision; follow the UI's fresh-import requirement before proposing an external relationship. Preserve original and revised imports. Use the ordinary saved relationship/query lifecycle above after reviewing the candidate. The [extension guide](../../../../docs/setup/factory-lab-upstream-extensions.md) and [receipt association/backup commands](../operator/README.md#local-invocation-linkage-and-complete-workspace-recovery) distinguish import, local receipt association and approval.

Keep source snapshots, documents, original exports, pending proposals, approvals, executed queries, reasoning receipts and failures. A restored saved result is replay evidence, not a new native/model run. The [license/provenance section](README.md#license-and-provenance) includes the unresolved separate redistribution grant for the inherited commerce-small fixture; it is not silently relicensed by this recipe.
