# Version-scoped manufacturing model queries

Status: design, unexecuted. Source: unchanged frozen MachineTool projection snapshots, previously inspected development data. No fresh heldout, no new physical operating facts. Existing workbooks remain main field/evidence illustration; actual manufacturing schema releases add version context.

Question: can saved old/new definitions coexist and can each adapter answer the same explicitly version-bound query after both releases are loaded? This extends prior seven-node backend parity; it does not establish engine superiority, ontology necessity or maintenance labor benefit.

Representation: version locator = original XML SHA256. Defined-node key = (source hash, namespace URI, numeric NodeId). Snapshot metadata records ModelUri, Version, PublicationDate and any ModelVersion separately. All assertions retain source snapshot. Defined nodes and unresolved reference targets must be distinct; a mentioned target is not a locally defined node. No reverse-reference completion or semantic inheritance performed: reference queries ask only explicitly serialized source relations. Existing parser excludes values/descriptions and full imported models. URI-only or display-Version-only maps are diagnostic alternatives, not endorsed standard identity rules.

Planned queries for each of two releases: (1) browse label for i5025; (2) declared parent for i5025; (3) explicit outgoing stored reference facts for i5025; (4) definitions of targets referenced from i5025, returning defined-in-selected-file vs not-defined-in-selected-file, never global missing; (5) SignalColor alias resolved namespace URI/numeric ID; (6) required IA model metadata exactly as declared, no dependency compatibility judgment. Two versions × six questions = twelve fixed contracts per adapter. Version constraints explicit in every query. No natural-language parsing claim.

All adapters get identical projected facts and contracts. First Python direct lookup vs SQLite/RDFLib with independently serialized output checks; actual Neo4j/Neptune only after review, bounded operation receipts and owned stop guard. Current resources remain stopped. No new infrastructure or paid LLM calls.

Failure denominator: record every source input, planned adapter/question and invalid-input control; if a source fails, its dependent questions fail and independent questions remain eligible. Never silently repair source/answers from expected results. Posthoc scorer reads retained rawXML locators and source hashes to verify declared fields, does not feed answers into runtime. Existing results untouched.

Controls: same numericID under different namespaces; missing requested source hash; existing reference target with no definition in selected file; a valid wrong version request produces that version's answer and is scored as a question-interpretation error only when a separately declared question contract demands another version. Never let a checker infer intended version from gold. Distinguish declared source version, selected evidence version and external truth.

Scope limit: exact file hashes here are reproducibility anchors, not OPC UA RequiredModels minimum-version compatibility rules. No safety/control recommendations. No automatic veto/repair. Record actual outputs/checks and omissions before any claims.
