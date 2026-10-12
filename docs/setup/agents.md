# Coding agents: Codex vs Orca (SSH / mobile)

## Codex와 Orca의 역할

| 도구 | 역할 | 서버에 따로 필요한 것 |
| --- | --- | --- |
| **Codex** | 실제 코딩 에이전트 (CLI/앱) | EC2에서 돌릴 거면 **Codex 설치·로그인** |
| **Orca** | 에이전트를 **붙여 쓰는 IDE/런타임** (UI·worktree·원격) | Orca만으로는 코드 안 짬 → **Codex 등 에이전트를 가져가야 함** |

Orca는 에이전트 구독을 팔지 않고, Claude Code / Codex / OpenCode 같은 CLI를 **가져오는(BYO)** 구조입니다.  
→ “Orca만 설치하면 알아서 코딩?” → **아니요.** 서버(또는 에이전트가 실행되는 쪽)에 에이전트 CLI + 인증이 있어야 합니다.

공식: [Ways to run Orca](https://www.onorca.dev/docs/ways-to-run), [Remote Orca Servers](https://www.onorca.dev/docs/remote-servers)

## AWS EC2의 SSH·모바일 접속 구성

### A) 노트북에서 UI, 서버에서만 실행 (SSH target)

1. 노트북에 Orca(또는 Codex 앱) 설치
2. Settings → SSH에 EC2 등록
3. worktree를 **Run on: SSH** 로 생성 → 에이전트·git worktree는 **원격(Ubuntu)에서** 실행

- EC2에 **두 번째 Orca 런타임**을 꼭 깔 필요는 없음 (SSH 모드)
- 그래도 원격에서 에이전트가 돌아가므로 **원격 PATH에 Codex(또는 쓸 에이전트) + 로그인**이 필요
- 노트북 절전/끊김 후에도 원격 작업은 이어질 수 있고, UI는 재연결

**모바일만**으로 같은 세션을 쓰기는 SSH 모드가 약함.

### B) 폰·브라우저까지 같은 세션 (Remote Orca Server) — 모바일 추천

1. EC2(Ubuntu)에 Orca 런타임 설치 후 `orca serve` (또는 데스크톱 Advertise)
2. 노트북/폰 클라이언트를 pairing URL로 연결
3. **프로젝트·터미널·에이전트 세션의 주인 = 서버**

- 모바일·웹·노트북이 **같은 런타임**을 공유
- 서버에 에이전트 CLI를 설치·인증해야 함 (노트북 로그인만으로는 안 넘어감)

### C) Codex만 (Orca 없이)

- SSH로 EC2 접속 후 `codex` TUI, 또는 Codex 앱의 Remote SSH
- 저장소 루트 `AGENTS.md`를 Codex가 자동으로 읽음
- 모바일은 Codex/ChatGPT 쪽 원격 기능에 의존 (환경마다 다름)

## 현재 단계의 권장 환경 구성

1. 서버: Ubuntu + `./scripts/bootstrap.sh` (**uv** 포함)
2. 에이전트 파일: 루트 **`AGENTS.md`** (Codex 표준 이름; `AGENT.md` 단수는 기본 미인식)
3. Orca 쓸지 Codex만 쓸지는 서버 뜬 뒤 결정 — 설치 스크립트는 아직 bootstrap에 **넣지 않음**
4. 실험 LLM 호출은 계속 **OpenRouter** (`.env`)

## `AGENTS.md` vs `AGENT.md`

- **Codex:** `AGENTS.md` / `AGENTS.override.md` 를 탐색합니다.
- 파일명을 `AGENT.md`만 두면 Codex 기본 설정에서는 **안 읽습니다.**
- 이 레포는 `AGENTS.md`를 둡니다. Orca에 붙인 Codex도 같은 파일을 보게 됩니다.
