# 선택적 확장 연결과 다섯 자료 묶음의 실행 기록

2026년 11월 19일 기준 기록입니다. auto-ontology의 실제 의미 제안을 가져와 수정·승인한 뒤 조회에 사용했고 OpenOntologies를 저장된 조회 결과에 연결해 별도 참고 기록을 만들었습니다. 아래 다섯 자료 묶음의 질문 실행은 사람이 작성한 질의 정의를 사용했습니다. 자연어 해석 능력이나 답변 정확도 비교는 아닙니다.

## 자료와 실행 범위

모든 묶음은 작성한 합성 자료입니다. 제조는 부품·검사·예외, 조직 운영은 배정·권한·시점·의존 관계, 이커머스는 주문 항목·가격·정책 조건을 다룹니다. 실제 사업 자료의 분야 전이를 검증한 것은 아닙니다.

| 자료 묶음 | 행 | 표 | 문서 | 문자 | 추정 토큰 | 추정 페이지 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| commerce-small | 180 | 3 | 2 | 398 | 100 | 1 |
| manufacturing-small | 280 | 6 | 4 | 3,694 | 924 | 2 |
| organization-small | 280 | 6 | 4 | 3,566 | 892 | 2 |
| commerce-medium | 15,680 | 12 | 24 | 23,512 | 5,878 | 8 |
| organization-medium | 17,250 | 12 | 24 | 24,713 | 6,179 | 9 |

문자는 공백을 포함한 Unicode 코드 포인트 수입니다. 토큰은 문자 수/4, 페이지는 문자 수/3,000을 올림한 추정치입니다. 실제 토크나이저나 렌더링 페이지 수를 측정한 값은 아닙니다. 문서 등록은 텍스트·Markdown과 원문 문단 검토이며 PDF 파싱이나 자동 정책 추출을 뜻하지 않습니다.

## 고정 질문 25건

최초 17건과 연산 추가 후 3건을 합쳐 20건을 실제 조회했습니다. 나머지 5건에는 검토자가 부족한 근거와 확인 범위를 기록했습니다. 이 기록은 답변도, 자료 전체에 해당 사실이 없다는 자동 판정도 아닙니다. 최초 미실행 상태는 [기계 판독 기록](factory-lab-extensions-20261119.json)에 그대로 남겼습니다. 이 질문 행렬의 LLM 호출은 0회입니다.

