# 주문별 수량 조회와 저장된 결과의 RDFS 추론

이 안내는 `commerce-small`의 원래 두 번째 질문 **“What total item quantity is recorded for each delivered order?”**를 다룬다. 배송 완료로 기록된 주문별 품목 수량을 조회한 뒤, 저장된 결과 행을 RDF로 투영하고 작은 RDFS 온톨로지로 분류한다. 질문 해석은 사람이 작성한 것이며 자연어 자동 해석이나 정답 판정이 아니다.

**검증 범위:** 2026년 11월 19일, 1440·375픽셀 브라우저에서 새 자료실을 만들고 필드·관계 검토, 질의 작성·승인·실행, 실제 OO 추론과 참고 기록 재열기까지 실행했다. 각 화면 크기에서 질의는 1회, 전후 온톨로지 추론은 2회 실행했으며 원래 답은 보존됐다. 화면 조작과 승인은 스크립트로 수행했다. 사람의 사용성 평가나 전문가 검토, 답의 정확도 채점은 아니다. upstream 설치는 기존 환경을 재사용했다.

## 원본 생성과 자료실 준비

질의의 형식화된 해석은 `examples/factory_lab/extensions/domain-packs/commerce-small/query-config.json`, 스키마와 물리 외래키는 같은 디렉터리의 `domain-config.json`에 있다. 저장소 루트에서 새 비공개 디렉터리에 공개 예제를 생성하고 등록한다.

```bash
uv run --locked python examples/factory_lab/extensions/domain-packs/generate.py \
  --output _workspace/my-worked-domain-packs
uv run --locked python -m apps.factory_lab.database_sources_cli \
  --registry _workspace/my-worked-databases register \
  _workspace/my-worked-domain-packs/commerce-small/source.sqlite \
  --label 'Commerce small worked example'
```

실제 등록 출력의 원본 ID와 해시를 보관한다. `registered-commerce/create_example.py`는 별도로 작성된 예제이므로 여기서는 사용하지 않는다. 설치와 OO 바이너리 빌드는 [운영자 안내](factory-lab-extension-operator.md)를 따른다. 서버를 시작할 때는 새 데이터 디렉터리와 비어 있는 루프백 포트를 쓰고 `--workspace-database-registry`에 **이 안내에서 만든** `_workspace/my-worked-databases`를 지정한다. `--workspace-reasoner-binary`에는 빌드하고 해시를 기록한 로컬 OO 바이너리를 지정한다. 실시간 모델 옵션은 켜지 않는다.

`/workspace`에서 `등록된 원본 목록 보기`를 누른다. 다음 값을 입력하고 `선택한 등록 원본으로 자료실 만들기`를 누른다.

| 화면 항목 | 입력·선택 값 |
| --- | --- |
| `새 자료실 이름` | `Commerce small quantity walkthrough` |
| `분야 이름 · 표시용` | `Authored commerce` |
| `운영자가 등록한 원본` | `Commerce small worked example` |

화면의 스냅샷 해시가 등록 출력과 같은지 확인한다. 시작 화면의 CSV 상거래 데모와 혼동하지 않는다. 이 질문은 기록된 수량 집계이므로 정책 문서 승인이 필요하지 않다.

전체 연결은 **등록 원본 → 필드·관계 승인 → 질의 승인·실행 → 저장된 답 → 투영·온톨로지 계획 승인 → OO 실행 → 선택한 참고 기록** 순서다. 온톨로지를 바꿀 때는 같은 저장된 답에서 새 계획을 만든다. 원래 답과 첫 계획은 보존한다.

## 다섯 필드의 의미 검토

`데이터 정리`에서 `검토할 표`를 선택하고 `열 이름 검색`에 열 이름을 입력해 정확한 필드 카드를 연다. 이름이 겹치면 표와 열을 함께 확인한다. 각 카드의 `검토 상태`를 `승인`으로 바꾸고 `검토한 의미 · 승인 시 필수`를 입력한 뒤 `이 필드의 검토 결정 저장`을 누른다. 승인 상태의 저장 값은 `approved`다.

| 물리 필드 | 검토할 의미의 예 |
| --- | --- |
| `order_items.line_id` | 이 스냅샷의 품목 행 하나를 식별한다. 집계의 기준 행이다. |
| `order_items.order_id` | 품목 행에 기록된 상위 주문 참조다. |
| `order_items.quantity` | 품목 행에 기록된 정수 수량이다. 단위를 변환하지 않고 합산한다. |
| `orders.order_id` | 기록된 주문 식별자이며 상위 표의 키다. |
| `orders.status` | 기록된 상태 문자열이다. `delivered`는 원본 값이며 실제 배송을 독립적으로 확인한 결과가 아니다. |

