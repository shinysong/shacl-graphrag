# Schema study result review
Review only this packet; full source/raw responses omitted and must be marked unverified. No paid launch requested. Study developmental, no freshholdout. Five pinned CycloneDX official examples, 3395 Python/independent SQLite querypairs, zero disagreements; 54 sixmodel mapping calls53exactcorrect1strictformatfailure; no validwrongmapping. 72 fieldsemantics calls sourceonly33/36correct(2validwrong+1outputfailure), same source plus normative schema36/36correct. Differencesall P03 entryrefonly vs absententry. Normative informationeffect, notSHACL. Posthoc P01/P02/P03 selectedaftererrors;18originaldrafts×2reviewconditions=36newcalls. Both exactsame source,normativepolicy,draft,additional2048outputcap; addedcomputedSHACLreportonly. Both17/18correct+1outputfailure;2validwrongdraftscorrectedboth; selfreview recovers1faileddraftbutfails1previouscorrect, SHACL preserves15correctandcorrects2wrongbutfailsoriginalfailed. No incrementalaccuracygain claim; no equivalence or ranking. Actual17completeSHACL/Pythonreportsagree,1inputrejection notviolation,32fixturepairsagree. Noevaluatorreadbyreportgenerator. Explanationtextnottruthscored.
ActualProtonreleasepair202identitymatchednodes,3added3removededges,8versionchangesincludingroot.808questions4operators,22answeridentitysetchanges. globalflag808(786unchanged),versiononly284(262unchanged),completeedgechange/oldreadscope23(1unchanged),all0misses. Hiddenchangefeedsyntheticcontrol0flags22misses. Strongmethodrequirescompletechangefeed; noSHACL-specificclaim or humanmaintenance threshold.
162paidattempts reported$2.721745950,nonrefunded$3.499338630,cap$15/180. No retries, noAWSrestart. Standalone replayUI shows54+808+72+36rows, browserchecksallvalues/390light1280darknooverflow/noJSerrors. Localchecksnotbenchmark. Rawproviderprices/sourcecode omitted. Researchopsregisteredchecks empty; directchecks documentedseparately.
Report text follows:
# 질문 해석과 변경 추적의 경계

이 실험은 기존 제조 자료와 Neo4j·Neptune 비교를 이어받는다. 이번에 추가한 소프트웨어 구성 목록(SBOM)은 제조 자료를 대체하는 데이터가 아니다. 실제 출처에 의존 관계, 누락의 의미, 두 버전의 변화가 함께 있어서 앞선 실험에서 사람이 제공했던 질문 해석과 변경 범위를 점검하는 보조 사례로 골랐다.

현재 세 가지를 확인했다. 질문의 대상·방향·깊이를 분명히 제시한 작은 사례에서는 모델이 대부분 올바른 실행 조건을 골랐다. 실제 두 버전의 의존 관계를 비교하면 전체 파일 변경보다 질문이 읽은 관계 범위로 재검토 대상을 좁힐 수 있었다. 다만 이러한 범위를 계산하는 절차와 출처의 의미를 정하는 정책은 여전히 필요하다. SHACL이 이를 알아서 발견한 것은 아니다.

## 앞선 실험에서 추가한 조건

앞선 제조 자료 실험은 질문별 의존 범위가 이미 맞게 주어진 상태에서 전체·유형·개별 질문의 변경 표시를 비교했다. 이번에는 두 지점을 분리했다.

- 질문 해석: 모델이 자연어에서 대상·관계 방향·탐색 깊이·자료 범위를 올바르게 선택하는가.
- 변경 추적: 실제 새 관계와 삭제된 관계를 알아낼 때, 이전 답에 등장했던 항목만 추적해도 되는가.

`질문 → 실행 조건 → 관계 조회 → 검토 보고서`를 하나의 성공률로 묶지 않았다. 조건이 잘못되었어도 조회가 정상 종료하고 검사를 통과할 수 있기 때문이다.

## 실제 출처와 질문

