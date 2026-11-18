# Persistent workspace and scoped stock review

Review actual listed source, read-only; never read other review outputs, secrets, held-out gold or historical raw model answers. No paid calls/AWS/push/services. Write only own output. Registered software checks are not benchmark or real-provider evidence.

Architecture: SQLite immutable source versions and operation records; pending/running/terminal checkpoint states, same-key replay and no automatic retries. Source hashes, original CSV logical/physical locations, approval history, human interpretations and model-selected parameters retained. Optional gateway is separately enabled and metered; coordinator tests use scripted responses only. The free-question path selects max4 fixed tools, executes actual source/engine code, then makes one answer call. Structural plan/citation validation is not semantic correctness. Full evidence is saved; 38000-byte model-input guard fails explicitly without truncating evidence. Existing projection omits duplicate graph serialization for full commerce results only.

Full replacement_proposal uses all approved fixed commerce fields and policy agreement/readiness, fixed RDF/SHACL/Python/OWL engines, KRW-only decision semantics. Do not relax that guard. Raw source_lookup and source_rows remain partial-approval, raw observation paths. Human annotations are untrusted context, not facts or executable policy. Fixed relations are not automatically compiled from reviewed relation suggestions. External ontology projects were source-inspected only. Manufacturing and historical research paths must remain unchanged.

Current scope: workspace_stock.py reads only uniquely approved skus.id and skus.available in one CSV. It preserves matching rows and physical locators; absent/duplicate/blank/unsupported quantities return unknown without validation. No sum or cross-file/warehouse join. Requested quantity is model-interpreted positive integer 1..1e9; source is canonical nonnegative integer <=1e9. Actual SHACL minInclusive and Python >= compare identical parsed quantity. No freshness/reservation/substitution/discount/shipping/order-approval inference. Non-KRW is allowed because no currency calculation occurs. Question catalog advertises stock_check only if mappings qualify; execution rechecks restored draft. Full replacement guard remains intact. Evidence UI distinguishes recorded quantity result, input origin and unchecked scope.

Observed coordinator development tests: stock and question subset9tests passed, actual stored comparison and scripted two-call answer; full replacement remains failed on missing prerequisites, restart/replay unchanged, revocation removes capability. This is not real-model selection or answer-quality evaluation. Browser attempt1/2 did not accept confirm dialog and therefore executed nothing; failure artifacts retained; corrected driver pending. Registered checks for current job have not run.

Known limitations: stock result contains whole identifier catalog and Turtle, so answer input may hit existing explicit context guard; no measured capacity. Numeric/cross-file/ambiguous-mapping boundaries beyond test coverage are unverified. Progress UI lacks interrupted label and polling decodes whole result. Wider nonstandard generation quality, composite identifiers and policy composition remain incomplete. Neither product completeness nor general SHACL advantage is claimed.

Review approval boundary, requested-vs-source quantity semantics, missing/duplicate outcomes, validation parity, dispatch, UI and durable history. Preserve blocker findings.

