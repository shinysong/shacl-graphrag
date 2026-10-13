# SHACL GraphRAG

온톨로지 제약 기반 검증 루프 GraphRAG

Graph User Group (GUG) 커뮤니티 프로젝트입니다.  
SHACL·OWL 제약을 GraphRAG의 검색–검증–생성 루프에 **런타임 구성요소**로 통합하고 온톨로지 도입 효과를 정량적으로 비교·공개하는 것을 목표로 합니다.

공개 저장소: [github.com/shinysong/shacl-graphrag](https://github.com/shinysong/shacl-graphrag)

## 배경

통제 가능한 업무·의사결정 시스템과 금융·의료 감사처럼 판단 근거가 중요한 활용에서 출발합니다. 이미 RDF나 그래프 데이터를 보유한 환경에서, 어떤 정보와 규칙을 명시적으로 관리하면 LLM의 잘못된 판단을 줄일 수 있는지 확인합니다.

모든 데이터를 온톨로지로 만들 필요가 있는지부터 비교합니다. JSON과 코드 규칙으로 충분한 범위, 필요한 필드만 RDF·SHACL로 관리하는 범위, LLM의 추가 검토를 쓰는 범위를 나누고 같은 질문·근거로 평가합니다. RDF·SHACL이 더 좋다는 결론을 전제하지 않습니다.

첫 데이터셋은 GLEIF의 법인·회계연결 모회사·보고 예외 데이터입니다. YAGO 4.6 후속 파일럿은 원본 SHACL을 수정하지 않고 출생지 질문에서 제약의 탐지 범위와 재검색 효과를 확인했습니다. 현재 [최소 온톨로지 개입 실험](docs/experiments/hybrid-study.md)에서는 관계 깊이·판단 조건·무관한 정보를 나누어 비교합니다.

## 구현 범위

GLEIF 개발 12개 기업·72개 사례와 별도 평가 30개 기업·180개 사례를 여섯 조건으로 세 번씩 실행했습니다. Jev의 별도 개발 216개 결과와 실제 Neo4j/Cypher 근거 대조도 기록했습니다. 코드 규칙과 SHACL의 별도 평가 결과는 같았으며 전체 GraphRAG나 엔진 성능의 우열을 입증한 것은 아닙니다.

[확대 실행 결과와 실제 사례](docs/journal/2026-10-13-expanded-comparison.md)

[의미 판단 후속 결과](docs/journal/2026-10-13-semantic-comparison.md)에는 합성 개발 180행과 오래된 검색 근거의 대응 점검 36행을 기록했습니다. 의미 판단·인용·추가조회 결정을 나누어 평가했으며 실제 GLEIF 벤치마크와 구분합니다.

[최소 온톨로지 개입 결과](docs/journal/2026-10-13-hybrid-intervention.md)에는 합성 첫 120문항과 반복 69문항의 공통 비교를 기록했습니다. 명시적 검사 보고서가 LLM의 계약 불일치를 줄였지만 코드와 SHACL의 판정은 같았습니다. 응답 미수신 두 건 이후 유료 호출을 중단했으며 GLEIF 모델 비교와 질문 계약 추출은 미실행입니다.

합성 RDF 사전 점검을 실행할 수 있습니다. GLEIF 배치 수집과 부분집합 추출, RDF 변환을 거쳐 SHACL 검증·OpenRouter 구조화 답변·정답 채점까지 실행할 수 있습니다.

- RDFLib 고정 질의로 근거 검색, pySHACL 또는 동등한 Python 규칙으로 검사
- 검증 후 보류·제한 재검색, 무조건 재조회 비교군
- 원본·입력 해시·질의·근거·보고서·LLM 사용량과 실패 기록

Text-to-SPARQL, OWL 추론, 독립적인 벡터 검색 RAG와 GraphDB·Neo4j·Neptune의 엔진 성능 비교는 후속 범위입니다.

## 후속 계획

1. GLEIF 동일 시점 배치 3종 수집과 관계·보고 예외를 보존한 부분집합 추출
2. SHACL·OWL 검증 로직 구현, 제약 위반 주입 프로토콜 및 채점 도구
3. Text-to-SPARQL 및 검증 루프 파이프라인 프로토타입
4. 조건별 비교 실험
   - 일반 RAG
   - 무제약 GraphRAG
   - 검증 루프 GraphRAG
   - 검증 계층 배치 비교 (엔진 내장 vs 외부 미들웨어)

## 실험 환경 (계획)

| 구분 | 내용 |
| --- | --- |
| 클라우드 | AWS EC2 (메모리 최적화), EBS, S3 |
| 주 그래프 DB | GraphDB Free (검증·추론 내장, EC2 자체 호스팅) |
| 비교군 | Neo4j Community (LPG, EC2 자체 호스팅) |
| 배치 비교 | Amazon Neptune Serverless (후반 한정) |
| OS | Ubuntu 22.04 / 24.04 |
| Python | **uv** (`pyproject.toml` → `.venv`) |
| LLM | OpenRouter API (자체 서빙·GPU 미사용) |
| IaC (예정) | Terraform (`infra/terraform/`) |

GLEIF 데이터는 CC0 이용 조건을 따릅니다. YAGO 4.6 후속 파일럿은 원본 SHACL과 tiny 부분집합을 사용하며 CC BY 4.0 출처를 표시합니다.

## 빠른 시작 (호스트 부트스트랩)

AWS EC2 **Ubuntu**에서 clone 후:

```bash
chmod +x scripts/*.sh scripts/lib/*.sh
./scripts/bootstrap.sh
```

- OpenRouter 키는 `.env.example` → `.env`에 채웁니다.
- GraphDB / Neo4j / Terraform / Codex·Orca 설치는 **아직 포함하지 않습니다.**
- 부트스트랩: [docs/setup/bootstrap.md](docs/setup/bootstrap.md)
- 에이전트(Codex/Orca): [docs/setup/agents.md](docs/setup/agents.md) · 루트 [`AGENTS.md`](AGENTS.md)
- 시행착오: [docs/lessons-learned/](docs/lessons-learned/)

## 실험과 연구 기록

[Lab 홈](docs/index.md)에서 [실험 명세](docs/experiments/specification.md),
[실행 기록](docs/experiments/records/index.md), [연구 일지](docs/journal/index.md)를 읽을 수 있습니다.
문서 원본은 Markdown이며 Jekyll의 Chirpy 테마로 GitHub Pages에 게시합니다.
공개 설정과 미리보기는 [기록 운영 방법](docs/setup/recording.md)을 따릅니다.

```bash
# 합성 데이터로 SHACL 검증과 채점 실행, 결과 기록
uv sync --locked
uv run --locked python scripts/run_validation_experiment.py

# 공개된 작은 GLEIF 입력으로 실제 LLM 파일럿 (.env 필요)
uv run --locked python scripts/run_gleif_pilot.py experiments/gleif/dataset.json

# 문서 원본 검사
uv sync --locked --group docs
uv run --locked --group docs mkdocs build --strict

# Chirpy 사이트 빌드 (Ruby 3.4 필요)
BUNDLE_GEMFILE=website/Gemfile bundle install
./scripts/build_site.sh
```

실행 기록은 `docs/experiments/records/`, 입력 사본과 상세 보고서는 `runs/`에 남습니다.
합성 데이터 실행기의 `--local-only`는 공개 기록 생성을 생략합니다. GLEIF 실행기는 기본적으로 `runs/`에만 저장하며 검토 후 공개용 기록을 내보냅니다. 전체 배치 재수집과 파일럿의 범위는 실험 명세를 따릅니다.
재현에 필요한 `uv.lock`도 코드·명세와 함께 버전 관리합니다.

## 연구 운영

연구 운영과 코드 작성은 [Codex와 서브에이전트](docs/setup/research-operations.md)가 맡습니다. 메인이 계획을 작성하고 두 담당이 독립 검토합니다. OpenRouter는 실험의 답변 모델에 사용합니다. 운영 도구는 모델 API를 호출하지 않으며 Codex 사용량은 계정의 한도를 따릅니다.

```bash
JOB_ID=$(uv run --locked python scripts/research_ops.py init research/operations/tasks/local-verification.json)
uv run --locked python scripts/research_ops.py request "$JOB_ID" plan
uv run --locked python scripts/research_ops.py status
```

## 예상 결과물

- 파이프라인·실험 코드
- 실험용 데이터셋
- 파일럿 실험 리포트
- 기술문서·튜토리얼

## 성과 지표 (초안)

**정량**

- 제약 위반 검출률 / 오탐률
- 검증 루프 적용 전후 근거 검증가능률
- 질의당 검증 지연 시간·토큰 사용량

**정성**

- 실험용 데이터셋·파이프라인 코드 공개
- 구축 과정 기술문서

## 커뮤니티

- 커뮤니티: Graph User Group
- 실무 담당: 송채은
- 활용 기간(지원 신청 기준): 2026년 9월 ~ 10월

## 라이선스

코드·문서 라이선스는 저장소 공개 시점에 확정합니다.  
GLEIF 데이터와 파생 부분집합은 [원본 CC0 이용 조건](https://www.gleif.org/en/meta/lei-data-terms-of-use/)을 따릅니다.

YAGO 파일럿: `uv run --locked python scripts/run_yago_pilot.py` (`.env` 필요). 배포 원본과 라이선스는 [YAGO 4.6](https://yago-knowledge.org/downloads/yago-4-6), 표본 출처는 [NOTICE](experiments/yago/NOTICE.md)를 따릅니다.

질의 관련성 후속 실험은 `uv run --locked python scripts/run_yago_selective.py`로 실행합니다. 비교 조건과 원천 누락 처리 기준은 [명세 0.4](docs/experiments/specification.md)를 따릅니다.