CycloneDX 공식 예제 저장소의 고정 커밋에서 다섯 파일을 보존했다. 저장소의 CC0-1.0 라이선스, 원문 주소와 SHA-256도 함께 기록했다. 이 파일들은 공개된 구성 목록 예제이며, 실제 고객 장비의 전체 설치 상태를 독립적으로 확인한 자료는 아니다. 이미 내용을 살펴보고 질문을 만든 개발 사례이므로 새 평가용 표본이라고 부르지 않는다.

| 자료 | 구성요소 수 | 의존 관계 수 | 의존 기록이 없는 구성요소 |
|---|---:|---:|---:|
| Proton Bridge 1.6.3 | 202 | 232 | 0 |
| Proton Bridge 1.8.0 | 202 | 232 | 0 |
| CERN LHC VdM Editor | 44 | 0 | 44 |
| Laravel 예제 | 63 | 113 | 0 |
| Dropwizard 예제 | 168 | 170 | 1 |

구성요소 수에는 문서의 루트 항목이 포함된다. CERN 자료의 관계 수가 0이라는 것은 실제 의존성이 없다는 뜻이 아니다. 해당 원문에 의존성 기록이 없다는 뜻이다. Laravel 파일 이름과 실제 루트 이름은 다르므로 질문과 연결에는 파일 이름 대신 원문의 `bom-ref`를 사용했다.

9개 질문에는 직접·간접 의존 대상, 역방향 의존 항목, 명시적인 빈 의존 기록, 의존 기록 자체의 부재, 실제 운영 환경의 완전성 요구, 관계 방향의 모호함, 여러 버전 중 대상을 정하지 않은 질문을 넣었다. 실행기는 여섯 가지 연산만 받으며, 자유로운 Text2SPARQL이나 일반적인 자연어 스키마 생성은 시험하지 않았다.

## 질문 해석 결과

6개 모델에 같은 9개 질문을 한 번씩 주었다. 모델은 답변 목록 대신 `operation`, `target`, `scope`를 골랐다. 선택된 조건을 공통 실행기가 처리하고, 사후 평가에서 사람이 작성한 조건과 대조했다. 평가 정답은 모델이나 실행기의 입력에 넣지 않았다.

54회 중 53회는 응답 형식과 질문 해석이 모두 맞았다. 나머지 1회는 JSON 앞에 설명문을 붙여 엄격한 응답 형식 검사에서 실패했다. 그 설명문과 JSON은 모호한 질문에 추가 확인이 필요하다는 취지였지만, 원래 결과를 성공으로 고치지 않았다. 이 사례들에서는 형식 검사를 통과한 잘못된 해석이 관측되지 않았다.

이 결과만으로 일반적인 질문 이해 능력이나 모델 순위를 정할 수 없다. 질문에 방향과 범위를 명시했고 지원 연산의 정의도 모든 모델에 제공했다. SHACL을 받지 않은 모델의 개선 전후 비교도 아니다. 이번 결과는 이 작은 인터페이스에서 질문 선택이 어디까지 되었는지를 보여준다.

사전 검토에서는 평가 규칙의 오류도 발견했다. 실제 운영 환경을 묻는 질문에 아무 대상이나 선택해도 마지막 상태가 ‘알 수 없음’이면 맞게 처리될 여지가 있었다. 호출 전에 이를 고쳐 모든 질문의 대상·연산·범위를 정확히 대조하고 최종 상태의 일치는 별도 지표로 남겼다. ‘모른다’는 답이 우연히 같아도 질문을 제대로 해석한 것은 아닐 수 있다.

## 실제 두 버전의 재검토 범위

Proton Bridge의 두 문서에서 `(type, group, name)`이 각각 유일한 202개 항목을 대응시켰다. 버전 문자열은 대응 키에서 제외했고 이 방법을 다른 생태계에도 통하는 일반적인 패키지 식별 규칙으로 간주하지 않았다. 대응 후 관계는 3개 추가되고 3개 삭제되었으며 루트를 포함한 8개 항목의 버전 필드가 바뀌었다.

202개 대상에 직접·간접, 정방향·역방향의 네 연산을 적용한 808개 질문을 비교했다. 여기서 답은 버전 문자열을 제외한 식별 대상의 집합이다. 모든 이전·이후 답을 독립적인 SQLite 재귀 질의와 대조했으며 808개가 완료되고 실패는 0개였다.

