# 2026-09-08 — 서버 전 부트스트랩만 먼저 고정

## Context

AWS EC2·Terraform·GraphDB/Neo4j는 아직 없고, 서버가 뜨면 한 번에 올릴 초기 세팅이 필요했다. LLM은 OpenRouter로 통일할 예정. Codex/Orca 같은 코딩 에이전트는 후보만 둠.

## Incident

- 저장소에 `scripts/bootstrap.sh` 체인(시스템 패키지 → venv → 디렉터리·`.env` → verify)을 넣었다.
- GraphDB/Neo4j/Terraform/에이전트 설치는 의도적으로 **제외**하고 `docs/setup/roadmap.md`에 미룸.
- `docs/lessons-learned/`를 두어 이후 시행착오를 남기기로 했다.

## Lesson

인프라·엔진·에이전트를 부트스트랩에 한꺼번에 넣지 말고, **호스트 공통 의존성 + env 템플릿**만 먼저 고정하면 서버 수령 직후 재실행이 쉽다.

## Follow-up

- [ ] EC2 OS 확정 후 `01_system_packages.sh` 실기 검증
- [ ] Terraform 초안 (`infra/terraform/`)
- [ ] Graph store compose / 설치 스크립트
- [ ] Codex 또는 Orca 중 운영 도구 결정
