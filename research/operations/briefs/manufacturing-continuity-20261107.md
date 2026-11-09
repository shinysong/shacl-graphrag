# Manufacturing continuity and evidence trace design
User authorized8h 2026-11-07 15:12:55–23:12:55UTC; manufacturing central, SBOM auxiliary. Current paidledger162/180attempts,$2.721745950reported,$3.499338630nonrefunded,$15cap unchanged. No newpaidlaunch orDBstart requested bythisjob.
Problem: priorlivebackend success compared retrievedbindings, not complete questionanswers. Need make remaining semantic/computation responsibilities explicit, rather than claiming genericSHACLadvantage. Actualweldingsource consumeddevelopment328nodes486edges; prior7nodes4edges chosenforQ1–Q9. Prior4backends×10queries40slots36completed4unsupported(Q7), includesSQLite,RDFLiboffline,Neo4jlive,NeptuneSPARQLlive. Q3onlytwooperands,Q4onlycandidates,Q5rawrolesnotprose,Q6identitiesundersuppliedpolicy,Q8emptyselectedbundlebindingnotglobalabsence,Q9supportvaluesnotdraftdecision. Authoredhierarchy andcontrolledchangesseparate,notrealhistory. OriginalLLMcampaign47completedtriples46draft46self47report, notwholeanswertruth. RecentSBOMmetadata33/36vs36/36butstrongselfandSHACLreviewboth17/18.
Proposed bounded phase: trace all9 manufacturing questions to (a) raw source locations, (b) declaredpolicy/semantic role provenance, (c) actualsavedquery/bindings on4backends, (d) remaining deterministic calculation/applicability contract, (e) limits of final-answerclaims. Build new offline deterministic answer-adapter ONLY from savedquerybindings+samepublishedpolicy, separate direct-source independent posthoccheck. Never feed evaluatorreferences to adapter; keep oldtraces unchanged. Ninequestions×fourbackends includeunsupported/history, sourceabsence, unimplementednatural-languagejudgment. Do notturnQ7 intoinventedrealhistory, orQ8emptyresultintoexternalabsence. Addpositive/negative projectioncontrols with authoredmutations separate. No newcalls/DB needed for initialreplay; livefreshquerypath later onlyifmeaningful.
Primarydemo should walk manufacturingQ2/Q5/Q6/Q8/Q9 actualsources and remainingassumptions, linkSBOMsupportforentryabsence/changefeed. Offline replay clear labels. StrongsharedPython baseline; RDF/SHACL benefit cannotbeassertedfromsamepolicyagreement. Humanmaintenanceeffortstillunmeasured. No physicalprocess prescriptions.
Please critique whether proposed answeradapter comparison addsvalue or merelyhidesmanualcontract assumptions, identify essential controls and avoidable work. Implementationreview can assessarchitecture only; code notyetprovided, markunverified. No approvalofpaidcalls/liveDB implied.
Questionlist follows:
[
  {
    "id": "Q1",
    "name": "직접 값 조회",
    "question": "PP6 작업표 2행의 x_init [mm]는 얼마인가요? 해당 셀을 제시해주세요.",
    "evidence_basis": "retained_source",
    "source_ids": [
      "PP6:2"
    ],
    "target_ability": "one scalar and explicit locator",
    "checker_coverage": "existing atomic checker; question-to-field applicability unverified",
    "capabilities": [
      "explicit_lookup"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q2",
    "name": "관계·코드북 해석",
    "question": "PP6 작업표 2행의 defect 코드가 가리키는 결함 이름은 무엇인가요? 작업표와 코드북의 근거를 함께 제시해주세요.",
    "evidence_basis": "retained_source",
    "source_ids": [
      "PP6:2",
      "PP6:defect_code:4"
    ],
    "target_ability": "follow declared source relationship",
    "checker_coverage": "existing two-template lookup checker; manual policy",
    "capabilities": [
      "relation_lookup"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q3",
    "name": "복수 기록 비교",
    "question": "PP6 작업표 2행과 12행의 설정 번호와 코드북상 명목 Idc를 비교해주세요. 두 행의 명목 Idc 차이도 알려주세요.",
    "evidence_basis": "retained_source",
    "source_ids": [
      "PP6:2",
      "PP6:12",
      "PP6:welding_settings_code:1",
      "PP6:welding_settings_code:3"
    ],
    "target_ability": "two lookups and derived difference, not operating recommendation",
    "checker_coverage": "lookup components covered; arithmetic remains derived/unverified",
    "capabilities": [
      "relation_lookup",
      "arithmetic"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q4",
    "name": "조건 검색·범위 내 집계",
    "question": "대상을 PP6 작업표 2행과 12행으로 한정할 때, x_init [mm]가 100 이상 250 이하이면서 코드북상 결함 이름이 Porosity인 행과 그 개수를 알려주세요.",
    "evidence_basis": "retained_source",
    "source_ids": [
      "PP6:2",
      "PP6:12",
      "PP6:defect_code:4",
      "PP6:defect_code:1"
    ],
    "target_ability": "bounded filtering and enumeration, not entire dataset recall",
    "checker_coverage": "current checker does not certify enumeration or completeness",
    "capabilities": [
      "relation_lookup",
      "bounded_aggregation"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q5",
    "name": "단위·값의 의미 구분",
    "question": "PP6 작업표 2행의 x_init [mm]와 x_init [# sample]은 각각 무엇인가요? 코드북의 Idc를 이 행에서 실제 측정한 전류라고 설명할 근거도 있나요?",
    "evidence_basis": "retained_source",
    "source_ids": [
      "PP6:2",
      "PP6:welding_settings_code:1"
    ],
    "target_ability": "distinguish units and nominal setting from measured observations",
    "checker_coverage": "header-bound unit checks partial; natural-language interpretation unverified",
    "capabilities": [
      "semantic_role_review"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q6",
    "name": "대상·출처 적용성",
    "question": "같은 파일의 명시된 코드북만 연결한다는 공통 규칙 아래, PP6 작업표 2행의 defect를 설명할 근거로 PP6 코드북의 코드 4와 PP7 코드북의 코드 4 중 어느 것을 사용할 수 있나요? 이름이 같다는 사실만으로 둘을 대체할 수 있나요?",
    "evidence_basis": "retained_source_with_declared_policy",
    "source_ids": [
      "PP6:2",
      "PP6:defect_code:4",
      "PP7:defect_code:4"
    ],
    "target_ability": "correct value alone does not establish source applicability",
    "checker_coverage": "same-workbook/ref policy covered; policy is experiment declaration, not universal domain law",
    "capabilities": [
      "source_applicability_review"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q7",
    "name": "시점·버전 적용성",
    "question": "가상 이력표와 시작일 포함·종료일 제외 규칙을 기준으로, 2025-06-30의 PP6 기록에 적용되는 검토 문서 버전을 골라주세요. 최신 버전과 적용 버전이 같은지도 설명해주세요.",
    "evidence_basis": "authored_synthetic_version_diagnostic",
    "source_ids": [],
    "target_ability": "effective-date and scope selection, including overlaps/missing history",
    "checker_coverage": "new temporal policy needed; not implemented in present checker or genuine history",
    "capabilities": [
      "synthetic_temporal_review"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q8",
    "name": "판단 한계·추가 근거 식별",
    "question": "제공된 작업표와 코드북으로 PP6 작업표 2행에 대해 확인할 수 있는 내용과 확인할 수 없는 내용을 나눠주세요. 명목 Idc, 실제 측정 전류, 적용 검토 문서 버전을 각각 판단하려면 어떤 근거가 필요한가요?",
    "evidence_basis": "bounded_evidence_review",
    "source_ids": [
      "PP6:2",
      "PP6:welding_settings_code:1"
    ],
    "target_ability": "preserve supported parts; specify missing evidence without claiming global absence",
    "checker_coverage": "unknown covers selected bindings only; sufficiency/applicability needs separate adjudication",
    "capabilities": [
      "evidence_limit_review"
    ],
    "native_ontology_inference_required": false
  },
  {
    "id": "Q9",
    "name": "초안 오류·검토 지점 식별",
    "question": "초안의 “PP6 작업표 2행의 결함은 Porosity이고 실제 측정 전류는 450 A다”를 제공된 자료와 대조해주세요. 유지·수정·판단 보류할 부분과 확인할 근거 위치를 제시해주세요.",
    "evidence_basis": "retained_source_plus_authored_draft",
    "source_ids": [
      "PP6:2",
      "PP6:defect_code:4",
      "PP6:welding_settings_code:1"
    ],
    "target_ability": "wrong label and unsupported measured interpretation distinguished",
    "checker_coverage": "declared-value mismatch detectable; measured-scope/projection semantics unverified",
    "capabilities": [
      "authored_draft_review"
    ],
    "native_ontology_inference_required": false
  }
]