- apps/factory_lab/policy_dates.py: 0fe495d2ffd41299793a6caf52a8dbae5543a26f5a8918911925645ef06b1fb4
- apps/factory_lab/policy_inputs.py: 53f52b29d2b526ba6bfd24271d10d5b7742e600208a5587a964ff19dd5796bcf
- apps/factory_lab/preparation.py: 5e1e9f9e69281935777af96554c4c5f64885673ab241020ef652173a40fa8f83
- apps/factory_lab/preparation_advisory.py: f3da43813bab3c3a3bf50a2a003f3c19797721fc08f401ac2325afe4498a1731
- apps/factory_lab/preparation_factory.py: 758584a7054a41ac93f38d60e6c958770b165400188a0e1ea015cd4ad9614964
- apps/factory_lab/preparation_model.py: 13ca112797edc51df4305f838dc5b1d7c68dba978b09ac784ad6414474db9667
- apps/factory_lab/preparation_service.py: 97b60d766fbadb00cb7d089e714e0c54776e574785754dd43f74e985c25e2383
- apps/factory_lab/preparation_sources.py: ebf0d5b4816103a2a1302b2cfaed8db9479731bdfa99d7635bbf085b4f7ef484
- apps/factory_lab/public_runtime.py: f27d04d4bb8f173f5e5dea6c9db6aad60473c4adc4c697e1907715e3e3205f91
- apps/factory_lab/public_server.py: fcad56356a715972a30a9a1f7a4ac6d1cd08799f4b8ffba14d8c01a82398959f
- apps/factory_lab/public_static/workspace.css: f6d4c6f66405616b8274b929a22267748068edffb082aef114fe8b94e6c99c18
- apps/factory_lab/public_static/workspace.html: 2893bbd4282fd9581c8bb632d6668f768681f0aa37643a8c857aa4a88324cdb4
- apps/factory_lab/public_static/workspace.js: 6a93d120cdd4dfa7d4a396f236f8659a25c5f02749860064859a1f04ab1f605d
- apps/factory_lab/workspace_diff.py: 847161a1f6482b560898cdf8139cbd09337e61bc509945055b33b4f2f09ca8db
- apps/factory_lab/workspace_lookup.py: 5c9f5eccfc7475cf017c446855f27470d35b231cb33275f66496d175ad11bcdb
- apps/factory_lab/workspace_policy.py: 22fff3e10dc569e0d0f71577aebeae06dad524a6cf7db438a076700cb7ee779e
- apps/factory_lab/workspace_question.py: 3de9beef7687d1769fb2990016813622c7a89a9b3f9b557748b6b39d4b92b270
- apps/factory_lab/workspace_service.py: f03438e04892cf1896625afcd83b9551157de79566ed66cfa0fb9d0e48c90bed
- apps/factory_lab/workspace_store.py: 4b8b365e1aa4c8cd70477b49cbaeb7abded79bb43f4224be6a484062252030fb
- docs/setup/workspace.md: 1c05b7573bcc98a50ad14d20b4b3ee849e3ad9a571a263f487ab1aa96133330d
- scripts/research_ops.py: 473d9290a228dcb3dd391e1e51d240c9cf2086c5244af386053ce64a01da4f64
- tests/test_policy_inputs.py: edcc7a4af8122df2cb490e8f8214c830b58377a15c7abb7f584a0e64d2bf7d53
- tests/test_preparation.py: 8be1382e168c36b78a6948bc0621312fe86d6f35d4824755515ca400bc026e06
- tests/test_preparation_advisory.py: 864a6ac3722aa14325ab47da4cf1bad3ed75ca3827e8a6c02662e71e8f644a50
- tests/test_preparation_history.py: 696c597de70dea25f1c0781ae5b48dee1789e205e369bd99860615f756d44c03
- tests/test_preparation_http.py: 9f54dedd620abfada98fa79dab28ed2ffe874855620b8c21e70dc91a377c4f80
- tests/test_preparation_model.py: a5553894071238dd8cc3df78671cf22926e2b670102d810e20bfe88cfa0cb674
- tests/test_preparation_restore.py: b3b503d504018c77d4bcb6d19908b78085a30c4e2aec8b53e414baa974de23c9
- tests/test_preparation_sources.py: 1edd99694b2465956699b15ab6246c6b1e3e84ce0a3da0ef292f7f7c97a1c859
- tests/test_workspace_buffer.py: e15dd7a7782cca5410583df7af4fdef0c8b442c368cef03d8b915b3133f1fd8b
- tests/test_workspace_currency.py: cf045c1514612a15747a1b3c4beff9d934612c58f0264b21d39c2ec0e34f55f3
- tests/test_workspace_dates.py: 7694835dca738a3be03fddde7df2c1b751307e9a99a0b67ade388ca9ecbb8afa
- tests/test_workspace_diff.py: 09cdfdbaaae21cd523e277c727ea6b7c124d2a2afd72ee9791d17a0490ce0c5b
- tests/test_workspace_generation.py: cae6724b18c0f4ec4b541bea5f972e61273f6ba4dcebd64edfc33db6bd7d20f0
- tests/test_workspace_http.py: b09ee4ac435f33765f9c4750dc1371df233b14d4411a73158b4b086b55950e11
- tests/test_workspace_lookup.py: d6f83aa715604786319a6e9e3ee6eb2a215bd102a62d2bca0b56ba6c36e8fae7
- tests/test_workspace_policy.py: 12c0fbc65943c7856a2ffbadba272ba3155261b4354ac023481c3987e6d021f6
- tests/test_workspace_question.py: dcf868d866d021868802b077468ba4660fd60728226f3eddaa62e7e8180c556d
- tests/test_workspace_service.py: 25782e158a85253d0de05ecf03ee8624a57caf36015d497f25e86453aa86cfca
- tests/test_workspace_store.py: 10b769c57b678d1da6d28ee2f379af01b07b3e658f59fdb6e118f6ba7b92b339
- tests/test_workspace_withdraw.py: 775cc008db9f73f038039fd6fa45ddf0aa53a6db63a3d1e90ead774ae00a0126
- apps/factory_lab/policy_agreement.py: 04de2111f061499e35848c20bab45c43ba619393ad341d6e6274c8baa2e24aa2
- tests/test_workspace_policy_agreement.py: f2c09a10f1144d2f538956787019e05b8bae29cfaecda40e6577185843ca1e23
- tests/workspace_fixtures.py: e184f517500ac3b2bb6cb28ba5fdce8cc1cc3ea3d7912891ee2b8d44c022c8ff
- tests/test_workspace_rows.py: 2ed847f65c01fe42a114da15cc7cd6313221768ebf1a974ed0e48bcfdf71777e
- tests/test_workspace_context_limit.py: ee4b1ea181137b8fb43488cb66c2435e278dc15db0a95cf35234c77d4b8f56cb
- tests/test_workspace_field_meaning.py: f64fa84a5609cfee77d77f707f2433fe0a3310d8802213d975ee40fed7985fd0
- tests/test_workspace_progress.py: 8df623970383ae9a4a106476f1a5e5668387a1293f22fb63e142f40430222f40
- apps/factory_lab/workspace_stock.py: baaeec5c63aed7c0c68cb8375b1871af80e72460388ea435c0bb6c9a711bde9c
- tests/test_workspace_stock.py: 722b145e682e2bffdb2908e66814f7897f254bb816dac469e4fa99971885f52a

