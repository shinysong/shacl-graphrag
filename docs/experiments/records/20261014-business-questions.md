# 2026-10-14 — 금융·제조업 여섯 업무 질문의 첫 실행

[업무 질문과 판단 기준](../business-questions-study.md)을 고정하고 질문마다 여섯 상황을 실행했다. 합성 사례 36개에 세 조건을 적용한 108행이며 별도로 실제 GLEIF 예시 네 개를 실행했다. 유료 모델 호출은 없었다.

## 질문·탐색·출력 도식

각 카드에 업무 질문, 입력 데이터, 탐색·판단 과정, 두 조건의 실제 출력을 함께 배치했다. 질문은 실행에 사용한 영어 질문을 한국어로 옮겼다. 탐색 과정은 저장된 입력과 실행 코드에서 재구성한 설명이며 별도로 수집한 단계별 로그는 아니다. 출력은 기존 실행 기록을 그대로 사용했다.

여섯 카드는 합성 사례다. 단순 조회는 일부 조건을 제거한 비교이며, 규칙·JSON과 규칙·RDF는 같은 판단 함수를 사용한다. 자연어를 자동으로 해석하거나 RDF 추론으로 답을 만든 실험은 아니다. 카드 아래 기존 표는 도식의 텍스트 설명으로도 읽을 수 있다.



[전체 도식 SVG 열기·확대](../figures/business-questions-overview.svg) · [원본 실행 데이터](20261014-business-questions-summary.json)

<div class="business-trace-cards" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px;margin:24px 0;">
<a href="/shacl-graphrag/experiments/figures/business-m1-1.svg" aria-label="제조 1 영향 제품 도식 확대"><img src="/experiments/figures/business-m1-1.svg" alt="제조 1 영향 제품: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
<a href="/shacl-graphrag/experiments/figures/business-m2-1.svg" aria-label="제조 2 교체 조건 도식 확대"><img src="/experiments/figures/business-m2-1.svg" alt="제조 2 교체 조건: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
<a href="/shacl-graphrag/experiments/figures/business-m3-1.svg" aria-label="제조 3 재검사 항목 도식 확대"><img src="/experiments/figures/business-m3-1.svg" alt="제조 3 재검사 항목: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
<a href="/shacl-graphrag/experiments/figures/business-f1-6.svg" aria-label="금융 1 직접 모회사 도식 확대"><img src="/experiments/figures/business-f1-6.svg" alt="금융 1 직접 모회사: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
<a href="/shacl-graphrag/experiments/figures/business-f2-5.svg" aria-label="금융 2 최종 모회사 도식 확대"><img src="/experiments/figures/business-f2-5.svg" alt="금융 2 최종 모회사: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
<a href="/shacl-graphrag/experiments/figures/business-f3-2.svg" aria-label="금융 3 내부 검토 도식 확대"><img src="/experiments/figures/business-f3-2.svg" alt="금융 3 내부 검토: 질문, 입력 데이터, 탐색 과정과 두 조건의 실제 출력. 상세 내용은 아래 표 참조." width="360" height="692" style="width:100%;height:auto;display:block;margin:0;" /></a>
</div>

### 실제 GLEIF 관계의 조회와 보류

별도 카드에는 실제 GLEIF 자료를 사용했다. 관계가 원천에 존재해도 등록 상태를 제한하는 내부 정책 때문에 보류할 수 있다. 이 예시에는 독립적인 정답률을 부여하지 않았다.

<img src="/experiments/figures/business-gleif-source.svg" alt="실제 GLEIF: ACTIVE 관계가 LAPSED 등록 상태 때문에 보류되는 과정" width="360" height="760" style="max-width:360px;width:100%;height:auto;" />

[실제 GLEIF 도식 SVG 확대](../figures/business-gleif-source.svg)

## 질문별 선언한 답과의 일치

| 업무 질문 | 단순 조회 | 규칙·JSON | 같은 규칙·RDF |
| --- | ---: | ---: | ---: |
| 제조 1 · 영향 제품 | 1/6 | 6/6 | 6/6 |
| 제조 2 · 대체 부품 조건 | 1/6 | 6/6 | 6/6 |
| 제조 3 · 재검사 항목 | 0/6 | 6/6 | 6/6 |
| 금융 1 · 직접 회계 연결 모회사 | 2/6 | 6/6 | 6/6 |
| 금융 2 · 같은 최종 회계 연결 모회사 | 3/6 | 6/6 | 6/6 |
| 금융 3 · 내부 자료 검토 | 2/6 | 6/6 | 6/6 |

표는 상태와 값의 일치다. 근거 ID까지 포함한 JSON·RDF 출력도 36쌍 모두 같았다. 사람이 규칙과 기대 답을 함께 작성한 개발 사례이므로 산업별 정확도나 일반화 성능으로 해석하지 않는다. 단순 조회는 역할·기간·단위 등의 검사를 일부러 제거한 비교 조건이며 LLM이나 현행 금융·제조 시스템의 성능을 대표하지 않는다. RDF도 실제 SPARQL 조회 뒤 JSON과 같은 Python 판단 함수를 사용했다.

## 업무 질문별 입력과 출력