이 의미들은 사용자가 검토할 제안이다. 독립적인 전문가 승인을 받았다는 뜻은 아니다. 화면은 실제 항목 ID를 연결하므로 예시 ID를 입력하거나 저장 JSON을 편집해 승인 상태를 만들지 않는다.

## 주문 외래키 제안과 승인

`선언된 외래키 검토`에서 **`order_items.order_id → orders.order_id`**를 연다. 양쪽 필드가 승인 상태인지 확인한다. `관계 식별 이름 · 영문자로 시작`에 `item_order`, `관계의 의미와 적용 범위`에 다음을 입력하고 `관계 제안 저장`을 누른다.

```text
Recorded item-to-order foreign key; child rows are retained, unmatched parent values are NULL; subsequent status filtering may exclude them.
```

저장된 제안을 열어 양쪽 필드, 고정된 원본, LEFT 다대일 연결의 자식 행 보존 조건을 확인한다. `이 저장본을 검토한 메모`를 작성하고 `저장된 원본·조건·한계를 확인하고 이 정의를 승인합니다`에 체크한 뒤 `이 저장된 정의 승인`을 누른다. 제안과 별도의 승인 기록이 생긴다. 다른 외래키인 `order_items.sku → products.sku`는 이 질문에 필요하지 않다.

## 주문별 수량 질의 작성

`원본 조회`에서 `질의 정의 작성`을 펼친다. `질의 종류`는 `행 조회 · 비교 · 집계`를 선택한다. 저장 값은 `relational`이다.

| 화면 항목 | 입력·선택 값 |
| --- | --- |
| `질의 식별 이름 · 영문자/숫자/밑줄` | `delivered_order_quantity` |
| `제목` | `Recorded quantity per delivered order` |
| `질문의 범위` | 원래 질문을 적고 기록된 상태가 입력 상태와 같은 주문의 품목 행 수량을 합산한다고 명시한다. |
| `기준 행의 승인 필드` | 승인한 `order_items.line_id` 항목 |
| `기준 표 별칭` | `r` |
| `결과 의미` | `기록된 사실` (`recorded_facts`) |
| `한계 · 한 줄에 하나` | 아래 두 줄 |
| `중복 출력 제거 DISTINCT` | 체크하지 않음 |

```text
Authored synthetic source; delivered is recorded status only.
Quantity aggregation does not determine return eligibility or external truth.
```

각 영역의 추가 버튼으로 다음 행만 만든다.

| 추가 버튼 | 입력·선택 값 |
| --- | --- |
| `관계 연결 추가` | `저장된 관계 승인 선택`을 펼치고 `저장 목록 불러오기`를 누른다. 양쪽 필드와 원본이 맞는 승인된 `item_order`를 찾아 `이 저장본 열기`를 누른다. `이미 연결된 자식 별칭`은 `r`, `새 부모 별칭`은 `o`로 지정한다. 대기 중인 제안이 아니라 승인을 선택한다. |
| `매개변수 추가` | `이름` = `status`, `자료형` = `text`. 값은 실행할 때 입력한다. |
| `필터 추가` | `승인 필드` = `orders.status`, `표 별칭` = `o`, `비교` = `같음` (`eq`), `매개변수 이름 · NULL 비교는 비움` = `status` |
| `출력 열 추가` | `승인 필드` = `orders.order_id`, `표 별칭` = `o`, `출력 이름` = `order_id` |
| `그룹 키 추가` | `승인 필드` = `orders.order_id`, `표 별칭` = `o` |
| `집계 추가` | `승인 필드` = `order_items.quantity`, `표 별칭` = `r`, `집계 방식` = `sum`, `출력 이름` = `total_quantity` |

스칼라 선택, 타입 비교, 원시 수량의 추가 출력, 정책 문단은 넣지 않는다. 주문 필드에는 부모 별칭 `o`를 쓰고 SUM에는 기준 행 별칭 `r`의 수량을 쓴다. 일반 출력인 `order_id`는 그룹 키에도 있어야 한다. NULL 수량은 SUM에서 제외되며 빈 그룹은 나타나지 않는다. 부모 상태 필터는 연결되지 않은 주문과 NULL 상태를 제외한다. 이는 해당 주문이 현실에 없다는 증거가 아니다.