Current review focus: question-first UI refactor only. renderQuestions now question form -> always-visible pending recovery -> operation history -> optional native details panels for direct lookup/proposal and saved templates. Direct panel defaults open when model disabled, closed when enabled; template panel collapsed. Per-workspace in-memory toggle preference survives render, not reload. Existing execution handlers/guards unchanged; model question results and failed/past-version records are not inside collapsed tool panels. Review content reachability, recovery, offline direct-tool access, keyboard details, manufacturing preservation and state interactions. Browser development exercise pending; no paid/provider claim.

Latest focus is stock answer projection in workspace_question.answer_evidence. Full durable evidence unchanged. Only recorded_stock_check projection removes scope.identifiers and validation data_turtle/shapes_turtle/report_turtle; records, mapping interpretation, source hashes/locations, requested units, parsed comparison, validation booleans/scope, unknown reasons and unchecked scope remain. Every removed path recorded in answer_projection. Existing commerce projection unchanged; failed tools unchanged; no truncation or automatic retry. New authored120SKU/4request scripted test proves old unprojected same-packet serialized bytes >38000 while projected second-call messages <=38000; exact expected structure compared; full historical results and restart replay retained. Separate duplicate-unknown/nonmutation check. This is byte-bound software evidence, not token cost/latency/providerquality benchmark. Existing context guard still applies to selected evidence and planner catalog.
- tests/test_workspace_stock_projection.py: af46c19c1bb6580cd09ab487184788403d5f3bc381d1e9b81d2484d2127af62a


Current v20 review focus: explicit human source_only mapping target, requiring nonempty interpretation on approval (including restored history). This is raw-row lookup permission only, not adapter semantics. compile skips it; fixed identifier/stock/decision catalogs require exact existing targets and remain unchanged. UI offers raw-only choice. Review unknown columns, approval/restore/change-history, duplicate raw-only fields, model source_rows evidence and revocation; no live model quality claim. New test tests/test_workspace_source_only.py uses two unknown columns and scripted question/replay, preserving blank/repeated rows and unapproved private column exclusion. Registered checks not yet run.
- tests/test_workspace_source_only.py: bbdfaae7b526ac5459108ba6ed1a844708ee1d0c1c693ea6eb318f1407d53638
