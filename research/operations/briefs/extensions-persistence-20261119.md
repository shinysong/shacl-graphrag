# Trusted operator persistence and upstream receipt linkage
Review bounded local operator backup/restore and receipt association, separately from browser draft import. Preserve all operation IDs/results/failures and original approval lineage; never promote imported untrusted draft approval. Backup must capture coherent SQLite state and referenced immutable source/document objects, refuse in-flight work, restore only into a new destination, verify pinned manifest/content hashes, preserve mutable source paths as provenance without depending on their existence. No secrets, model credentials or provider configuration in bundle. Check bounds, traversal/symlink behavior, partial failure, active SQLite snapshots and disabled-provider replay. Associations must preserve original import result, match actual export/source/schema/pinned upstream stages, be locally attributed and never claim authenticated upstream producer or human semantic approval. Idempotent replay must not need external producer files. Inspect implementation notes and code; report unverified omitted paths rather than assuming execution.
UI renders association separately with local linkage versus approval/authentication distinction, original import link and raw saved record; no automatic retry for this operator action. Browser check remains pending. Only after both independent reviews ready run registered workspace-extension-pytest and research-ops-tests. No paid/model/AWS/browser invocation in this gate. These software tests are not upstream semantic execution or a business benchmark. Actual recovery acceptance over saved native/query results remains a subsequent bounded check. Do not inspect other reviewers or secrets/gold.
- apps/factory_lab/workspace_backup.py SHA256 089f9183e86c5490b99dd183b669df19902cf70541ff69de0588f99b151ff10a
- apps/factory_lab/workspace_backup_cli.py SHA256 a1293e5090b11a65a5d7946702f873c14c7143f66d94ac1a1ea49de351799893
- apps/factory_lab/workspace_extension_receipt.py SHA256 1d812dbc5b7d7444f28c07948f35923d16d620533345de58503ec44812467e25
- apps/factory_lab/workspace_extension_receipt_cli.py SHA256 4cafa778c401452c7b709f4ef4955bfbd8cd21846520e8062593f01ebe20beca
- apps/factory_lab/workspace_store.py SHA256 dd6b38a877905e69134572a8e6da2ff0afa3d3c9119b2a7b5deeb5bf518d1f3c
- apps/factory_lab/workspace_database.py SHA256 54e03ad7fd2307db43bb39fc32ac52f11a1aa3cb8307227444903e7ea0f50535
- apps/factory_lab/workspace_source_documents.py SHA256 e7c6dbc9eb4b11a80da6a5a821e61c5bf9659cb430bb72900b67eac4bb424752
- apps/factory_lab/workspace_extensions.py SHA256 925592a02ea427ed7298e224f35f6ec690f7f462614164275341e637c1c872ec
- apps/factory_lab/public_static/workspace.js SHA256 4f16eebca294042ce31b94aea933892357d5ded25cf7331aea3d0bb3a51fc8ac
- tests/test_workspace_backup.py SHA256 0caf46875f876b5ff715563a5d6cf89ce526ce62261500a0ecf76565c9b190ad
- tests/test_workspace_extension_receipt.py SHA256 91c3df832323801cb70a5c8ca1ecb5e4cc6fadf1df7ff21dbad005d3b646ef43
- scripts/research_ops.py SHA256 539db63458a29df1db32a8e154b45bd1216d6ac25d77ac370b36b68bfb854310
- tests/test_research_ops.py SHA256 1180089bf12a100d9990b37daff966af1e41e04afdac98d467f9551b13af44eb
