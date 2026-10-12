# 2026-09-08 — uv + Ubuntu 고정, Orca는 BYO 에이전트

## Context

호스트는 Ubuntu로 확정. Python은 venv/pip 대신 uv. 원격 개발은 SSH·모바일을 염두에 두고 Codex/Orca를 검토.

## What happened

- bootstrap을 Ubuntu-only + `uv` 설치/`uv sync`로 바꿈 (`pyproject.toml`, `.python-version`).
- Codex 표준인 `AGENTS.md`를 추가 (`AGENT.md` 단수는 Codex가 기본으로 안 읽음).
- Orca 문서 확인: Orca는 IDE/런타임이고 에이전트 자체는 아님. Codex 등 CLI를 서버(에이전트 실행 측)에 설치·인증해야 함. 모바일은 Remote Orca Server(`orca serve`)가 SSH-only보다 맞음.

## Lesson

원격 박스에 “Orca만” 올리면 부족하다. **에이전트가 어디서 도는지**에 CLI를 두고, UI만 노트북/폰에 두는 그림을 먼저 고른다.

## Follow-up

- [ ] EC2 Ubuntu에서 `bootstrap.sh` 실기
- [ ] Codex vs Orca(+Codex) 운영 선택 후 optional 설치 스크립트
- [ ] `uv.lock` 커밋 (첫 `uv sync` 이후)