| 질문 ID | 고정한 질문 원문 | 실행 범위 |
| --- | --- | --- |
| `commerce-medium-1` | List non-suspended supplier IDs. | 조회 35행 |
| `commerce-medium-2` | What is recorded line value in cents per customer for confirmed orders? | 조회 200행 / 전체 900행, 표시 제한 · 연산 추가 후 실행 |
| `commerce-medium-3` | Which promotions apply to product 1 for customer 1 on 2026-11-19 under the published date and tier rule? | 조회 0행 · 연산 추가 후 실행 |
| `commerce-medium-4` | Which confirmed orders contain products supplied by supplier 1 and need review if it is suspended? | 조회 150행 |
| `commerce-medium-5` | What was the actual carbon footprint of shipping order 1? | 미해결 요구 기록 · 부재 검증 안 됨 |
| `commerce-small-1` | List SKUs in the equipment category. | 조회 10행 |
| `commerce-small-2` | What total item quantity is recorded for each delivered order? | 조회 20행 |
| `commerce-small-3` | Which orders have the delivered status required by the return policy? This is a status prerequisite only. | 조회 20행 |
| `commerce-small-4` | Which orders contain SKU S000 and are candidates for review if that SKU is recalled? | 조회 2행 |
| `commerce-small-5` | Which named customer owns order O000? | 미해결 요구 기록 · 부재 검증 안 됨 |
| `manufacturing-small-1` | List released product IDs. | 조회 13행 |
| `manufacturing-small-2` | How many active BOM units does each released product require on 2026-11-19? | 조회 13행 |
| `manufacturing-small-3` | Which approved cosmetic-only waivers remain unexpired on 2026-11-19? | 조회 5행 |
| `manufacturing-small-4` | Which products have an active direct dependency on part 0 on 2026-11-19? | 조회 2행 |
| `manufacturing-small-5` | What is the real-world fatigue life in hours of part 0? | 미해결 요구 기록 · 부재 검증 안 됨 |
| `organization-medium-1` | List open approval request IDs for project 1. | 조회 7행 |
| `organization-medium-2` | Count recorded approval events per owner team. | 조회 30행 |
| `organization-medium-3` | Which active employees have an unexpired approval-capable role on 2026-11-19? This is role eligibility only. | 조회 200행 / 전체 400행, 표시 제한 |
| `organization-medium-4` | Which milestones are transitively downstream of milestone 0 and candidates for review if it slips? | 조회 4행 · 연산 추가 후 실행 |
| `organization-medium-5` | What is the external legal validity of approval request 1? | 미해결 요구 기록 · 부재 검증 안 됨 |
| `organization-small-1` | List active employee IDs in team 1. | 조회 5행 |
| `organization-small-2` | Count active employees with currently valid assignments per project on 2026-11-19. | 조회 20행 |
| `organization-small-3` | Which project exceptions are unexpired on 2026-11-19? | 조회 5행 |
| `organization-small-4` | Which projects have a current assignment for employee 1 and need review if that employee leaves? | 조회 2행 |
| `organization-small-5` | What is employee 1 annual salary? | 미해결 요구 기록 · 부재 검증 안 됨 |

commerce-medium-2는 전체 자료에서 900개 집계를 계산하고 200개를 반환했습니다. organization-medium-3은 400개 중 200개를 반환했습니다. 전체 원본에 대한 조회와 화면에 반환한 결과 범위는 다릅니다. 잘린 결과를 완전한 근거로 표시하지 않습니다.

## 공급자별 실제 확인

| 경로 | 실제 확인 | 해석의 한계 |
| --- | --- | --- |
| auto-ontology 의미 생성 | 기존 소규모 이커머스 DB의 실제 YAML 제안을 수정·승인하고 필드·관계·질의에 재사용 | 전문 도메인 검토나 의미 정확도 평가 아님 |
| auto-ontology 공개 예제 | 새 예제 등록 후 공식 카탈로그 수집과 YAML 내보내기; 3개 표·9개 열, 3,052바이트 | 기존 설치·마이그레이션 재사용; 새 환경 설치와 모델 의미 생성은 이 실행에 포함하지 않음 |
| OpenOntologies | 같은 저장 조회를 RDF 관측 행으로 투영하고 두 RDFS 온톨로지로 실제 실행; 선택한 도출문을 참고 기록으로 저장 | 원래 답을 수정하지 않음; 전체 DB 추론·현실 사실 검증·인증서 검증 아님 |
| 다섯 자료 묶음 | 승인한 관계·질의와 원문 문단을 사용한 조회 및 미해결 요구 기록 | 모든 묶음에서 두 upstream의 의미 생성을 실행한 것은 아님 |

OpenOntologies의 전후 도출문 수는 20개와 41개였습니다. 차이 21개에는 온톨로지 관련 문장도 들어 있으므로 새 업무 객체 21개를 발견했다고 해석할 수 없습니다. 현재 연결은 최대 12개 테이블·테이블당 40열·원본 16 MiB로 제한합니다. catalog 모드는 전체 등록 사본의 스키마와 물리 관계를 수집하며 행 수 때문에 앞부분을 자르지 않습니다. semantic 모드는 테이블당 1,000행과 셀 크기 제한을 유지합니다. 중규모 DB의 카탈로그 수집과 LLM 의미 생성은 별도 기능입니다. 이 연결에는 문서 입력 경로가 없습니다.