| 재검토 정책 | 표시한 질문 | 답이 바뀌었는데 놓친 질문 | 답의 집합은 같지만 표시한 질문 |
|---|---:|---:|---:|
| 원문 파일 해시 변경 | 808 | 0 | 786 |
| 이전 답·시작 항목의 버전 필드만 추적 | 284 | 0 | 262 |
| 완전한 관계 변경 내역 + 이전 조회 범위 | 23 | 0 | 1 |
| 변경 통지를 모두 숨긴 인위적 대조군 | 0 | 22 | 0 |

실제로 답이 바뀐 질문은 22개였다. 강한 비교 방법은 바뀐 관계의 출발점 또는 도착점이 그 질문의 이전 조회 범위에 들어가는지를 확인했다. 역방향 질문에서는 관계의 방향을 반대로 적용했다. 이 방법은 정해진 네 연산과 완전한 변경 내역이라는 조건에 의존한다.

버전 필드만 보는 약한 방법도 이 두 문서에서는 바뀐 답을 놓치지 않았다. 이를 일반적인 안전성으로 확대하지 않는다. 별도의 인위적인 회귀 사례에서는 이전 답에 없던 새 선행 항목이 관계로 연결될 때 버전 변경 없이 답이 바뀔 수 있음을 확인했다. 실제 관측 결과와 이 인위적 반례는 구분한다.

변경 내역은 공짜로 주어지지 않았다. 두 원문을 모두 읽은 374,693바이트와 한 번의 논리적 변경 계산 입력인 464개 정규화 관계를 기록했다. 이 수치는 전체 실행 시간이나 반복 조회를 포함한 총 연산량이 아니다. 답이 같아도 버전·출처를 검토할 이유는 남을 수 있으므로, 표의 마지막 열을 업무상 오탐으로 단정하지 않는다.

## 아직 확인하지 않은 의의

현재 결과는 ‘데이터가 몇 개를 넘으면 SHACL이 필요하다’는 기준을 제시하지 않는다. 공유 Python 정책으로도 같은 의미와 변경 검사를 구현할 수 있다. 사람이 규칙을 바꾸는 시간, 여러 팀이 같은 의미를 유지하는 비용, 변경 승인 과정과 회귀 오류를 측정해야 관리상 이점을 비교할 수 있다.

이번에 구체화한 기여 후보는 복잡성의 개수보다 조건이다. 질문의 해석이 명시되어 있는지, 원문에서 누락을 어떻게 해석해야 하는지, 관계 변경 내역이 완전한지, 검사가 읽는 범위를 누가 계산했는지를 드러내는 것이다. 이 조건을 빠뜨리면 검사가 성공해도 결론은 틀릴 수 있다.

## 원문의 부재와 표준 기본값

이어 6개 사례를 6개 모델에 주고 원문만 제공한 조건과 같은 원문에 해당 버전의 표준 정의를 더한 조건을 비교했다. 총 72회이며 각 조건은 36회다. 질문의 작업 종류는 미리 제공했다. 자연어에서 작업을 고르는 앞선 54회와 다른 실험이다.

원문만 받은 조건은 36회 중 33회가 맞았고, 표준 정의를 추가한 조건은 36회 모두 맞았다. 차이는 모두 Laravel의 `brick/math` 의존 기록에서 나왔다. 이 항목은 의존성 배열에 `ref`만 있고 `dependsOn`이 없다. 적용한 문서 해석 정책은 이를 빈 의존 기록으로 처리한다. 그래프에 항목 자체가 없는 경우와 구분한다. 원문 조건에서 Luna와 Fable은 형식상 유효하지만 잘못된 ‘알 수 없음’을 골랐고, Flash는 출력 한도 안에 유효한 JSON을 완성하지 못했다. 따라서 세 차이를 모두 의미 판단 오류라고 세지 않았다.