`정의 검증 후 제안 저장`을 누른다. 저장된 정의에서 실제 관계 승인 의존성과 원본 지문을 확인한다. 검토 메모를 작성하고 `저장된 원본·조건·한계를 확인하고 이 정의를 승인합니다`에 체크한 뒤 `이 저장된 정의 승인`을 누른다. 해당 승인의 `승인된 정의 실행`에서 `status · text`에 **`delivered`**를 입력하고 `승인된 질의 실행`을 누른다.

답이 접혀 있으면 `결과와 근거 열기`를 누른다. 저장된 `order_id`, `total_quantity`와 원본·승인·매개변수 출처를 확인한다. 이 안내는 예상 행이나 합계를 제공하지 않는다. 실행 실패, 미완료, 표시 잘림이 있으면 중단하고 기록을 보존한다. 원본에 연결된 추론 계획에는 완료 상태이며 전체 결과가 있고 잘리지 않은 일반 관계형 결과가 필요하다. 실패를 빈 답으로 바꾸지 않는다.

## 저장된 결과의 RDF 투영

그 답에서 `저장된 질의 결과에서 추론 · 별도 참고 근거`, `투영과 RDFS 온톨로지 작성`을 차례로 펼친다. `관측 행 클래스 IRI`는 다음과 같다.

```text
urn:factory-lab:semantics:RecordedDeliveredQuantity
```

첫 매핑 행을 채우고 `출력 열 매핑 추가`로 두 번째 행을 만든다.

| `저장된 출력 열` | `술어 IRI` | `선언할 자료형` |
| --- | --- | --- |
| `order_id` | `urn:factory-lab:semantics:recordedOrderId` | `문자열` (`text`) |
| `total_quantity` | `urn:factory-lab:semantics:recordedQuantity` | `정확한 signed64 정수` (`integer`) |

`이 투영의 해석`에 다음을 입력한다.

```text
Each subject is one saved grouped query output observation, not an order entity or external delivery certification.
```

`해석의 한계 · 한 줄에 하나`에는 다음 두 줄을 입력한다.

```text
Authored source and scripted reviewer choices; no factual truth or business accuracy claim.
Includes only complete selected query output, not entire database semantics.
```

주어는 실제 실행과 행 순번에서 생성된다. 주문 식별자를 RDF 주어로 대신 쓰거나 실행 ID를 만들어 넣지 않는다. 저장 정책은 `execution_row_ordinal`이며 NULL 처리는 `omit_with_manifest`다. 누락은 명세에 남는다. 자료형은 표본에서 추정하는 것이 아니라 여기서 선언한다.

## 첫 온톨로지의 승인과 OO 실행

`검토할 RDFS 온톨로지 · UTF-8 최대 16 KiB`에 다음 Turtle을 그대로 입력한다.

```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:factory-lab:semantics:RecordedDeliveredQuantity> rdfs:subClassOf <urn:factory-lab:semantics:RecordedQuantity> .
```

`투영·온톨로지 계획 저장`을 누르고 계획의 다음 항목을 열어 검토한다.

- `검토할 투영 정의 · 한계`
- `원본·질의 승인·매개변수 연결`
- `행·열·NULL 누락·집계 표현·의존성 명세`
- `온톨로지 원문 · asserted`
- `실제 실행에 제출할 결합 입력`

저장된 질의 실행, 질의 승인, 스냅샷, 매개변수, 출력, 실제 바이너리 해시가 연결되어 있는지 확인한다. `계획 승인 검토 메모`를 작성하고 `저장된 투영·원문 온톨로지·누락·한계를 확인하고 이 계획을 승인합니다`에 체크한 뒤 `이 추론 계획만 승인`을 누른다. 승인만으로 OO가 실행되지는 않는다. 만들어진 승인 기록에서 `승인한 입력으로 OO 추론 실행`을 눌러야 한다.

`실제 영수증 · 이벤트·표준 출력·오류·출처`에서 입력과 바이너리 해시를 포함한 실행 기록을 확인한다. 실패하거나 일부만 처리되었다면 영수증을 보존한다. 대체 문장을 만들어 선택하지 않는다. 여기서 검토하는 추론은 투영된 관측 행의 `RecordedQuantity` 분류이며 수량 재계산이나 배송 인증이 아니다.

## 참고 문장 저장과 다시 열기