| 사례 | 입력 상황 | 단순 조회의 실제 출력 | 규칙을 적용한 실제 출력 |
| --- | --- | --- | --- |
| 제조 1 | 부품 A → 조립체 → 제품 X의 두 단계 구성 관계 | 영향 제품 없음 | 제품 X, 근거 b1·b2 |
| 제조 2 | 요구 허용치 0.1 mm, 후보 허용치 50 µm, 지정 인증·인터페이스 충족 | 조건 미충족 | 0.05 mm로 환산하여 조건 충족 |
| 제조 3 | 공차만 변경, 공차·인증·조립 검사 목록 존재 | 검사 세 항목 모두 | 공차와 연결된 fit-review만 |
| 금융 1 | A와 P 사이에 펀드 운용 관계만 존재 | P를 직접 모회사로 반환 | 직접 회계 연결 자료 확인 불가 |
| 금융 2 | 두 기업의 최종 모회사가 같지만 한 관계는 기간 만료 | 같은 모회사 | 확인 불가 |
| 금융 3 | 법인은 ACTIVE, LEI 등록은 LAPSED | 검토 가능 | 재검토 필요 |

제조 1의 자료 누락 사례에서는 단순 조회가 빈 목록을 확정했지만 규칙 조건은 보류했다. 반대로 제조 2의 정상 단위 환산 사례에서는 단순 조회가 가능한 후보를 잘못 거절했다. 잘못된 허용과 불필요한 거절을 함께 봐야 한다. 두 규칙 조건에는 이번 선언한 기대 답을 기준으로 한 불일치가 없었지만 실제 업무의 과잉 보류가 없다는 뜻은 아니다.

## 실제 GLEIF에서 드러난 정책 선택

2026-10-12 Golden Copy의 같은 릴리스에서 LEI·RR·REPEX를 결합했다. 선택한 세 주체의 관계를 찾기 위해 RR 490,833행과 REPEX 6,411,075행을 검색했고 LEI는 첫 19행에서 세 주체를 모두 찾았다. 편의 표본이며 아래 예시에 독립적인 정답률을 부여하지 않았다.

**GESTION PLACEMENTS DESJARDINS INC.** (`010PWNH4K3BLIC3I7R03`)에는 직접 모회사 `549300COKYB5EGSU1838`이 기록돼 있다. 관계 상태는 ACTIVE지만 RR 등록 상태는 LAPSED다. 단순 조회는 모회사를 반환했고 PUBLISHED만 채택하는 이번 규칙은 확인 불가를 반환했다. 원천에 관계가 없어서 보류한 것이 아니다. 이 보류가 업무상 필요한지는 별도 정책 검토가 필요하다.

**Fidelity Advisor Leveraged Company Stock Fund** (`001GPB6A9XPE8XJICC14`)의 운용 관계를 단순 조회는 모회사처럼 반환했다. 규칙 조건은 직접 회계 연결 범주의 NON_CONSOLIDATING 보고 예외를 반환했다. 운용사와 회계 연결 모회사를 구분한 사례다. 법인 상태 ACTIVE·LEI 등록 LAPSED를 사용한 내부 검토는 재검토 필요로 나왔다. 단순 조회의 이 조건은 대상 필터도 생략하므로 실제 예시의 차이를 등록 상태 검사 하나의 효과로 해석하지 않는다.

두 기업의 최종 모회사 비교에서는 한쪽 RR가 LAPSED여서 규칙 조건이 보류했다. 관계의 기록 사실과 그 자료를 의사결정에 채택하는 기준을 별도로 표시할 필요가 드러났다. 다음 확장에서는 “보고된 관계와 상태를 함께 제시”하는 응답과 “검토 완료 여부”를 분리해 비교한다. 이는 아직 실행하지 않은 후속 설계다.

## 검증과 제한

실행 ID는 `20261014T230240Z-business-questions-synthetic`와 `20261014T230240Z-business-questions-gleif`다. 합성 실행은 내부 측정 0.385초, GLEIF 실행은 23.221초였다. 외부 측정 최대 RSS는 각각 38,736 KiB와 38,340 KiB다. 전체 테스트 212개가 통과했고 독립 방법·구현 검토 후 실행했다. 소프트웨어 테스트는 연구 성능 지표가 아니다.

별도 분석기가 108행의 식별자·점수·근거 ID·저장 파일 해시를 확인했다. 실제 예시의 선택 원천 레코드는 ZIP을 다시 읽어 대조했다. LEI 중복 검사는 선택한 첫 19행 안에서만 수행했으며 전체 릴리스의 중복을 검증하지 않았다. 기대 답 자체의 독립적인 업무 전문가 검증은 남아 있다.

제조업은 전부 합성 데이터다. 완전한 BOM·의존성 목록이라는 선언도 입력으로 제공했다. 제조 1의 포함 부정 레코드는 단독으로도 충돌을 일으키는 보수적 정책이다. 자유로운 자연어 해석, Text2SPARQL, OWL 추론, 실제 그래프 DB 성능, 실제 교체 승인과 금융 심사는 평가하지 않았다.

[전체 질문별 집계와 사례 JSON](20261014-business-questions-summary.json)
