# Setup roadmap (초기 이후)

부트스트랩(`scripts/bootstrap.sh`) 다음에 올 작업. **지금 저장소에는 자리만 둠.**

## 1. Terraform (AWS)

경로: `infra/terraform/`

예정 리소스 초안:

- EC2 (메모리 최적화, 예: r7g 계열) + EBS
- S3 (실험 산출물)
- IAM (최소 권한, MFA는 콘솔/계정 정책)
- (후반) Neptune Serverless — 검증 계층 배치 비교용, 단기간만

서버가 생기기 전에는 Terraform apply를 하지 않습니다.

## 2. 그래프 DB

| 엔진 | 역할 | 설치 방식 (예정) |
| --- | --- | --- |
| GraphDB Free | SHACL·추론 주 실험 | Docker Compose 또는 EC2 native |
| Neo4j Community | LPG 비교군 | 동일 호스트 Docker |
| Neptune | 외부 미들웨어 검증 배치 비교 | Terraform + 5~6주차 한정 |

별도 `scripts/05_graph_stores.sh` / `docker-compose.yml`은 DB 버전·포트 확정 후 추가.

## 3. LLM API

- **OpenRouter** 단일 게이트웨이 (`OPENROUTER_*` in `.env`)
- 조건별 모델 slug만 바꿔 비교 실험
- GPU / 자체 서빙 없음

## 4. 코딩 에이전트 (Codex / Orca)

상세: [agents.md](agents.md)

- **Orca** = UI/런타임, **Codex 등** = 실제 에이전트 (Orca만으로는 코딩 안 됨)
- SSH만: 노트북 Orca + EC2 SSH target (원격에 에이전트 CLI 필요)
- 모바일: EC2에 `orca serve` (Remote Orca Server) 쪽이 맞음
- 저장소 지침 파일: 루트 `AGENTS.md`
- API 키는 `.env` / OS 자격증명에만; 설치 스크립트는 합의 후 optional로 추가

## 5. 데이터

YAGO 4.6 슬라이스 다운로드·적재 스크립트는 KB 라이선스·용량 확인 후 `scripts/`에 추가.
