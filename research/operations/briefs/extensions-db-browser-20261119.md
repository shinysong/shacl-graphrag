# Actual DB question browser path with scripted provider
Review private browser_db_question.py and imported ready/Gateway helper. Read interface.md for disclosures. No source change since a19103 344tests. Fixture seeds source/approvals; two scripted model responses; actual SQLite and HTTP/browser1440/375. Verify answer/child lineage, disabled-provider replay/reload, source hashes, cleanup. No actual model/semantic upstream/accuracy claim. No paid calls, no environment secrets. Do not inspect other review folders. After ready run research-ops-tests then uv run --locked --with playwright python _workspace/extensions-20261119/browser_db_question.py --review-gate-passed.
_workspace/extensions-20261119/browser_db_question.py SHA256 c7bce9b5bb9f3705455b78ef12e5d02a3bcc10563bd08b1f8365e4eda4dbb695
tests/test_workspace_database_question_service.py SHA256 6b2f84b26201f4dfc94f89e05c50b24029c08ee4a8e408027f3df73b02867c37
apps/factory_lab/public_server.py SHA256 53c0b2e3ff932f01029276c1d88001c60ba54dd3f34f79485fe749f28a8c28a2
apps/factory_lab/workspace_database_question_service.py SHA256 8524b1e34c6ec3bd594ddb1099dcb926308f4fbc779a0f2e2d6df336e121ffe3
apps/factory_lab/workspace_database_question.py SHA256 b5393c013e48e7f393dfaec1a10de41d226efb176404c1e823316874f7db5589
apps/factory_lab/workspace_query_service.py SHA256 1043d7aa54744daab54d680481f795609b1f34cfe05b6a0bc8e415813a88f77a
apps/factory_lab/public_static/workspace.js SHA256 329aa7e1cff0bc6a5258e6c2cc800a00284d3ee754edf87e441e3dfafe0a9215