`scope`가 없는 구성요소의 표준 기본값과 실제 고객 환경의 설치 여부를 구분하는 사례에서는 두 조건 모두 맞았다. 표준 기본값 `required`는 실제 설치의 증거가 아니다. 또한 CycloneDX 1.4의 관련 표현은 SHOULD이므로 모든 구현에 강제되는 MUST로 바꾸어 설명하지 않는다. 모델의 설명문은 보존했지만 설명의 모든 문장을 자동으로 사실 검증한 것은 아니다.

이 비교는 표준 의미 정보를 더 제공한 효과다. SHACL 보고서, RDF 직렬화, 그래프 DB의 효과로 해석하지 않는다.

## 같은 초안의 자체 검토와 SHACL 검토

위 오류를 본 뒤 3개 사례를 골라 후속 개발 실험을 했다. 선택 이후의 결과이므로 독립 평가 표본이 아니다. 6개 모델의 원문 조건 초안 18개를 공유하고 각 초안에 두 검토 방법을 적용했다. 두 방법 모두 같은 원문, 표준 정의, 초안과 추가 출력 한도 2,048을 받았다. SHACL 조건에만 선택된 증거와 초안을 검사한 보고서를 더 주었다. 통과·실패를 강제적인 답변 거부로 사용하지 않았다.

| 결과 | 자체 검토 | SHACL 보고서 추가 |
|---|---:|---:|
| 계획한 검토 | 18 | 18 |
| 유효한 최종 응답 | 17 | 17 |
| 맞은 최종 분류 | 17 | 17 |
| 유효하지만 틀렸던 초안의 수정 | 2 | 2 |
| 출력 실패 초안의 회복 | 1 | 0 |
| 맞았던 초안 이후 출력 실패 | 1 | 0 |

자체 검토에서는 Sonnet의 한 응답이 형식 검사에 실패했고 SHACL 조건에서는 Flash의 한 응답이 출력에 실패했다. 이 둘을 ‘잘못된 유효 답변’으로 바꾸어 세지 않는다. 원래 틀렸던 유효 초안 2개는 두 방법 모두 고쳤다. 이번에는 표준 설명을 갖춘 자체 검토보다 SHACL 보고서가 정확도를 더 높였다는 증거가 나오지 않았다. 한 번씩 실행한 작은 개발 실험이므로 두 방법의 일반적인 동등성도 입증하지 않는다.

보고서 생성기는 평가 정답을 읽지 않았다. 선택된 원문에서 필드와 의존 기록의 존재 여부를 추출하고 공개된 표준 정책으로 검사했다. 실제 RDF와 pySHACL 검사 결과를 같은 정책의 Python 검사와 대조했다. 응답 형식이 잘못된 초안은 SHACL 위반으로 부르지 않고 입력 거절로 분리했다. 이 보고서는 원문의 완전성이나 실제 운영 환경의 사실을 보증하지 않는다.

## 재생 데모와 실행 비용

[저장된 결과 재생 데모](../experiments/seminar/schema-management.html)에서 질문과 모델을 선택하면 실제 실행 조건, 검사 결과, 원문 응답을 볼 수 있다. 변경 추적 화면은 두 버전의 답과 재검토 표시를 함께 보여준다. 데모는 저장된 결과만 읽으며 API나 DB를 호출하지 않는다. [이전 Neo4j·Neptune 실험](2026-11-06-backend-inference-review.md)과 연결하되 이번 SBOM을 실제 두 DB에서 실행한 것으로 표시하지 않았다.

이번 세 단계에서 실제 호출은 54 + 72 + 36 = 162회다. 제공자가 보고한 비용은 $2.721745950이며 실패에 배정한 예약 금액을 반환하지 않는 내부 예산 사용량은 $3.499338630이다. 승인 한도는 $15이고 실행기 시도 상한은 180회다. 실패 호출을 재시도하거나 남은 한도를 채우기 위해 반복 실행하지 않았다. 기존 Neptune은 이번 호출 동안 재시작하지 않았다.

원문·라이선스·해시와 평가 결과는 `research/schema-management-1/`에, 비공개 호출 원장과 실패 원문은 `_workspace/schema-management-20261106/`에 보존했다. 모델별 한 번의 결과를 순위나 대표 정확도로 발표하지 않는다. 질문 선택, 의미 정보 제공, 검토 보고서 추가는 별개의 비교 축이다.
