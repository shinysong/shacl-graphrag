# SHACL GraphRAG

온톨로지 제약 기반 검증 루프 GraphRAG

Graph User Group (GUG) 커뮤니티 프로젝트입니다.  
SHACL·OWL 제약을 GraphRAG의 검색–검증–생성 루프에 **런타임 구성요소**로 통합하고 온톨로지 도입 효과를 정량적으로 비교·공개하는 것을 목표로 합니다.

공개 저장소: [github.com/shinysong/shacl-graphrag](https://github.com/shinysong/shacl-graphrag)

## 배경

기존 GraphRAG 연구는 온톨로지를 검색 범위 축소나 사후 필터에 쓰는 경우가 많습니다.  
스키마 수준의 논리 제약과 검증 계층이 없으면 잘못된 근거로 답변이 나와도 위반을 판정하기 어렵습니다.

본 프로젝트는 ‘그래프 구조의 효과’와 ‘스키마 제약의 효과’를 분리 측정할 수 있도록 제약 검증이 내장된 공개 지식베이스(YAGO 4.6)를 기반으로 데이터셋·검증 루프·비교 실험까지 한 사이클을 완결합니다.

## 주요 기능 (예정)

현재 호스트 부트스트랩과 합성 RDF의 SHACL 검증 실험(사전 점검)을 실행할 수 있습니다. 아래 GraphRAG 기능은 후속 구현 범위입니다.

- Ontology Constraint Validation (SHACL·OWL)
- GraphRAG Pipeline (검색–검증–생성 루프)
- Text-to-SPARQL

## 수행 범위

1. 공개 지식베이스(YAGO 4.6) 슬라이스 추출 및 그래프 DB 적재
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

지식베이스는 공개 라이선스(CC BY) 데이터만 사용합니다.

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

# 문서 원본 검사
uv sync --locked --group docs
uv run --locked --group docs mkdocs build --strict

# Chirpy 사이트 빌드 (Ruby 3.4 필요)
BUNDLE_GEMFILE=website/Gemfile bundle install
./scripts/build_site.sh
```

실행 기록은 `docs/experiments/records/`, 입력 사본과 상세 보고서는 `runs/`에 남습니다.
공개 문서용 기록 없이 점검하려면 실행기에 `--local-only`를 붙입니다.
재현에 필요한 `uv.lock`도 코드·명세와 함께 버전 관리합니다.

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
데이터셋은 원본 지식베이스(YAGO 등) 라이선스를 따릅니다.
