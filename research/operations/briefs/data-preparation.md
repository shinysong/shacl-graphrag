# Bounded data preparation review

Review current apps/factory_lab/preparation*.py, public_server.py, public_static/prepare.{html,js,css}, index link, tests/test_preparation*.py, scripts/research_ops.py registration and test allowlist, examples/data_preparation/*, docs/setup/data-preparation.md and research/data-preparation-1/external-inspection-001.json. Relevant existing commerce.py, explanation.py and factory fixed tools may be read. Do not inspect other reviewers, secrets, raw paid responses or evaluator gold. Write only your own assigned JSON result. No code edits or network.

Objective: multiple CSV + UTF8 policy TXT/MD -> inspect source/provenance -> editable candidate field/relationship/policy decisions -> approve/version/save/reload -> existing factory/commerce local engine execution. Local exact-name and keyword/span generator, NOT LLM, no general NL-to-ontology or efficacy claim. External Open Ontologies/NVIDIA sources inspected and pinned, NOT installed/connected; generator interface separates proposals from approvals. Strict bounded source parser; physical lines vs logical records; null only explicitly nullable fields. Fixed existing adapter policy semantics. Policy clauses matched only as candidates; explicit human interpretation required. Unsupported after-discount/exception/futuredate clauses refused by limited lexical checks; not universal semantic validator. Context and excluded decisions retained. All entries must resolve before execution; no silent unknown execution. Factory oneCSV per table, typed edges/refs; existing queries namespace factory-v3 disclosed as not historical source identity. Commerce shared computed-feature Python/SHACL; factory existing selected-evidence checks; separate authored OWL class illustration.

Data review sessions memory max4; source refresh conservatively resets all decisions, retains previous/retired entries. Approved bundle includes original text/hashes/decisions/materialized data; restore reconstructs/replays then verifies data; digest not signature. Token/Host/Origin/shared execution lock preserved, no source/paid/cloud mutations. User file content rendered textContent. UI decisions/download/import/execute both domains exercised at1440light390dark; no external requests, no overflow, paid0. Targeted development tests passed, not yet registered reviewer-gated checks. Initial regex/harness errors preserved privately. Existing legacy9260 untouched, tempservers stopped. Need scrutinize actual unsupported policies, approval/provenance semantics, mapping safety, UI stale states, malformed input and restoration correctness. Identify genuine remaining blockers rather than assuming requirement success.

Final doc prose humanize may change expression only after review; implementation changes require new review job. Historical research outputs must remain unchanged.

Revision: prior independent review remains needs_revision. Added flat bounded history with source hashes and identity-aware relation matching; history restored without replaying old approvals. Added BOM-preserving browser decoding, stale result invalidation, list/get session recovery, bounded expected validation errors. Relation256/1MB, paragraphs256/document, entries1024, history4096/2MiB, draft16MiB limits. Current development tests/browser passed before final history identity adjustment; final tests and browser still pending. Scrutinize these changes independently.

Frozen source files:
- apps/factory_lab/preparation.py: b28f6ba85145c1a01bd9959551907c462bf8439bd599794ab156e4a2291969c6
- apps/factory_lab/preparation_factory.py: 758584a7054a41ac93f38d60e6c958770b165400188a0e1ea015cd4ad9614964
- apps/factory_lab/preparation_service.py: 97b60d766fbadb00cb7d089e714e0c54776e574785754dd43f74e985c25e2383
- apps/factory_lab/preparation_sources.py: af5938678b68d2fd55893e5d65f161b78bae41a28dd822ddafe58c6f6af5fc23
- apps/factory_lab/public_server.py: fc39c6032a640898a2036b7c54a3ad53f4d4b9f72b5aee02bfab14728f248376
- apps/factory_lab/public_static/prepare.css: f0f8fb1fbf5fb6b953517ce49a57c2045c83cc3c4ca3c61fee04afb56f185abd
- apps/factory_lab/public_static/prepare.html: b71419f33f5d98f26779b985cfe18801d56dc461aac8bd46ea42bdaff1119a65
- apps/factory_lab/public_static/prepare.js: 9637d9e7cd05d04eea5efd55bd605f81ef89ea8df6cc9e0820fd834ff79ab361
- docs/setup/data-preparation.md: e7a9664424f70bdbec293b6cb2ce5b3a42f158d1016fdd2944239c69b3bd8375
- tests/test_preparation.py: 8be1382e168c36b78a6948bc0621312fe86d6f35d4824755515ca400bc026e06
- tests/test_preparation_history.py: 696c597de70dea25f1c0781ae5b48dee1789e205e369bd99860615f756d44c03
- tests/test_preparation_http.py: 9f54dedd620abfada98fa79dab28ed2ffe874855620b8c21e70dc91a377c4f80
- tests/test_preparation_sources.py: 1edd99694b2465956699b15ab6246c6b1e3e84ce0a3da0ef292f7f7c97a1c859

Final requirement audit addition: policy_hint now returns scope_candidates as verbatim sentences containing bounded domain nouns (Korean/English); absent cues return empty. These are unverified applicability candidates, not inferred bindings. One focused test passes. Prior job check output remains historical because this source addition occurred after its freeze; new job required.
