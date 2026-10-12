# Host bootstrap

**Target OS: Ubuntu 22.04 / 24.04** (다른 배포판은 지원하지 않음)

서버(EC2)가 준비되면 저장소를 clone한 뒤 **한 번** 실행하면 됩니다.

```bash
git clone https://github.com/shinysong/shacl-graphrag.git
cd shacl-graphrag
chmod +x scripts/*.sh scripts/lib/*.sh
./scripts/bootstrap.sh
```

## 하는 일

| Step | Script | 내용 |
| --- | --- | --- |
| 1 | `01_system_packages.sh` | git, curl, jq, Python3, JDK 17, Docker, **uv** |
| 2 | `02_python_env.sh` | `uv sync` → `.venv` + deps (`pyproject.toml`) |
| 3 | `03_dirs_and_env.sh` | `data/`, `results/`, `runs/`, `logs/` + `.env` 생성 |
| 4 | `04_verify.sh` | 도구·패키지 존재 확인 |

## 옵션

```bash
./scripts/bootstrap.sh --skip-system   # sudo 없이 (패키지·uv 이미 있을 때)
./scripts/bootstrap.sh --skip-python
./scripts/bootstrap.sh --verify-only
```

일상 명령 예:

```bash
source .venv/bin/activate   # 또는
uv run python -c "import rdflib; print(rdflib.__version__)"
```

## 필수 수동 작업

1. `.env`에 `OPENROUTER_API_KEY` 입력
2. Docker 그룹 반영을 위해 **재로그인** (또는 `newgrp docker`)
3. GraphDB / Neo4j / Terraform / Codex·Orca 설치는 bootstrap에 **미포함** → [roadmap.md](roadmap.md), [agents.md](agents.md)

## 로컬 (Windows)

WSL2 **Ubuntu**에서 동일 스크립트를 사용하세요.
