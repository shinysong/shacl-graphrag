# Prospective dual-question protocol review

Read-only design review. No experiment/code execution. Two questions share explicitly authored schema-inspired records; preserved public schemas and upstream examples are distinct. Check ambiguity, temporal policy, graph completeness, denominators and comparator fairness. Identify blocking underspecification before fixture implementation. No other reviews/secrets/heldout. Full draft follows:

```json
{
  "id": "industrial-questions-1",
  "version": "draft-1",
  "status": "prospective_pending_independent_review",
  "scope": "Offline controlled schema-inspired authored study of two questions sharing records. Not actual enterprise data, legal eligibility, physical safety, full OWL, or measured human review time.",
  "sources": [
    "ERPNext e864addb6c367688d2b264f284c2dd9b9360a97d Item/PO Item/PR Item/QI/BOM/BOM Item schemas",
    "Schema.org Certification development snapshot acquired2026-10-21",
    "Original upstream BOM test fixtures remain separate unscored illustration; no inferred generated IDs"
  ],
  "origin_labels": [
    "public_schema",
    "upstream_authored_example",
    "study_authored_record",
    "study_authored_policy",
    "injected_fault",
    "candidate_mapping",
    "human_confirmed_mapping"
  ],
  "time": {
    "receipt_at": "2026-09-15",
    "as_of": "2026-10-21",
    "format": "ISO date only, no timezones in v1",
    "validity": "valid_from <= date < expires; expires date is excluded by authored policy, not inferred from schema standard"
  },
  "identity": {
    "key": "(record_type, id); repeated same key is ambiguous even if payload identical",
    "part": "(item_id,revision); no label matching or automatic sameAs",
    "facility": "exact facility ID",
    "linkage": "Explicit order_line_id, inspection_id, certificate_id on receipt. One matching record per typed key required; no fallback from names or item_id. Receipt/order/inspection part+revision and facility must match; certificate scope checked separately. Missing reference or zero matches = missing; >1=ambiguous; exactly1=resolved. Link status is independent of content equality."
  },
  "tables": {
    "receipt": [
      "id",
      "part",
      "revision",
      "facility",
      "order_line_id",
      "inspection_id",
      "certificate_id",
      "quantity",
      "uom",
      "received_at"
    ],
    "order_line": [
      "id",
      "part",
      "revision",
      "facility",
      "remaining_quantity",
      "uom"
    ],
    "inspection": [
      "id",
      "receipt_id",
      "part",
      "revision",
      "facility",
      "status"
    ],
    "certificate": [
      "id",
      "part",
      "revision",
      "facility",
      "valid_from",
      "expires",
      "status"
    ],
    "component_edge": [
      "id",
      "component_item",
      "component_revision",
      "parent_item",
      "parent_revision",
      "active"
    ],
    "product": [
      "id",
      "revision",
      "facility",
      "requires_current_certificate"
    ],
    "coverage": [
      "table",
      "complete"
    ]
  },
  "receipt_policy": {
    "checks": [
      "exact part/revision/facility equality across receipt/order/inspection",
      "inspection.receipt_id equals receipt.id",
      "quantity finite and >0 and <= order.remaining_quantity; both units exactly Nos; different units -> unknown, never convert",
      "inspection.status exactly Accepted; Rejected -> violation; other/missing -> unknown",
      "certificate matches receipt part/revision/facility and status Active, and is valid at received_at"
    ],
    "certificate_status": "Active allowed; Inactive is violation; any other/missing unknown. Exact known mismatched scope is violation.",
    "aggregation": "Resolve all3links first. Missing/ambiguous link -> unknown, do not inspect arbitrarily chosen row. With resolved links, definite violation takes precedence over other unknown checks, else unknown if any required value missing/invalid, else accept. Never treat invalid/missing numeric/date as violation.",
    "output": [
      "accept",
      "violation",
      "unknown",
      "error"
    ]
  },
  "impact_policy": {
    "target": "Question supplies target part+revision and certificate_id, not inferred from receipt acceptance. All cases use same target as receipt.",
    "candidate": "Non-reflexive positive reachability from target to product via active component->parent edges, exact revision, any positive path. Visited set prevents cycles; a cycle returning to target does not make target a product candidate. Do not infer reverse edges.",
    "edge_validity": "active must be boolean; malformed endpoint/revision/active marks graph incomplete and excludes that edge. Duplicate edge IDs exclude all rows under that ID and mark incomplete. Valid unrelated edges remain.",
    "candidate_outcome": "observed path -> yes. No path and complete edge coverage with no malformed/ambiguous edges -> no. Otherwise -> unknown. Product output universe is explicit four products; complete means only this supplied universe, not real world.",
    "recheck": "For candidate=yes, require exact certificate target-part/revision equality, certificate facility==product.facility, product.requires_current_certificate boolean. If requirement=false or known scope mismatch -> not_required. If requirement=true and scope matches and as_of >= expires -> required. If requirement=true and scope matches and valid_from <= as_of < expires and status Active -> not_required. Inactive with unexpired or not-yet-valid -> unknown in expiry-only v1; missing/invalid/conflicting certificate -> unknown. A current-expiry recheck never retroactively changes receipt acceptance.",
    "candidate_no": "recheck=not_required when candidate=no; candidate=unknown -> recheck=unknown, even if policy would otherwise exclude product.",
    "precedence": "For candidate=yes resolve question certificate uniquely first; missing/duplicate -> unknown. Then known requirement=false or known scope mismatch can yield not_required; otherwise missing requirement/scope/date -> unknown. Finite ISO dates required; expires<=valid_from -> unknown.",
    "outputs": [
      "candidate yes/no/unknown/error",
      "recheck required/not_required/unknown/error",
      "completeness complete/partial",
      "source row IDs supporting each positive path"
    ]
  },
  "comparators": [
    {
      "arm": "python_rules",
      "description": "Independent Python exact joins, numeric/date policy and graph closure."
    },
    {
      "arm": "rdf_owl_shacl",
      "description": "Same public runtime facts and authored policies. Explicit adapter exact-key checks and parsing; RDF active eligible edges; OWL-RL transitive relation for candidate reachability; SHACL constraints for receipt content. Shared adapter exclusions and final status aggregation disclosed, not attributed to OWL/SHACL. No external database."
    },
    {
      "arm": "asserted_only",
      "description": "Optional predeclared ablation direct component links only; same eligibility rules, no multihop closure; label ablation not full code baseline."
    }
  ],
  "cases": {
    "development": "12 predeclared scenario families x2 depths(1 and3) =24 scenes. Each has1receipt,4products,3explicit receipt links. Product roles: reachable+required-policy, reachable+exempt-policy, unrelated, reachable+other-facility. Use opaque IDs unrelated to scenario labels. Depth applies target->first two reachable products; third reachable other-facility may branch at final node.",
    "families": [
      "complete_expired_now_valid_at_receipt",
      "unexpired_now",
      "expires_exactly_as_of",
      "expired_before_receipt",
      "rejected_inspection",
      "over_remaining_quantity",
      "missing_inspection_source",
      "ambiguous_order_line",
      "missing_certificate_expiry",
      "component_edge_missing_source",
      "component_edge_omitted_projection",
      "certificate_wrong_revision"
    ],
    "missing_source": "Delete required record/edge in authored source before projection; coverage false for affected table. Scorer retains design lineage separately, runtime never receives deleted fact or expected answer.",
    "retrieval_omission": "Preserve original source edge but omit it from runtime projection, runtime coverage false. Do not give runtime an omission-type label. Treat source and projection omissions as separate scorer strata; indistinguishable runtime evidence may correctly give same unknown.",
    "reserved": "Do not yet generate or call any cohort heldout. Reserve future12scenes after development implementation is frozen; protocol+generator+scorer review required. Existing retail610 untouched."
  },
  "scoring": {
    "per_arm": "24 receipt outcomes;72 typed-link outcomes;96 product-candidate outcomes;96 product-recheck outcomes;24 completeness outcomes. Report separate denominators, not one accuracy.",
    "reference": "Separately authored expectation ledger based on frozen policy/source provenance, not importing runtime functions or model outputs. Freeze before executing arms. Unknown reference remains unknown; do not force binary truth.",
    "metrics": [
      "wrong accepts among reference violation/unknown",
      "unnecessary withholding among reference accept",
      "wrong required and missed required rechecks",
      "candidate false positive/negative only on reference-known cases with explicit universe",
      "coverage/unknown/error counts over all cases",
      "unsafe complete claims on partial source or projection",
      "source-vs-projection omission strata"
    ],
    "external_truth": "Injected controlled full-source topology can support separately labeled synthetic full-source reachability. Evidence-sufficient policy agreement is primary; do not conflate omission abstention with external factual error.",
    "runtime_scorer_boundary": "Runtime receives facts, declared coverage, question, policy only. Exclude case family, origin fault labels and expectation ledger. Save outputs before offline scoring. Never repair from scorer. Keep construction/execution failures in denominator."
  },
  "limits": {
    "max_scenes_this_stage": 24,
    "max_records_per_scene": 100,
    "paid_calls": 0,
    "new_services": 0,
    "push": false,
    "scope": "No performance superiority claim from descriptive timing; one authored design and controlled strata not prevalence sample. Human labor and maintenance unmeasured."
  },
  "next": "Independent design reviews now; exact fixtures/expectations and implementation each require fresh review before checks/execution."
}
```