성공한 추론 기록에서 `참고로 저장할 행 분류 선택 · N개`를 펼친다. **N은 현재 화면의 실제 개수**다. 과거 실행의 값을 복사하지 않는다. 직접 확인한 실제 저장 트리플만 선택하고 `선택한 도출문의 참고 해석`에 다음을 입력한다.

```text
Saved query observations classified under the reviewed hierarchy; no delivery or quantity truth certification.
```

`참고 사용 검토 메모`를 작성하고 `선택한 문장을 원래 답과 별도인 참고 근거로 저장합니다`에 체크한 뒤 `선택한 도출문을 참고 기록으로 저장`을 누른다.

저장된 참고 기록에서 `저장한 참고 문장 원문 불러오기`를 누르고 `선택한 도출문 · 원래 추론 기록에서 조회`를 연다. 저장된 문장 ID를 실제 추론 기록에서 다시 읽는 경로다. `원래 질의 답 열기`로 수량 답이 남아 있는지 확인한다. 답의 추론 패널에서 `이 답의 추론·참고 기록 불러오기` 또는 `연결 목록 새로 확인`을 누르고 실제 저장 참고 항목의 `이 추론 연결 기록 열기`를 사용한다. UUID를 추측해 입력하지 않는다. 새 로컬 추론이 비활성화되어도 이미 저장한 기록은 다시 열 수 있다.

## 온톨로지 변경과 별도 계획 비교

같은 원래 질의 답으로 돌아간다. 투영은 유지하고 다음 온톨로지로 **새 계획**을 만든다.

```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<urn:factory-lab:semantics:RecordedDeliveredQuantity> rdfs:subClassOf <urn:factory-lab:semantics:RecordedQuantity> .
<urn:factory-lab:semantics:RecordedQuantity> rdfs:subClassOf <urn:factory-lab:semantics:ReviewEvidence> .
```

계획 검토, 명시적 승인, OO 실행을 반복한다. 원하면 확인한 도출문을 별도 참고 기록으로 저장한다. 첫 계획과 실행은 보존한다. 추가한 하위 클래스 규칙은 RDFS의 추이성을 통해 관측 행을 `ReviewEvidence`로 분류할 수 있게 한다. 비교 대상은 **실제 저장된 도출 집합**이다. 실행이 반환하지 않은 예상 트리플을 넣어서는 안 된다.

어느 버전도 SUM을 바꾸거나 원본 행을 다시 조회하지 않는다. 누락된 정책 근거를 보충하거나 외부 사실의 진위를 입증하지도 않는다.

## 독립 RDF 업로드 예제와의 구분

`examples/factory_lab/extensions/rdfs-change/before.ttl`과 `after.ttl`은 기계·작업지시 사실과 domain/range 공리를 담은 별도 예제다. `O17 assignedTo M02`를 `O17 assignedTo M03`으로 바꾼다. 이 파일들은 현재 SQLite 실행, 출력 열, 원본 해시와 자동으로 연결되지 않는다. 주문 합계의 투영인 것처럼 붙여 넣으면 안 된다.

이 안내의 경로는 저장된 결과에서 관측 행 RDF를 명시적으로 생성하고 검토한 작은 온톨로지와 결합한다. 기존 업로드 RDF 경로와 연결 근거가 다르다.

## 확인 근거와 남은 검증

이 안내의 소규모 이커머스 절차는 1440·375픽셀의 새 자료실에서 확인했다. 확인 범위는 필드·관계 검토, 질의 작성·승인·실행, 실제 OO 추론과 참고 기록 재열기까지다. 각 화면 크기에서 질의 1회와 전후 추론 2회를 실행했다. 승인과 조작은 스크립트로 수행했고 설치는 기존 환경을 재사용했다. 이 기록이 수동 사용자 평가나 새 호스트 설치 검증을 대신하지는 않는다.

기존 CSV·로컬 생성기와 외부 확장 없이 사용하는 경로를 유지한다. 세 분야의 설정과 화면 입력 예제는 연결된 사용 안내에서 확인할 수 있다. 새 제조·조직 운영 안내 자체를 처음부터 끝까지 브라우저에서 재실행한 기록은 아직 없다. 원래 실행의 결과와 새 안내의 검증 상태를 구분한다.

[세 분야의 사용 절차](factory-lab-domain-workflows.md)와 [실행 기록](../experiments/records/factory-lab-extensions-20261119.md)을 함께 확인한다.
