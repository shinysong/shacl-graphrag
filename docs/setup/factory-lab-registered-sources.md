# DB와 정책 문서 등록

운영 자료실은 운영자가 등록한 SQLite 사본을 읽습니다. 브라우저에서 서버 파일 경로를 입력하거나 원본 DB를 수정하지 않습니다. 문서는 같은 DB 사본의 식별자와 해시에 연결합니다. 등록은 승인이나 정책 해석을 대신하지 않습니다.

## 공개 예제 준비

저장소 루트에서 다음 명령을 실행합니다. 출력 폴더는 새 경로여야 합니다. 예제는 제품 20행, 주문 40행, 주문 항목 120행과 짧은 문서 2개를 만듭니다. 모두 작성한 합성 자료이며 실제 고객 자료가 아닙니다.

```bash
uv run --locked python examples/factory_lab/extensions/registered-commerce/create_example.py --output _workspace/my-commerce
uv run --locked python -m apps.factory_lab.database_sources_cli --registry _workspace/my-databases register _workspace/my-commerce/commerce.sqlite --label '내 주문 예제'
```

두 번째 명령이 출력한 source_id와 snapshot_sha256을 다음 명령의 SOURCE_ID와 SNAPSHOT_SHA256 자리에 넣습니다.

```bash
uv run --locked python -m apps.factory_lab.document_sources_cli --database-registry _workspace/my-databases --registry _workspace/my-documents register _workspace/my-commerce/returns.txt --source-id SOURCE_ID --snapshot-sha256 SNAPSHOT_SHA256 --label '반품 정책 예제' --version v1
uv run --locked python -m apps.factory_lab.document_sources_cli --database-registry _workspace/my-databases --registry _workspace/my-documents list --source-id SOURCE_ID --snapshot-sha256 SNAPSHOT_SHA256
```

quantities.txt도 같은 방식으로 별도 등록합니다. 자신의 자료를 쓸 때는 승인된 로컬 SQLite 파일과 UTF-8 .txt 또는 .md 파일로 경로를 바꿉니다. 공개 표시 이름과 버전에 비밀 정보나 서버 경로를 넣지 않습니다.

## 자료실 연결과 검토

사용하지 않는 로컬 포트를 골라 실행합니다. 아래 9273은 예시이며 이미 사용 중이면 다른 포트를 선택합니다.

```bash
uv run --locked python -m apps.factory_lab.public_server --port 9273 --data-dir _workspace/my-workspace --workspace-database-registry _workspace/my-databases --workspace-document-registry _workspace/my-documents
```

이 명령은 유료 언어모델이나 외부 확장을 켜지 않습니다. 자료실에서 등록 원본으로 작업 공간을 만든 뒤 필드 의미를 검토합니다. 원문 문단과 해석은 나란히 확인하고 저장합니다. 관계와 질의도 제안 저장, 승인, 실행을 각각 진행합니다. 승인만으로 조회가 실행되지는 않습니다.

예제의 주문 상태로 수량을 집계할 수 있지만 반품 가능 여부는 확정할 수 없습니다. 정책에는 배송 후 30일과 미사용 조건이 있고 DB에는 배송일과 상품 상태가 없습니다. 이 차이를 자료 부족으로 남기는 것이 예제의 목적입니다.

## 범위와 한계

문서 등록은 현재 UTF-8 텍스트와 Markdown만 지원합니다. 기본 한도는 문서 100개, 파일당 2 MiB입니다. PDF 파싱, 자동 정책 추출, 문서 전체 검색을 지원한다는 뜻은 아닙니다. 원문 바이트와 문단 위치를 보존하며 검토한 해석의 진실이나 법적 효력을 검증하지 않습니다.

원본 DB를 수정해도 등록한 사본은 바뀌지 않습니다. 새 자료를 쓰려면 새로 등록하고 매핑과 문서 연결을 다시 검토합니다. 기존 실행은 이전 사본의 근거로 남습니다.

등록 명령은 로컬 예제로 사전 실행했습니다. 새 환경에서 이 안내 전체를 재현하는 검증은 남아 있습니다. 외부 도구 연결의 실제 확인 범위는 [선택적 온톨로지 확장](factory-lab-upstream-extensions.md)에서 따로 설명합니다. 등록 확인만으로 자연어 질문 실행이나 운영 성능을 검증했다고 보지 않습니다.

<!-- HUMANIZE-SUMMARY -->
<!--
경로: light / 장르: report
수정: C-11에 따라 연결어미 뒤 쉼표 2개만 제거했습니다.
보존: 사실, 수치, 명령, 경로, 제목, 내용 앵커, 한계와 검증 진행 상태를 유지했습니다.
자가검증: 6항 점검 완료. 변경률 확정 판정은 오케스트레이터의 verify_change_rate.py 실행에 맡깁니다.
-->