실제 중규모 수집에서는 이커머스 15,680행의 12개 표·46개 열·12개 외래키와 조직 운영 17,250행의 12개 표·47개 열·15개 외래키가 원본 구조와 일치했습니다. 두 결과를 자료실의 승인 대기 제안으로 가져오고 운영자가 보관한 실행 기록과 연결했습니다. 모델 호출은 없었고 원본 해시는 유지됐으며 전용 카탈로그 서비스는 실행 후 중지했습니다. 이 결과는 의미 해석의 정확도나 전체 행의 LLM 분석을 입증하지 않습니다.

## 저장된 조회 결과의 추론 범위

다음 표는 실제 OpenOntologies 실행에서 읽은 저장된 출력 행과 도출문 수다. 제조·조직 운영의 투영과 RDFS 규칙은 사람이 작성했다. 이커머스의 외부 의미 제안 수정·승인 사례와 이 규칙 작성 절차를 구분한다.

| 자료 | 저장된 출력 행 | 변경 전 도출문 | 변경 후 도출문 |
| --- | ---: | ---: | ---: |
| commerce-small | 20 | 20 | 41 |
| manufacturing-small | 13 | 13 | 39 |
| organization-small | 20 | 20 | 61 |
| commerce-medium | 35 | 35 | 71 |
| organization-medium | 30 | 30 | 61 |

도출문에는 온톨로지 관련 문장도 포함되므로 증가분을 새 업무 객체 수로 해석하지 않는다. 중규모 DB의 전체 행을 추론한 것이 아니라 완료된 조회 결과만 투영했다. 제조·조직 운영 소규모와 중규모 두 사례에서는 외부 도구를 끈 뒤에도 각각 8개 요청의 저장 결과를 다시 읽었다. 원본과 원래 답변은 유지했다. 이 검사는 업무 판단의 정확도나 답변 개선 효과를 측정하지 않는다.

## 재현 경로와 남은 검증

[운영자 안내](../../setup/factory-lab-extension-operator.md)에는 고정 upstream 설치, 비공개 설정, 카탈로그 실행과 서버 연결 명령이 있습니다. [세 분야 사용 절차](../../setup/factory-lab-domain-workflows.md)에는 다섯 묶음 생성, 분야별 설정과 제안 준비 절차가 있습니다. 새 분야는 테이블·열·행의 단위·관계·정책 근거·질의 한계를 설정으로 정의합니다. 기존 연산으로 표현할 수 없는 요구는 별도 구현과 검토가 필요합니다.

Python 3.11.17로 다섯 묶음을 생성하고 무결성·외래키를 확인했습니다. SQLite 버전 차이로 새로 생성한 네 DB의 파일 해시는 달랐지만 별도 비교에서 모든 표의 정렬한 행은 같았습니다. 새 등록에는 새 해시를 사용해야 합니다. 기존 commerce-small 사본은 바이트가 같았으며 해당 예제 데이터의 별도 재배포 라이선스 근거는 아직 정리되지 않았습니다. 다른 네 묶음은 기존 CC0 고지를 유지합니다.

[연결 안내](../../setup/factory-lab-upstream-extensions.md)에서 시작할 수 있습니다. 새 환경에서 설치부터 전체 사용 절차를 끝까지 재현한 검증은 남아 있습니다. 기존 구성요소의 브라우저 검사는 1440 px와 375 px에서 수행했지만 모든 질문의 모바일 사용성이나 접근성 평가를 대신하지 않습니다.

시간·등록 소요와 원본 해시는 JSON에 측정 정의와 함께 보존했습니다. 준비 시간에는 생성·검사·직렬화가 포함되고 사람의 작성 시간은 제외됩니다. 서로 다른 연산의 소요를 엔진 성능이나 유지보수 비용의 우열로 비교하지 않습니다. 문서 자동 해석, 전문가 정확도, 수백만 행 운영 성능과 실제 사용자 평가도 미검증입니다.
