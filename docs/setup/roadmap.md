# 실험 환경과 다음 연결 작업

이 페이지는 설치 계획과 실제 실행을 구분합니다. 실험 수치는 각 [실행 기록](../experiments/records/index.md)에서 확인할 수 있습니다.

## 현재 연결 상태

| 구성 요소 | 확인한 범위 | 남은 일 |
| --- | --- | --- |
| RDFLib·pySHACL | 로컬 RDF 조회와 선택 근거 검사를 실행했습니다. | 더 큰 자료와 새 질문에서 검사 범위를 검토해야 합니다. |
| Neo4j Community·n10s | 실제 Cypher 조회, 일부 RDF 매핑·추론·변경 사례를 실행했습니다. Factory Lab은 Neo4j를 기본 조회 저장소로 사용합니다. | 규칙 변경의 운영 비용과 동시 수정은 측정하지 않았습니다. |
| Amazon Neptune | 이전의 제한된 세션에서 RDF/SPARQL 조회와 외부에서 계산한 추론 결과의 저장·변경 비교를 실행했습니다. | Factory Lab의 새 v3 조회 48건은 아직 Neptune에서 실행하지 않았습니다. 새 운영 시간과 종료 절차를 확인한 뒤 진행합니다. |
| GraphDB Free | 연구의 비교 후보입니다. | 이 연구의 Factory Lab 비교에는 아직 연결하지 않았습니다. |
| OpenRouter | 여섯 모델 사후 검토 개발 실험과 Factory Lab의 한 사례 실제 답변을 실행했습니다. | 새 유료 실행은 범위와 비용을 다시 고정해야 합니다. |

Factory Lab의 이번 [Neo4j·로컬 RDF 조회 비교](../experiments/records/2026-11-10-factory-rdf-parity.json)는 정해진 다섯 조회 도구가 반환한 결과를 확인한 소규모 통합 검사입니다. 저장소 성능이나 임의의 SPARQL·Cypher가 동등한지는 다루지 않습니다. [실제 LLM 답변 기록](../experiments/records/2026-11-10-factory-renewal-live.json)은 Neo4j 경로에서만 실행했습니다.

## 다음 연결 작업

1. Neptune 운영 시간을 한정하고 중지 절차를 준비한 뒤, Factory Lab의 동일한 RDF 스냅샷과 48개 조회를 실행합니다.
2. 저장소가 반환하는 공통 근거와 LLM에게 전달하는 도구 메타데이터를 분리해, 백엔드별 답변 비교의 입력을 맞춥니다.
3. 같은 정책의 Python·SHACL 구현에서 규칙 변경 위치, 재검토 대상, 담당자 설명 자료를 비교합니다. 실제 유지보수 시간은 별도 측정 대상입니다.

`infra/terraform/`는 현재 운영 중인 Neptune을 재현하는 확정된 배포 코드가 아닙니다. 인프라를 다시 만들기 전에 계정·리전·예산·보존 정책을 따로 검토해야 합니다. 연구 운영 절차는 [에이전트와 검토 체계](research-operations.md), 공개 절차는 [기록과 GitHub Pages 운영](recording.md)에 있습니다.
