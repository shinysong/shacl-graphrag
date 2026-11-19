# Commerce line-item sources

These fictional CSVs and the Korean reference document are original project examples under the root Apache-2.0 license. Upload **only** `orders.csv`, `catalog.csv`, and `policy.md`; README and manifest are not source inputs.

Start the single-user workspace as described in [the workspace guide](../../../../docs/setup/workspace.md). Plain startup enables local preparation and direct lookups. Real model proposals and questions require the separate opt-in flags and your own configured shared budget.

For a raw-evidence walkthrough, review each of the six CSV columns as `source_only` and write its meaning. `purchase_ref` is a purchase reference that may repeat across line items; `sku` references the catalog SKU; `stage` is a recorded state, not delivery proof. Catalog `label` and `family` are recorded name and category. Review both policy paragraphs as `context` (reference text), not executable refund approval rules. These are operator decisions, not automatic facts.

If reviewing a relationship, the described endpoint pair is `orders.csv.sku` to `catalog.csv.sku`. Verify the source explanation before approval. A model proposal may require different or corrected targets; applying a proposal leaves it pending. Do not approve a candidate merely because values match.

Suggested question: `구매 참조 O-211에 기록된 상품의 이름과 분류, 배송 상태를 확인하고 환불을 승인할 수 있는지도 알려줘.`

One bounded live-model walkthrough used a purchase-reference row lookup, passed its single recorded SKU to a second raw lookup, and read the refund reference paragraph. The result reported recorded product/state information and left refund approval unresolved. It did not execute a refund rule, SHACL, OWL, reservation, payment, or order change. Human preparation was part of that walkthrough; it is not an automatic-mapping accuracy benchmark or an expected plan enforced at runtime.

`O-210` has multiple line items and distinct SKUs. Its presence illustrates the input structure; it is not a claim that automatic fan-out traversal or every multi-item question is supported. Current value binding requires one distinct nonblank value across all rows returned by an earlier lookup. Read the guide for input limits, review/version semantics and unsupported operations.
