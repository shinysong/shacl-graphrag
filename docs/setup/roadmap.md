# Setup roadmap (초기 이후)

부트스트랩(`scripts/bootstrap.sh`) 이후 진행된 인프라 및 실험 환경 현황과 후속 계획입니다.

## 1. 그래프 저장소 및 쿼리 엔진 현황

| 엔진 | 역할 | 상태 및 구현 내용 |
| --- | --- | --- |
| **RDFLib / pySHACL** | 온톨로지 모델링, 1:1 무조인 엔티티 그래프 투영 및 SHACL 유효성 검증 | **완료** (`unified_rule_lifecycle.py`, 4단계 생명주기 검증 완료) |
| **Neo4j Community** | 라벨 속성 그래프(LPG) 비교군, Cypher 다중 홉 관계 탐색 | **완료** (`graphrag_neo4j.py`, `run_neo4j_retrieval.py` 하이브리드 검색 검증 완료) |
| **GraphDB Free** | 대규모 RDF 저장 및 SHACL 네이티브 엔진 비교 | 예정 (도메인 실증 데이터 확장 시 도입) |
| **Neptune Serverless** | 클라우드 관리형 그래프 DB 및 검증 계층 배치 비교 | 후반 예정 (Terraform 인프라 확정 후) |

## 2. LLM 게이트웨이 및 모델 평가

- **OpenRouter** 게이트웨이 (`.env` 기반):
  - 모델별 추론 및 사후 검토(Post-Answer Review) 파이프라인 구축 완료.
  - Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, Llama 3.1 70B 등 6개 모델 대상 조언적 SHACL 검증 보고서의 유효성 검증 완료.

## 3. 클라우드 인프라 (AWS)

경로: `infra/terraform/`

예정 리소스 초안:
- EC2 (메모리 최적화 계열) + EBS
- S3 (실험 산출물 및 데이터셋 아카이브)
- IAM (최소 권한 원칙)
- Neptune Serverless 연동

## 4. 코딩 에이전트 협업 체계 (Codex / Orca / Gemini)

상세: [agents.md](agents.md) 및 `_workspace/handoff.md`

- **Codex CLI (`gpt-6-astra`)**: 주력 실행·검증·테스트 및 엄밀한 리뷰 엔진 (`fork_turns="none"` 기반 독립 리뷰)
- **Gemini / Antigravity**: 거시 프레임워크 설계, 구조 개고, 연구 종합 및 외부 교차 감사
- **세션 연속성**: `MEMORY.md` 및 `_workspace/handoff.md`를 통한 바통 인계 프로토콜 운용
